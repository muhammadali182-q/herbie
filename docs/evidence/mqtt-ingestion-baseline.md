# MQTT Ingestion Baseline Evidence

## Identity

| Field | Value |
|---|---|
| Implementation commit | [`d1f3ba5f2287352b185112cb7831e616a7986caf`](https://github.com/muhammadali182-q/herbie/commit/d1f3ba5f2287352b185112cb7831e616a7986caf) |
| Hosted run | [`45697561268`](https://github.com/muhammadali182-q/herbie/actions/runs/45697561268) |
| System job | [`139498829983`](https://github.com/muhammadali182-q/herbie/actions/runs/45697561268/job/139498829983) |
| Branch | `feat/mqtt-ingestion` |
| Run date | 2026-11-25 UTC |
| Hosted environment | GitHub-hosted Ubuntu 26.04.1, Python 3.12.16, uv 0.11.26 |

## Measured Results

All six quality jobs passed: backend, frontend, documentation, containers,
secret scan, and MQTT system. The normal backend job collected 144 tests: 143
passed, the opt-in system test was skipped as designed, and total branch
coverage was 93.08% against a 90% gate.

The separate MQTT system job started RabbitMQ 4.1.4, DynamoDB Local 2.6.1, and
MinIO `2025.7.23`. Its one end-to-end procedure passed in 37.19 seconds and then
removed containers, volumes, and the test network.

The procedure demonstrated:

- one device-authenticated MQTT QoS 1 event reaching DynamoDB;
- one immutable canonical gzip NDJSON object in MinIO;
- duplicate publication producing one event and one logical archive membership;
- a worker process exiting after DynamoDB commit and before ACK;
- RabbitMQ redelivery followed by duplicate-safe drain;
- malformed input reaching `herbie.telemetry.dead.v1`;
- Device A publishing successfully to Device A's exact topic;
- Device A being denied publication to Device B's topic;
- no denied publication reaching `herbie.telemetry.v1` or DynamoDB;
- Device A subscribing to its own command topic and being denied Device B's;
- simultaneous ordinary resource permissions and exact `amq.topic` permissions;
  and
- disposable user, container, volume, and network cleanup.

## Evidence Classification

The CI timings and observed service behavior are measured in the stated hosted
environment. The test uses a single RabbitMQ node and classic queues; it does
not demonstrate HA, quorum behavior, elasticity, production scale, or annual
availability.

MinIO lacks AWS public-access-block support and ran without a KMS. Explicit
local-only compatibility settings were enabled. Default production behavior
still requests encryption and fails closed when public-access controls cannot
be applied. This run is functional S3-compatibility evidence, not encryption or
AWS evidence.

TLS configuration, a command payload round trip, broker restart, 2,000
connections, 200 messages/second duration, 1,000 messages/second peak, and
provider resource usage remain separate evidence requirements.
