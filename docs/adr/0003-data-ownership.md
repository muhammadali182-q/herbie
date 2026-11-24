# ADR-0003: Data Ownership by Access Pattern

- Status: Accepted
- Date: 2026-11-24
- Deciders: H.E.R.B.I.E. project team
- Requirements: FR-001, FR-005 through FR-007, QR-010, ER-001
- Clarified by: ADR-0004

## Context

The Assignment 1 architecture names PostgreSQL, DynamoDB, and S3 but does not
define authority, retention, duplicate handling, or cross-store failure. Using
all three without ownership rules would make billing and recovery ambiguous.

## Decision

- PostgreSQL is authoritative for control-plane and financial records.
- DynamoDB stores recent immutable telemetry and latest device state.
- S3 stores compressed batches of raw events and tenant exports.
- Each accepted event has a stable message ID.
- Cross-store work uses retries, conditional writes, an outbox where needed,
  and reconciliation rather than distributed transactions.

## Consequences

- Billing never derives directly from an unbounded scan of raw S3 objects.
- DynamoDB TTL controls hot-storage cost.
- S3 writes must batch many events per compressed object.
- Partial failures are visible as pending/retryable states.
- Tenant scope must be enforced independently in every store and tested.

## Validation

Duplicate and out-of-order fixtures must produce one accepted telemetry event,
one monotonic session checkpoint, and one deterministic charge. A restore and
reconciliation test must explain any difference between stores.
