"""Configuration contract tests."""

import pytest
from pydantic import ValidationError

from herbie.config import Settings


def test_settings_use_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "local"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert "localhost" in settings.database_url
    assert settings.amqp_prefetch == 100
    assert settings.telemetry_max_payload_bytes == 65_536
    assert settings.registered_devices == ()
    assert settings.worker_role == "telemetry"


def test_environment_values_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERBIE_ENVIRONMENT", "test")
    monkeypatch.setenv("HERBIE_API_PORT", "8123")

    settings = Settings(_env_file=None)

    assert settings.environment == "test"
    assert settings.api_port == 8123


def test_settings_are_immutable() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValidationError):
        setattr(settings, "api_port", 9000)  # noqa: B010 - exercise frozen runtime behavior


def test_replay_retention_must_exceed_event_retention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERBIE_TELEMETRY_EVENT_RETENTION_DAYS", "365")
    monkeypatch.setenv("HERBIE_TELEMETRY_REPLAY_RETENTION_DAYS", "180")

    with pytest.raises(ValidationError, match="must exceed"):
        Settings(_env_file=None)


def test_registered_devices_require_tenant_and_charger_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERBIE_REGISTERED_DEVICES", '["not-a-device"]')

    with pytest.raises(ValidationError, match="registered devices"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("HERBIE_AMQP_PREFETCH", "0"),
        ("HERBIE_TELEMETRY_MAX_PAYLOAD_BYTES", "100"),
        ("HERBIE_TELEMETRY_RETRY_LIMIT", "21"),
        ("HERBIE_ARCHIVE_BATCH_LIMIT", "0"),
        ("HERBIE_WORKER_ROLE", "both"),
    ],
)
def test_worker_setting_bounds_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
