"""CLI for inspecting deterministic simulator output."""

import argparse
import sys
from collections.abc import Sequence

from herbie_simulator.scenario import Scenario, generate_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate H.E.R.B.I.E. charger telemetry")
    parser.add_argument("--tenants", type=int, default=3)
    parser.add_argument("--chargers-per-tenant", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--interval-seconds", type=int, default=10)
    parser.add_argument("--seed", default="herbie-demo-v1")
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
