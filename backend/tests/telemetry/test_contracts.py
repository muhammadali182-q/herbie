"""Versioned telemetry wire-contract tests."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.errors import InvalidTopicError
from herbie.telemetry.topic import TelemetryTopic


def valid_event(**overrides: object) -> TelemetryEvent:
    values: dict[str, object] = {
        "schema_version": "1.0",
        "message_id": uuid4(),
        "message_type": MessageType.TELEMETRY_REPORTED,
        "occurred_at": datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        "sent_at": datetime(2026, 1, 1, 0, 0, 11, tzinfo=UTC),
        "boot_id": uuid4(),
        "boot_started_at": datetime(2026, 1, 1, tzinfo=UTC),
        "sequence": 1,
        "tenant_id": uuid4(),
        "charger_id": uuid4(),
        "connector_id": 1,
        "payload": TelemetryPayload(
            cumulative_energy_wh=42,
            power_w=7_200,
            status=ChargerStatus.CHARGING,
        ),
    }
    values.update(overrides)
    return TelemetryEvent.model_validate(values)


def test_contract_round_trips_stable_canonical_json_and_fingerprint() -> None:
    event = valid_event()

    restored = TelemetryEvent.from_json(event.canonical_json())

    assert restored == event
    assert restored.canonical_json() == event.canonical_json()
    assert restored.semantic_fingerprint() == event.semantic_fingerprint()
    assert len(event.semantic_fingerprint()) == 64


@pytest.mark.parametrize("field", ["occurred_at", "sent_at", "boot_started_at"])
def test_contract_rejects_naive_timestamps(field: str) -> None:
    with pytest.raises(ValidationError, match="timezone offset"):
        valid_event(**{field: datetime(2026, 1, 1)})


def test_wire_contract_rejects_numeric_timestamp() -> None:
    wire = json.loads(valid_event().canonical_json())
    wire["occurred_at"] = 1_767_225_600

    with pytest.raises(ValidationError, match="RFC 3339 text"):
        TelemetryEvent.from_json(json.dumps(wire))


@pytest.mark.parametrize("bad_value", [True, "7200", 7200.0])
def test_wire_contract_rejects_coerced_integer_measurements(bad_value: object) -> None:
    wire = json.loads(valid_event().canonical_json())
    wire["payload"]["power_w"] = bad_value

    with pytest.raises(ValidationError):
        TelemetryEvent.from_json(json.dumps(wire))


def test_wire_contract_rejects_noncanonical_uuid() -> None:
    wire = json.loads(valid_event().canonical_json())
    wire["message_id"] = wire["message_id"].upper()

    with pytest.raises(ValidationError, match="canonical lowercase"):
        TelemetryEvent.from_json(json.dumps(wire))


def test_timestamps_are_normalized_to_utc() -> None:
    event = valid_event(
        boot_started_at="2026-01-01T05:00:00+05:00",
        occurred_at="2026-01-01T05:00:10+05:00",
        sent_at="2026-01-01T05:00:11+05:00",
    )

    assert event.boot_started_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert event.occurred_at == datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "boot_started_at": datetime(2026, 1, 1, 0, 0, 20, tzinfo=UTC),
            "occurred_at": datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        },
        {
            "occurred_at": datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
            "sent_at": datetime(2026, 1, 1, 0, 0, 9, tzinfo=UTC),
        },
    ],
)
def test_contract_rejects_impossible_temporal_order(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        valid_event(**overrides)


def test_payload_rejects_negative_or_implausible_measurements() -> None:
    with pytest.raises(ValidationError):
        TelemetryPayload(
            cumulative_energy_wh=-1,
            power_w=1_000_001,
            status=ChargerStatus.CHARGING,
        )


def test_contract_rejects_sequence_outside_signed_64_bit_range() -> None:
    with pytest.raises(ValidationError):
        valid_event(sequence=2**63)


def test_topic_round_trips_device_identity() -> None:
    tenant_id = UUID("11111111-1111-1111-1111-111111111111")
    charger_id = UUID("22222222-2222-2222-2222-222222222222")

    topic = TelemetryTopic.for_device(tenant_id, charger_id)

    assert TelemetryTopic.parse(topic) == TelemetryTopic(tenant_id, charger_id)


@pytest.mark.parametrize(
    "topic",
    [
        "herbie/v2/tenants/a/chargers/b/up/telemetry",
        "herbie/v1/tenants/not-a-uuid/chargers/not-a-uuid/up/telemetry",
        "herbie/v1/tenants/11111111111111111111111111111111/chargers/"
        "22222222-2222-2222-2222-222222222222/up/telemetry",
        "herbie/v1/tenants/11111111-1111-1111-1111-111111111111/up/telemetry",
        "herbie/v1/tenants/11111111-1111-1111-1111-111111111111/chargers/"
        "22222222-2222-2222-2222-222222222222/down/telemetry",
    ],
)
def test_topic_rejects_invalid_routes(topic: str) -> None:
    with pytest.raises(InvalidTopicError):
        TelemetryTopic.parse(topic)
