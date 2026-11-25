# Requirements Traceability

Status values are `Planned`, `Implemented`, `Verified`, `Deferred`, or
`Out of scope`. A status applies only to the boundary stated in its evidence;
component evidence does not verify an unfinished parent requirement.

| Requirement | Design owner | Planned implementation | Planned verification | Status and evidence |
|---|---|---|---|---|
| FR-001 Tenant isolation | ADR-0003, tenancy architecture | Identity-derived tenant context, PostgreSQL RLS, scoped data keys, broker ACLs | API, repository, database, export, and MQTT negative tests | Implemented and verified for exact per-device MQTT topic denial only; PostgreSQL, API, and export isolation remain planned. See [MQTT ingestion evidence][mqtt-evidence] |
| FR-002 Tenant configuration | Domain architecture | Tenant, site, charger, tariff, maintenance, and alert APIs | Three-tenant end-to-end scenario | Planned |
| FR-003 Sessions | Session state ADR to be added | Transactional session state machine and idempotency keys | Unit, concurrency, duplicate, and end-to-end tests | Planned |
| FR-004 Power allocation | Allocation ADR to be added | Integer weighted max-min allocation with serialized site decisions | Property and concurrent command tests | Planned |
| FR-005 Telemetry and metering | ADR-0002, ADR-0003, ADR-0004 | Versioned MQTT messages, conditional inserts, monotonic meter checkpoints | Duplicate, stale, reset, and ordering fixtures | Verified for MQTT transport, duplicate-safe persistence, and canonical local archive; session metering remains planned. See [telemetry storage evidence][telemetry-evidence] and [MQTT ingestion evidence][mqtt-evidence] |
| FR-006 Session charges | Billing ADR to be added | Immutable tariff versions and integer currency calculation | Golden billing fixtures | Planned |
| FR-007 Platform invoices | Billing ADR to be added | Unique period invoice and reconciled usage counters | Repeated generation and reconciliation tests | Planned |
| FR-008 Dashboard | UI architecture to be added | Responsive operator dashboard over tenant-scoped API | Browser workflow and cross-tenant tests | Planned |
| FR-009 Commands | ADR-0002 | Transactional outbox and versioned commands | Crash, duplicate, expiry, and stale-version tests | Planned |
| FR-010 Offboarding | Lifecycle runbook | Export, final invoice, revoke, delete, retention report | Synthetic tenant EOL drill | Planned |
| QR-001 Charger representation | Performance plan | Deterministic distributed simulator | Identity-count, concurrent-connection, and generator-limit evidence | Implemented for deterministic logical generation and configurable MQTT clients; 2,000 concurrent connections remain unverified. See [telemetry storage evidence][telemetry-evidence] |
| QR-002 Baseline rate | Performance plan | Instrumented MQTT workload | 200 messages/second for at least 30 minutes | Planned |
| QR-003 Peak rate | Performance plan | Instrumented MQTT workload | 1,000 messages/second for at least five minutes or measured limit | Planned |
| QR-004 Authorization latency | Performance plan | Instrumented authorization path | p50, p95, p99, and errors under declared normal load | Planned |
| QR-005 Resilience | Deployment architecture | Replicated stateless processes and at-least-once work | Forced process termination under load | Implemented and verified for one worker death after commit and before ACK; API failure and under-load recovery remain planned. See [MQTT ingestion evidence][mqtt-evidence] |
| QR-006 Noisy neighbor | Tenancy architecture | Quotas, bounded workers, separate control and telemetry work | Hot-tenant paired control experiment | Planned |
| QR-007 Observability | Operations architecture | Structured logs, metrics, health, dashboards, alerts | Alert and incident drill | Planned |
| QR-008 Deployment | Infrastructure ADR to be added | Docker definitions, Terraform profiles, CI deployment | Fresh deploy and destroy run | Planned; local definitions and image builds are implemented |
| QR-009 Evolution | Upgrade runbook | Versioned contracts and expand-migrate-contract changes | N/N+1 compatibility and rollback | Planned |
| QR-010 Restore | Backup runbook | Database backup and isolated restore | Restore and record reconciliation | Planned |
| QR-011 Security | Threat model to be added | TLS, secrets, least privilege, validation, audit | Secret, dependency, authorization, and configuration scans | Implemented for strict validation, secret scanning, and exact demo topic/resource ACLs; TLS system evidence and complete threat model remain planned. See [MQTT ingestion evidence][mqtt-evidence] |
| QR-012 Elasticity | Scaling plan | Queue-age-driven worker scaling in target profile | Scale timeline and task-hour comparison | Planned |
| ER-001 to ER-004 Economics | Economic model | Versioned assumptions and formulas | Recalculation and actual-versus-model review | Planned |
| LC-001 to LC-003 Lifecycle | Runbooks and final report | Responsibility, incident, upgrade, offboarding, and teardown procedures | Timed operational drills | Planned |

## Verified Telemetry Components

| Component | Status | Evidence boundary |
|---|---|---|
| Strict telemetry contract and trusted identity boundary | Verified | Unit and service tests reject malformed, mismatched, stale, conflicting, and future-skewed input; no broker ACL claim |
| Deterministic simulator | Verified | Stable multi-tenant logical publications, expected energy vectors, MQTT client IDs, pacing, reconnects, and PUBACK accounting; no connection-scale or throughput claim |
| DynamoDB adapter | Verified | Moto-backed transaction, ordering, replay, TTL-configuration, and bootstrap tests; no DynamoDB Local or AWS claim |
| S3 adapter | Verified | Moto-backed immutable encrypted writes, checksum retry, and public-access configuration tests; no MinIO or AWS claim |
| Archive outbox and canonical batching | Verified | Atomic archive-pending state and deterministic gzip NDJSON flushing; runtime scheduling and global exactly-once membership are not claimed |

The fixed implementation baseline is commit [`8dccb85`][storage-commit]. Hosted
verification is GitHub Actions run [`45566373644`][storage-ci].

## CLO Mapping

| Deliverable | CLO | Traceable project evidence |
|---|---|---|
| D1 Problem, feasibility, architecture | CLO-3 primary, CLO-2 supporting | Original PDF plus the assumption review and updated architecture decisions |
| D2 Technical design, elasticity, economics | CLO-2 primary, CLO-3 supporting | ADRs, contracts, workload model, performance plan, and economic model |
| D3 Prototype and demonstration | CLO-4 primary, CLO-2 supporting | Fixed release, automated tests, cloud deployment, raw measurements, and demo script |
| D4 Final lifecycle evaluation | CLO-3 primary, CLO-2 supporting | Final traceability, measured-versus-modeled analysis, operations, evolution, and EOL evidence |

[storage-ci]: https://github.com/muhammadali182-q/herbie/actions/runs/45566373644
[storage-commit]: https://github.com/muhammadali182-q/herbie/commit/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf
[telemetry-evidence]: ../evidence/telemetry-storage-baseline.md
[mqtt-evidence]: ../evidence/mqtt-ingestion-baseline.md
