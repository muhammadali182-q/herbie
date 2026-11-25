"""Runtime composition for telemetry and archive worker process roles."""

import asyncio
from contextlib import suppress
from datetime import timedelta
from typing import Any

import boto3
import structlog
from botocore.config import Config

from herbie.config import Settings
from herbie.telemetry.archive import TelemetryArchiveService
from herbie.telemetry.dynamodb import DynamoTelemetryRepository, ensure_telemetry_table
from herbie.telemetry.rabbitmq import RabbitTelemetryConsumer
from herbie.telemetry.registry import StaticDeviceRegistry
from herbie.telemetry.s3 import S3TelemetryArchiveSink, ensure_archive_bucket
from herbie.telemetry.service import TelemetryIngestionService


async def run_telemetry_worker(settings: Settings, stopped: asyncio.Event) -> None:
    """Consume broker deliveries and commit them to the hot telemetry store."""

    logger = structlog.get_logger("herbie.telemetry.runtime")
    dynamodb: Any = boto3.client(
        "dynamodb",
        endpoint_url=settings.dynamodb_endpoint,
        region_name=settings.dynamodb_region,
    )
    try:
        await asyncio.to_thread(
            ensure_telemetry_table,
            dynamodb,
            settings.dynamodb_telemetry_table,
        )
        logger.info(
            "telemetry_storage_ready",
            process_role="telemetry",
            table=settings.dynamodb_telemetry_table,
        )
        repository = DynamoTelemetryRepository(
            dynamodb,
            settings.dynamodb_telemetry_table,
            settings.telemetry_event_retention_days,
            settings.telemetry_replay_retention_days,
        )
        service = TelemetryIngestionService(
            repository,
            max_future_skew=timedelta(seconds=settings.telemetry_max_future_skew_seconds),
        )
        registry = StaticDeviceRegistry.from_entries(settings.registered_devices)
        consumer = RabbitTelemetryConsumer(
            settings.amqp_url,
            service,
            registry,
            prefetch=settings.amqp_prefetch,
            max_payload_bytes=settings.telemetry_max_payload_bytes,
            retry_limit=settings.telemetry_retry_limit,
            retry_delay_ms=settings.telemetry_retry_delay_ms,
            shutdown_timeout_seconds=settings.telemetry_shutdown_timeout_seconds,
        )
        await consumer.run(stopped)
    finally:
        dynamodb.close()


async def run_archive_worker(settings: Settings, stopped: asyncio.Event) -> None:
    """Flush the durable archive outbox through one configured scheduler."""

    logger = structlog.get_logger("herbie.telemetry.runtime")
    dynamodb: Any = boto3.client(
        "dynamodb",
        endpoint_url=settings.dynamodb_endpoint,
        region_name=settings.dynamodb_region,
    )
    s3_config = Config(s3={"addressing_style": "path"}) if settings.s3_endpoint else None
    s3: Any = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        config=s3_config,
    )
    try:
        await asyncio.to_thread(
            ensure_telemetry_table,
            dynamodb,
            settings.dynamodb_telemetry_table,
        )
        await asyncio.to_thread(
            ensure_archive_bucket,
            s3,
            settings.s3_bucket,
            settings.s3_region,
            settings.s3_allow_unsupported_public_access_block,
        )
        logger.info(
            "archive_storage_ready",
            process_role="archive",
            table=settings.dynamodb_telemetry_table,
            bucket=settings.s3_bucket,
        )
        repository = DynamoTelemetryRepository(
            dynamodb,
            settings.dynamodb_telemetry_table,
            settings.telemetry_event_retention_days,
            settings.telemetry_replay_retention_days,
        )
        sink = S3TelemetryArchiveSink(
            s3,
            settings.s3_bucket,
            settings.s3_kms_key_id,
            encrypt=not settings.s3_allow_unencrypted_objects,
        )
        archive = TelemetryArchiveService(repository, sink)
        await _run_archive_loop(archive, settings, stopped)
    finally:
        s3.close()
        dynamodb.close()


async def _run_archive_loop(
    archive: TelemetryArchiveService,
    settings: Settings,
    stopped: asyncio.Event,
) -> None:
    logger = structlog.get_logger("herbie.telemetry.archive_worker")
    while not stopped.is_set():
        try:
            result = await archive.flush(settings.archive_batch_limit)
            if result.events_archived:
                logger.info(
                    "telemetry_archive_flushed",
                    events_archived=result.events_archived,
                    objects_written=result.objects_written,
                )
        except Exception as error:
            logger.exception(
                "telemetry_archive_flush_failed",
                error_type=type(error).__name__,
            )
        with suppress(TimeoutError):
            await asyncio.wait_for(
                stopped.wait(),
                timeout=settings.archive_flush_interval_seconds,
            )
