"""Simulator CLI tests."""

import pytest

from herbie_simulator import cli
from herbie_simulator.cli import main
from herbie_simulator.mqtt import PublishSummary


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


def test_mqtt_mode_requires_password_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("HERBIE_SIMULATOR_MQTT_PASSWORD", raising=False)

    result = main(["--mqtt", "--tenants", "1", "--chargers-per-tenant", "1"])

    assert result == 2
    assert "password environment variable" in capsys.readouterr().err


def test_mqtt_mode_reports_pubacks_separately_from_durable_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HERBIE_SIMULATOR_MQTT_PASSWORD", "test-only")
    publish = lambda *args, **kwargs: PublishSummary(  # noqa: E731
        represented_devices=1,
        connected_clients=1,
        offered_messages=2,
        pubacknowledged_messages=2,
        failed_messages=0,
        elapsed_seconds=0.125,
    )
    monkeypatch.setattr(cli, "publish_scenario", publish)

    result = main(
        [
            "--mqtt",
            "--tenants",
            "1",
            "--chargers-per-tenant",
            "1",
            "--rounds",
            "2",
            "--reporting-mode",
            "synchronized",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "offered=2 pubacknowledged=2" in output
    assert "durable_ingestion=not_measured" in output


def test_mqtt_and_summary_modes_are_mutually_exclusive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HERBIE_SIMULATOR_MQTT_PASSWORD", "test-only")

    assert main(["--mqtt", "--summary"]) == 2
    assert "cannot be combined" in capsys.readouterr().err
