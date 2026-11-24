"""Deterministic in-memory adapters for local development and tests."""

import asyncio
from datetime import datetime
from uuid import UUID

from herbie.telemetry.errors import MessageIdentityConflictError
from herbie.telemetry.repository import (
    StoredTelemetry,
    TelemetryArchive,
    TelemetryRepository,
    TelemetryWriteResult,
)


class InMemoryTelemetryRepository(TelemetryRepository):
    """Concurrency-safe repository preserving production idempotency semantics."""

    def __init__(self) -> None:
        self._events: dict[tuple[UUID, UUID, UUID], StoredTelemetry] = {}
        self._latest: dict[tuple[UUID, UUID], StoredTelemetry] = {}
        self._lock = asyncio.Lock()

    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        event = telemetry.event
        event_key = (event.tenant_id, event.charger_id, event.message_id)
        charger_key = (event.tenant_id, event.charger_id)

        async with self._lock:
            existing = self._events.get(event_key)
            if existing is not None:
                if existing.event.canonical_json() != event.canonical_json():
                    raise MessageIdentityConflictError(
                        "message ID was already accepted with different content"
                    )
                return TelemetryWriteResult(
                    created=False,
                    latest_updated=False,
                    stored=existing,
                )

            self._events[event_key] = telemetry
            current = self._latest.get(charger_key)
            latest_updated = current is None or self._rank(telemetry) > self._rank(current)
            if latest_updated:
                self._latest[charger_key] = telemetry

            return TelemetryWriteResult(
                created=True,
                latest_updated=latest_updated,
                stored=telemetry,
            )

    async def latest_for_charger(
        self,
        tenant_id: UUID,
        charger_id: UUID,
    ) -> StoredTelemetry | None:
        async with self._lock:
            return self._latest.get((tenant_id, charger_id))

    async def list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        async with self._lock:
            states = [
                state
                for (stored_tenant_id, _), state in self._latest.items()
                if stored_tenant_id == tenant_id
            ]
        return sorted(states, key=lambda state: str(state.event.charger_id))

    @staticmethod
    def _rank(telemetry: StoredTelemetry) -> tuple[datetime, str, int, str]:
        event = telemetry.event
        return (
            event.occurred_at,
            str(event.boot_id),
            event.sequence,
            str(event.message_id),
        )


class InMemoryTelemetryArchive(TelemetryArchive):
    """Append-only archive used to assert one-write behavior."""

    def __init__(self) -> None:
        self._items: dict[UUID, dict[tuple[UUID, UUID], StoredTelemetry]] = {}
        self._lock = asyncio.Lock()

    async def append(self, telemetry: StoredTelemetry) -> None:
        async with self._lock:
            tenant_items = self._items.setdefault(telemetry.event.tenant_id, {})
            key = (telemetry.event.charger_id, telemetry.event.message_id)
            tenant_items.setdefault(key, telemetry)

    async def items_for_tenant(self, tenant_id: UUID) -> tuple[StoredTelemetry, ...]:
        async with self._lock:
            return tuple(self._items.get(tenant_id, {}).values())
