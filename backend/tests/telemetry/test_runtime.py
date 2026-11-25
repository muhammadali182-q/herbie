"""Telemetry worker runtime-composition tests."""

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from herbie.config import Settings
from herbie.telemetry import runtime
from herbie.telemetry.archive import ArchiveFlushResult, TelemetryArchiveService


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_telemetry_runtime_bootstraps_storage_and_runs_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dynamodb = FakeClient()
    ensure_table = MagicMock()
    repository = MagicMock()
    service = MagicMock()
    registry = MagicMock()
    consumer = SimpleNamespace(run=AsyncMock())
    consumer_factory = MagicMock(return_value=consumer)
    settings = Settings(
        registered_devices=(
            "11111111-1111-1111-1111-111111111111/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ),
        _env_file=None,
    )
    stopped = asyncio.Event()

    monkeypatch.setattr(
        "herbie.telemetry.runtime.boto3.client",
        lambda *args, **kwargs: dynamodb,
    )
    monkeypatch.setattr(runtime, "ensure_telemetry_table", ensure_table)
    monkeypatch.setattr(runtime, "DynamoTelemetryRepository", MagicMock(return_value=repository))
    monkeypatch.setattr(runtime, "TelemetryIngestionService", MagicMock(return_value=service))
    registry_factory = MagicMock(return_value=registry)
    monkeypatch.setattr(
        "herbie.telemetry.runtime.StaticDeviceRegistry.from_entries",
        registry_factory,
    )
    monkeypatch.setattr(runtime, "RabbitTelemetryConsumer", consumer_factory)

    await runtime.run_telemetry_worker(settings, stopped)

    ensure_table.assert_called_once_with(dynamodb, settings.dynamodb_telemetry_table)
    registry_factory.assert_called_once_with(settings.registered_devices)
    consumer.run.assert_awaited_once_with(stopped)
    assert consumer_factory.call_args.kwargs["prefetch"] == 100
    assert dynamodb.closed is True


@pytest.mark.asyncio
async def test_archive_runtime_bootstraps_both_stores_and_closes_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dynamodb = FakeClient()
    s3 = FakeClient()
    clients = iter([dynamodb, s3])
    ensure_table = MagicMock()
    ensure_bucket = MagicMock()
    archive = MagicMock()
    run_loop = AsyncMock()
    settings = Settings(worker_role="archive", _env_file=None)
    stopped = asyncio.Event()

    monkeypatch.setattr(
        "herbie.telemetry.runtime.boto3.client",
        lambda *args, **kwargs: next(clients),
    )
    monkeypatch.setattr(runtime, "ensure_telemetry_table", ensure_table)
    monkeypatch.setattr(runtime, "ensure_archive_bucket", ensure_bucket)
    monkeypatch.setattr(runtime, "DynamoTelemetryRepository", MagicMock())
    monkeypatch.setattr(runtime, "S3TelemetryArchiveSink", MagicMock())
    monkeypatch.setattr(runtime, "TelemetryArchiveService", MagicMock(return_value=archive))
    monkeypatch.setattr(runtime, "_run_archive_loop", run_loop)

    await runtime.run_archive_worker(settings, stopped)

    ensure_table.assert_called_once_with(dynamodb, settings.dynamodb_telemetry_table)
    ensure_bucket.assert_called_once_with(s3, settings.s3_bucket, settings.s3_region)
    run_loop.assert_awaited_once_with(archive, settings, stopped)
    assert dynamodb.closed is True
    assert s3.closed is True


class FakeArchive:
    def __init__(self, stopped: asyncio.Event, error: Exception | None = None) -> None:
        self.stopped = stopped
        self.error = error
        self.calls: list[int] = []

    async def flush(self, limit: int) -> ArchiveFlushResult:
        self.calls.append(limit)
        self.stopped.set()
        if self.error is not None:
            raise self.error
        return ArchiveFlushResult(events_archived=2, objects_written=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [None, RuntimeError("archive unavailable")])
async def test_archive_loop_reports_success_and_survives_failure(
    error: Exception | None,
) -> None:
    stopped = asyncio.Event()
    archive = FakeArchive(stopped, error)
    settings = Settings(worker_role="archive", archive_batch_limit=25, _env_file=None)

    await runtime._run_archive_loop(
        cast(TelemetryArchiveService, archive),
        settings,
        stopped,
    )

    assert archive.calls == [25]
