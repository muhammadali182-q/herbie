"""Versioned telemetry contract tests."""

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
        "occurred_at": datetime(2026, 1, 1, tzinfo=UTC),
        "sent_at": datetime(2026, 1, 1, tzinfo=UTC),
        "boot_id": uuid4(),
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


def test_contract_round_trips_canonical_json() -> None:
    event = valid_event()

    restored = TelemetryEvent.from_json(event.canonical_json())

    assert restored == event


@pytest.mark.parametrize("field", ["occurred_at", "sent_at"])
def test_contract_rejects_naive_timestamps(field: str) -> None:
    with pytest.raises(ValidationError, match="timezone offset"):
        valid_event(**{field: datetime(2026, 1, 1)})


def test_payload_rejects_negative_measurements() -> None:
    with pytest.raises(ValidationError):
        TelemetryPayload(
            cumulative_energy_wh=-1,
            power_w=1,
            status=ChargerStatus.CHARGING,
        )


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
