"""RabbitMQ topology and manual-ack telemetry consumption."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from contextlib import suppress
from enum import StrEnum
from typing import Any, Protocol, cast

import aio_pika
import structlog
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractExchange,
    AbstractIncomingMessage,
    AbstractQueue,
    AbstractRobustConnection,
)
from aio_pika.exceptions import AMQPException
from pydantic import ValidationError

from herbie.telemetry.errors import (
    BootIdentityConflictError,
    InvalidTopicError,
    MessageIdentityConflictError,
    SequenceIdentityConflictError,
    TelemetryClockSkewError,
    TelemetryError,
    TelemetryPayloadTooLargeError,
    TopicIdentityMismatchError,
    UnregisteredDeviceError,
)
from herbie.telemetry.registry import DeviceRegistry
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import TelemetryTopic

TELEMETRY_QUEUE = "herbie.telemetry.v1"
TELEMETRY_BINDING = "herbie.v1.tenants.*.chargers.*.up.telemetry"
CONTROL_QUEUE = "herbie.control.v1"
CONTROL_BINDING = "herbie.v1.tenants.*.chargers.*.up.control.#"
DEAD_LETTER_EXCHANGE = "herbie.dead-letter"
DEAD_LETTER_QUEUE = "herbie.telemetry.dead.v1"
RETRY_EXCHANGE = "herbie.telemetry.retry"
RETRY_QUEUE = "herbie.telemetry.retry.v1"


class MessageDisposition(StrEnum):
    """Observable terminal action for one broker delivery."""

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED_CONTRACT = "rejected_contract"
    REJECTED_IDENTITY = "rejected_identity"
    REJECTED_CLOCK = "rejected_clock"
    REJECTED_CONFLICT = "rejected_conflict"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTERED_STORAGE = "dead_lettered_storage"


class IncomingTelemetryMessage(Protocol):
    """Incoming-message behavior needed by the disposition policy."""

    body: bytes
    routing_key: str
    headers: Mapping[str, Any] | None
    content_type: str | None
    content_encoding: str | None
    correlation_id: str | None
    message_id: str | None

    async def ack(self, multiple: bool = False) -> None:
        """Acknowledge the durable broker delivery."""

    async def reject(self, requeue: bool = False) -> None:
        """Reject and optionally requeue the broker delivery."""


class RetryPublisher(Protocol):
    """Confirmed publication into the bounded-delay retry path."""

    async def publish(self, message: IncomingTelemetryMessage) -> None:
        """Republish before the original delivery is acknowledged."""


class TelemetryMessageHandler:
    """Apply deterministic broker dispositions around durable ingestion."""

    def __init__(
        self,
        service: TelemetryIngestionService,
        registry: DeviceRegistry,
        retry_publisher: RetryPublisher,
        *,
        max_payload_bytes: int,
        retry_limit: int,
        logger: Any | None = None,
    ) -> None:
        self._service = service
        self._registry = registry
        self._retry_publisher = retry_publisher
        self._max_payload_bytes = max_payload_bytes
        self._retry_limit = retry_limit
        self._logger = logger or structlog.get_logger("herbie.telemetry.consumer")

    async def handle(self, message: IncomingTelemetryMessage) -> MessageDisposition:
        """Process one delivery and settle it exactly once at the broker boundary."""

        try:
            if len(message.body) > self._max_payload_bytes:
                raise TelemetryPayloadTooLargeError("telemetry payload exceeds configured limit")
            topic = mqtt_topic_from_routing_key(message.routing_key)
            topic_identity = TelemetryTopic.parse(topic)
            identity = await self._registry.resolve(topic_identity)
            if identity is None:
                raise UnregisteredDeviceError("telemetry route is not registered")
            result = await self._service.ingest(identity, topic, message.body)
        except TelemetryPayloadTooLargeError as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_CONTRACT,
                "telemetry_contract_rejected",
                error,
            )
        except (InvalidTopicError, ValidationError) as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_CONTRACT,
                "telemetry_contract_rejected",
                error,
            )
        except (TopicIdentityMismatchError, UnregisteredDeviceError) as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_IDENTITY,
                "telemetry_identity_rejected",
                error,
                security_event=True,
            )
        except TelemetryClockSkewError as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_CLOCK,
                "telemetry_clock_rejected",
                error,
            )
        except (
            MessageIdentityConflictError,
            SequenceIdentityConflictError,
            BootIdentityConflictError,
        ) as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_CONFLICT,
                "telemetry_identity_conflict",
                error,
                high_severity=True,
            )
        except TelemetryError as error:
            return await self._reject(
                message,
                MessageDisposition.REJECTED_CONTRACT,
                "telemetry_rejected",
                error,
            )
        except Exception as error:
            return await self._retry_or_dead_letter(message, error)

        await message.ack()
        disposition = (
            MessageDisposition.DUPLICATE if result.duplicate else MessageDisposition.ACCEPTED
        )
        self._logger.info(
            "telemetry_accepted",
            disposition=disposition,
            tenant_id=str(result.telemetry.event.tenant_id),
            charger_id=str(result.telemetry.event.charger_id),
            connector_id=result.telemetry.event.connector_id,
            message_id=str(result.telemetry.event.message_id),
        )
        return disposition

    async def _reject(
        self,
        message: IncomingTelemetryMessage,
        disposition: MessageDisposition,
        event: str,
        error: Exception,
        *,
        security_event: bool = False,
        high_severity: bool = False,
    ) -> MessageDisposition:
        await message.reject(requeue=False)
        log = self._logger.critical if high_severity else self._logger.warning
        log(
            event,
            disposition=disposition,
            routing_key=message.routing_key,
            error_type=type(error).__name__,
            security_event=security_event,
        )
        return disposition

    async def _retry_or_dead_letter(
        self,
        message: IncomingTelemetryMessage,
        error: Exception,
    ) -> MessageDisposition:
        retry_count = retry_count_from_headers(message.headers)
        if retry_count >= self._retry_limit:
            await message.reject(requeue=False)
            self._logger.error(
                "telemetry_storage_dead_lettered",
                disposition=MessageDisposition.DEAD_LETTERED_STORAGE,
                routing_key=message.routing_key,
                retry_count=retry_count,
                error_type=type(error).__name__,
            )
            return MessageDisposition.DEAD_LETTERED_STORAGE

        try:
            await self._retry_publisher.publish(message)
        except Exception as publish_error:
            await message.reject(requeue=True)
            self._logger.error(
                "telemetry_retry_publish_failed",
                routing_key=message.routing_key,
                retry_count=retry_count,
                error_type=type(publish_error).__name__,
            )
            return MessageDisposition.RETRY_SCHEDULED

        await message.ack()
        self._logger.warning(
            "telemetry_storage_retry_scheduled",
            disposition=MessageDisposition.RETRY_SCHEDULED,
            routing_key=message.routing_key,
            retry_count=retry_count + 1,
            error_type=type(error).__name__,
        )
        return MessageDisposition.RETRY_SCHEDULED


class AioPikaRetryPublisher:
    """Publish persistent retries with broker confirmation."""

    def __init__(self, exchange: AbstractExchange) -> None:
        self._exchange = exchange

    async def publish(self, message: IncomingTelemetryMessage) -> None:
        retry = Message(
            body=message.body,
            headers=dict(message.headers or {}),
            content_type=message.content_type,
            content_encoding=message.content_encoding,
            correlation_id=message.correlation_id,
            message_id=message.message_id,
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(
            retry,
            routing_key=message.routing_key,
            mandatory=True,
            timeout=10,
        )


class RabbitTelemetryConsumer:
    """Supervise a robust AMQP consumer with bounded in-flight work."""

    def __init__(
        self,
        amqp_url: str,
        service: TelemetryIngestionService,
        registry: DeviceRegistry,
        *,
        prefetch: int,
        max_payload_bytes: int,
        retry_limit: int,
        retry_delay_ms: int,
        shutdown_timeout_seconds: float,
    ) -> None:
        self._amqp_url = amqp_url
        self._service = service
        self._registry = registry
        self._prefetch = prefetch
        self._max_payload_bytes = max_payload_bytes
        self._retry_limit = retry_limit
        self._retry_delay_ms = retry_delay_ms
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._logger = structlog.get_logger("herbie.telemetry.rabbitmq")

    async def run(self, stopped: asyncio.Event) -> None:
        """Consume until stopped, reconnecting after broker interruptions."""

        reconnect_delay = 1.0
        while not stopped.is_set():
            try:
                connection = await aio_pika.connect_robust(self._amqp_url, timeout=10)
                await self._consume_connection(connection, stopped)
                reconnect_delay = 1.0
            except (AMQPException, ConnectionError, OSError, TimeoutError) as error:
                if stopped.is_set():
                    return
                self._logger.warning(
                    "rabbitmq_connection_failed",
                    error_type=type(error).__name__,
                    retry_delay_seconds=reconnect_delay,
                )
                await _wait_or_stop(stopped, reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30.0)

    async def _consume_connection(
        self,
        connection: AbstractRobustConnection,
        stopped: asyncio.Event,
    ) -> None:
        async with connection:
            channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
            await channel.set_qos(prefetch_count=self._prefetch)
            topology = await declare_messaging_topology(channel, self._retry_delay_ms)
            handler = TelemetryMessageHandler(
                self._service,
                self._registry,
                AioPikaRetryPublisher(topology.retry_exchange),
                max_payload_bytes=self._max_payload_bytes,
                retry_limit=self._retry_limit,
            )
            in_flight: set[asyncio.Task[None]] = set()

            async def consume(message: AbstractIncomingMessage) -> None:
                task = asyncio.current_task()
                if task is not None:
                    in_flight.add(task)
                try:
                    await handler.handle(cast(IncomingTelemetryMessage, message))
                except Exception as error:
                    self._logger.exception(
                        "telemetry_delivery_failed",
                        error_type=type(error).__name__,
                    )
                    if not message.processed:
                        await message.reject(requeue=True)
                finally:
                    if task is not None:
                        in_flight.discard(task)

            consumer_tag = await topology.telemetry_queue.consume(consume, no_ack=False)
            self._logger.info(
                "telemetry_consumer_started",
                queue=TELEMETRY_QUEUE,
                prefetch=self._prefetch,
            )
            await stopped.wait()
            await topology.telemetry_queue.cancel(consumer_tag)
            await _drain_in_flight(in_flight, self._shutdown_timeout_seconds)
            self._logger.info("telemetry_consumer_stopped", queue=TELEMETRY_QUEUE)


class MessagingTopology:
    """Declared entities needed by telemetry and future control consumers."""

    def __init__(
        self,
        telemetry_queue: AbstractQueue,
        retry_exchange: AbstractExchange,
    ) -> None:
        self.telemetry_queue = telemetry_queue
        self.retry_exchange = retry_exchange


async def declare_messaging_topology(
    channel: AbstractChannel,
    retry_delay_ms: int,
) -> MessagingTopology:
    """Idempotently declare classic demo queues and dead-letter routing."""

    topic_exchange = await channel.get_exchange("amq.topic")
    dead_exchange = await channel.declare_exchange(
        DEAD_LETTER_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    retry_exchange = await channel.declare_exchange(
        RETRY_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    telemetry_queue = await channel.declare_queue(
        TELEMETRY_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
        },
    )
    await telemetry_queue.bind(topic_exchange, TELEMETRY_BINDING)

    control_queue = await channel.declare_queue(
        CONTROL_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )
    await control_queue.bind(topic_exchange, CONTROL_BINDING)

    dead_queue = await channel.declare_queue(
        DEAD_LETTER_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )
    await dead_queue.bind(dead_exchange, "#")

    retry_queue = await channel.declare_queue(
        RETRY_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-message-ttl": retry_delay_ms,
            "x-dead-letter-exchange": "amq.topic",
        },
    )
    await retry_queue.bind(retry_exchange, TELEMETRY_BINDING)
    return MessagingTopology(telemetry_queue, retry_exchange)


def mqtt_topic_from_routing_key(routing_key: str) -> str:
    """Reverse RabbitMQ MQTT's slash-to-dot topic translation."""

    parts = routing_key.split(".")
    if len(parts) != 8 or any(not part for part in parts):
        raise InvalidTopicError("routing key must match the v1 telemetry route")
    return "/".join(parts)


def retry_count_from_headers(headers: Mapping[str, Any] | None) -> int:
    """Read the broker-owned retry queue death count, ignoring other deaths."""

    if not headers:
        return 0
    deaths = headers.get("x-death")
    if not isinstance(deaths, (list, tuple)):
        return 0
    retry_count = 0
    for death in deaths:
        if not isinstance(death, Mapping):
            continue
        queue = _header_text(death.get("queue"))
        reason = _header_text(death.get("reason"))
        count = death.get("count")
        if queue == RETRY_QUEUE and reason == "expired" and isinstance(count, int):
            retry_count = max(retry_count, count)
    return retry_count


def _header_text(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value if isinstance(value, str) else None


async def _wait_or_stop(stopped: asyncio.Event, delay_seconds: float) -> None:
    with suppress(TimeoutError):
        await asyncio.wait_for(stopped.wait(), timeout=delay_seconds)


async def _drain_in_flight(tasks: set[asyncio.Task[None]], timeout_seconds: float) -> None:
    if not tasks:
        return
    _, pending = await asyncio.wait(tasks, timeout=timeout_seconds)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
