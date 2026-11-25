"""Asynchronous worker process entry point."""

import asyncio
import signal
from contextlib import suppress

import structlog

from herbie import __version__
from herbie.config import get_settings
from herbie.logging import configure_logging
from herbie.telemetry.runtime import run_archive_worker, run_telemetry_worker


def install_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    stopped: asyncio.Event,
) -> int:
    """Install supported process shutdown handlers and return their count."""

    installed = 0
    for shutdown_signal in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(shutdown_signal, stopped.set)
            installed += 1
    return installed


async def serve(stop_event: asyncio.Event | None = None) -> None:
    """Run the configured worker role until a shutdown signal is received."""

    settings = get_settings()
    configure_logging(settings.log_level)
    logger = structlog.get_logger("herbie.worker")
    stopped = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()

    if stop_event is None:
        install_signal_handlers(loop, stopped)

    logger.info(
        "worker_started",
        environment=settings.environment,
        process_role=settings.worker_role,
        version=__version__,
    )
    try:
        if stopped.is_set():
            return
        if settings.worker_role == "archive":
            await run_archive_worker(settings, stopped)
        else:
            await run_telemetry_worker(settings, stopped)
    finally:
        logger.info("worker_stopped", process_role=settings.worker_role)


def run() -> None:
    """Run the worker process."""

    with suppress(KeyboardInterrupt):
        asyncio.run(serve())


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
