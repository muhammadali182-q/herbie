"""CLI for inspecting deterministic simulator output."""

import argparse
import os
import sys
from collections.abc import Sequence

from herbie_simulator.mqtt import (
    MQTTProtocol,
    MQTTPublishConfig,
    MQTTPublishError,
    ReportingMode,
    TemplateCredentialProvider,
    publish_scenario,
)
from herbie_simulator.scenario import Scenario, generate_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate H.E.R.B.I.E. charger telemetry")
    parser.add_argument("--tenants", type=int, default=3)
    parser.add_argument("--chargers-per-tenant", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument("--seed", default="herbie-demo-v1")
    parser.add_argument("--mqtt", action="store_true", help="Publish with MQTT QoS 1")
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument(
        "--mqtt-protocol", choices=[item.value for item in MQTTProtocol], default="5"
    )
    parser.add_argument("--connection-count", type=int)
    parser.add_argument("--connection-workers", type=int, default=64)
    parser.add_argument("--message-rate", type=float, default=200.0)
    parser.add_argument("--mqtt-connect-timeout", type=float, default=10.0)
    parser.add_argument("--mqtt-publish-timeout", type=float, default=10.0)
    parser.add_argument("--mqtt-reconnect-min-delay", type=float, default=0.25)
    parser.add_argument("--mqtt-reconnect-max-delay", type=float, default=30.0)
    parser.add_argument("--mqtt-reconnect-attempts", type=int, default=8)
    parser.add_argument(
        "--reporting-mode",
        choices=[item.value for item in ReportingMode],
        default=ReportingMode.JITTERED.value,
    )
    parser.add_argument("--mqtt-tls", action="store_true")
    parser.add_argument("--mqtt-ca-file")
    parser.add_argument("--mqtt-cert-file")
    parser.add_argument("--mqtt-key-file")
    parser.add_argument(
        "--mqtt-username-template",
        default="device-{charger_id}",
        help="Supports {tenant_id} and {charger_id}",
    )
    parser.add_argument(
        "--mqtt-password-env",
        default="HERBIE_SIMULATOR_MQTT_PASSWORD",
        help="Environment variable containing the broker password",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print counts instead of newline-delimited publication records",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    try:
        scenario = Scenario(
            tenants=args.tenants,
            chargers_per_tenant=args.chargers_per_tenant,
            rounds=args.rounds,
            interval_seconds=args.interval_seconds,
            seed=args.seed,
        )
    except ValueError as error:
        print(f"invalid scenario: {error}", file=sys.stderr)
        return 2

    if args.mqtt and args.summary:
        print("invalid scenario: --mqtt and --summary cannot be combined", file=sys.stderr)
        return 2

    if args.mqtt:
        password = os.environ.get(args.mqtt_password_env)
        if password is None:
            print(
                f"MQTT password environment variable {args.mqtt_password_env} is not set",
                file=sys.stderr,
            )
            return 2
        try:
            config = MQTTPublishConfig(
                host=args.mqtt_host,
                port=args.mqtt_port,
                protocol=MQTTProtocol(args.mqtt_protocol),
                connection_count=args.connection_count,
                connection_workers=args.connection_workers,
                message_rate=args.message_rate,
                reporting_mode=ReportingMode(args.reporting_mode),
                connect_timeout_seconds=args.mqtt_connect_timeout,
                publish_timeout_seconds=args.mqtt_publish_timeout,
                reconnect_min_delay_seconds=args.mqtt_reconnect_min_delay,
                reconnect_max_delay_seconds=args.mqtt_reconnect_max_delay,
                reconnect_attempts=args.mqtt_reconnect_attempts,
                tls_enabled=args.mqtt_tls,
                tls_ca_file=args.mqtt_ca_file,
                tls_cert_file=args.mqtt_cert_file,
                tls_key_file=args.mqtt_key_file,
            )
            credentials = TemplateCredentialProvider(args.mqtt_username_template, password)
            result = publish_scenario(scenario, config, credentials)
        except (MQTTPublishError, ValueError) as error:
            print(f"MQTT publication failed: {error}", file=sys.stderr)
            return 1
        print(
            f"represented_devices={result.represented_devices} "
            f"connected_clients={result.connected_clients} "
            f"offered={result.offered_messages} "
            f"pubacknowledged={result.pubacknowledged_messages} "
            f"failed={result.failed_messages} "
            "durable_ingestion=not_measured "
            f"elapsed_seconds={result.elapsed_seconds:.3f}"
        )
        return 0

    publications = generate_scenario(scenario)
    if args.summary:
        total = scenario.tenants * scenario.chargers_per_tenant * scenario.rounds
        print(
            f"tenants={scenario.tenants} "
            f"chargers={scenario.tenants * scenario.chargers_per_tenant} "
            f"events={total} interval_seconds={scenario.interval_seconds}"
        )
        return 0

    for publication in publications:
        print(
            publication.event.model_dump_json(exclude_none=True),
            "\t",
            publication.topic,
            sep="",
        )
    return 0


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
