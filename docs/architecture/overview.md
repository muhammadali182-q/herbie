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
| DynamoDB | Recent immutable telemetry and latest charger state | 7 to 14 days with TTL |
| S3 | Compressed, batched raw event archive and exports | 90 days for the project model |

The system assumes at-least-once delivery. Stable message and command IDs,
conditional writes, monotonic checkpoints, and reconciliation make duplicates
safe. There is no distributed transaction across the three stores.

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
