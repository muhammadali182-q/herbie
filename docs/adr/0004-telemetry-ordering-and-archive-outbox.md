# ADR-0004: Telemetry Ordering and Canonical Archive Outbox

- Status: Accepted
- Date: 2026-11-24
- Deciders: H.E.R.B.I.E. project team
- Requirements: FR-001, FR-005, QR-005, QR-010, ER-001

## Context

MQTT QoS 1 can redeliver events, device clocks can move, multiple connectors
share a charger, and a charger can reboot. Object storage only supports whole
immutable objects efficiently, so an event-level append cannot represent a
durable batched archive. Treating a random UUID or device timestamp as total
chronology would corrupt latest state under delayed delivery.

## Decision

- A trusted broker principal, exact topic identity, and payload identity must
  agree before persistence.
- Latest state is keyed by tenant, charger, and connector.
- Within a boot, sequence determines chronology.
- Across boots, explicit `boot_started_at` determines chronology.
- `(tenant, charger, connector, boot, sequence)` has one message identity.
- Message semantic equality uses a versioned sorted-JSON SHA-256 fingerprint.
- Accepting an event atomically creates an archive-pending record.
- A separate worker groups pending canonical records by tenant and UTC hour,
  writes deterministic gzip NDJSON objects, then stores object receipts.
- Object-write failure leaves durable pending state for retry and reconciliation.

## Alternatives Considered

| Alternative | Reason rejected |
|---|---|
| Order by device timestamp and UUID | Clock skew and random lexical order are not business chronology |
| Write every event directly to S3 | Hundreds of millions of requests make the cost model infeasible |
| Call S3 after hot-store write without an outbox | A crash can permanently omit the archive record |
| Preserve exact untrusted bytes as the main archive | Prevents canonical reconciliation and retains ambiguous representations |

## Consequences

- Chargers must report `boot_started_at` and retain IDs across retries.
- Device clock policy is explicit and future-skew is bounded.
- Invalid wire bytes require a separate quarantine policy if retained.
- Durable adapters must transactionally create immutable event, sequence
  ownership, replay marker, latest conditional update, and archive-pending state.
- Replay tombstones must outlive event TTL and every valid retry/reconciliation
  window.

## Validation

Commit
[`8dccb85`](https://github.com/muhammadali182-q/herbie/commit/8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf)
implements the decision. Unit and Moto-backed adapter tests cover concurrent
duplicates in the in-memory repository, conflicting message and sequence IDs,
clock rollback, future skew, reordered boots, multiple connectors, archive
failure, immutable object retries, transaction composition, and bootstrap
validation. Hosted run
[`45566373644`](https://github.com/muhammadali182-q/herbie/actions/runs/45566373644)
passed all quality jobs.

This evidence verifies the application and adapter behavior against Moto. It
does not verify RabbitMQ redelivery, DynamoDB Local concurrency, MinIO
compatibility, AWS behavior, multiple archive schedulers, or global exactly-once
archive membership. Those boundaries remain explicit follow-up work.
