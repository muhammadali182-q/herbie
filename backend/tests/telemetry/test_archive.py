"""Durable canonical archive-outbox and batching tests."""

import asyncio
import gzip
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from herbie.telemetry.archive import (
    InMemoryTelemetryArchiveSink,
    TelemetryArchiveService,
    build_archive_batch,
)
from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.errors import ArchiveObjectConflictError
from herbie.telemetry.memory import InMemoryTelemetryRepository
from herbie.telemetry.repository import StoredTelemetry
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic

TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
ARCHIVE_TIME = datetime(2026, 1, 1, 1, tzinfo=UTC)


def telemetry(tenant_id: UUID, charger_number: int, minute: int = 0) -> TelemetryEvent:
    charger_id = UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-{charger_number:012d}")
    occurred_at = datetime(2026, 1, 1, 0, minute, 10, tzinfo=UTC)
    return TelemetryEvent(
        schema_version="1.0",
        message_id=UUID(f"dddddddd-dddd-dddd-dddd-{charger_number:012d}"),
        message_type=MessageType.TELEMETRY_REPORTED,
        occurred_at=occurred_at,
        sent_at=occurred_at,
        boot_id=UUID(f"bbbbbbbb-bbbb-bbbb-bbbb-{charger_number:012d}"),
        boot_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sequence=1,
        tenant_id=tenant_id,
        charger_id=charger_id,
        connector_id=1,
        payload=TelemetryPayload(
            cumulative_energy_wh=100,
            power_w=7_000,
            status=ChargerStatus.CHARGING,
        ),
    )


async def accept(repository: InMemoryTelemetryRepository, event: TelemetryEvent) -> None:
    service = TelemetryIngestionService(
        repository,
        clock=lambda: event.occurred_at + timedelta(seconds=1),
    )
    await service.ingest(
        DeviceIdentity(event.tenant_id, event.charger_id),
        TelemetryTopic.for_device(event.tenant_id, event.charger_id),
        event.canonical_json(),
    )


@pytest.mark.asyncio
async def test_flush_writes_one_deterministic_gzip_object_and_marks_receipts() -> None:
    repository = InMemoryTelemetryRepository()
    first = telemetry(TENANT_A, 1)
    second = telemetry(TENANT_A, 2, minute=20)
    await accept(repository, first)
    await accept(repository, second)
    sink = InMemoryTelemetryArchiveSink()
    archive = TelemetryArchiveService(repository, sink, lambda: ARCHIVE_TIME)

    result = await archive.flush()

    assert result.events_archived == 2
    assert result.objects_written == 1
    assert len(sink.objects) == 1
    batch = next(iter(sink.objects.values()))
    assert batch.object_key.startswith(f"raw/tenant_id={TENANT_A}/year=2026/")
    lines = gzip.decompress(batch.content).decode().strip().splitlines()
    assert len(lines) == 2
    assert '"archive_schema_version":"1.0"' in lines[0]
    assert await repository.list_archive_pending(10) == []
    assert await repository.archive_receipt_for(batch.events[0].key) is not None


@pytest.mark.asyncio
async def test_failed_object_write_leaves_pending_for_retry() -> None:
    repository = InMemoryTelemetryRepository()
    event = telemetry(TENANT_A, 1)
    await accept(repository, event)
    durable_sink = InMemoryTelemetryArchiveSink()

    class FailsOnceSink:
        def __init__(self) -> None:
            self.attempts = 0

        async def put(self, batch):  # type: ignore[no-untyped-def]
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("synthetic S3 outage")
            await durable_sink.put(batch)

    sink = FailsOnceSink()
    archive = TelemetryArchiveService(repository, sink, lambda: ARCHIVE_TIME)

    with pytest.raises(RuntimeError, match="S3 outage"):
        await archive.flush()
    assert len(await repository.list_archive_pending(10)) == 1

    repaired = await archive.flush()

    assert repaired.events_archived == 1
    assert sink.attempts == 2
    assert len(durable_sink.objects) == 1


@pytest.mark.asyncio
async def test_one_archive_service_serializes_concurrent_flushes() -> None:
    repository = InMemoryTelemetryRepository()
    event = telemetry(TENANT_A, 1)
    await accept(repository, event)
    sink = InMemoryTelemetryArchiveSink()
    archive = TelemetryArchiveService(repository, sink, lambda: ARCHIVE_TIME)

    first, second = await asyncio.gather(archive.flush(), archive.flush())

    assert first.events_archived + second.events_archived == 1
    assert sink.put_attempts == 1
    assert len(sink.objects) == 1


@pytest.mark.asyncio
async def test_batches_are_separated_by_tenant() -> None:
    repository = InMemoryTelemetryRepository()
    await accept(repository, telemetry(TENANT_A, 1))
    await accept(repository, telemetry(TENANT_B, 2))
    sink = InMemoryTelemetryArchiveSink()

    result = await TelemetryArchiveService(repository, sink, lambda: ARCHIVE_TIME).flush()

    assert result.objects_written == 2
    assert {batch.tenant_id for batch in sink.objects.values()} == {TENANT_A, TENANT_B}


def test_batch_bytes_are_independent_of_input_order() -> None:
    first = stored(telemetry(TENANT_A, 1))
    second = stored(telemetry(TENANT_A, 2))

    forward = build_archive_batch([first, second])
    reverse = build_archive_batch([second, first])

    assert forward.object_key == reverse.object_key
    assert forward.checksum_sha256 == reverse.checksum_sha256
    assert forward.content == reverse.content


def test_batch_rejects_empty_or_cross_tenant_inputs() -> None:
    with pytest.raises(ValueError, match="empty"):
        build_archive_batch([])
    with pytest.raises(ValueError, match="one tenant"):
        build_archive_batch([stored(telemetry(TENANT_A, 1)), stored(telemetry(TENANT_B, 2))])


@pytest.mark.asyncio
async def test_sink_rejects_same_key_with_different_checksum() -> None:
    sink = InMemoryTelemetryArchiveSink()
    batch = build_archive_batch([stored(telemetry(TENANT_A, 1))])
    await sink.put(batch)

    with pytest.raises(ArchiveObjectConflictError):
        await sink.put(replace(batch, checksum_sha256="0" * 64))


def stored(event: TelemetryEvent) -> StoredTelemetry:
    return StoredTelemetry(
        event=event,
        topic=TelemetryTopic.for_device(event.tenant_id, event.charger_id),
        received_at=event.occurred_at + timedelta(seconds=1),
        fingerprint=event.semantic_fingerprint(),
    )
