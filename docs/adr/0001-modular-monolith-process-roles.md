# ADR-0001: Modular Monolith with Process Roles

- Status: Accepted
- Date: 2026-11-24
- Deciders: H.E.R.B.I.E. project team
- Requirements: FR-001 through FR-010, QR-005, QR-008, QR-009

## Context

The project needs independently scalable ingestion and HTTP workloads, but the
team has less than three weeks, limited cloud budget, and one tightly connected
domain. Independent microservices would add contract, deployment, tracing, and
failure-management work before the core invariants are proven.

## Decision

Use one Python domain and application package with independently runnable API,
control-worker, telemetry-worker, scheduled-job, and simulator entry points.
Build one immutable backend image and select the process role at startup.

## Alternatives Considered

| Alternative | Reason not selected |
|---|---|
| Independent microservices for every capability | Excessive operations and distributed-consistency risk for the schedule |
| One synchronous web process | Telemetry bursts and long-running work would interfere with control requests |
| Serverless functions for every event | Per-message cost and fragmented local testing conflict with the workload and economic hypothesis |

## Consequences

- Business invariants and migrations remain in one codebase.
- API and workers can still scale separately.
- Module boundaries require tests and import rules because process separation
  does not enforce them automatically.
- A module may be extracted only when measured load or ownership justifies it.

## Validation

The decision is valid if one codebase can run each process independently and
load tests show that telemetry work does not block authorization work.
