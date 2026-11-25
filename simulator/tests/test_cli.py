"""Simulator CLI tests."""

import pytest

from herbie_simulator.cli import main


def test_summary_reports_bounded_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(
        [
            "--tenants",
            "3",
            "--chargers-per-tenant",
            "2",
            "--rounds",
            "4",
            "--summary",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert output.strip() == "tenants=3 chargers=6 events=24 interval_seconds=10"


def test_invalid_scenario_has_nonzero_exit(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--tenants", "0"])

    error = capsys.readouterr().err
    assert result == 2
    assert "tenants must be at least one" in error


def test_default_output_contains_payload_and_topic(capsys: pytest.CaptureFixture[str]) -> None:
    result = main(["--tenants", "1", "--chargers-per-tenant", "1", "--rounds", "1"])

    output = capsys.readouterr().out
    assert result == 0
    assert '"schema_version":"1.0"' in output
    assert "\therbie/v1/tenants/" in output
