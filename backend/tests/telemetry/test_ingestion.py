"""Telemetry ingestion and idempotency tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.errors import MessageIdentityConflictError, TopicIdentityMismatchError
from herbie.telemetry.memory import InMemoryTelemetryArchive, InMemoryTelemetryRepository
from herbie.telemetry.repository import StoredTelemetry
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import TelemetryTopic

TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
CHARGER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def event(
    *,
    tenant_id: UUID = TENANT_A,
    charger_id: UUID = CHARGER_A,
    message_id: UUID | None = None,
    sequence: int = 1,
    occurred_at: datetime | None = None,
    power_w: int = 7_200,
) -> TelemetryEvent:
    timestamp = occurred_at or datetime(2026, 1, 1, tzinfo=UTC)
    return TelemetryEvent(
        schema_version="1.0",
        message_id=message_id or uuid4(),
        message_type=MessageType.TELEMETRY_REPORTED,
        occurred_at=timestamp,
        sent_at=timestamp,
        boot_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        sequence=sequence,
        tenant_id=tenant_id,
        charger_id=charger_id,
        connector_id=1,
        payload=TelemetryPayload(
            cumulative_energy_wh=100 + sequence,
            power_w=power_w,
            status=ChargerStatus.CHARGING,
        ),
    )


def service() -> tuple[
    TelemetryIngestionService,
    InMemoryTelemetryRepository,
    InMemoryTelemetryArchive,
]:
    repository = InMemoryTelemetryRepository()
    archive = InMemoryTelemetryArchive()
    received_at = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)
    return (
        TelemetryIngestionService(repository, archive, lambda: received_at),
        repository,
        archive,
    )


@pytest.mark.asyncio
async def test_ingestion_accepts_and_archives_new_event() -> None:
    ingestion, repository, archive = service()
    telemetry = event()
    topic = TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id)

    result = await ingestion.ingest(topic, telemetry.canonical_json())

    assert result.accepted is True
    assert result.duplicate is False
    assert result.latest_updated is True
    assert await repository.latest_for_charger(TENANT_A, CHARGER_A) == result.telemetry
    assert await archive.items_for_tenant(TENANT_A) == (result.telemetry,)


@pytest.mark.asyncio
async def test_duplicate_is_not_archived_or_applied_twice() -> None:
    ingestion, _, archive = service()
    telemetry = event()
    topic = TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id)

    first = await ingestion.ingest(topic, telemetry.canonical_json())
    duplicate = await ingestion.ingest(topic, telemetry.canonical_json())

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.duplicate is True
    assert await archive.items_for_tenant(TENANT_A) == (first.telemetry,)


@pytest.mark.asyncio
async def test_retry_repairs_archive_after_hot_store_succeeds() -> None:
    repository = InMemoryTelemetryRepository()
    archive = InMemoryTelemetryArchive()
    attempts = 0

    class FailsOnceArchive:
        async def append(self, telemetry: StoredTelemetry) -> None:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("synthetic archive outage")
            await archive.append(telemetry)

    ingestion = TelemetryIngestionService(repository, FailsOnceArchive())
    telemetry = event()
    topic = TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id)

    with pytest.raises(RuntimeError, match="archive outage"):
        await ingestion.ingest(topic, telemetry.canonical_json())

    repaired = await ingestion.ingest(topic, telemetry.canonical_json())

    assert repaired.duplicate is True
    assert attempts == 2
    assert len(await archive.items_for_tenant(TENANT_A)) == 1


@pytest.mark.asyncio
async def test_message_id_reuse_with_other_content_is_rejected() -> None:
    ingestion, _, _ = service()
    message_id = uuid4()
    original = event(message_id=message_id, power_w=7_200)
    conflict = event(message_id=message_id, power_w=22_000)
    topic = TelemetryTopic.for_device(original.tenant_id, original.charger_id)

    await ingestion.ingest(topic, original.canonical_json())

    with pytest.raises(MessageIdentityConflictError):
        await ingestion.ingest(topic, conflict.canonical_json())


@pytest.mark.asyncio
async def test_payload_cannot_forge_topic_identity() -> None:
    ingestion, _, _ = service()
    telemetry = event(tenant_id=TENANT_B)
    trusted_topic = TelemetryTopic.for_device(TENANT_A, telemetry.charger_id)

    with pytest.raises(TopicIdentityMismatchError):
        await ingestion.ingest(trusted_topic, telemetry.canonical_json())


@pytest.mark.asyncio
async def test_stale_event_is_retained_without_replacing_latest() -> None:
    ingestion, repository, archive = service()
    latest_event = event(sequence=2, occurred_at=datetime(2026, 1, 1, 0, 0, 20, tzinfo=UTC))
    stale_event = event(sequence=1, occurred_at=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC))
    topic = TelemetryTopic.for_device(TENANT_A, CHARGER_A)

    latest_result = await ingestion.ingest(topic, latest_event.canonical_json())
    stale_result = await ingestion.ingest(topic, stale_event.canonical_json())

    assert stale_result.accepted is True
    assert stale_result.latest_updated is False
    assert await repository.latest_for_charger(TENANT_A, CHARGER_A) == latest_result.telemetry
    assert len(await archive.items_for_tenant(TENANT_A)) == 2


@pytest.mark.asyncio
async def test_latest_listing_never_crosses_tenant_boundary() -> None:
    repository = InMemoryTelemetryRepository()
    received = datetime(2026, 1, 1, tzinfo=UTC)
    event_a = event(tenant_id=TENANT_A)
    event_b = event(tenant_id=TENANT_B)
    await repository.store(StoredTelemetry(event=event_a, received_at=received))
    await repository.store(StoredTelemetry(event=event_b, received_at=received))

    tenant_a_items = await repository.list_latest_for_tenant(TENANT_A)

    assert [item.event.tenant_id for item in tenant_a_items] == [TENANT_A]


@pytest.mark.asyncio
async def test_same_message_id_is_scoped_to_its_device() -> None:
    repository = InMemoryTelemetryRepository()
    received = datetime(2026, 1, 1, tzinfo=UTC)
    message_id = uuid4()
    first = event(message_id=message_id)
    second = event(message_id=message_id, charger_id=uuid4())

    first_write = await repository.store(StoredTelemetry(first, received))
    second_write = await repository.store(StoredTelemetry(second, received))

    assert first_write.created is True
    assert second_write.created is True


def test_stored_telemetry_is_immutable() -> None:
    stored = StoredTelemetry(event=event(), received_at=datetime(2026, 1, 1, tzinfo=UTC))

    with pytest.raises(FrozenInstanceError):
        stored.received_at = datetime(2027, 1, 1, tzinfo=UTC)  # type: ignore[misc]
