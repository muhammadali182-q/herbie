"""Docker-backed MQTT ingestion, authorization, and redelivery evidence."""

from __future__ import annotations

import base64
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import paho.mqtt.client as mqtt
import pytest
from botocore.config import Config
from paho.mqtt.enums import CallbackAPIVersion

from herbie.telemetry.topic import DeviceIdentity
from herbie_simulator.mqtt import MQTTDeviceCredentials, MQTTPublishConfig, PahoDeviceConnection
from herbie_simulator.scenario import Scenario, generate_scenario

RUN_SYSTEM_TESTS = os.environ.get("HERBIE_RUN_SYSTEM_TESTS") == "1"
pytestmark = [
    pytest.mark.system,
    pytest.mark.skipif(not RUN_SYSTEM_TESTS, reason="set HERBIE_RUN_SYSTEM_TESTS=1"),
]

ROOT = Path(__file__).resolve().parents[3]
RABBIT_API = "http://127.0.0.1:15672/api"
RABBIT_USER = "herbie"
RABBIT_PASSWORD = "local_only"
DEVICE_PASSWORD = "system-test-device-password"
AMQP_URL = f"amqp://{RABBIT_USER}:{RABBIT_PASSWORD}@127.0.0.1:5672/%2F"
DYNAMODB_ENDPOINT = "http://127.0.0.1:8001"
S3_ENDPOINT = "http://127.0.0.1:9000"
AWS_ACCESS_KEY = "herbie"
AWS_SECRET_KEY = "local_only_change_me"


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 30,
    interval: float = 0.2,
    description: str,
) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception as error:
            last_error = error
        time.sleep(interval)
    detail = f": {last_error}" if last_error else ""
    raise AssertionError(f"timed out waiting for {description}{detail}")


def rabbit_api(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    credentials = base64.b64encode(f"{RABBIT_USER}:{RABBIT_PASSWORD}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{RABBIT_API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise AssertionError(
            f"RabbitMQ API {method} {path} failed: {error.code} {detail}"
        ) from error
    return json.loads(payload) if payload else {}


def queue_state(name: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(name, safe="")
    return rabbit_api("GET", f"/queues/%2F/{encoded}")


def provision_device(identity: DeviceIdentity) -> tuple[str, str]:
    username = f"device-{identity.charger_id}"
    client_id = f"herbie-{identity.charger_id}"
    encoded_user = urllib.parse.quote(username, safe="")
    rabbit_api("PUT", f"/users/{encoded_user}", {"password": DEVICE_PASSWORD, "tags": ""})

    subscription_queue = re.escape(f"mqtt-subscription-{client_id}qos") + r"[01]"
    queue_resources = rf"^(?:amq\.topic|{subscription_queue})$"
    rabbit_api(
        "PUT",
        f"/permissions/%2F/{encoded_user}",
        {
            "configure": rf"^{subscription_queue}$",
            "write": queue_resources,
            "read": queue_resources,
        },
    )
    upstream = re.escape(
        f"herbie.v1.tenants.{identity.tenant_id}.chargers.{identity.charger_id}.up.telemetry"
    )
    downstream = re.escape(
        f"herbie.v1.tenants.{identity.tenant_id}.chargers.{identity.charger_id}.down.commands"
    )
    rabbit_api(
        "PUT",
        f"/topic-permissions/%2F/{encoded_user}",
        {
            "exchange": "amq.topic",
            "write": rf"^{upstream}$",
            "read": rf"^{downstream}$",
        },
    )
    return username, client_id


def worker_environment(
    table: str, bucket: str, identity: DeviceIdentity, role: str
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_KEY,
            "HERBIE_ENVIRONMENT": "system-test",
            "HERBIE_LOG_LEVEL": "INFO",
            "HERBIE_WORKER_ROLE": role,
            "HERBIE_AMQP_URL": AMQP_URL,
            "HERBIE_DYNAMODB_ENDPOINT": DYNAMODB_ENDPOINT,
            "HERBIE_DYNAMODB_REGION": "us-east-1",
            "HERBIE_DYNAMODB_TELEMETRY_TABLE": table,
            "HERBIE_REGISTERED_DEVICES": json.dumps(
                [f"{identity.tenant_id}/{identity.charger_id}"]
            ),
            "HERBIE_S3_ENDPOINT": S3_ENDPOINT,
            "HERBIE_S3_REGION": "us-east-1",
            "HERBIE_S3_BUCKET": bucket,
            "HERBIE_S3_ALLOW_UNSUPPORTED_PUBLIC_ACCESS_BLOCK": "true",
            "HERBIE_ARCHIVE_FLUSH_INTERVAL_SECONDS": "0.2",
            "HERBIE_ARCHIVE_BATCH_LIMIT": "100",
        }
    )
    return environment


def start_worker(environment: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "herbie.worker"],
        cwd=ROOT,
        env=environment,
        text=True,
    )


def stop_process(process: subprocess.Popen[str]) -> str:
    if process.poll() is None:
        process.terminate()
        try:
            output = process.communicate(timeout=10)[0]
            return output or ""
        except subprocess.TimeoutExpired:
            process.kill()
    output = process.communicate(timeout=10)[0]
    return output or ""


def assert_process_running(process: subprocess.Popen[str], role: str) -> bool:
    if process.poll() is None:
        return True
    raise AssertionError(f"{role} exited unexpectedly with {process.returncode}")


def item_count(dynamodb: Any, table: str, kind: str) -> int:
    response = dynamodb.scan(
        TableName=table,
        FilterExpression="#kind = :kind",
        ExpressionAttributeNames={"#kind": "kind"},
        ExpressionAttributeValues={":kind": {"S": kind}},
        Select="COUNT",
    )
    return int(response["Count"])


def mqtt_publish(
    username: str,
    client_id: str,
    topic: str,
    payload: bytes,
) -> bool:
    completed = __import__("threading").Event()
    result = {"accepted": False}
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
        reconnect_on_failure=False,
    )
    client.username_pw_set(username, DEVICE_PASSWORD)

    def on_connect(client: Any, userdata: Any, flags: Any, reason: Any, properties: Any) -> None:
        del userdata, flags, properties
        if getattr(reason, "is_failure", True):
            completed.set()
            return
        client.publish(topic, payload, qos=1, retain=False)

    def on_publish(
        client: Any,
        userdata: Any,
        mid: int,
        reason: Any,
        properties: Any,
    ) -> None:
        del client, userdata, mid, properties
        result["accepted"] = not getattr(reason, "is_failure", True)
        completed.set()

    def on_disconnect(
        client: Any,
        userdata: Any,
        flags: Any,
        reason: Any,
        properties: Any,
    ) -> None:
        del client, userdata, flags, reason, properties
        completed.set()

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect
    client.connect("127.0.0.1", 1883, 30)
    client.loop_start()
    try:
        completed.wait(timeout=5)
        return result["accepted"]
    finally:
        client.disconnect()
        client.loop_stop()


def mqtt_subscribe_allowed(username: str, client_id: str, topic: str) -> bool:
    completed = __import__("threading").Event()
    result = {"allowed": False}
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
        reconnect_on_failure=False,
    )
    client.username_pw_set(username, DEVICE_PASSWORD)

    def on_connect(client: Any, userdata: Any, flags: Any, reason: Any, properties: Any) -> None:
        del userdata, flags, properties
        if getattr(reason, "is_failure", True):
            completed.set()
            return
        client.subscribe(topic, qos=1)

    def on_subscribe(
        client: Any,
        userdata: Any,
        mid: int,
        reasons: list[Any],
        properties: Any,
    ) -> None:
        del client, userdata, mid, properties
        result["allowed"] = bool(reasons) and all(
            not getattr(reason, "is_failure", True) for reason in reasons
        )
        completed.set()

    def on_disconnect(
        client: Any,
        userdata: Any,
        flags: Any,
        reason: Any,
        properties: Any,
    ) -> None:
        del client, userdata, flags, reason, properties
        completed.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.connect("127.0.0.1", 1883, 30)
    client.loop_start()
    try:
        completed.wait(timeout=5)
        return result["allowed"]
    finally:
        client.disconnect()
        client.loop_stop()


@pytest.fixture(scope="module")
def service_readiness() -> Iterator[None]:
    wait_until(
        lambda: bool(rabbit_api("GET", "/overview")),
        timeout=60,
        description="RabbitMQ management API",
    )
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        config=Config(s3={"addressing_style": "path"}),
    )
    wait_until(
        lambda: isinstance(dynamodb.list_tables(), dict),
        timeout=60,
        description="DynamoDB Local",
    )
    wait_until(
        lambda: isinstance(s3.list_buckets(), dict),
        timeout=60,
        description="MinIO",
    )
    yield


def test_mqtt_to_dynamodb_to_s3_acl_dlq_and_redelivery(service_readiness: None) -> None:
    del service_readiness
    suffix = uuid4().hex[:8]
    table = f"herbie-telemetry-system-{suffix}"
    bucket = f"herbie-archive-system-{suffix}"
    publications = list(generate_scenario(Scenario(tenants=1, chargers_per_tenant=2, rounds=2)))
    first = publications[0]
    other_device = publications[1]
    crash_event = publications[2]
    identity = DeviceIdentity(first.event.tenant_id, first.event.charger_id)
    username, client_id = provision_device(identity)
    environment = worker_environment(table, bucket, identity, "telemetry")
    dynamodb = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        config=Config(s3={"addressing_style": "path"}),
    )
    processes: list[subprocess.Popen[str]] = []

    try:
        worker = start_worker(environment)
        processes.append(worker)
        wait_until(
            lambda: (
                assert_process_running(worker, "telemetry worker")
                and int(queue_state("herbie.telemetry.v1").get("consumers", 0)) >= 1
            ),
            timeout=60,
            description="telemetry consumer",
        )

        publisher = PahoDeviceConnection(
            identity,
            MQTTDeviceCredentials(username, DEVICE_PASSWORD),
            MQTTPublishConfig(
                host="127.0.0.1",
                port=1883,
                reconnect_attempts=2,
                connect_timeout_seconds=3,
                publish_timeout_seconds=5,
            ),
            "system-test-seed",
        )
        publisher.publish(first)
        publisher.publish(first)
        publisher.close()
        wait_until(
            lambda: item_count(dynamodb, table, "EVENT") == 1,
            timeout=30,
            description="one duplicate-safe DynamoDB event",
        )

        archive_environment = worker_environment(table, bucket, identity, "archive")
        archive_worker = start_worker(archive_environment)
        processes.append(archive_worker)
        wait_until(
            lambda: (
                assert_process_running(archive_worker, "archive worker")
                and bucket in {item["Name"] for item in s3.list_buckets().get("Buckets", [])}
            ),
            timeout=30,
            description="MinIO archive bucket bootstrap",
        )
        wait_until(
            lambda: (
                assert_process_running(archive_worker, "archive worker")
                and len(s3.list_objects_v2(Bucket=bucket).get("Contents", [])) == 1
            ),
            timeout=30,
            description="one MinIO archive object",
        )
        archive_key = s3.list_objects_v2(Bucket=bucket)["Contents"][0]["Key"]
        archive_body = s3.get_object(Bucket=bucket, Key=archive_key)["Body"].read()
        records = [json.loads(line) for line in gzip.decompress(archive_body).splitlines()]
        assert [record["event"]["message_id"] for record in records] == [
            str(first.event.message_id)
        ]
        stop_process(archive_worker)
        processes.remove(archive_worker)

        stop_process(worker)
        processes.remove(worker)
        wait_until(
            lambda: int(queue_state("herbie.telemetry.v1").get("consumers", 0)) == 0,
            description="telemetry worker shutdown",
        )

        unauthorized = mqtt_publish(
            username,
            client_id,
            other_device.topic,
            other_device.event.model_dump_json(exclude_none=True).encode(),
        )
        assert unauthorized is False
        time.sleep(0.5)
        assert int(queue_state("herbie.telemetry.v1").get("messages_ready", 0)) == 0
        assert item_count(dynamodb, table, "EVENT") == 1

        own_command = (
            f"herbie/v1/tenants/{identity.tenant_id}/chargers/{identity.charger_id}/down/commands"
        )
        other_command = (
            f"herbie/v1/tenants/{other_device.event.tenant_id}/chargers/"
            f"{other_device.event.charger_id}/down/commands"
        )
        assert mqtt_subscribe_allowed(username, client_id, own_command) is True
        assert mqtt_subscribe_allowed(username, client_id, other_command) is False

        worker = start_worker(environment)
        processes.append(worker)
        wait_until(
            lambda: (
                assert_process_running(worker, "telemetry worker")
                and int(queue_state("herbie.telemetry.v1").get("consumers", 0)) >= 1
            ),
            timeout=60,
            description="restarted telemetry consumer",
        )
        assert mqtt_publish(username, client_id, first.topic, b"not-json") is True
        wait_until(
            lambda: int(queue_state("herbie.telemetry.dead.v1").get("messages", 0)) >= 1,
            timeout=30,
            description="malformed telemetry dead letter",
        )
        stop_process(worker)
        processes.remove(worker)

        crash_environment = worker_environment(table, bucket, identity, "telemetry")
        crash_worker = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("crash_before_ack_worker.py"))],
            cwd=ROOT,
            env=crash_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        processes.append(crash_worker)
        assert crash_worker.stdout is not None
        wait_until(
            lambda: (
                crash_worker.stdout is not None
                and crash_worker.stdout.readline().strip() == "CRASH_WORKER_READY"
            ),
            timeout=60,
            description="crash worker readiness",
        )
        crash_publisher = PahoDeviceConnection(
            identity,
            MQTTDeviceCredentials(username, DEVICE_PASSWORD),
            MQTTPublishConfig(host="127.0.0.1", port=1883, reconnect_attempts=2),
            "system-test-seed",
        )
        crash_publisher.publish(crash_event)
        crash_publisher.close()
        assert crash_worker.wait(timeout=30) == 23
        processes.remove(crash_worker)
        wait_until(
            lambda: (
                item_count(dynamodb, table, "EVENT") == 2
                and int(queue_state("herbie.telemetry.v1").get("messages_ready", 0)) == 1
            ),
            timeout=30,
            description="unacknowledged committed delivery",
        )

        worker = start_worker(environment)
        processes.append(worker)
        wait_until(
            lambda: (
                assert_process_running(worker, "telemetry worker")
                and int(queue_state("herbie.telemetry.v1").get("messages", 0)) == 0
            ),
            timeout=60,
            description="idempotent redelivery drain",
        )
        assert item_count(dynamodb, table, "EVENT") == 2
        message_stats = queue_state("herbie.telemetry.v1").get("message_stats", {})
        assert int(message_stats.get("redeliver", 0)) >= 1
    finally:
        for process in reversed(processes):
            stop_process(process)
        rabbit_api("DELETE", f"/users/{urllib.parse.quote(username, safe='')}")
