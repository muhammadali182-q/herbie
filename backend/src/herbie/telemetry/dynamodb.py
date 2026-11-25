"""DynamoDB implementation of immutable telemetry and its archive outbox."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from time import sleep
from typing import TYPE_CHECKING, Any
from uuid import UUID

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_dynamodb.type_defs import (
        PutTypeDef,
        TransactGetItemTypeDef,
        TransactWriteItemTypeDef,
    )

from herbie.telemetry.contracts import TelemetryEvent
from herbie.telemetry.errors import (
    BootIdentityConflictError,
    MessageIdentityConflictError,
    SequenceIdentityConflictError,
)
from herbie.telemetry.repository import (
    ArchiveReceipt,
    StoredTelemetry,
    TelemetryKey,
    TelemetryRepository,
    TelemetryWriteResult,
)

ARCHIVE_PENDING_INDEX = "archive-pending-index"
TENANT_LATEST_INDEX = "tenant-latest-index"
TRANSACTION_RETRY_LIMIT = 8


class DynamoTelemetryRepository(TelemetryRepository):
    """DynamoDB repository with transactional replay and sequence ownership."""

    def __init__(
        self,
        client: DynamoDBClient,
        table_name: str,
        event_retention_days: int = 14,
        replay_retention_days: int = 180,
    ) -> None:
        if event_retention_days < 1:
            raise ValueError("event retention must be at least one day")
        if replay_retention_days <= event_retention_days:
            raise ValueError("replay retention must exceed event retention")
        self._client = client
        self._table_name = table_name
        self._event_retention = timedelta(days=event_retention_days)
        self._replay_retention = timedelta(days=replay_retention_days)
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        return await asyncio.to_thread(self._store, telemetry)

    def _store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        event = telemetry.event
        partition_key = _connector_partition(event.tenant_id, event.charger_id, event.connector_id)
        event_key = f"EVENT#{event.message_id}"
        replay_key = f"REPLAY#{event.message_id}"
        boot_key = f"BOOT#{event.boot_id}"
        sequence_key = f"SEQUENCE#{event.boot_id}#{event.sequence:020d}"
        event_expiry = int((telemetry.received_at + self._event_retention).timestamp())
        replay_expiry = int((telemetry.received_at + self._replay_retention).timestamp())
        event_item: dict[str, Any] = {
            "pk": partition_key,
            "sk": event_key,
            "kind": "EVENT",
            "event_json": event.canonical_json(),
            "fingerprint": telemetry.fingerprint,
            "topic": telemetry.topic,
            "received_at": _timestamp(telemetry.received_at),
            # Pending events cannot expire before the archive worker records a receipt.
            "event_expires_at": event_expiry,
            "gsi1pk": "ARCHIVE#PENDING",
            "gsi1sk": (
                f"{_timestamp(telemetry.received_at)}#{event.tenant_id}#"
                f"{event.charger_id}#{event.connector_id:04d}#{event.message_id}"
            ),
        }
        replay_item = {
            "pk": partition_key,
            "sk": replay_key,
            "kind": "REPLAY",
            "fingerprint": telemetry.fingerprint,
            "expires_at": replay_expiry,
        }
        sequence_item = {
            "pk": partition_key,
            "sk": sequence_key,
            "kind": "SEQUENCE",
            "message_id": str(event.message_id),
            "fingerprint": telemetry.fingerprint,
            "expires_at": replay_expiry,
        }

        last_error: ClientError | None = None
        for _attempt in range(TRANSACTION_RETRY_LIMIT):
            current_latest = self._get(partition_key, "LATEST")
            latest_updated = current_latest is None or self._is_newer(
                telemetry,
                self._stored_from_item(current_latest),
            )
            transaction: list[TransactWriteItemTypeDef] = [
                self._conditional_put(event_item),
                self._conditional_put(replay_item),
                self._boot_update(partition_key, boot_key, event.boot_started_at, replay_expiry),
                self._conditional_put(sequence_item),
            ]
            if latest_updated:
                transaction.append(
                    self._conditional_latest_put(
                        self._latest_item(telemetry),
                        current_latest,
                    )
                )

            try:
                self._client.transact_write_items(TransactItems=transaction)
                return TelemetryWriteResult(
                    created=True,
                    latest_updated=latest_updated,
                    archive_pending=True,
                    stored=telemetry,
                )
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                    raise
                last_error = error
                try:
                    resolved = self._resolve_transaction_conflict(
                        telemetry,
                        partition_key,
                        event_key,
                        replay_key,
                        boot_key,
                        sequence_key,
                    )
                except ClientError as read_error:
                    if read_error.response.get("Error", {}).get("Code") != (
                        "TransactionCanceledException"
                    ):
                        raise
                    sleep(min(0.005 * (2**_attempt), 0.1))
                    continue
                if resolved is not None:
                    stored, archive_pending = resolved
                    return TelemetryWriteResult(
                        created=False,
                        latest_updated=False,
                        archive_pending=archive_pending,
                        stored=stored,
                    )
                sleep(min(0.005 * (2**_attempt), 0.1))

        if last_error is None:  # pragma: no cover - retry loop always executes
            raise RuntimeError("telemetry transaction retry loop did not execute")
        raise last_error

    def _resolve_transaction_conflict(
        self,
        incoming: StoredTelemetry,
        partition_key: str,
        event_key: str,
        replay_key: str,
        boot_key: str,
        sequence_key: str,
    ) -> tuple[StoredTelemetry, bool] | None:
        existing_event, replay, boot, sequence = self._transact_get(
            partition_key,
            (event_key, replay_key, boot_key, sequence_key),
        )

        if replay is not None:
            if replay.get("fingerprint") != incoming.fingerprint:
                raise MessageIdentityConflictError(
                    "message ID was already accepted with different content"
                )
            if existing_event is not None:
                if existing_event.get("fingerprint") != incoming.fingerprint:
                    raise MessageIdentityConflictError(
                        "message ID was already accepted with different content"
                    )
                return self._stored_from_item(existing_event), existing_event.get(
                    "gsi1pk"
                ) is not None
            return incoming, False

        if boot is not None and boot.get("boot_started_at") != _timestamp(
            incoming.event.boot_started_at
        ):
            raise BootIdentityConflictError(
                "boot ID was already accepted with another start timestamp"
            )
        if sequence is not None:
            raise SequenceIdentityConflictError(
                "boot sequence was already accepted with another message ID"
            )
        return None

    def _boot_update(
        self,
        partition_key: str,
        boot_key: str,
        boot_started_at: datetime,
        replay_expiry: int,
    ) -> TransactWriteItemTypeDef:
        return {
            "Update": {
                "TableName": self._table_name,
                "Key": self._serialize({"pk": partition_key, "sk": boot_key}),
                "UpdateExpression": (
                    "SET #kind = if_not_exists(#kind, :kind), "
                    "boot_started_at = if_not_exists(boot_started_at, :started), "
                    "expires_at = :expires"
                ),
                "ConditionExpression": ("attribute_not_exists(pk) OR boot_started_at = :started"),
                "ExpressionAttributeNames": {"#kind": "kind"},
                "ExpressionAttributeValues": self._serialize(
                    {
                        ":kind": "BOOT",
                        ":started": _timestamp(boot_started_at),
                        ":expires": replay_expiry,
                    }
                ),
            }
        }

    def _latest_item(self, telemetry: StoredTelemetry) -> dict[str, Any]:
        event = telemetry.event
        return {
            "pk": _connector_partition(event.tenant_id, event.charger_id, event.connector_id),
            "sk": "LATEST",
            "kind": "LATEST",
            "event_json": event.canonical_json(),
            "message_id": str(event.message_id),
            "fingerprint": telemetry.fingerprint,
            "topic": telemetry.topic,
            "received_at": _timestamp(telemetry.received_at),
            "boot_id": str(event.boot_id),
            "boot_started_at": _timestamp(event.boot_started_at),
            "sequence": event.sequence,
            "gsi2pk": f"TENANT#{event.tenant_id}#LATEST",
            "gsi2sk": f"CHARGER#{event.charger_id}#CONNECTOR#{event.connector_id:04d}",
        }

    def _conditional_latest_put(
        self,
        item: dict[str, Any],
        current: dict[str, Any] | None,
    ) -> TransactWriteItemTypeDef:
        put: PutTypeDef = {
            "TableName": self._table_name,
            "Item": self._serialize(item),
        }
        if current is None:
            put["ConditionExpression"] = "attribute_not_exists(pk)"
        else:
            put["ConditionExpression"] = (
                "#fingerprint = :expected_fingerprint AND message_id = :expected_message"
            )
            put["ExpressionAttributeNames"] = {"#fingerprint": "fingerprint"}
            put["ExpressionAttributeValues"] = self._serialize(
                {
                    ":expected_fingerprint": current["fingerprint"],
                    ":expected_message": current["message_id"],
                }
            )
        return {"Put": put}

    @staticmethod
    def _is_newer(candidate: StoredTelemetry, current: StoredTelemetry) -> bool:
        candidate_event = candidate.event
        current_event = current.event
        if candidate_event.boot_id == current_event.boot_id:
            return candidate_event.sequence > current_event.sequence
        return candidate_event.boot_started_at > current_event.boot_started_at

    async def latest_for_connector(
        self,
        tenant_id: UUID,
        charger_id: UUID,
        connector_id: int,
    ) -> StoredTelemetry | None:
        return await asyncio.to_thread(
            self._latest_for_connector,
            tenant_id,
            charger_id,
            connector_id,
        )

    def _latest_for_connector(
        self,
        tenant_id: UUID,
        charger_id: UUID,
        connector_id: int,
    ) -> StoredTelemetry | None:
        item = self._get(_connector_partition(tenant_id, charger_id, connector_id), "LATEST")
        return self._stored_from_item(item) if item is not None else None

    async def list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        return await asyncio.to_thread(self._list_latest_for_tenant, tenant_id)

    def _list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        items = self._query_all(
            IndexName=TENANT_LATEST_INDEX,
            KeyConditionExpression="gsi2pk = :tenant",
            ExpressionAttributeValues=self._serialize({":tenant": f"TENANT#{tenant_id}#LATEST"}),
        )
        return [self._stored_from_item(item) for item in items]

    async def list_archive_pending(self, limit: int) -> list[StoredTelemetry]:
        if limit < 1:
            raise ValueError("limit must be at least one")
        return await asyncio.to_thread(self._list_archive_pending, limit)

    def _list_archive_pending(self, limit: int) -> list[StoredTelemetry]:
        request: dict[str, Any] = {
            "IndexName": ARCHIVE_PENDING_INDEX,
            "KeyConditionExpression": "gsi1pk = :pending",
            "ExpressionAttributeValues": self._serialize({":pending": "ARCHIVE#PENDING"}),
        }
        items: list[dict[str, Any]] = []
        while len(items) < limit:
            response = self._client.query(
                TableName=self._table_name,
                Limit=limit - len(items),
                **request,
            )
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if last_key is None:
                break
            request["ExclusiveStartKey"] = last_key
        return [self._stored_from_item(self._deserialize(item)) for item in items]

    async def mark_archived(
        self,
        keys: tuple[TelemetryKey, ...],
        receipt: ArchiveReceipt,
    ) -> None:
        await asyncio.to_thread(self._mark_archived, keys, receipt)

    def _mark_archived(
        self,
        keys: tuple[TelemetryKey, ...],
        receipt: ArchiveReceipt,
    ) -> None:
        for key in keys:
            partition_key = _connector_partition(
                key.tenant_id,
                key.charger_id,
                key.connector_id,
            )
            try:
                self._client.update_item(
                    TableName=self._table_name,
                    Key=self._serialize({"pk": partition_key, "sk": f"EVENT#{key.message_id}"}),
                    UpdateExpression=(
                        "SET archive_object_key = :object, archive_checksum = :checksum, "
                        "archived_at = :archived, expires_at = event_expires_at "
                        "REMOVE gsi1pk, gsi1sk"
                    ),
                    ConditionExpression=(
                        "attribute_exists(pk) AND attribute_not_exists(archive_object_key)"
                    ),
                    ExpressionAttributeValues=self._serialize(
                        {
                            ":object": receipt.object_key,
                            ":checksum": receipt.checksum_sha256,
                            ":archived": _timestamp(receipt.archived_at),
                        }
                    ),
                )
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != (
                    "ConditionalCheckFailedException"
                ):
                    raise

    def _conditional_put(self, item: dict[str, Any]) -> TransactWriteItemTypeDef:
        return {
            "Put": {
                "TableName": self._table_name,
                "Item": self._serialize(item),
                "ConditionExpression": "attribute_not_exists(pk)",
            }
        }

    def _get(self, partition_key: str, sort_key: str) -> dict[str, Any] | None:
        response = self._client.get_item(
            TableName=self._table_name,
            Key=self._serialize({"pk": partition_key, "sk": sort_key}),
            ConsistentRead=True,
        )
        item = response.get("Item")
        return self._deserialize(item) if item is not None else None

    def _transact_get(
        self,
        partition_key: str,
        sort_keys: tuple[str, ...],
    ) -> tuple[dict[str, Any] | None, ...]:
        transact_items: list[TransactGetItemTypeDef] = [
            {
                "Get": {
                    "TableName": self._table_name,
                    "Key": self._serialize({"pk": partition_key, "sk": sort_key}),
                }
            }
            for sort_key in sort_keys
        ]
        response = self._client.transact_get_items(TransactItems=transact_items)
        return tuple(
            self._deserialize(item_response["Item"]) if "Item" in item_response else None
            for item_response in response["Responses"]
        )

    def _query_all(self, **request: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            response = self._client.query(TableName=self._table_name, **request)
            items.extend(self._deserialize(item) for item in response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if last_key is None:
                return items
            request["ExclusiveStartKey"] = last_key

    def _stored_from_item(self, item: dict[str, Any]) -> StoredTelemetry:
        return StoredTelemetry(
            event=TelemetryEvent.from_json(item["event_json"]),
            topic=item["topic"],
            received_at=datetime.fromisoformat(item["received_at"].replace("Z", "+00:00")),
            fingerprint=item["fingerprint"],
        )

    def _serialize(self, item: dict[str, Any]) -> dict[str, Any]:
        return {key: self._serializer.serialize(value) for key, value in item.items()}

    def _deserialize(self, item: dict[str, Any]) -> dict[str, Any]:
        return {key: self._deserializer.deserialize(value) for key, value in item.items()}


def ensure_telemetry_table(client: DynamoDBClient, table_name: str) -> None:
    """Create the local/demo table and indexes when absent."""

    try:
        description = client.describe_table(TableName=table_name)
    except client.exceptions.ResourceNotFoundException:
        with suppress(client.exceptions.ResourceInUseException):
            client.create_table(
                TableName=table_name,
                BillingMode="PAY_PER_REQUEST",
                KeySchema=[
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                    {"AttributeName": "gsi1pk", "AttributeType": "S"},
                    {"AttributeName": "gsi1sk", "AttributeType": "S"},
                    {"AttributeName": "gsi2pk", "AttributeType": "S"},
                    {"AttributeName": "gsi2sk", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": ARCHIVE_PENDING_INDEX,
                        "KeySchema": [
                            {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                            {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                    {
                        "IndexName": TENANT_LATEST_INDEX,
                        "KeySchema": [
                            {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                            {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                ],
            )
        client.get_waiter("table_exists").wait(TableName=table_name)
        description = client.describe_table(TableName=table_name)

    table = description["Table"]
    if table.get("TableStatus") != "ACTIVE":
        client.get_waiter("table_exists").wait(TableName=table_name)
        table = client.describe_table(TableName=table_name)["Table"]
    _validate_table_schema(table)

    ttl = client.describe_time_to_live(TableName=table_name).get("TimeToLiveDescription", {})
    ttl_status = ttl.get("TimeToLiveStatus")
    ttl_attribute = ttl.get("AttributeName")
    if ttl_status in {"ENABLED", "ENABLING"}:
        if ttl_attribute != "expires_at":
            raise ValueError("telemetry table TTL must use expires_at")
        return
    if ttl_status == "DISABLING":
        raise RuntimeError("telemetry table TTL is still disabling")
    client.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )


def _validate_table_schema(table: Mapping[str, Any]) -> None:
    expected_table_key = {"pk": "HASH", "sk": "RANGE"}
    table_key = {item["AttributeName"]: item["KeyType"] for item in table.get("KeySchema", [])}
    if table_key != expected_table_key:
        raise ValueError("telemetry table has an incompatible primary key schema")

    expected_attribute_types = {
        "pk": "S",
        "sk": "S",
        "gsi1pk": "S",
        "gsi1sk": "S",
        "gsi2pk": "S",
        "gsi2sk": "S",
    }
    attribute_types = {
        item["AttributeName"]: item["AttributeType"]
        for item in table.get("AttributeDefinitions", [])
    }
    if attribute_types != expected_attribute_types:
        raise ValueError("telemetry table has incompatible key attribute types")

    expected_indexes = {
        ARCHIVE_PENDING_INDEX: {"gsi1pk": "HASH", "gsi1sk": "RANGE"},
        TENANT_LATEST_INDEX: {"gsi2pk": "HASH", "gsi2sk": "RANGE"},
    }
    indexes = {item["IndexName"]: item for item in table.get("GlobalSecondaryIndexes", [])}
    for index_name, expected_key in expected_indexes.items():
        index = indexes.get(index_name)
        if index is None:
            raise ValueError(f"telemetry table is missing {index_name}")
        actual_key = {item["AttributeName"]: item["KeyType"] for item in index.get("KeySchema", [])}
        if actual_key != expected_key:
            raise ValueError(f"telemetry table has an incompatible {index_name} schema")
        if index.get("Projection", {}).get("ProjectionType") != "ALL":
            raise ValueError(f"telemetry table {index_name} must project all attributes")

    billing_mode = table.get("BillingModeSummary", {}).get("BillingMode")
    if billing_mode != "PAY_PER_REQUEST":
        raise ValueError("telemetry table must use on-demand billing")


def _connector_partition(tenant_id: UUID, charger_id: UUID, connector_id: int) -> str:
    return f"TENANT#{tenant_id}#CHARGER#{charger_id}#CONNECTOR#{connector_id:04d}"


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
