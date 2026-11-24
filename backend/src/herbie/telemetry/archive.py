"""Canonical, compressed batching of the durable telemetry archive outbox."""

import gzip
import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from herbie.telemetry.errors import ArchiveObjectConflictError
from herbie.telemetry.repository import (
    ArchiveReceipt,
    StoredTelemetry,
    TelemetryRepository,
)


@dataclass(frozen=True, slots=True)
class ArchiveBatch:
    """One immutable gzip NDJSON object and its source event keys."""

    tenant_id: UUID
    object_key: str
    checksum_sha256: str
    content: bytes
    events: tuple[StoredTelemetry, ...]


@dataclass(frozen=True, slots=True)
class ArchiveFlushResult:
    """Observable outcome of one bounded archive worker pass."""

    events_archived: int
    objects_written: int


class TelemetryArchiveSink(Protocol):
    """Immutable object-store port."""

    async def put(self, batch: ArchiveBatch) -> None:
        """Idempotently persist one object or reject a content conflict."""


class InMemoryTelemetryArchiveSink(TelemetryArchiveSink):
    """In-memory immutable-object semantics for tests."""

    def __init__(self) -> None:
        self.objects: dict[str, ArchiveBatch] = {}
        self.put_attempts = 0

    async def put(self, batch: ArchiveBatch) -> None:
        self.put_attempts += 1
        existing = self.objects.get(batch.object_key)
        if existing is not None and existing.checksum_sha256 != batch.checksum_sha256:
            raise ArchiveObjectConflictError("archive key already contains other content")
        self.objects.setdefault(batch.object_key, batch)


class TelemetryArchiveService:
    """Drain pending events into deterministic tenant/hour archive objects."""

    def __init__(
        self,
        repository: TelemetryRepository,
        sink: TelemetryArchiveSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._sink = sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def flush(self, limit: int = 1_000) -> ArchiveFlushResult:
        pending = await self._repository.list_archive_pending(limit)
        grouped: defaultdict[tuple[UUID, datetime], list[StoredTelemetry]] = defaultdict(list)
        for item in pending:
            event_hour = item.event.occurred_at.replace(minute=0, second=0, microsecond=0)
            grouped[(item.event.tenant_id, event_hour)].append(item)

        events_archived = 0
        for _group_key, events in sorted(grouped.items(), key=lambda group: str(group[0])):
            batch = build_archive_batch(events)
            await self._sink.put(batch)
            archived_at = self._clock()
            if archived_at.tzinfo is None or archived_at.utcoffset() is None:
                raise ValueError("archive clock must include a timezone offset")
            receipt = ArchiveReceipt(
                object_key=batch.object_key,
                checksum_sha256=batch.checksum_sha256,
                archived_at=archived_at.astimezone(UTC),
            )
            await self._repository.mark_archived(
                tuple(item.key for item in batch.events),
                receipt,
            )
            events_archived += len(batch.events)

        return ArchiveFlushResult(
            events_archived=events_archived,
            objects_written=len(grouped),
        )


def build_archive_batch(events: list[StoredTelemetry]) -> ArchiveBatch:
    """Build one deterministic canonical batch for a single tenant/hour."""

    if not events:
        raise ValueError("archive batch cannot be empty")
    ordered = sorted(
        events,
        key=lambda item: (
            item.received_at,
            str(item.event.charger_id),
            item.event.connector_id,
            str(item.event.message_id),
        ),
    )
    tenant_id = ordered[0].event.tenant_id
    event_hour = ordered[0].event.occurred_at.replace(minute=0, second=0, microsecond=0)
    if any(
        item.event.tenant_id != tenant_id
        or item.event.occurred_at.replace(minute=0, second=0, microsecond=0) != event_hour
        for item in ordered
    ):
        raise ValueError("archive batch must contain one tenant and UTC hour")

    lines = [_canonical_archive_line(item) for item in ordered]
    canonical_content = ("\n".join(lines) + "\n").encode()
    checksum = hashlib.sha256(canonical_content).hexdigest()
    compressed = gzip.compress(canonical_content, compresslevel=6, mtime=0)
    object_key = (
        f"raw/tenant_id={tenant_id}/year={event_hour:%Y}/month={event_hour:%m}/"
        f"day={event_hour:%d}/hour={event_hour:%H}/{checksum[:24]}.jsonl.gz"
    )
    return ArchiveBatch(
        tenant_id=tenant_id,
        object_key=object_key,
        checksum_sha256=checksum,
        content=compressed,
        events=tuple(ordered),
    )


def _canonical_archive_line(telemetry: StoredTelemetry) -> str:
    record = {
        "archive_schema_version": "1.0",
        "event": telemetry.event.model_dump(mode="json", exclude_none=True),
        "fingerprint": telemetry.fingerprint,
        "received_at": telemetry.received_at.isoformat().replace("+00:00", "Z"),
        "topic": telemetry.topic,
    }
    return json.dumps(record, sort_keys=True, separators=(",", ":"))
