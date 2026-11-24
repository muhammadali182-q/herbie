"""Worker lifecycle tests."""

import asyncio

import pytest

from herbie import worker
from herbie.worker import serve


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


def test_worker_console_runner_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def fake_serve(stop_event: asyncio.Event | None = None) -> None:
        nonlocal called
        assert stop_event is None
        called = True

    monkeypatch.setattr(worker, "serve", fake_serve)

    worker.run()

    assert called is True
