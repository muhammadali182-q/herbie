"""Deterministic MQTT QoS 1 publication for simulated chargers."""

from __future__ import annotations

import random
import ssl
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from itertools import groupby, islice
from typing import Any, Protocol, cast

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion, MQTTErrorCode

from herbie.telemetry.topic import DeviceIdentity
from herbie_simulator.scenario import Scenario, SimulatedPublication, generate_scenario


class ReportingMode(StrEnum):
    """How device timers are phased within each reporting cycle."""

    SYNCHRONIZED = "synchronized"
    JITTERED = "jittered"


class MQTTProtocol(StrEnum):
    """Supported wire-protocol profiles."""

    V5 = "5"
    V311 = "3.1.1"


class MQTTPublishError(RuntimeError):
    """A connection or QoS 1 publication could not be confirmed."""


@dataclass(frozen=True, slots=True)
class MQTTDeviceCredentials:
    """One broker login selected for a logical charger identity."""

    username: str
    password: str


class CredentialProvider(Protocol):
    """Supply credentials without embedding them in generated events."""

    def for_device(self, identity: DeviceIdentity) -> MQTTDeviceCredentials:
        """Return credentials for one logical device."""


class TemplateCredentialProvider(CredentialProvider):
    """Render per-device usernames while keeping the password outside Git."""

    def __init__(self, username_template: str, password: str) -> None:
        if not username_template:
            raise ValueError("MQTT username template cannot be empty")
        if not password:
            raise ValueError("MQTT password cannot be empty")
        self._username_template = username_template
        self._password = password

    def for_device(self, identity: DeviceIdentity) -> MQTTDeviceCredentials:
        try:
            username = self._username_template.format(
                tenant_id=identity.tenant_id,
                charger_id=identity.charger_id,
            )
        except (IndexError, KeyError, ValueError) as error:
            raise ValueError("invalid MQTT username template") from error
        if not username:
            raise ValueError("MQTT username template produced an empty username")
        return MQTTDeviceCredentials(username=username, password=self._password)


@dataclass(frozen=True, slots=True)
class MQTTPublishConfig:
    """Bounded connection, pacing, retry, and TLS configuration."""

    host: str = "localhost"
    port: int = 1883
    protocol: MQTTProtocol = MQTTProtocol.V5
    connection_count: int | None = None
    connection_workers: int = 64
    message_rate: float = 200.0
    reporting_mode: ReportingMode = ReportingMode.JITTERED
    keepalive_seconds: int = 60
    connect_timeout_seconds: float = 10.0
    publish_timeout_seconds: float = 10.0
    reconnect_min_delay_seconds: float = 0.25
    reconnect_max_delay_seconds: float = 30.0
    reconnect_attempts: int = 8
    tls_enabled: bool = False
    tls_ca_file: str | None = None
    tls_cert_file: str | None = None
    tls_key_file: str | None = None

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("MQTT host cannot be empty")
        if not 1 <= self.port <= 65_535:
            raise ValueError("MQTT port must be between 1 and 65535")
        if self.connection_count is not None and self.connection_count < 1:
            raise ValueError("MQTT connection count must be at least one")
        if self.connection_workers < 1:
            raise ValueError("MQTT connection workers must be at least one")
        if self.message_rate <= 0:
            raise ValueError("MQTT message rate must be greater than zero")
        if not 1 <= self.keepalive_seconds <= 65_535:
            raise ValueError("MQTT keepalive must be between 1 and 65535 seconds")
        if self.connect_timeout_seconds <= 0 or self.publish_timeout_seconds <= 0:
            raise ValueError("MQTT timeouts must be greater than zero")
        if self.reconnect_min_delay_seconds < 0:
            raise ValueError("MQTT minimum reconnect delay cannot be negative")
        if self.reconnect_max_delay_seconds < self.reconnect_min_delay_seconds:
            raise ValueError("MQTT maximum reconnect delay must not be smaller than minimum")
        if self.reconnect_attempts < 1:
            raise ValueError("MQTT reconnect attempts must be at least one")
        if (self.tls_cert_file is None) != (self.tls_key_file is None):
            raise ValueError("MQTT TLS certificate and key must be configured together")
        if not self.tls_enabled and any((self.tls_ca_file, self.tls_cert_file, self.tls_key_file)):
            raise ValueError("MQTT TLS files require TLS to be enabled")


@dataclass(frozen=True, slots=True)
class PublishSummary:
    """Generator-side results; PUBACK is not durable-ingestion evidence."""

    represented_devices: int
    connected_clients: int
    offered_messages: int
    pubacknowledged_messages: int
    failed_messages: int
    elapsed_seconds: float


class PahoClient(Protocol):
    """Paho behavior used by one logical connection."""

    on_connect: Any
    on_disconnect: Any

    def username_pw_set(self, username: str, password: str | None = None) -> None: ...

    def tls_set(
        self,
        ca_certs: str | None = None,
        certfile: str | None = None,
        keyfile: str | None = None,
        tls_version: int | None = None,
    ) -> None: ...

    def loop_start(self) -> MQTTErrorCode: ...

    def loop_stop(self) -> MQTTErrorCode: ...

    def connect(
        self,
        host: str,
        port: int,
        keepalive: int,
        clean_start: Any = ...,
    ) -> MQTTErrorCode: ...

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> mqtt.MQTTMessageInfo: ...

    def disconnect(self) -> MQTTErrorCode: ...


ClientFactory = Callable[[str, MQTTProtocol], PahoClient]


class PahoDeviceConnection:
    """One stable client ID and QoS 1 connection per selected charger."""

    def __init__(
        self,
        identity: DeviceIdentity,
        credentials: MQTTDeviceCredentials,
        config: MQTTPublishConfig,
        scenario_seed: str,
        *,
        client_factory: ClientFactory | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.identity = identity
        self.client_id = f"herbie-{identity.charger_id}"
        self._config = config
        self._sleeper = sleeper
        self._random = random.Random(f"{scenario_seed}:{identity.charger_id}:reconnect")
        self._connected = threading.Event()
        self._started = False
        factory = client_factory or _new_client
        self._client = factory(self.client_id, config.protocol)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.username_pw_set(credentials.username, credentials.password)
        if config.tls_enabled:
            self._client.tls_set(
                ca_certs=config.tls_ca_file,
                certfile=config.tls_cert_file,
                keyfile=config.tls_key_file,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )

    def start(self) -> None:
        """Start network processing and establish the initial connection."""

        if self._started:
            return
        self._connect_with_backoff()

    def publish(self, publication: SimulatedPublication) -> None:
        """Wait for the QoS 1 PUBACK for one matching device publication."""

        if publication.event.charger_id != self.identity.charger_id:
            raise ValueError("publication does not belong to this MQTT client")
        if not self._started:
            self.start()
        if not self._connected.is_set():
            self._connect_with_backoff()
        info = self._client.publish(
            publication.topic,
            publication.event.model_dump_json(exclude_none=True).encode(),
            qos=1,
            retain=False,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self._connected.clear()
            raise MQTTPublishError(f"MQTT publish failed with result {info.rc}")
        info.wait_for_publish(timeout=self._config.publish_timeout_seconds)
        if not info.is_published():
            raise MQTTPublishError("MQTT QoS 1 PUBACK timed out")

    def close(self) -> None:
        """Disconnect this logical device and stop its network thread."""

        if not self._started:
            return
        self._client.disconnect()
        self._client.loop_stop()
        self._connected.clear()
        self._started = False

    def _connect_with_backoff(self) -> None:
        self._connected.clear()
        if self._started:
            self._client.loop_stop()
            self._started = False
        last_error: Exception | None = None
        for attempt in range(self._config.reconnect_attempts):
            try:
                result = self._client.connect(
                    self._config.host,
                    self._config.port,
                    self._config.keepalive_seconds,
                    clean_start=mqtt.MQTT_CLEAN_START_FIRST_ONLY,
                )
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self._client.loop_start()
                    self._started = True
                    if self._connected.wait(timeout=self._config.connect_timeout_seconds):
                        return
                    self._client.loop_stop()
                    self._started = False
                last_error = MQTTPublishError(f"MQTT connection failed with result {result}")
            except (OSError, TimeoutError) as error:
                last_error = error
            if attempt + 1 < self._config.reconnect_attempts:
                self._sleeper(self._reconnect_delay(attempt))
        self._connected.clear()
        raise MQTTPublishError("MQTT connection retry limit exhausted") from last_error

    def _reconnect_delay(self, attempt: int) -> float:
        base = min(
            self._config.reconnect_min_delay_seconds * (2**attempt),
            self._config.reconnect_max_delay_seconds,
        )
        return float(base * (0.5 + self._random.random()))

    def _on_connect(
        self,
        client: PahoClient,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, flags, properties
        if not getattr(reason_code, "is_failure", reason_code != 0):
            self._connected.set()

    def _on_disconnect(
        self,
        client: PahoClient,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, disconnect_flags, reason_code, properties
        self._connected.clear()


def publish_scenario(
    scenario: Scenario,
    config: MQTTPublishConfig,
    credentials: CredentialProvider,
    *,
    client_factory: ClientFactory | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> PublishSummary:
    """Publish selected logical devices with deterministic timer phasing."""

    represented_devices = scenario.tenants * scenario.chargers_per_tenant
    connection_count = config.connection_count or represented_devices
    if connection_count > represented_devices:
        raise ValueError("MQTT connection count cannot exceed represented devices")

    first_round = list(islice(generate_scenario(scenario), represented_devices))
    selected_ids = {item.event.charger_id for item in first_round[:connection_count]}
    connections: dict[Any, PahoDeviceConnection] = {}
    for publication in first_round[:connection_count]:
        identity = DeviceIdentity(
            publication.event.tenant_id,
            publication.event.charger_id,
        )
        connections[identity.charger_id] = PahoDeviceConnection(
            identity,
            credentials.for_device(identity),
            config,
            scenario.seed,
            client_factory=client_factory,
            sleeper=sleeper,
        )

    offered = 0
    acknowledged = 0
    failed = 0
    started_at = monotonic()
    workers = min(config.connection_workers, connection_count)
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="herbie-mqtt")
    try:
        list(executor.map(lambda connection: connection.start(), connections.values()))
        publications = (
            item for item in generate_scenario(scenario) if item.event.charger_id in selected_ids
        )
        rounds = groupby(publications, key=lambda item: item.event.sequence)
        cycle_seconds = max(
            float(scenario.interval_seconds),
            connection_count / config.message_rate,
        )
        previous_offset = 0.0
        first_round_seen = False
        for sequence, round_items in rounds:
            items = list(round_items)
            if config.reporting_mode == ReportingMode.SYNCHRONIZED:
                if first_round_seen:
                    sleeper(cycle_seconds)
                outcomes = executor.map(
                    lambda item: _publish_one(connections[item.event.charger_id], item),
                    items,
                )
                round_outcomes = list(outcomes)
            else:
                scheduled = sorted(
                    (
                        _jitter_offset(scenario.seed, sequence, item, cycle_seconds),
                        item,
                    )
                    for item in items
                )
                if first_round_seen:
                    sleeper(max(cycle_seconds - previous_offset + scheduled[0][0], 0.0))
                elif scheduled[0][0] > 0:
                    sleeper(scheduled[0][0])
                round_outcomes = []
                last_offset = scheduled[0][0]
                for index, (offset, item) in enumerate(scheduled):
                    if index:
                        sleeper(max(offset - last_offset, 0.0))
                    round_outcomes.append(_publish_one(connections[item.event.charger_id], item))
                    last_offset = offset
                previous_offset = last_offset
            first_round_seen = True
            offered += len(round_outcomes)
            acknowledged += sum(round_outcomes)
            failed += len(round_outcomes) - sum(round_outcomes)
    finally:
        list(executor.map(lambda connection: connection.close(), connections.values()))
        executor.shutdown(wait=True, cancel_futures=False)

    return PublishSummary(
        represented_devices=represented_devices,
        connected_clients=connection_count,
        offered_messages=offered,
        pubacknowledged_messages=acknowledged,
        failed_messages=failed,
        elapsed_seconds=monotonic() - started_at,
    )


def _publish_one(
    connection: PahoDeviceConnection,
    publication: SimulatedPublication,
) -> int:
    try:
        connection.publish(publication)
    except MQTTPublishError:
        return 0
    return 1


def _jitter_offset(
    seed: str,
    sequence: int,
    publication: SimulatedPublication,
    cycle_seconds: float,
) -> float:
    generator = random.Random(f"{seed}:{sequence}:{publication.event.charger_id}:reporting-jitter")
    return generator.random() * cycle_seconds


def _new_client(client_id: str, protocol: MQTTProtocol) -> PahoClient:
    wire_protocol = mqtt.MQTTv5 if protocol == MQTTProtocol.V5 else mqtt.MQTTv311
    return cast(
        PahoClient,
        mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=wire_protocol,
            reconnect_on_failure=False,
        ),
    )
