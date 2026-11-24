# Semester Implementation Plan

The implementation is timeboxed to fifteen working days because fewer than
three weeks remain. Infrastructure and dashboard work may proceed in parallel
after the contracts are fixed.

| Phase | Target | Deliverables | Exit gate |
|---|---|---|---|
| 0. Scope and governance | Day 1 | Scope, requirements, traceability, ADRs, risk register, journal | Every mandatory concern maps to evidence |
| 1. Reproducible foundation | Days 1-2 | Monorepo, pinned tools, local services, API/worker/web skeleton, CI | Clean setup and fast checks succeed |
| 2. Telemetry walking skeleton | Days 3-4 | Simulator, MQTT contract, ingestion, hot storage, archive, fleet view | One duplicate-safe event travels end to end |
| 3. Safe multi-tenancy | Days 5-6 | Identity, tenant context, RLS, broker ACLs, configuration | Cross-tenant negative matrix passes |
| 4. Sessions and allocation | Days 7-8 | State machine, outbox, commands, allocation algorithm | Session and allocation invariants pass |
| 5. Metering and billing | Days 9-10 | Checkpoints, tariff snapshots, charges, usage invoices | Golden reconciliation is exact and repeatable |
| 6. Cloud operations | Days 11-12 | Terraform profiles, monitoring, backup, rollback, teardown | Cost-controlled deploy and destroy are reproducible |
| 7. Quantitative evidence | Days 13-14 | Load, isolation, failure, upgrade, security, EOL, economics | Evidence index links raw results to a fixed commit |
| 8. Demonstration and report | Day 15 | Demo script, final report, contribution record, release | A non-author can execute the documented demo |

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
