"""Deterministic simulator scenario tests."""

from collections.abc import Callable
from datetime import UTC, datetime

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


@pytest.mark.parametrize(
    ("field", "factory"),
    [
        ("tenants", lambda: Scenario(tenants=0)),
        ("chargers_per_tenant", lambda: Scenario(chargers_per_tenant=0)),
        ("rounds", lambda: Scenario(rounds=0)),
        ("interval_seconds", lambda: Scenario(interval_seconds=0)),
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


def test_scenario_accepts_explicit_utc_start() -> None:
    scenario = Scenario(starts_at=datetime(2026, 2, 1, tzinfo=UTC))

    first = next(generate_scenario(scenario))

    assert first.event.occurred_at == datetime(2026, 2, 1, tzinfo=UTC)
