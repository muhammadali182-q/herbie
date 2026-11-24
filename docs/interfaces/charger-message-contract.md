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

The authenticated broker topic is trusted for tenant and charger identity. A
payload with different identifiers is rejected. The v1 contract accepts only
canonical UUID identifiers and an exact telemetry route.

## Telemetry Envelope

```json
{
  "schema_version": "1.0",
  "message_id": "f02b5884-9211-5f85-8be9-fc4d33ef5236",
  "message_type": "telemetry.reported",
  "occurred_at": "2026-01-01T00:00:00Z",
  "sent_at": "2026-01-01T00:00:00.025Z",
  "boot_id": "1ca2a6b9-5c56-5d2b-a241-09e584ab3f5e",
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
- `sequence` is monotonic only within a boot.
- All timestamps require an explicit timezone offset and are stored as UTC.
- Energy and power use integer Wh and W. Currency never appears in telemetry.
- Unknown fields are rejected to expose incompatible producers early.
- Older valid events are retained but cannot replace a newer latest-state view.

## Deterministic Simulator

The simulator derives tenant, charger, boot, and message UUIDs from a stable
seed. Given the same scenario inputs, it produces byte-equivalent logical
events in the same order. This supports repeatable demos and golden tests.

```powershell
uv run herbie-simulator --summary
uv run herbie-simulator --tenants 3 --chargers-per-tenant 4 --rounds 3
```

The first implementation models many logical chargers but does not yet prove
the same number of simultaneous MQTT connections. Connection-scale evidence is
tracked separately under QR-001.
