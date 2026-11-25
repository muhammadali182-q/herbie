"""RabbitMQ topology and broker-disposition tests."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from aio_pika import DeliveryMode
from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractRobustConnection

from herbie.telemetry.contracts import ChargerStatus, MessageType, TelemetryEvent, TelemetryPayload
from herbie.telemetry.memory import InMemoryTelemetryRepository
from herbie.telemetry.rabbitmq import (
    CONTROL_BINDING,
    DEAD_LETTER_EXCHANGE,
    RETRY_QUEUE,
    TELEMETRY_BINDING,
    AioPikaRetryPublisher,
    IncomingTelemetryMessage,
    MessageDisposition,
    RabbitTelemetryConsumer,
    TelemetryMessageHandler,
    _drain_in_flight,
    _wait_or_stop,
    declare_messaging_topology,
    mqtt_topic_from_routing_key,
    retry_count_from_headers,
)
from herbie.telemetry.registry import StaticDeviceRegistry
from herbie.telemetry.repository import StoredTelemetry, TelemetryWriteResult
from herbie.telemetry.service import TelemetryIngestionService
from herbie.telemetry.topic import DeviceIdentity, TelemetryTopic

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
CHARGER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_CHARGER_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
BOOT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MESSAGE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SERVER_TIME = datetime(2026, 1, 1, 0, 1, tzinfo=UTC)


class FakeMessage:
    """Record manual acknowledgement decisions."""

    def __init__(
        self,
        body: bytes,
        routing_key: str,
        headers: Mapping[str, Any] | None = None,
    ) -> None:
        self.body = body
        self.routing_key = routing_key
        self.headers = headers
        self.content_type: str | None = "application/json"
        self.content_encoding: str | None = None
        self.correlation_id: str | None = "correlation-1"
        self.message_id: str | None = "broker-message-1"
        self.acked = 0
        self.rejections: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejections.append(requeue)


class FakeRetryPublisher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.messages: list[IncomingTelemetryMessage] = []

    async def publish(self, message: IncomingTelemetryMessage) -> None:
        if self.error is not None:
            raise self.error
        self.messages.append(message)


class FailingRepository(InMemoryTelemetryRepository):
    async def store(self, telemetry: StoredTelemetry) -> TelemetryWriteResult:
        raise RuntimeError("storage unavailable")


def event(
    *,
    charger_id: UUID = CHARGER_ID,
    message_id: UUID = MESSAGE_ID,
    sequence: int = 1,
    occurred_at: datetime | None = None,
) -> TelemetryEvent:
    timestamp = occurred_at or datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC)
    return TelemetryEvent(
        schema_version="1.0",
        message_id=message_id,
        message_type=MessageType.TELEMETRY_REPORTED,
        occurred_at=timestamp,
        sent_at=timestamp,
        boot_id=BOOT_ID,
        boot_started_at=datetime(2026, 1, 1, tzinfo=UTC),
        sequence=sequence,
        tenant_id=TENANT_ID,
        charger_id=charger_id,
        connector_id=1,
        payload=TelemetryPayload(
            cumulative_energy_wh=100,
            power_w=7_200,
            status=ChargerStatus.CHARGING,
        ),
    )


def routing_key(charger_id: UUID = CHARGER_ID) -> str:
    return TelemetryTopic.for_device(TENANT_ID, charger_id).replace("/", ".")


def handler(
    repository: InMemoryTelemetryRepository | None = None,
    registry: StaticDeviceRegistry | None = None,
    retry: FakeRetryPublisher | None = None,
    *,
    max_payload_bytes: int = 65_536,
    retry_limit: int = 3,
) -> TelemetryMessageHandler:
    actual_repository = repository or InMemoryTelemetryRepository()
    service = TelemetryIngestionService(actual_repository, lambda: SERVER_TIME)
    actual_registry = registry or StaticDeviceRegistry([DeviceIdentity(TENANT_ID, CHARGER_ID)])
    return TelemetryMessageHandler(
        service,
        actual_registry,
        retry or FakeRetryPublisher(),
        max_payload_bytes=max_payload_bytes,
        retry_limit=retry_limit,
    )


@pytest.mark.asyncio
async def test_valid_event_is_acked_only_after_storage_and_duplicate_is_safe() -> None:
    repository = InMemoryTelemetryRepository()
    consumer = handler(repository)
    payload = event().canonical_json().encode()
    first = FakeMessage(payload, routing_key())
    duplicate = FakeMessage(payload, routing_key())

    assert await consumer.handle(first) == MessageDisposition.ACCEPTED
    assert await consumer.handle(duplicate) == MessageDisposition.DUPLICATE

    assert first.acked == 1
    assert duplicate.acked == 1
    assert first.rejections == duplicate.rejections == []
    assert len(await repository.list_archive_pending(10)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (FakeMessage(b"not-json", routing_key()), MessageDisposition.REJECTED_CONTRACT),
        (
            FakeMessage(event().canonical_json().encode(), "invalid.route"),
            MessageDisposition.REJECTED_CONTRACT,
        ),
        (FakeMessage(b"x" * 20, routing_key()), MessageDisposition.REJECTED_CONTRACT),
    ],
)
async def test_poison_messages_are_rejected_without_requeue(
    message: FakeMessage,
    expected: MessageDisposition,
) -> None:
    max_bytes = 10 if message.body.startswith(b"x") else 65_536

    assert await handler(max_payload_bytes=max_bytes).handle(message) == expected
    assert message.acked == 0
    assert message.rejections == [False]


@pytest.mark.asyncio
async def test_unregistered_route_and_payload_identity_mismatch_are_rejected() -> None:
    unregistered = FakeMessage(event().canonical_json().encode(), routing_key())
    mismatched = FakeMessage(
        event(charger_id=OTHER_CHARGER_ID).canonical_json().encode(),
        routing_key(),
    )

    empty_registry = StaticDeviceRegistry([])
    assert await handler(registry=empty_registry).handle(unregistered) == (
        MessageDisposition.REJECTED_IDENTITY
    )
    assert await handler().handle(mismatched) == MessageDisposition.REJECTED_IDENTITY
    assert unregistered.rejections == mismatched.rejections == [False]


@pytest.mark.asyncio
async def test_clock_skew_and_sequence_conflict_are_dead_lettered() -> None:
    future = event(occurred_at=SERVER_TIME + timedelta(minutes=6))
    future_message = FakeMessage(future.canonical_json().encode(), routing_key())
    assert await handler().handle(future_message) == MessageDisposition.REJECTED_CLOCK

    repository = InMemoryTelemetryRepository()
    consumer = handler(repository)
    first = FakeMessage(event().canonical_json().encode(), routing_key())
    conflicting = FakeMessage(
        event(message_id=UUID(int=5), sequence=1).canonical_json().encode(),
        routing_key(),
    )
    assert await consumer.handle(first) == MessageDisposition.ACCEPTED
    assert await consumer.handle(conflicting) == MessageDisposition.REJECTED_CONFLICT
    assert conflicting.rejections == [False]


@pytest.mark.asyncio
async def test_storage_error_uses_confirmed_retry_then_acks_original() -> None:
    retry = FakeRetryPublisher()
    message = FakeMessage(event().canonical_json().encode(), routing_key())

    disposition = await handler(FailingRepository(), retry=retry).handle(message)

    assert disposition == MessageDisposition.RETRY_SCHEDULED
    assert retry.messages == [message]
    assert message.acked == 1
    assert message.rejections == []


@pytest.mark.asyncio
async def test_storage_error_is_dead_lettered_after_retry_limit() -> None:
    headers = {
        "x-death": [
            {"queue": RETRY_QUEUE.encode(), "reason": b"expired", "count": 3},
        ]
    }
    message = FakeMessage(event().canonical_json().encode(), routing_key(), headers)

    disposition = await handler(FailingRepository(), retry_limit=3).handle(message)

    assert disposition == MessageDisposition.DEAD_LETTERED_STORAGE
    assert message.acked == 0
    assert message.rejections == [False]


@pytest.mark.asyncio
async def test_failed_retry_publication_requeues_original_delivery() -> None:
    retry = FakeRetryPublisher(RuntimeError("publisher unavailable"))
    message = FakeMessage(event().canonical_json().encode(), routing_key())

    disposition = await handler(FailingRepository(), retry=retry).handle(message)

    assert disposition == MessageDisposition.RETRY_SCHEDULED
    assert message.acked == 0
    assert message.rejections == [True]


def test_routing_key_and_broker_retry_headers_are_parsed_strictly() -> None:
    topic = TelemetryTopic.for_device(TENANT_ID, CHARGER_ID)

    assert mqtt_topic_from_routing_key(topic.replace("/", ".")) == topic
    assert retry_count_from_headers(None) == 0
    assert retry_count_from_headers({"x-death": "invalid"}) == 0
    assert (
        retry_count_from_headers(
            {
                "x-death": [
                    {"queue": "another-queue", "reason": "expired", "count": 99},
                    {"queue": RETRY_QUEUE, "reason": "rejected", "count": 8},
                    {"queue": RETRY_QUEUE, "reason": "expired", "count": 2},
                ]
            }
        )
        == 2
    )


@pytest.mark.asyncio
async def test_retry_publisher_preserves_safe_metadata_and_uses_persistence() -> None:
    exchange = MagicMock()
    exchange.publish = AsyncMock(return_value=True)
    publisher = AioPikaRetryPublisher(cast(AbstractExchange, exchange))
    incoming = FakeMessage(
        event().canonical_json().encode(),
        routing_key(),
        {"trace": "value"},
    )

    await publisher.publish(incoming)

    published = exchange.publish.await_args.args[0]
    assert published.body == incoming.body
    assert published.headers == {"trace": "value"}
    assert published.delivery_mode == DeliveryMode.PERSISTENT
    assert exchange.publish.await_args.kwargs == {
        "routing_key": routing_key(),
        "mandatory": True,
        "timeout": 10,
    }


@pytest.mark.asyncio
async def test_topology_declares_separate_classic_queues_and_bindings() -> None:
    topic_exchange = MagicMock()
    dead_exchange = MagicMock()
    retry_exchange = MagicMock()
    queues = [MagicMock() for _ in range(4)]
    for queue in queues:
        queue.bind = AsyncMock()
    channel = MagicMock()
    channel.get_exchange = AsyncMock(return_value=topic_exchange)
    channel.declare_exchange = AsyncMock(side_effect=[dead_exchange, retry_exchange])
    channel.declare_queue = AsyncMock(side_effect=queues)

    topology = await declare_messaging_topology(cast(AbstractChannel, channel), 5_000)

    assert topology.telemetry_queue is queues[0]
    assert topology.retry_exchange is retry_exchange
    queues[0].bind.assert_awaited_once_with(topic_exchange, TELEMETRY_BINDING)
    queues[1].bind.assert_awaited_once_with(topic_exchange, CONTROL_BINDING)
    queues[2].bind.assert_awaited_once_with(dead_exchange, "#")
    queues[3].bind.assert_awaited_once_with(retry_exchange, TELEMETRY_BINDING)
    assert channel.declare_exchange.await_args_list[0].args[0] == DEAD_LETTER_EXCHANGE


class FakeConnection:
    def __init__(self, channel: Any) -> None:
        self._channel = channel
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> FakeConnection:
        self.entered = True
        return self

    async def __aexit__(self, *args: object) -> None:
        self.exited = True

    async def channel(self, **kwargs: Any) -> Any:
        assert kwargs == {"publisher_confirms": True, "on_return_raises": True}
        return self._channel


def rabbit_consumer() -> RabbitTelemetryConsumer:
    repository = InMemoryTelemetryRepository()
    service = TelemetryIngestionService(repository, lambda: SERVER_TIME)
    registry = StaticDeviceRegistry([DeviceIdentity(TENANT_ID, CHARGER_ID)])
    return RabbitTelemetryConsumer(
        "amqp://example",
        service,
        registry,
        prefetch=100,
        max_payload_bytes=65_536,
        retry_limit=3,
        retry_delay_ms=5_000,
        shutdown_timeout_seconds=1,
    )


@pytest.mark.asyncio
async def test_consumer_session_starts_cancels_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped = asyncio.Event()
    stopped.set()
    channel = MagicMock()
    channel.set_qos = AsyncMock()
    queue = MagicMock()
    queue.consume = AsyncMock(return_value="consumer-tag")
    queue.cancel = AsyncMock()
    topology = MagicMock(telemetry_queue=queue, retry_exchange=MagicMock())
    declare = AsyncMock(return_value=topology)
    monkeypatch.setattr("herbie.telemetry.rabbitmq.declare_messaging_topology", declare)
    connection = FakeConnection(channel)

    await rabbit_consumer()._consume_connection(
        cast(AbstractRobustConnection, connection),
        stopped,
    )

    channel.set_qos.assert_awaited_once_with(prefetch_count=100)
    queue.consume.assert_awaited_once()
    queue.cancel.assert_awaited_once_with("consumer-tag")
    assert connection.entered is True
    assert connection.exited is True


@pytest.mark.asyncio
async def test_consumer_retries_initial_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped = asyncio.Event()

    async def fail_connect(*args: object, **kwargs: object) -> None:
        raise OSError("broker unavailable")

    async def stop_instead_of_wait(event: Any, delay: float) -> None:
        assert delay == 1.0
        event.set()

    monkeypatch.setattr("herbie.telemetry.rabbitmq.aio_pika.connect_robust", fail_connect)
    monkeypatch.setattr("herbie.telemetry.rabbitmq._wait_or_stop", stop_instead_of_wait)

    await rabbit_consumer().run(stopped)

    assert stopped.is_set()


@pytest.mark.asyncio
async def test_wait_and_drain_helpers_cover_stop_timeout_and_cancellation() -> None:
    stopped = asyncio.Event()
    await _wait_or_stop(stopped, 0.001)
    stopped.set()
    await _wait_or_stop(stopped, 1)

    release = asyncio.Event()

    async def blocked() -> None:
        await release.wait()

    task = asyncio.create_task(blocked())
    await _drain_in_flight({task}, 0.001)
    assert task.cancelled()
    await _drain_in_flight(set(), 1)
