"""Telemetry ingestion, ordering, concurrency, and tenancy tests."""

import asyncio
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.errors import (
    MessageIdentityConflictError,
    SequenceIdentityConflictError,
    TelemetryClockSkewError,
    TopicIdentityMismatchError,
)
from herbie.telemetry.memory import InMemoryTelemetryRepository
from herbie.telemetry.repository import StoredTelemetry
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic

TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
CHARGER_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BOOT_A = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
BOOT_B = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SERVER_TIME = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


def event(
    *,
    tenant_id: UUID = TENANT_A,
    charger_id: UUID = CHARGER_A,
    connector_id: int = 1,
    message_id: UUID | None = None,
    boot_id: UUID = BOOT_A,
    boot_started_at: datetime | None = None,
    sequence: int = 1,
    occurred_at: datetime | None = None,
    power_w: int = 7_200,
) -> TelemetryEvent:
    started = boot_started_at or datetime(2026, 1, 1, tzinfo=UTC)
    timestamp = occurred_at or started + timedelta(seconds=sequence * 10)
    return TelemetryEvent(
        schema_version="1.0",
        message_id=message_id or uuid4(),
        message_type=MessageType.TELEMETRY_REPORTED,
        occurred_at=timestamp,
        sent_at=timestamp,
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


def identity(telemetry: TelemetryEvent) -> DeviceIdentity:
    return DeviceIdentity(telemetry.tenant_id, telemetry.charger_id)


def topic(telemetry: TelemetryEvent) -> str:
    return TelemetryTopic.for_device(telemetry.tenant_id, telemetry.charger_id)


def service() -> tuple[TelemetryIngestionService, InMemoryTelemetryRepository]:
    repository = InMemoryTelemetryRepository()
    return TelemetryIngestionService(repository, lambda: SERVER_TIME), repository


async def ingest(service: TelemetryIngestionService, telemetry: TelemetryEvent):  # type: ignore[no-untyped-def]
    return await service.ingest(identity(telemetry), topic(telemetry), telemetry.canonical_json())


@pytest.mark.asyncio
async def test_ingestion_accepts_new_event_and_creates_archive_outbox() -> None:
    ingestion, repository = service()
    telemetry = event()

    result = await ingest(ingestion, telemetry)

    assert result.accepted is True
    assert result.duplicate is False
    assert result.latest_updated is True
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == result.telemetry
    assert await repository.list_archive_pending(10) == [result.telemetry]


@pytest.mark.asyncio
async def test_duplicate_does_not_create_another_event_or_outbox_record() -> None:
    ingestion, repository = service()
    telemetry = event()

    first, duplicate = await asyncio.gather(
        ingest(ingestion, telemetry),
        ingest(ingestion, telemetry),
    )

    assert sum(result.accepted for result in (first, duplicate)) == 1
    assert sum(result.duplicate for result in (first, duplicate)) == 1
    assert len(await repository.list_archive_pending(10)) == 1


@pytest.mark.asyncio
async def test_message_id_reuse_with_other_content_is_rejected() -> None:
    ingestion, _ = service()
    message_id = uuid4()
    original = event(message_id=message_id, power_w=7_200)
    conflict = event(message_id=message_id, power_w=22_000)

    await ingest(ingestion, original)

    with pytest.raises(MessageIdentityConflictError):
        await ingest(ingestion, conflict)


@pytest.mark.asyncio
async def test_boot_sequence_reuse_with_other_message_id_is_rejected() -> None:
    ingestion, _ = service()
    original = event(sequence=3)
    conflict = event(sequence=3)

    await ingest(ingestion, original)

    with pytest.raises(SequenceIdentityConflictError):
        await ingest(ingestion, conflict)


@pytest.mark.asyncio
async def test_authenticated_identity_topic_and_payload_must_all_match() -> None:
    ingestion, _ = service()
    telemetry = event(tenant_id=TENANT_B)
    trusted_topic = TelemetryTopic.for_device(TENANT_A, telemetry.charger_id)

    with pytest.raises(TopicIdentityMismatchError):
        await ingestion.ingest(identity(telemetry), trusted_topic, telemetry.canonical_json())

    with pytest.raises(TopicIdentityMismatchError):
        await ingestion.ingest(
            DeviceIdentity(TENANT_A, telemetry.charger_id),
            topic(telemetry),
            telemetry.canonical_json(),
        )


@pytest.mark.asyncio
async def test_sequence_orders_one_boot_even_if_device_clock_moves_backward() -> None:
    ingestion, repository = service()
    first = event(sequence=1, occurred_at=datetime(2026, 1, 1, 0, 0, 20, tzinfo=UTC))
    second = event(sequence=2, occurred_at=datetime(2026, 1, 1, 0, 0, 15, tzinfo=UTC))

    await ingest(ingestion, first)
    latest = await ingest(ingestion, second)

    assert latest.latest_updated is True
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == latest.telemetry


@pytest.mark.asyncio
async def test_newer_boot_wins_and_delayed_old_boot_cannot_replace_it() -> None:
    ingestion, repository = service()
    old_boot = event(
        boot_id=BOOT_A,
        boot_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sequence=100,
        occurred_at=datetime(2026, 1, 1, 0, 0, 20, tzinfo=UTC),
    )
    new_boot = event(
        boot_id=BOOT_B,
        boot_started_at=datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC),
        sequence=0,
        occurred_at=datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC),
    )
    delayed_old = event(
        boot_id=BOOT_A,
        boot_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sequence=101,
        occurred_at=datetime(2026, 1, 1, 0, 0, 50, tzinfo=UTC),
    )

    await ingest(ingestion, old_boot)
    new_result = await ingest(ingestion, new_boot)
    delayed_result = await ingest(ingestion, delayed_old)

    assert new_result.latest_updated is True
    assert delayed_result.latest_updated is False
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == new_result.telemetry


@pytest.mark.asyncio
async def test_future_device_clock_is_rejected_without_pinning_latest_state() -> None:
    ingestion, repository = service()
    future = event(
        boot_started_at=SERVER_TIME + timedelta(minutes=6),
        occurred_at=SERVER_TIME + timedelta(minutes=6),
    )

    with pytest.raises(TelemetryClockSkewError):
        await ingest(ingestion, future)

    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) is None


@pytest.mark.asyncio
async def test_connectors_keep_independent_latest_state() -> None:
    ingestion, repository = service()
    connector_one = event(connector_id=1, sequence=1)
    connector_two = event(connector_id=2, sequence=9)

    one = await ingest(ingestion, connector_one)
    two = await ingest(ingestion, connector_two)

    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 1) == one.telemetry
    assert await repository.latest_for_connector(TENANT_A, CHARGER_A, 2) == two.telemetry


@pytest.mark.asyncio
async def test_latest_listing_never_crosses_tenant_boundary() -> None:
    ingestion, repository = service()
    await ingest(ingestion, event(tenant_id=TENANT_A))
    await ingest(ingestion, event(tenant_id=TENANT_B))

    tenant_a_items = await repository.list_latest_for_tenant(TENANT_A)

    assert [item.event.tenant_id for item in tenant_a_items] == [TENANT_A]


@pytest.mark.asyncio
async def test_server_clock_must_be_timezone_aware() -> None:
    repository = InMemoryTelemetryRepository()
    ingestion = TelemetryIngestionService(repository, lambda: datetime(2026, 1, 1))
    telemetry = event()

    with pytest.raises(ValueError, match="server clock"):
        await ingest(ingestion, telemetry)


def test_stored_telemetry_is_immutable() -> None:
    telemetry = event()
    stored = StoredTelemetry(
        event=telemetry,
        topic=topic(telemetry),
        received_at=SERVER_TIME,
        fingerprint=telemetry.semantic_fingerprint(),
    )

    with pytest.raises(FrozenInstanceError):
        stored.received_at = datetime(2027, 1, 1, tzinfo=UTC)  # type: ignore[misc]
