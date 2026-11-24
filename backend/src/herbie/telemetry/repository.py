"""Telemetry persistence ports used by the application layer."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from herbie.telemetry.contracts import TelemetryEvent


@dataclass(frozen=True, slots=True)
class StoredTelemetry:
    """A validated telemetry event and server receipt timestamp."""

    event: TelemetryEvent
    received_at: datetime


@dataclass(frozen=True, slots=True)
class TelemetryWriteResult:
    """Outcome of an idempotent event write."""

    created: bool
    latest_updated: bool
    stored: StoredTelemetry


class TelemetryRepository(Protocol):
    """Required behavior for hot telemetry storage."""

    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        """Store once and update latest state when this event is newer."""

    async def latest_for_charger(
        self,
        tenant_id: UUID,
        charger_id: UUID,
    ) -> StoredTelemetry | None:
        """Return one tenant-scoped charger's latest accepted state."""

    async def list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        """Return latest charger states without crossing a tenant boundary."""


class TelemetryArchive(Protocol):
    """Required behavior for the raw event archive."""

    async def append(self, telemetry: StoredTelemetry) -> None:
        """Idempotently append an event for later batched persistence."""
