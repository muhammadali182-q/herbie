# Semester Implementation Plan

Phases express dependency order rather than calendar-day commitments.
Infrastructure and dashboard work may proceed in parallel after their contracts
and security boundaries are fixed.

| Phase | Status | Deliverables | Exit gate or current boundary |
|---|---|---|---|
| 0. Scope and governance | Completed | Scope, requirements, traceability, ADRs, risk register, journal | Mandatory concerns have stable IDs and evidence rules; named operational ownership remains follow-up work |
| 1. Reproducible foundation | Completed | Monorepo, pinned tools, local services, API/worker/web skeleton, CI | Clean setup and hosted quality checks succeed |
| 2. Telemetry storage slice | Completed | Deterministic simulator, strict MQTT contract, duplicate-safe ingestion core, hot storage, archive outbox | Direct ingestion and Moto-backed durable adapters are verified at [`8dccb85`](https://github.com/muhammadali182-q/herbie/commit/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf); broker transport is not claimed |
| 3. MQTT system integration | In progress | Authenticated endpoint, durable queues, worker ACK policy, MQTT simulator, local-service tests | One duplicate-safe event travels MQTT to DynamoDB and S3; ACL, redelivery, and DLQ tests pass |
| 4. Safe multi-tenancy | Planned | Identity, tenant context, PostgreSQL RLS, configuration APIs | Cross-tenant negative matrix passes |
| 5. Dashboard integration | Planned | OIDC-compatible authentication and tenant-scoped live workflows | Seeded tenant data renders without cross-tenant leakage |
| 6. Sessions and allocation | Planned | State machine, outbox, commands, allocation algorithm | Session and allocation invariants pass |
| 7. Metering and billing | Planned | Checkpoints, tariff snapshots, charges, usage invoices | Golden reconciliation is exact and repeatable |
| 8. Cloud operations | Planned | Terraform profiles, monitoring, backup, rollback, teardown | Cost-controlled deploy and destroy are reproducible |
| 9. Evidence and release | Planned | Load, isolation, failure, upgrade, security, EOL, economics, demo, report | Evidence links raw results to a fixed release and a non-author can run the demo |

## Parallel Workstreams

| Workstream | Primary output |
|---|---|
| Domain and API | Tenancy, sessions, allocation, billing |
| Messaging and simulation | MQTT contracts, simulator, workers, load generation |
| Dashboard and evidence | Operator workflows, charts, demo, evidence index |
| Cloud and operations | Infrastructure, monitoring, runbooks, economics, lifecycle |

Every workstream requires a second reviewer. Team ownership will be recorded
after members confirm availability and GitHub identities.

## Stop/Go Gates

| Gate | Go condition | Fallback |
|---|---|---|
| G0 Scope | Requirements and non-goals approved | Do not add implementation scope |
| G1 Messaging | MQTT spike passes protocol and redelivery checks | Use Mosquitto plus a separate durable queue |
| G2 Isolation | Cross-tenant matrix passes | Block dependent demo work |
| G3 Allocation | Site-limit properties pass | Cut optional UI and alerts, not safety |
| G4 Billing | Reconciliation is exact | Do not present invoice claims |
| G5 Cloud safety | Budget, identity, plan, rollback, and destroy reviewed | Use local evidence and modeled target architecture |
| G6 Evidence | Results identify commit, environment, workload, and limitations | Reduce claims to the measured boundary |

## Scope Reduction Order

If the schedule slips, reduce work in this order:

1. Visual polish and nonessential charts.
2. Advanced alert customization.
3. Sophisticated tariffs beyond energy plus fixed fee.
4. Dynamic device credential provisioning.
5. Deployed stateful broker clustering.

Tenant isolation, allocation correctness, billing correctness, reproducibility,
secret safety, evidence, and teardown are not optional.
