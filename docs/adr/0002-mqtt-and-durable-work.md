# ADR-0002: MQTT Endpoint and Durable Work Broker

- Status: Accepted for the one-node semester demonstrator
- Date: 2026-11-24
- Deciders: H.E.R.B.I.E. project team
- Requirements: FR-003, FR-005, FR-009, QR-001 through QR-006

## Context

The proposal requires simplified MQTT, duplicate-safe processing, commands,
worker scaling, and recovery after a worker failure. Two unrelated MQTT
containers behind a network load balancer do not replicate subscriptions,
session state, or queued work.

## Proposed Decision

Validate RabbitMQ with its MQTT plugin as both the charger endpoint and durable
internal work broker. Chargers use MQTT QoS 1. Workers consume durable AMQP
queues, and commands are routed back to charger MQTT topics.

The semester demonstrator may use one broker node and must label it as a single
point of failure. A production target needs three voting nodes across failure
domains or a managed MQTT service.

## Alternatives Considered

| Alternative | Trade-off |
|---|---|
| Mosquitto plus a separate work queue | Smaller MQTT footprint but adds another delivery bridge and product |
| EMQX cluster | MQTT-focused clustering but introduces another operational model to validate |
| AWS IoT Core | Managed availability and easy elasticity but high per-message cost at the proposed rate |

## Spike Acceptance Criteria

- TLS-authenticated simulated charger can publish and receive a command.
- Topic identity and payload identity mismatch is rejected.
- QoS 1 duplicate delivery is processed idempotently.
- A worker crash returns unacknowledged work to another worker.
- Control work is isolated from telemetry backlog.
- Resource use is acceptable on the selected demo environment.

If the spike fails within the allocated timebox, use Mosquitto for the device
edge and a separate durable queue, then record the replacement ADR.

## Implementation Progress

The application adapter now declares separate telemetry and control queues, a
dead-letter exchange and queue, and a bounded TTL retry path. It consumes with
manual acknowledgements and prefetch 100, confirms retry publications, and
ACKs valid or duplicate events only after DynamoDB acceptance. A separate
process role drains the archive outbox.

Hosted run
[`45697561268`](https://github.com/muhammadali182-q/herbie/actions/runs/45697561268)
accepts RabbitMQ for the one-node semester demonstrator. Its real-service test
proved exact topic and resource authorization, duplicate-safe DynamoDB writes,
canonical MinIO archival, worker redelivery, dead lettering, and command-topic
subscription isolation.

This acceptance does not close every target criterion. TLS transport is
configurable but has not completed a broker-backed system test. The command
test covers subscription authorization rather than a domain command round trip,
and resource use is not yet measured under the declared workload. Those items
remain required before selecting the same topology for a cloud or production
profile.
