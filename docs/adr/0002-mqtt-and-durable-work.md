# ADR-0002: MQTT Endpoint and Durable Work Broker

- Status: Proposed
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
