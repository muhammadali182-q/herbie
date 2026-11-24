# Charger Message Contract

## Scope

The semester prototype uses a simplified MQTT contract rather than claiming
OCPP conformance. The contract preserves the central-system concepts needed to
demonstrate charger identity, telemetry, sessions, commands, idempotency, and
power limits. A later document will map these concepts to selected OCPP flows.

## Telemetry Topic

```text
herbie/v1/tenants/{tenant_id}/chargers/{charger_id}/up/telemetry
```

The broker adapter supplies an authenticated device principal separately from
the topic. The principal, exact topic identity, registered charger, and payload
identity must agree. Topic equality alone is not authentication. Production
provisioning must give each device exact publish/subscribe ACLs. The v1
contract accepts only canonical lowercase UUID identifiers and an exact route.

## Telemetry Envelope

```json
{
  "schema_version": "1.0",
  "message_id": "f02b5884-9211-5f85-8be9-fc4d33ef5236",
  "message_type": "telemetry.reported",
  "occurred_at": "2026-01-01T00:00:10Z",
  "sent_at": "2026-01-01T00:00:10.025Z",
  "boot_id": "1ca2a6b9-5c56-5d2b-a241-09e584ab3f5e",
  "boot_started_at": "2026-01-01T00:00:00Z",
  "sequence": 0,
  "tenant_id": "0c2533f9-ec96-56e1-92ba-74482d4f06bd",
  "charger_id": "e3c23bf3-445f-55de-a5f6-bc821631b943",
  "connector_id": 1,
  "payload": {
    "cumulative_energy_wh": 19,
    "power_w": 7000,
    "status": "charging",
    "voltage_v": 230,
    "current_ma": 30434
  }
}
```

## Semantics

- MQTT QoS 1 means duplicates are expected.
- A retry retains the same `message_id`, `occurred_at`, and content.
- Reusing a message ID with other content is a protocol conflict.
- `boot_id` changes when the charger process restarts.
- `boot_started_at` orders different boots and cannot follow `occurred_at`.
- `sequence` is monotonic only within a boot.
- The pair `(boot_id, sequence)` identifies one event and cannot be reused with
  another message ID.
- Within one boot, sequence orders state even when the charger clock moves
  backward. Across boots, `boot_started_at` orders state. UUID lexical order is
  never used as chronology.
- All timestamps must be RFC 3339 text with an explicit timezone and are
  normalized to UTC. Numeric epoch timestamps and implausible future times are
  rejected.
- Energy and power use integer Wh and W. Currency never appears in telemetry.
- Booleans, numeric strings, and floats are not coerced into integer fields.
- Unknown fields are rejected to expose incompatible producers early.
- Older valid events are retained but cannot replace a newer per-connector
  latest-state view.
- Semantic equality uses a versioned, sorted canonical JSON fingerprint.
- Compact replay markers must outlive the broker replay, billing, and archive
  reconciliation windows; the initial target is at least 180 days.

## Canonical Archive

S3 stores canonical validated events, not the exact untrusted wire bytes. Each
NDJSON record includes the normalized event, trusted topic, server receipt
time, semantic fingerprint, and archive schema version. Invalid wire payloads
will use a separate bounded quarantine path.

Acceptance atomically creates an archive-pending record in the hot store. A
separate worker groups pending events by tenant and UTC hour, produces an
immutable gzip object with a content-derived key, and records its checksum.
Failure leaves pending state for retry; writing an object does not mutate it.

## Deterministic Simulator

The simulator derives a run namespace from its schema version, seed, start
time, interval, tenant count, charger count, and rounds. Tenant, charger, boot,
and message UUIDs derive from that namespace. Identical inputs produce
byte-equivalent logical events; content-shaping input changes cannot silently
reuse message IDs. Tenant events are interleaved per charger slot.

```powershell
uv run herbie-simulator --summary
uv run herbie-simulator --tenants 3 --chargers-per-tenant 4 --rounds 3
```

The first implementation models many logical chargers but does not yet prove
the same number of simultaneous MQTT connections. Connection-scale evidence is
tracked separately under QR-001.
