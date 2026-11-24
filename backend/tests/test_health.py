"""API foundation tests."""

import pytest
from fastapi.testclient import TestClient

from herbie.config import Settings
from herbie import main
from herbie.main import create_app


def test_liveness_identifies_the_running_service() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
        "environment": "test",
    }


def test_readiness_is_explicit_about_foundation_state() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_metadata_declares_protocol_and_phase() -> None:
    app = create_app(Settings(environment="test", _env_file=None))

    with TestClient(app) as client:
        response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "name": "H.E.R.B.I.E.",
        "version": "0.1.0",
        "protocol": "simplified-mqtt-v1",
        "phase": "foundation",
    }


def test_console_runner_uses_typed_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured.update(kwargs)

    settings = Settings(api_host="0.0.0.0", api_port=9123, _env_file=None)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    monkeypatch.setattr(main.uvicorn, "run", fake_run)

    main.run()

    assert captured["args"] == ("herbie.main:app",)
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9123
    assert captured["log_config"] is None
