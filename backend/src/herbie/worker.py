"""Asynchronous worker process entry point."""

import asyncio
import signal
from contextlib import suppress

import structlog

from herbie import __version__
from herbie.config import get_settings
from herbie.logging import configure_logging


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
    """Run until the process receives a shutdown signal.

    Message consumers are attached in the telemetry vertical slice. Keeping a
    real process lifecycle here makes container and signal behavior testable
    before a broker adapter is introduced.
    """

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
        version=__version__,
    )
    await stopped.wait()
    logger.info("worker_stopped")


def run() -> None:
    """Run the worker process."""

    with suppress(KeyboardInterrupt):
        asyncio.run(serve())


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
