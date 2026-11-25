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
    topic: str
    received_at: datetime
    fingerprint: str

    @property
    def key(self) -> "TelemetryKey":
        event = self.event
        return TelemetryKey(
            tenant_id=event.tenant_id,
            charger_id=event.charger_id,
            connector_id=event.connector_id,
            message_id=event.message_id,
        )


@dataclass(frozen=True, slots=True)
class TelemetryKey:
    """Stable identity for one immutable event."""

    tenant_id: UUID
    charger_id: UUID
    connector_id: int
    message_id: UUID


@dataclass(frozen=True, slots=True)
class TelemetryWriteResult:
    """Outcome of an idempotent event write."""

    created: bool
    latest_updated: bool
    archive_pending: bool
    stored: StoredTelemetry


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    """Location and checksum of an immutable canonical archive batch."""

    object_key: str
    checksum_sha256: str
    archived_at: datetime


class TelemetryRepository(Protocol):
    """Required behavior for hot telemetry storage."""

    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        """Store once and update latest state when this event is newer."""

    async def latest_for_connector(
        self,
        tenant_id: UUID,
        charger_id: UUID,
        connector_id: int,
    ) -> StoredTelemetry | None:
        """Return one tenant-scoped connector's latest accepted state."""

    async def list_latest_for_tenant(self, tenant_id: UUID) -> list[StoredTelemetry]:
        """Return latest charger states without crossing a tenant boundary."""

    async def list_archive_pending(self, limit: int) -> list[StoredTelemetry]:
        """Return deterministic pending canonical events for an archive worker."""

    async def mark_archived(
        self,
        keys: tuple[TelemetryKey, ...],
        receipt: ArchiveReceipt,
    ) -> None:
        """Mark events archived after an immutable batch is durably stored."""
