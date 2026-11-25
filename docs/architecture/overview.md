# Architecture Overview

## Architectural Style

H.E.R.B.I.E. uses a modular monolith with independently runnable process roles.
One domain package supplies an HTTP API, asynchronous workers, scheduled jobs,
and test tooling. This keeps business invariants consistent while preserving
the ability to scale stateless work independently.

```text
Simulated chargers
        |
   MQTT over TLS
        |
 MQTT-capable broker
        |
 control and telemetry workers
    |          |          |
PostgreSQL  DynamoDB     S3
    |
 FastAPI API ---- React operator dashboard
```

## Logical Modules

| Module | Responsibility |
|---|---|
| Identity and tenancy | Human/device identity, memberships, roles, tenant context, audit |
| Fleet | Sites, chargers, connectors, maintenance, operational status |
| Sessions | Authorization and charging-session state machine |
| Smart charging | Site policy, allocation runs, commands, acknowledgements |
| Telemetry | Message validation, deduplication, current state, hot readings |
| Tariffs and billing | Immutable prices, meter reconciliation, session charges, invoices |
| Alerts | Fault/offline rules, deduplication, acknowledgement |
| Operations | Health, metrics, logs, jobs, backup, upgrade, and EOL procedures |

Modules communicate through explicit application commands, queries, and domain
events rather than modifying each other's tables directly.

## Data Ownership

| Store | Authoritative data | Prototype retention |
|---|---|---|
| PostgreSQL | Tenants, fleet, policies, sessions, commands, tariffs, charges, invoices, audit | Long-lived according to lifecycle policy |
| DynamoDB | Recent immutable telemetry, per-connector latest state, archive outbox, and compact replay tombstones | Events: 7 to 14 days; replay markers: at least 180 days |
| S3 | Compressed, batched canonical validated-event archive and exports | 90 days for the project model |

The system assumes at-least-once delivery. Stable message and command IDs,
conditional writes, monotonic checkpoints, and reconciliation make duplicates
safe. There is no distributed transaction across the three stores.

An accepted telemetry write atomically creates both the immutable hot event and
an archive-pending record. A separate worker creates deterministic tenant/hour
objects, then records the object key and checksum. Failed object writes remain
visible for retry and reconciliation.

RabbitMQ's MQTT plugin translates slash-separated MQTT topics into dot-separated
`amq.topic` routing keys. The telemetry worker consumes the durable classic
`herbie.telemetry.v1` queue with prefetch 100 and manual acknowledgements. It
reverses that transport mapping, confirms the route in a fail-closed device
registry, validates the payload identity, and ACKs only after the DynamoDB
transaction succeeds or confirms an exact duplicate. Contract, identity,
clock, and identity-conflict failures are rejected to
`herbie.telemetry.dead.v1`.

Storage failures are republished with publisher confirmation through a bounded
TTL retry queue before the original delivery is ACKed. Retry attempts are read
from broker-owned `x-death` metadata rather than a device-controlled header.
The one-node demo uses classic queues and remains non-HA. The target profile
requires a three-node quorum queue; that topology is documented, not deployed
or measured.

The simulator keeps deterministic logical event generation separate from MQTT
transport. Each selected charger receives a stable client ID and broker login,
publishes at QoS 1, and counts PUBACKs independently from worker receipts or
durable writes. Synchronized mode creates phase-aligned bursts; jittered mode
uses seed-derived timer offsets. Connection count and offered message rate are
reported separately so represented identities are not mislabeled as concurrent
connections.

Archive objects are idempotent by content, not a claim of global exactly-once
membership. The current slice serializes one in-process archive scheduler;
multi-process archive workers require a durable batch-claim manifest before
horizontal scaling. Stable message IDs make overlap detectable and safe to
deduplicate during reconciliation.

## Deployment Profiles

| Profile | Intended evidence | Explicit limitation |
|---|---|---|
| Local | Functional correctness, integration, load generation, deterministic reset | Does not prove cloud availability |
| Demo-lite | Actual cloud hosting, managed storage, monitoring, deployment and teardown | May use single-node stateful services and cannot claim multi-AZ HA |
| Target | Multi-AZ stateless services, broker quorum or managed MQTT, Multi-AZ PostgreSQL, scaling and encryption | Modeled unless temporarily deployed and measured |

## Security Boundaries

- Human users authenticate through an OIDC-compatible identity provider.
- Tenant membership, not a client-supplied tenant ID, establishes tenant
  context.
- PostgreSQL RLS is defense in depth and uses a non-owner application role.
- Each charger can publish only to its own upstream topics and subscribe only
  to its own downstream topics.
- Tenant-owned DynamoDB keys and S3 prefixes are mandatory in repository APIs.
- Secrets and cloud state are never stored in Git.

## Availability Language

The target architecture is designed to support a 99.9% control-plane
objective. The project will measure individual recovery behavior and synthetic
probe results. It will not claim statistically proven annual availability from
a short test window.
