# Project Scope

## Product Statement

H.E.R.B.I.E. is a Track B cloud-hosted platform that lets multiple EV charging
operators share backend infrastructure while retaining isolated data and
configuration. Simulated chargers communicate through a simplified MQTT
protocol. Operators use a web dashboard to manage sites and observe charging,
power allocation, usage, and billing.

## Stakeholders

| Stakeholder | Interest |
|---|---|
| Charging operator | Reliable charger operation, isolated data, configurable tariffs and limits, predictable fees |
| Driver | Correct authorization, charging session, energy measurement, and charge calculation |
| Platform provider | Safe multi-tenancy, operability, scalable cost, usage metering, and revenue |
| Cloud provider | Correct shared-responsibility use of managed infrastructure |
| Course evaluator | Evidence that architecture and economics are reasoned, implemented, and measured |

## Semester MVP

- Three synthetic operator tenants.
- Tenant-scoped users, sites, chargers, connectors, tariffs, and site limits.
- A deterministic simulator for simplified MQTT charger traffic.
- Charger status, authorization, session start/stop, telemetry, and command
  acknowledgement messages.
- Per-site weighted equal-share allocation that never intentionally commands
  more than the configured site limit.
- Duplicate-safe telemetry, cumulative energy metering, immutable tariff
  selection, and deterministic session charges.
- Platform usage metering and tenant invoice generation.
- An operator dashboard for fleet status, active sessions, site allocation,
  usage, and invoices.
- Local reproducibility and a free-tier-conscious AWS demonstration profile.
- Evidence for tenant isolation, correctness, throughput, recovery, cost,
  upgrades, and end-of-life procedures.

## Non-Goals

- Real EVSE hardware or electrical safety certification.
- Full OCPP conformance or interoperability certification.
- Card storage, payment processing, settlement, tax, roaming, or refunds.
- A native mobile application or production-quality driver application.
- Multi-region active-active service.
- Statistical proof of 99.9% annual availability during a short project.
- Production operation of 2,000 real chargers.
- Complex time-of-use pricing, demand response markets, or phase balancing.

## Constraints

- Less than three weeks are available for implementation and evaluation.
- AWS usage must stay within verified free-tier or promotional-credit limits.
- Real chargers are unavailable; all device behavior is simulated.
- The detailed D2-D4 rubrics are unavailable, so the supplied project brief is
  the traceability source.
- The current workstation has Node.js and Python but no Docker or Terraform.

## Claim Policy

Every significant conclusion must be labeled as one of:

| Label | Meaning |
|---|---|
| Measured | Observed in a documented experiment tied to a commit and environment |
| Modeled | Calculated from explicit formulas and inputs |
| Assumed | Used for planning but not yet validated |
| Provider-claimed | Taken from a cloud-provider SLA, price, or specification |

Architecture intent must not be presented as measured runtime behavior.
