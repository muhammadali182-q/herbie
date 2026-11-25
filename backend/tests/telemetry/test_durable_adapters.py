"""DynamoDB and S3 adapter conformance tests using in-process AWS emulation."""

import gzip
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient
from mypy_boto3_s3 import S3Client

from herbie.telemetry.archive import TelemetryArchiveService, build_archive_batch
from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.dynamodb import DynamoTelemetryRepository, ensure_telemetry_table
from herbie.telemetry.errors import (
    ArchiveObjectConflictError,
    BootIdentityConflictError,
    MessageIdentityConflictError,
    SequenceIdentityConflictError,
)
from herbie.telemetry.repository import ArchiveReceipt, StoredTelemetry, TelemetryKey
from herbie.telemetry.s3 import S3TelemetryArchiveSink, ensure_archive_bucket
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic

REGION = "us-east-1"
TABLE_NAME = "herbie-telemetry-test"
BUCKET_NAME = "herbie-archive-test"
TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
CHARGER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BOOT_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
BOOT_B = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
RECEIVED_AT = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


@pytest.fixture
def aws_clients(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[DynamoDBClient, S3Client]]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)
        ensure_telemetry_table(dynamodb, TABLE_NAME)
        ensure_archive_bucket(s3, BUCKET_NAME, REGION)
        yield dynamodb, s3


def event(
    *,
    tenant_id: UUID = TENANT_A,
    charger_id: UUID = CHARGER_A,
    connector_id: int = 1,
    message_id: UUID | None = None,
    boot_id: UUID = BOOT_A,
    boot_started_at: datetime | None = None,
    sequence: int = 1,
    power_w: int = 7_200,
) -> TelemetryEvent:
    started = boot_started_at or datetime(2026, 1, 1, tzinfo=UTC)
    occurred = started + timedelta(seconds=max(sequence, 1))
    return TelemetryEvent(
        schema_version="1.0",
        message_id=message_id or uuid4(),
        message_type=MessageType.TELEMETRY_REPORTED,
        occurred_at=occurred,
        sent_at=occurred,
        boot_id=boot_id,
        boot_started_at=started,
        sequence=sequence,
        tenant_id=tenant_id,
        charger_id=charger_id,
        connector_id=connector_id,
        payload=TelemetryPayload(
            cumulative_energy_wh=100 + sequence,
            power_w=power_w,
            status=ChargerStatus.CHARGING,
        ),
    )


def stored(telemetry: TelemetryEvent) -> StoredTelemetry:
    return StoredTelemetry(
        event=telemetry,
        topic=TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id),
        received_at=RECEIVED_AT,
        fingerprint=telemetry.semantic_fingerprint(),
    )


def raw_item(
    client: DynamoDBClient,
    telemetry: TelemetryEvent,
    sort_key: str,
) -> dict[str, Any]:
    partition_key = (
        f"TENANT#{telemetry.tenant_id}#CHARGER#{telemetry.charger_id}#"
        f"CONNECTOR#{telemetry.connector_id:04d}"
    )
    response = client.get_item(
        TableName=TABLE_NAME,
        Key={"pk": {"S": partition_key}, "sk": {"S": sort_key}},
        ConsistentRead=True,
    )
    return response["Item"]


@pytest.mark.asyncio
async def test_dynamodb_store_is_idempotent_and_keeps_archive_pending(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    repository = DynamoTelemetryRepository(aws_clients[0], TABLE_NAME)
    telemetry = stored(event())

    created = await repository.store(telemetry)
    duplicate = await repository.store(telemetry)

    assert created.created is True
    assert duplicate.created is False
    assert duplicate.latest_updated is False
    assert duplicate.stored == telemetry
    assert duplicate.archive_pending is True
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == telemetry
    assert await repository.list_archive_pending(10) == [telemetry]


@pytest.mark.asyncio
async def test_dynamodb_rejects_message_and_sequence_identity_conflicts(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    repository = DynamoTelemetryRepository(aws_clients[0], TABLE_NAME)
    message_id = uuid4()
    original = stored(event(message_id=message_id, power_w=7_200, sequence=7))
    message_conflict = stored(event(message_id=message_id, power_w=9_000, sequence=8))
    sequence_conflict = stored(event(message_id=uuid4(), power_w=7_200, sequence=7))
    boot_conflict = stored(
        event(
            message_id=uuid4(),
            boot_started_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
            sequence=8,
        )
    )
    await repository.store(original)

    with pytest.raises(MessageIdentityConflictError):
        await repository.store(message_conflict)
    with pytest.raises(SequenceIdentityConflictError):
        await repository.store(sequence_conflict)
    with pytest.raises(BootIdentityConflictError):
        await repository.store(boot_conflict)


@pytest.mark.asyncio
async def test_dynamodb_ordering_matches_boot_and_sequence_contract(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    repository = DynamoTelemetryRepository(aws_clients[0], TABLE_NAME)
    boot_started = datetime(2026, 1, 1, tzinfo=UTC)
    higher_sequence = stored(event(sequence=2, boot_started_at=boot_started))
    lower_sequence = stored(event(sequence=1, boot_started_at=boot_started))
    newer_boot = stored(
        event(
            boot_id=BOOT_B,
            boot_started_at=boot_started + timedelta(milliseconds=100),
            sequence=0,
        )
    )

    first = await repository.store(higher_sequence)
    stale = await repository.store(lower_sequence)
    rebooted = await repository.store(newer_boot)

    assert first.latest_updated is True
    assert stale.created is True
    assert stale.latest_updated is False
    assert rebooted.latest_updated is True
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == newer_boot


@pytest.mark.asyncio
async def test_dynamodb_retries_a_transactional_conflict_read(
    aws_clients: tuple[DynamoDBClient, S3Client],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dynamodb = aws_clients[0]
    repository = DynamoTelemetryRepository(dynamodb, TABLE_NAME)
    telemetry = stored(event(sequence=6))
    await repository.store(telemetry)
    original_get = dynamodb.transact_get_items
    attempts = 0

    def conflict_once(**request: Any) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "synthetic transaction conflict",
                    }
                },
                "TransactGetItems",
            )
        return original_get(**request)

    monkeypatch.setattr(dynamodb, "transact_get_items", conflict_once)

    duplicate = await repository.store(telemetry)

    assert duplicate.created is False
    assert attempts == 2


@pytest.mark.asyncio
async def test_dynamodb_latest_state_is_connector_and_tenant_scoped(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    repository = DynamoTelemetryRepository(aws_clients[0], TABLE_NAME)
    one = stored(event(sequence=1, connector_id=1))
    two = stored(event(sequence=9, connector_id=2))
    other_tenant = stored(event(sequence=2, tenant_id=TENANT_B))
    await repository.store(one)
    await repository.store(two)
    await repository.store(other_tenant)

    tenant_items = await repository.list_latest_for_tenant(TENANT_A)

    assert {item.event.connector_id for item in tenant_items} == {1, 2}
    assert {item.event.tenant_id for item in tenant_items} == {TENANT_A}


@pytest.mark.asyncio
async def test_dynamodb_archive_receipt_removes_pending_index(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    repository = DynamoTelemetryRepository(aws_clients[0], TABLE_NAME)
    telemetry = stored(event())
    await repository.store(telemetry)
    receipt = ArchiveReceipt(
        object_key="raw/example.jsonl.gz",
        checksum_sha256="a" * 64,
        archived_at=RECEIVED_AT,
    )
    replacement = ArchiveReceipt(
        object_key="raw/replacement.jsonl.gz",
        checksum_sha256="b" * 64,
        archived_at=RECEIVED_AT + timedelta(minutes=1),
    )
    missing = TelemetryKey(TENANT_A, CHARGER_A, 1, uuid4())

    before = raw_item(aws_clients[0], telemetry.event, f"EVENT#{telemetry.event.message_id}")
    replay = raw_item(aws_clients[0], telemetry.event, f"REPLAY#{telemetry.event.message_id}")
    assert "expires_at" not in before
    assert int(replay["expires_at"]["N"]) > int(before["event_expires_at"]["N"])

    await repository.mark_archived((telemetry.key,), receipt)
    await repository.mark_archived((telemetry.key, missing), replacement)

    assert await repository.list_archive_pending(10) == []
    archived = raw_item(aws_clients[0], telemetry.event, f"EVENT#{telemetry.event.message_id}")
    assert archived["archive_object_key"]["S"] == receipt.object_key
    assert archived["archive_checksum"]["S"] == receipt.checksum_sha256
    assert archived["expires_at"] == archived["event_expires_at"]
    assert "gsi1pk" not in archived


@pytest.mark.asyncio
async def test_s3_sink_is_idempotent_and_rejects_key_conflict(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    s3 = aws_clients[1]
    sink = S3TelemetryArchiveSink(s3, BUCKET_NAME)
    batch = build_archive_batch([stored(event())])

    await sink.put(batch)
    await sink.put(batch)
    response = s3.get_object(Bucket=BUCKET_NAME, Key=batch.object_key)

    assert gzip.decompress(response["Body"].read()).decode().count("\n") == 1
    assert response["ServerSideEncryption"] == "AES256"
    with pytest.raises(ArchiveObjectConflictError):
        await sink.put(replace(batch, checksum_sha256="f" * 64))


@pytest.mark.asyncio
async def test_s3_sink_requires_explicit_opt_out_for_unencrypted_emulator(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    s3 = aws_clients[1]
    batch = build_archive_batch([stored(event(message_id=UUID(int=50)))])

    await S3TelemetryArchiveSink(s3, BUCKET_NAME, encrypt=False).put(batch)

    response = s3.head_object(Bucket=BUCKET_NAME, Key=batch.object_key)
    assert "ServerSideEncryption" not in response
    with pytest.raises(ValueError, match="cannot be disabled"):
        S3TelemetryArchiveSink(s3, BUCKET_NAME, "kms-key", encrypt=False)


@pytest.mark.asyncio
async def test_s3_sink_retries_conditional_request_conflict(
    aws_clients: tuple[DynamoDBClient, S3Client],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s3 = aws_clients[1]
    original_put = s3.put_object
    attempts = 0

    def conflict_once(**request: Any) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ClientError(
                {
                    "Error": {
                        "Code": "ConditionalRequestConflict",
                        "Message": "synthetic concurrent write",
                    },
                },
                "PutObject",
            )
        return original_put(**request)

    monkeypatch.setattr(s3, "put_object", conflict_once)
    batch = build_archive_batch([stored(event())])

    await S3TelemetryArchiveSink(s3, BUCKET_NAME).put(batch)

    assert attempts == 2
    assert (
        s3.head_object(Bucket=BUCKET_NAME, Key=batch.object_key)["Metadata"]["canonical-sha256"]
        == batch.checksum_sha256
    )


@pytest.mark.asyncio
async def test_archive_service_moves_dynamodb_pending_events_to_s3(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    dynamodb, s3 = aws_clients
    repository = DynamoTelemetryRepository(dynamodb, TABLE_NAME)
    ingestion = TelemetryIngestionService(repository, lambda: RECEIVED_AT)
    telemetry = event()
    await ingestion.ingest(
        DeviceIdentity(telemetry.tenant_id, telemetry.charger_id),
        TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id),
        telemetry.canonical_json(),
    )
    archive = TelemetryArchiveService(
        repository,
        S3TelemetryArchiveSink(s3, BUCKET_NAME),
        lambda: RECEIVED_AT,
    )

    result = await archive.flush()

    assert result.events_archived == 1
    assert await repository.list_archive_pending(10) == []
    listed = s3.list_objects_v2(Bucket=BUCKET_NAME)
    assert listed["KeyCount"] == 1


def test_bootstrap_and_retention_validation_are_idempotent(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    dynamodb, s3 = aws_clients

    ensure_telemetry_table(dynamodb, TABLE_NAME)
    ensure_archive_bucket(s3, BUCKET_NAME, REGION)

    ttl = dynamodb.describe_time_to_live(TableName=TABLE_NAME)["TimeToLiveDescription"]
    assert ttl["TimeToLiveStatus"] in {"ENABLING", "ENABLED"}
    assert ttl["AttributeName"] == "expires_at"
    access_block = s3.get_public_access_block(Bucket=BUCKET_NAME)["PublicAccessBlockConfiguration"]
    assert all(access_block.values())

    with pytest.raises(ValueError, match="at least one day"):
        DynamoTelemetryRepository(dynamodb, TABLE_NAME, event_retention_days=0)
    with pytest.raises(ValueError, match="replay retention"):
        DynamoTelemetryRepository(
            dynamodb,
            TABLE_NAME,
            event_retention_days=14,
            replay_retention_days=14,
        )


def test_bucket_bootstrap_allows_only_explicitly_unsupported_local_api(
    aws_clients: tuple[DynamoDBClient, S3Client],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s3 = aws_clients[1]
    unsupported = ClientError(
        cast(
            Any,
            {
                "Error": {"Code": "MalformedXML", "Message": "unsupported"},
                "ResponseMetadata": {"HTTPStatusCode": 400},
            },
        ),
        "PutPublicAccessBlock",
    )
    monkeypatch.setattr(
        s3, "put_public_access_block", lambda **request: (_ for _ in ()).throw(unsupported)
    )

    ensure_archive_bucket(
        s3,
        BUCKET_NAME,
        REGION,
        allow_unsupported_public_access_block=True,
    )
    with pytest.raises(ClientError):
        ensure_archive_bucket(s3, BUCKET_NAME, REGION)


def test_table_bootstrap_rejects_an_incompatible_existing_table(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    dynamodb = aws_clients[0]
    incompatible_table = "herbie-incompatible-test"
    dynamodb.create_table(
        TableName=incompatible_table,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
    )

    with pytest.raises(ValueError, match="primary key schema"):
        ensure_telemetry_table(dynamodb, incompatible_table)


def test_table_bootstrap_rejects_incomplete_index_projection(
    aws_clients: tuple[DynamoDBClient, S3Client],
) -> None:
    dynamodb = aws_clients[0]
    incompatible_table = "herbie-incomplete-index-test"
    dynamodb.create_table(
        TableName=incompatible_table,
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
                "IndexName": "archive-pending-index",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
            {
                "IndexName": "tenant-latest-index",
                "KeySchema": [
                    {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    with pytest.raises(ValueError, match="project all"):
        ensure_telemetry_table(dynamodb, incompatible_table)
