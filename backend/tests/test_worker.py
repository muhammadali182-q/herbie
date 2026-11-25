"""Worker lifecycle tests."""

import asyncio
from typing import Literal, cast
from unittest.mock import MagicMock

import pytest

from herbie import worker
from herbie.config import Settings
from herbie.worker import install_signal_handlers, serve


@pytest.mark.asyncio
async def test_worker_stops_when_requested() -> None:
    stop_event = asyncio.Event()
    stop_event.set()

    await asyncio.wait_for(serve(stop_event), timeout=1)


@pytest.mark.asyncio
async def test_worker_installs_signal_handlers_for_process_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_event = asyncio.Event()
    stop_event.set()
    monkeypatch.setattr(asyncio, "Event", lambda: stop_event)

    await asyncio.wait_for(serve(), timeout=1)


def test_signal_handler_registration_is_observable() -> None:
    loop = cast(asyncio.AbstractEventLoop, MagicMock(spec=asyncio.AbstractEventLoop))
    stop_event = asyncio.Event()

    installed = install_signal_handlers(loop, stop_event)

    assert installed == 2
    assert cast(MagicMock, loop.add_signal_handler).call_count == 2


def test_worker_console_runner_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def fake_serve(stop_event: asyncio.Event | None = None) -> None:
        nonlocal called
        assert stop_event is None
        called = True

    monkeypatch.setattr(worker, "serve", fake_serve)

    worker.run()

    assert called is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "expected"),
    [("telemetry", "telemetry"), ("archive", "archive")],
)
async def test_worker_dispatches_configured_role(
    monkeypatch: pytest.MonkeyPatch,
    role: Literal["telemetry", "archive"],
    expected: str,
) -> None:
    called: list[str] = []
    stopped = asyncio.Event()

    async def fake_telemetry(settings: Settings, event: asyncio.Event) -> None:
        assert settings.worker_role == role
        assert event is stopped
        called.append("telemetry")

    async def fake_archive(settings: Settings, event: asyncio.Event) -> None:
        assert settings.worker_role == role
        assert event is stopped
        called.append("archive")

    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: Settings(worker_role=role, _env_file=None),
    )
    monkeypatch.setattr(worker, "run_telemetry_worker", fake_telemetry)
    monkeypatch.setattr(worker, "run_archive_worker", fake_archive)

    await serve(stopped)

    assert called == [expected]
