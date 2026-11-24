# Requirements Traceability

Status values are `Planned`, `Implemented`, `Verified`, `Deferred`, or
`Out of scope`. Evidence links will be filled as vertical slices are completed.

| Requirement | Design owner | Planned implementation | Planned verification | Status |
|---|---|---|---|---|
| FR-001 Tenant isolation | ADR-0003, tenancy architecture | Identity-derived tenant context, PostgreSQL RLS, scoped data keys, broker ACLs | API, repository, database, export, and MQTT negative tests | Planned |
| FR-002 Tenant configuration | Domain architecture | Tenant, site, charger, tariff, maintenance, and alert APIs | Three-tenant end-to-end scenario | Planned |
| FR-003 Sessions | Session state ADR to be added | Transactional session state machine and idempotency keys | Unit, concurrency, duplicate, and end-to-end tests | Planned |
| FR-004 Power allocation | Allocation ADR to be added | Integer weighted max-min allocation with serialized site decisions | Property and concurrent command tests | Planned |
| FR-005 Telemetry and metering | ADR-0002, ADR-0003 | Versioned MQTT messages, conditional inserts, monotonic meter checkpoints | Duplicate, stale, reset, and ordering fixtures | Planned |
| FR-006 Session charges | Billing ADR to be added | Immutable tariff versions and integer currency calculation | Golden billing fixtures | Planned |
| FR-007 Platform invoices | Billing ADR to be added | Unique period invoice and reconciled usage counters | Repeated generation and reconciliation tests | Planned |
| FR-008 Dashboard | UI architecture to be added | Responsive operator dashboard over tenant-scoped API | Browser workflow and cross-tenant tests | Planned |
| FR-009 Commands | ADR-0002 | Transactional outbox and versioned commands | Crash, duplicate, expiry, and stale-version tests | Planned |
| FR-010 Offboarding | Lifecycle runbook | Export, final invoice, revoke, delete, retention report | Synthetic tenant EOL drill | Planned |
| QR-001 to QR-004 Scale and latency | Performance plan | Deterministic distributed simulator and instrumented paths | Baseline, peak, burst, and authorization runs | Planned |
| QR-005 Resilience | Deployment architecture | Replicated stateless processes and at-least-once work | Forced process termination under load | Planned |
| QR-006 Noisy neighbor | Tenancy architecture | Quotas, bounded workers, separate control and telemetry work | Hot-tenant paired control experiment | Planned |
| QR-007 Observability | Operations architecture | Structured logs, metrics, health, dashboards, alerts | Alert and incident drill | Planned |
| QR-008 Deployment | Infrastructure ADR to be added | Docker definitions, Terraform profiles, CI deployment | Fresh deploy and destroy run | Planned |
| QR-009 Evolution | Upgrade runbook | Versioned contracts and expand-migrate-contract changes | N/N+1 compatibility and rollback | Planned |
| QR-010 Restore | Backup runbook | Database backup and isolated restore | Restore and record reconciliation | Planned |
| QR-011 Security | Threat model to be added | TLS, secrets, least privilege, validation, audit | Secret, dependency, authorization, and configuration scans | Planned |
| QR-012 Elasticity | Scaling plan | Queue-age-driven worker scaling in target profile | Scale timeline and task-hour comparison | Planned |
| ER-001 to ER-004 Economics | Economic model | Versioned assumptions and formulas | Recalculation and actual-versus-model review | Planned |
| LC-001 to LC-003 Lifecycle | Runbooks and final report | Responsibility, incident, upgrade, offboarding, and teardown procedures | Timed operational drills | Planned |

## CLO Mapping

| Deliverable | CLO | Traceable project evidence |
|---|---|---|
| D1 Problem, feasibility, architecture | CLO-3 primary, CLO-2 supporting | Original PDF plus the assumption review and updated architecture decisions |
| D2 Technical design, elasticity, economics | CLO-2 primary, CLO-3 supporting | ADRs, contracts, workload model, performance plan, and economic model |
| D3 Prototype and demonstration | CLO-4 primary, CLO-2 supporting | Fixed release, automated tests, cloud deployment, raw measurements, and demo script |
| D4 Final lifecycle evaluation | CLO-3 primary, CLO-2 supporting | Final traceability, measured-versus-modeled analysis, operations, evolution, and EOL evidence |
