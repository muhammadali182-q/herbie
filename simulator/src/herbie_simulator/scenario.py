"""Pure deterministic scenario generation for reproducible tests and demos."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.topic import TelemetryTopic


@dataclass(frozen=True, slots=True)
class Scenario:
    """A bounded synthetic workload specification."""

    tenants: int = 3
    chargers_per_tenant: int = 4
    rounds: int = 3
    interval_seconds: int = 10
    seed: str = "herbie-demo-v1"
    starts_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)

    def __post_init__(self) -> None:
        positive_fields = {
            "tenants": self.tenants,
            "chargers_per_tenant": self.chargers_per_tenant,
            "rounds": self.rounds,
            "interval_seconds": self.interval_seconds,
        }
        for name, value in positive_fields.items():
            if value < 1:
                raise ValueError(f"{name} must be at least one")
        if self.starts_at.tzinfo is None or self.starts_at.utcoffset() is None:
            raise ValueError("starts_at must include a timezone offset")


@dataclass(frozen=True, slots=True)
class SimulatedPublication:
    """One protocol-valid topic and payload pair."""

    topic: str
    event: TelemetryEvent


def generate_scenario(scenario: Scenario) -> Iterator[SimulatedPublication]:
    """Yield events in deterministic round-robin tenant/device order."""

    scenario_namespace = uuid5(NAMESPACE_URL, f"herbie:{scenario.seed}")
    devices = list(_devices(scenario, scenario_namespace))

    for round_index in range(scenario.rounds):
        occurred_at = scenario.starts_at + timedelta(
            seconds=round_index * scenario.interval_seconds
        )
        for tenant_index, charger_index, tenant_id, charger_id, boot_id in devices:
            power_w = 7_000 + ((tenant_index * 1_307 + charger_index * 911) % 15_000)
            energy_increment_wh = power_w * scenario.interval_seconds // 3_600
            cumulative_energy_wh = (round_index + 1) * energy_increment_wh
            message_id = uuid5(boot_id, f"telemetry:{round_index}")
            event = TelemetryEvent(
                schema_version="1.0",
                message_id=message_id,
                message_type=MessageType.TELEMETRY_REPORTED,
                occurred_at=occurred_at,
                sent_at=occurred_at + timedelta(milliseconds=25 + charger_index),
                boot_id=boot_id,
                sequence=round_index,
                tenant_id=tenant_id,
                charger_id=charger_id,
                connector_id=1,
                payload=TelemetryPayload(
                    cumulative_energy_wh=cumulative_energy_wh,
                    power_w=power_w,
                    status=ChargerStatus.CHARGING,
                    voltage_v=230,
                    current_ma=power_w * 1_000 // 230,
                ),
            )
            yield SimulatedPublication(
                topic=TelemetryTopic.for_device(tenant_id, charger_id),
                event=event,
            )


def _devices(
    scenario: Scenario,
    namespace: UUID,
) -> Iterator[tuple[int, int, UUID, UUID, UUID]]:
    for tenant_index in range(scenario.tenants):
        tenant_id = uuid5(namespace, f"tenant:{tenant_index}")
        for charger_index in range(scenario.chargers_per_tenant):
            charger_id = uuid5(tenant_id, f"charger:{charger_index}")
            boot_id = uuid5(charger_id, "boot:0")
            yield tenant_index, charger_index, tenant_id, charger_id, boot_id
