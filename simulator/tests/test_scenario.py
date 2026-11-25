"""Deterministic simulator scenario tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from herbie_simulator.scenario import Scenario, generate_scenario


def test_scenario_is_deterministic_and_balanced() -> None:
    scenario = Scenario(tenants=3, chargers_per_tenant=2, rounds=4, seed="repeatable")

    first = list(generate_scenario(scenario))
    second = list(generate_scenario(scenario))

    assert first == second
    assert len(first) == 24
    assert len({item.event.tenant_id for item in first}) == 3
    assert len({item.event.charger_id for item in first}) == 6
    assert len({item.event.message_id for item in first}) == 24


def test_each_chargers_meter_and_sequence_are_monotonic() -> None:
    publications = list(generate_scenario(Scenario(chargers_per_tenant=2, rounds=5)))
    chargers = {item.event.charger_id for item in publications}

    for charger_id in chargers:
        events = [item.event for item in publications if item.event.charger_id == charger_id]
        assert [event.sequence for event in events] == list(range(5))
        energies = [event.payload.cumulative_energy_wh for event in events]
        assert energies == sorted(energies)
        assert len(set(energies)) == 5


def test_energy_uses_total_elapsed_time_without_per_round_truncation() -> None:
    events = list(
        generate_scenario(Scenario(tenants=1, chargers_per_tenant=1, rounds=3, interval_seconds=10))
    )

    assert [item.event.payload.power_w for item in events] == [7_000, 7_000, 7_000]
    assert [item.event.payload.cumulative_energy_wh for item in events] == [19, 38, 58]


def test_content_shaping_configuration_changes_message_identity() -> None:
    baseline = next(generate_scenario(Scenario(interval_seconds=10)))
    changed_interval = next(generate_scenario(Scenario(interval_seconds=11)))
    changed_start = next(generate_scenario(Scenario(starts_at=datetime(2026, 1, 2, tzinfo=UTC))))

    assert (
        len(
            {
                baseline.event.message_id,
                changed_interval.event.message_id,
                changed_start.event.message_id,
            }
        )
        == 3
    )


def test_device_order_interleaves_tenants_per_charger_slot() -> None:
    events = list(generate_scenario(Scenario(tenants=3, chargers_per_tenant=2, rounds=1)))

    assert len({item.event.tenant_id for item in events[:3]}) == 3
    assert len({item.event.tenant_id for item in events[3:6]}) == 3


@pytest.mark.parametrize(
    ("field", "factory"),
    [
        ("tenants", lambda: Scenario(tenants=0)),
        ("chargers_per_tenant", lambda: Scenario(chargers_per_tenant=0)),
        ("rounds", lambda: Scenario(rounds=0)),
        ("interval_seconds", lambda: Scenario(interval_seconds=0)),
        ("tenants", lambda: Scenario(tenants=True)),
    ],
)
def test_scenario_rejects_unbounded_zero_dimensions(
    field: str,
    factory: Callable[[], Scenario],
) -> None:
    with pytest.raises(ValueError, match=field):
        factory()


def test_scenario_requires_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        Scenario(starts_at=datetime(2026, 1, 1))


def test_scenario_rejects_empty_seed_and_excessive_event_count() -> None:
    with pytest.raises(ValueError, match="seed"):
        Scenario(seed=" ")
    with pytest.raises(ValueError, match="cannot exceed"):
        Scenario(tenants=2_000, chargers_per_tenant=2_000, rounds=1)


def test_scenario_accepts_explicit_utc_start() -> None:
    scenario = Scenario(starts_at=datetime(2026, 2, 1, tzinfo=UTC))

    first = next(generate_scenario(scenario))

    assert first.event.boot_started_at == datetime(2026, 2, 1, tzinfo=UTC)
    assert first.event.occurred_at == datetime(2026, 2, 1, tzinfo=UTC) + timedelta(seconds=10)
