# Telemetry Storage Baseline Evidence

## Identity

| Field | Value |
|---|---|
| Implementation commit | [`8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf`](https://github.com/muhammadali182-q/herbie/commit/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf) |
| Hosted run | [`45566373644`](https://github.com/muhammadali182-q/herbie/actions/runs/45566373644) |
| Branch | `feat/telemetry-slice` |
| Run date | 2026-11-25 UTC |
| Hosted environment | GitHub-hosted Ubuntu 26.04.1, Python 3.12.16, uv 0.11.26 |

## Results

All five hosted jobs passed: secret scan, backend, documentation, frontend, and
containers. The backend collected 80 tests and reported 92.56% total branch
coverage against a 90% gate. Ruff, formatting, strict mypy, dependency-lock
verification, Markdown lint, frontend tests/build, Compose validation, and both
container builds passed.

The implementation and tests cover:

- strict, canonical telemetry envelopes and topic/payload identity checks;
- duplicate, message-ID, boot-ID, and sequence-ID conflict handling;
- explicit same-boot and cross-boot ordering;
- deterministic multi-tenant simulator publications;
- DynamoDB transaction composition, replay markers, latest state, archive
  pending state, TTL configuration, and schema validation;
- canonical gzip NDJSON batching and receipt recording; and
- immutable encrypted S3 writes with checksum-verified retry behavior.

Primary test sources at the fixed commit are:

- [`test_contracts.py`](https://github.com/muhammadali182-q/herbie/blob/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf/backend/tests/telemetry/test_contracts.py)
- [`test_ingestion.py`](https://github.com/muhammadali182-q/herbie/blob/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf/backend/tests/telemetry/test_ingestion.py)
- [`test_archive.py`](https://github.com/muhammadali182-q/herbie/blob/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf/backend/tests/telemetry/test_archive.py)
- [`test_durable_adapters.py`](https://github.com/muhammadali182-q/herbie/blob/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf/backend/tests/telemetry/test_durable_adapters.py)
- [`test_scenario.py`](https://github.com/muhammadali182-q/herbie/blob/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf/simulator/tests/test_scenario.py)

## Evidence Classification

The hosted test and coverage results are measured. Storage behavior is measured
against Moto 5.2.6, not against AWS. Retention periods and the target deployment
topology are configured or modeled assumptions rather than observed provider
behavior.

This baseline does not establish MQTT connectivity, broker authorization,
worker redelivery, DynamoDB Local concurrency, MinIO compatibility, AWS
durability or availability, 2,000 concurrent connections, declared throughput,
or global exactly-once archive membership. Those claims require separate system
or provider evidence.
