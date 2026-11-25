"""MQTT simulator connection, pacing, and PUBACK tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast
from uuid import UUID

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.enums import MQTTErrorCode

from herbie.telemetry.topic import DeviceIdentity
from herbie_simulator.mqtt import (
    MQTTDeviceCredentials,
    MQTTProtocol,
    MQTTPublishConfig,
    MQTTPublishError,
    PahoClient,
    PahoDeviceConnection,
    ReportingMode,
    TemplateCredentialProvider,
    publish_scenario,
)
from herbie_simulator.scenario import Scenario, generate_scenario

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
CHARGER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class ReasonCode:
    def __init__(self, is_failure: bool = False) -> None:
        self.is_failure = is_failure


class FakeMessageInfo:
    def __init__(
        self,
        *,
        result: MQTTErrorCode = mqtt.MQTT_ERR_SUCCESS,
        published: bool = True,
    ) -> None:
        self.rc = result
        self.published = published
        self.waits: list[float | None] = []

    def wait_for_publish(self, timeout: float | None = None) -> None:
        self.waits.append(timeout)

    def is_published(self) -> bool:
        return self.published


class FakeClient:
    def __init__(
        self,
        connect_results: list[MQTTErrorCode | Exception] | None = None,
        infos: list[FakeMessageInfo] | None = None,
    ) -> None:
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.connect_results = connect_results or [mqtt.MQTT_ERR_SUCCESS]
        self.infos = infos or [FakeMessageInfo()]
        self.username: tuple[str, str | None] | None = None
        self.tls: dict[str, Any] | None = None
        self.loop_started = 0
        self.loop_stopped = 0
        self.disconnects = 0
        self.connects = 0
        self.publications: list[tuple[str, bytes, int, bool]] = []

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.username = (username, password)

    def tls_set(
        self,
        ca_certs: str | None = None,
        certfile: str | None = None,
        keyfile: str | None = None,
        tls_version: int | None = None,
    ) -> None:
        self.tls = {
            "ca_certs": ca_certs,
            "certfile": certfile,
            "keyfile": keyfile,
            "tls_version": tls_version,
        }

    def loop_start(self) -> MQTTErrorCode:
        self.loop_started += 1
        return mqtt.MQTT_ERR_SUCCESS

    def loop_stop(self) -> MQTTErrorCode:
        self.loop_stopped += 1
        return mqtt.MQTT_ERR_SUCCESS

    def connect(
        self,
        host: str,
        port: int,
        keepalive: int,
        clean_start: Any = None,
    ) -> MQTTErrorCode:
        assert host
        assert port > 0
        assert keepalive > 0
        assert clean_start is not None
        result = self.connect_results[min(self.connects, len(self.connect_results) - 1)]
        self.connects += 1
        if isinstance(result, Exception):
            raise result
        if result == mqtt.MQTT_ERR_SUCCESS and self.on_connect is not None:
            self.on_connect(self, None, None, ReasonCode(), None)
        return result

    def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool,
    ) -> Any:
        self.publications.append((topic, payload, qos, retain))
        return self.infos[min(len(self.publications) - 1, len(self.infos) - 1)]

    def disconnect(self) -> MQTTErrorCode:
        self.disconnects += 1
        if self.on_disconnect is not None:
            self.on_disconnect(self, None, None, ReasonCode(), None)
        return mqtt.MQTT_ERR_SUCCESS


def identity() -> DeviceIdentity:
    return DeviceIdentity(TENANT_ID, CHARGER_ID)


def credentials() -> MQTTDeviceCredentials:
    return MQTTDeviceCredentials("device-a", "test-password")


def factory_for(client: FakeClient) -> Callable[[str, MQTTProtocol], PahoClient]:
    def factory(client_id: str, protocol: MQTTProtocol) -> PahoClient:
        assert client_id == f"herbie-{CHARGER_ID}"
        assert protocol == MQTTProtocol.V5
        return cast(PahoClient, client)

    return factory


def test_template_credentials_render_stable_device_identity() -> None:
    provider = TemplateCredentialProvider("device-{tenant_id}-{charger_id}", "secret")

    result = provider.for_device(identity())

    assert result.username == f"device-{TENANT_ID}-{CHARGER_ID}"
    assert result.password == "secret"


@pytest.mark.parametrize(
    ("template", "password", "message"),
    [
        ("", "secret", "template cannot be empty"),
        ("device", "", "password cannot be empty"),
        ("device-{unknown}", "secret", "invalid MQTT username template"),
    ],
)
def test_template_credentials_reject_invalid_configuration(
    template: str,
    password: str,
    message: str,
) -> None:
    if "unknown" not in template:
        with pytest.raises(ValueError, match=message):
            TemplateCredentialProvider(template, password)
        return
    provider = TemplateCredentialProvider(template, password)
    with pytest.raises(ValueError, match=message):
        provider.for_device(identity())


@pytest.mark.parametrize(
    "changes",
    [
        {"host": ""},
        {"port": 0},
        {"connection_count": 0},
        {"connection_workers": 0},
        {"message_rate": 0},
        {"keepalive_seconds": 0},
        {"connect_timeout_seconds": 0},
        {"publish_timeout_seconds": 0},
        {"reconnect_min_delay_seconds": -1},
        {"reconnect_min_delay_seconds": 2, "reconnect_max_delay_seconds": 1},
        {"reconnect_attempts": 0},
        {"tls_cert_file": "client.crt"},
        {"tls_ca_file": "ca.crt"},
    ],
)
def test_publish_config_rejects_invalid_bounds(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        MQTTPublishConfig(**changes)


def test_device_connection_uses_qos_one_puback_and_tls() -> None:
    client = FakeClient()
    config = MQTTPublishConfig(
        tls_enabled=True,
        tls_ca_file="ca.crt",
        tls_cert_file="client.crt",
        tls_key_file="client.key",
    )
    connection = PahoDeviceConnection(
        identity(),
        credentials(),
        config,
        "seed",
        client_factory=factory_for(client),
    )
    publication = next(
        item
        for item in generate_scenario(Scenario(tenants=1, chargers_per_tenant=1, rounds=1))
        if item.event.charger_id != CHARGER_ID
    )
    matching = publication.__class__(
        topic=publication.topic.replace(str(publication.event.charger_id), str(CHARGER_ID)),
        event=publication.event.model_copy(
            update={"tenant_id": TENANT_ID, "charger_id": CHARGER_ID}
        ),
    )

    connection.publish(matching)
    connection.close()

    assert connection.client_id == f"herbie-{CHARGER_ID}"
    assert client.username == ("device-a", "test-password")
    assert client.tls is not None
    assert client.publications[0][2:] == (1, False)
    assert client.infos[0].waits == [10.0]
    assert client.disconnects == 1


def test_device_connection_retries_with_seeded_backoff() -> None:
    client = FakeClient(connect_results=[OSError("offline"), mqtt.MQTT_ERR_SUCCESS])
    sleeps: list[float] = []
    connection = PahoDeviceConnection(
        identity(),
        credentials(),
        MQTTPublishConfig(reconnect_min_delay_seconds=1, reconnect_attempts=2),
        "seed",
        client_factory=factory_for(client),
        sleeper=sleeps.append,
    )

    connection.start()
    connection.start()
    connection.close()

    assert client.connects == 2
    assert len(sleeps) == 1
    assert 0.5 <= sleeps[0] <= 1.5
    assert client.loop_started == client.loop_stopped == 1


def test_device_connection_restarts_network_loop_after_disconnect() -> None:
    client = FakeClient(connect_results=[mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_SUCCESS])
    connection = PahoDeviceConnection(
        identity(),
        credentials(),
        MQTTPublishConfig(),
        "seed",
        client_factory=factory_for(client),
    )
    publication = next(generate_scenario(Scenario(tenants=1, chargers_per_tenant=1, rounds=1)))
    matching = publication.__class__(
        topic=publication.topic.replace(str(publication.event.charger_id), str(CHARGER_ID)),
        event=publication.event.model_copy(
            update={"tenant_id": TENANT_ID, "charger_id": CHARGER_ID}
        ),
    )

    connection.start()
    client.on_disconnect(client, None, None, ReasonCode(), None)
    connection.publish(matching)
    connection.close()

    assert client.connects == 2
    assert client.loop_started == 2
    assert client.loop_stopped == 2


def test_device_connection_reports_retry_exhaustion_and_puback_failure() -> None:
    offline = FakeClient(connect_results=[OSError("offline")])
    connection = PahoDeviceConnection(
        identity(),
        credentials(),
        MQTTPublishConfig(reconnect_attempts=1),
        "seed",
        client_factory=factory_for(offline),
    )
    with pytest.raises(MQTTPublishError, match="retry limit"):
        connection.start()
    assert offline.loop_started == offline.loop_stopped == 0

    no_ack = FakeClient(infos=[FakeMessageInfo(published=False)])
    connection = PahoDeviceConnection(
        identity(),
        credentials(),
        MQTTPublishConfig(),
        "seed",
        client_factory=factory_for(no_ack),
    )
    publication = next(generate_scenario(Scenario(tenants=1, chargers_per_tenant=1, rounds=1)))
    with pytest.raises(ValueError, match="does not belong"):
        connection.publish(publication)
    matching = publication.__class__(
        topic=publication.topic.replace(str(publication.event.charger_id), str(CHARGER_ID)),
        event=publication.event.model_copy(
            update={"tenant_id": TENANT_ID, "charger_id": CHARGER_ID}
        ),
    )
    with pytest.raises(MQTTPublishError, match="PUBACK timed out"):
        connection.publish(matching)
    connection.close()


class ClientCollection:
    def __init__(self, fail_publish: bool = False) -> None:
        self.clients: dict[str, FakeClient] = {}
        self.fail_publish = fail_publish

    def factory(self, client_id: str, protocol: MQTTProtocol) -> PahoClient:
        assert protocol == MQTTProtocol.V5
        info = FakeMessageInfo(published=not self.fail_publish)
        client = FakeClient(infos=[info])
        self.clients[client_id] = client
        return cast(PahoClient, client)


def monotonic_values(values: Iterable[float]) -> Callable[[], float]:
    iterator: Iterator[float] = iter(values)
    return lambda: next(iterator)


def test_publish_scenario_separates_connections_offers_and_pubacks() -> None:
    clients = ClientCollection()
    sleeps: list[float] = []
    scenario = Scenario(tenants=1, chargers_per_tenant=3, rounds=2, interval_seconds=10)
    config = MQTTPublishConfig(
        connection_count=2,
        reporting_mode=ReportingMode.SYNCHRONIZED,
        message_rate=200,
    )

    result = publish_scenario(
        scenario,
        config,
        TemplateCredentialProvider("device-{charger_id}", "secret"),
        client_factory=clients.factory,
        sleeper=sleeps.append,
        monotonic=monotonic_values([1.0, 13.0]),
    )

    assert result.represented_devices == 3
    assert result.connected_clients == 2
    assert result.offered_messages == result.pubacknowledged_messages == 4
    assert result.failed_messages == 0
    assert result.elapsed_seconds == 12.0
    assert sleeps == [10.0]
    assert len(clients.clients) == 2
    assert all(len(client.publications) == 2 for client in clients.clients.values())


def test_jittered_schedule_is_repeatable_and_failed_pubacks_are_counted() -> None:
    scenario = Scenario(tenants=1, chargers_per_tenant=2, rounds=1)
    config = MQTTPublishConfig(reporting_mode=ReportingMode.JITTERED)

    def run_once() -> tuple[list[float], int]:
        clients = ClientCollection(fail_publish=True)
        sleeps: list[float] = []
        result = publish_scenario(
            scenario,
            config,
            TemplateCredentialProvider("device-{charger_id}", "secret"),
            client_factory=clients.factory,
            sleeper=sleeps.append,
            monotonic=monotonic_values([0.0, 1.0]),
        )
        return sleeps, result.failed_messages

    first = run_once()
    second = run_once()

    assert first == second
    assert first[1] == 2


def test_publish_scenario_rejects_more_connections_than_devices() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        publish_scenario(
            Scenario(tenants=1, chargers_per_tenant=1, rounds=1),
            MQTTPublishConfig(connection_count=2),
            TemplateCredentialProvider("device-{charger_id}", "secret"),
        )
