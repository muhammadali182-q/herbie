"""Deterministic in-memory adapters for local development and tests."""

import asyncio
from uuid import UUID

from herbie.telemetry.errors import (
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


class InMemoryTelemetryRepository(TelemetryRepository):
    """Concurrency-safe repository preserving production idempotency semantics."""

    def __init__(self) -> None:
        self._events: dict[TelemetryKey, StoredTelemetry] = {}
        self._sequences: dict[tuple[UUID, UUID, int, UUID, int], TelemetryKey] = {}
        self._latest: dict[tuple[UUID, UUID, int], StoredTelemetry] = {}
        self._archive_pending: dict[TelemetryKey, StoredTelemetry] = {}
        self._archive_receipts: dict[TelemetryKey, ArchiveReceipt] = {}
        self._lock = asyncio.Lock()

    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        event = telemetry.event
        event_key = telemetry.key
        sequence_key = (
            event.tenant_id,
            event.charger_id,
            event.connector_id,
            event.boot_id,
            event.sequence,
        )
        connector_key = (event.tenant_id, event.charger_id, event.connector_id)

        async with self._lock:
            existing = self._events.get(event_key)
            if existing is not None:
                if existing.fingerprint != telemetry.fingerprint:
                    raise MessageIdentityConflictError(
                        "message ID was already accepted with different content"
                    )
                return TelemetryWriteResult(
                    created=False,
                    latest_updated=False,
                    archive_pending=event_key in self._archive_pending,
                    stored=existing,
                )

            sequence_owner = self._sequences.get(sequence_key)
            if sequence_owner is not None:
                raise SequenceIdentityConflictError(
                    "boot sequence was already accepted with another message ID"
                )

            self._events[event_key] = telemetry
            self._sequences[sequence_key] = event_key
            self._archive_pending[event_key] = telemetry
            current = self._latest.get(connector_key)
            latest_updated = current is None or self._is_newer(telemetry, current)
            if latest_updated:
                self._latest[connector_key] = telemetry

            return TelemetryWriteResult(
                created=True,
                latest_updated=latest_updated,
                archive_pending=True,
                stored=telemetry,
            )

    async def latest_for_connector(
        self,
        tenant_id: UUID,
        charger_id: UUID,
        connector_id: int,
    ) -> StoredTelemetry | None:
        async with self._lock:
            return self._latest.get((tenant_id, charger_id, connector_id))

    async def list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        async with self._lock:
            states = [
                state
                for (stored_tenant_id, _, _), state in self._latest.items()
                if stored_tenant_id == tenant_id
            ]
        return sorted(
            states,
            key=lambda state: (str(state.event.charger_id), state.event.connector_id),
        )

    @staticmethod
    def _is_newer(candidate: StoredTelemetry, current: StoredTelemetry) -> bool:
        candidate_event = candidate.event
        current_event = current.event
        if candidate_event.boot_id == current_event.boot_id:
            return candidate_event.sequence > current_event.sequence
        return candidate_event.boot_started_at > current_event.boot_started_at

    async def list_archive_pending(self, limit: int) -> list[StoredTelemetry]:
        if limit < 1:
            raise ValueError("limit must be at least one")
        async with self._lock:
            items = sorted(
                self._archive_pending.values(),
                key=lambda item: (
                    item.received_at,
                    str(item.event.tenant_id),
                    str(item.event.charger_id),
                    item.event.connector_id,
                    str(item.event.message_id),
                ),
            )
            return items[:limit]

    async def mark_archived(
        self,
        keys: tuple[TelemetryKey, ...],
        receipt: ArchiveReceipt,
    ) -> None:
        async with self._lock:
            for key in keys:
                if key in self._events:
                    self._archive_pending.pop(key, None)
                    self._archive_receipts.setdefault(key, receipt)

    async def archive_receipt_for(self, key: TelemetryKey) -> ArchiveReceipt | None:
        async with self._lock:
            return self._archive_receipts.get(key)
