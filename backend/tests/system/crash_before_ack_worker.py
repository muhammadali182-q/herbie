"""System-test worker that exits after DynamoDB commit and before broker ACK."""

import asyncio
import os

import aio_pika
import boto3
from aio_pika.abc import AbstractIncomingMessage

from herbie.config import Settings
from herbie.telemetry.dynamodb import DynamoTelemetryRepository, ensure_telemetry_table
from herbie.telemetry.rabbitmq import declare_messaging_topology, mqtt_topic_from_routing_key
from herbie.telemetry.registry import StaticDeviceRegistry
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import TelemetryTopic


async def main() -> None:
    """Consume once, commit, and terminate without settling the delivery."""

    settings = Settings(_env_file=None)
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=settings.dynamodb_endpoint,
        region_name=settings.dynamodb_region,
    )
    ensure_telemetry_table(dynamodb, settings.dynamodb_telemetry_table)
    repository = DynamoTelemetryRepository(
        dynamodb,
        settings.dynamodb_telemetry_table,
        settings.telemetry_event_retention_days,
        settings.telemetry_replay_retention_days,
    )
    service = TelemetryIngestionService(repository)
    registry = StaticDeviceRegistry.from_entries(settings.registered_devices)
    connection = await aio_pika.connect_robust(settings.amqp_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    topology = await declare_messaging_topology(channel, settings.telemetry_retry_delay_ms)

    async def consume(message: AbstractIncomingMessage) -> None:
        if message.routing_key is None:
            await message.reject(requeue=False)
            return
        topic = mqtt_topic_from_routing_key(message.routing_key)
        route = TelemetryTopic.parse(topic)
        identity = await registry.resolve(route)
        if identity is None:
            await message.reject(requeue=False)
            return
        await service.ingest(identity, topic, message.body)
        print("COMMITTED_BEFORE_ACK", flush=True)
        os._exit(23)

    await topology.telemetry_queue.consume(consume, no_ack=False)
    print("CRASH_WORKER_READY", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
