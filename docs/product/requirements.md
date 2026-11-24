# Requirements and Acceptance Criteria

The IDs in this document are stable references for code, tests, evidence, and
the final report. `P0` requirements are mandatory for the semester MVP.

## Functional Requirements

| ID | Priority | Requirement | Acceptance criterion |
|---|---|---|---|
| FR-001 | P0 | Isolate each operator's data and configuration | Automated negative tests perform zero successful cross-tenant reads, writes, exports, or MQTT topic operations |
| FR-002 | P0 | Manage tenant-specific sites, chargers, tariffs, power limits, maintenance windows, and alert thresholds | Three tenants hold different configurations and changes apply without application redeployment |
| FR-003 | P0 | Authorize and manage charging sessions | Valid sessions follow the defined state machine; invalid and duplicate transitions are rejected or idempotent |
| FR-004 | P0 | Share site power safely between active sessions | No generated target or acknowledged allocation set exceeds the configured site limit |
| FR-005 | P0 | Record telemetry and calculate session energy | Retries create no duplicate immutable record; stale readings may be audited but never move the metering checkpoint or increase billed energy |
| FR-006 | P0 | Apply tenant tariffs and calculate session charges | Golden fixtures match exact integer-unit energy and currency totals |
| FR-007 | P0 | Meter platform usage and create tenant invoices | Re-running invoice generation for the same period produces one identical invoice |
| FR-008 | P0 | Present operator workflows in a web dashboard | An operator can inspect its sites, chargers, active sessions, allocation, usage, and invoices without seeing another tenant |
| FR-009 | P1 | Generate and acknowledge backend commands | Commands have stable IDs, versions, expiry, and duplicate-safe acknowledgements |
| FR-010 | P1 | Export and offboard a tenant | Data export, final billing, credential revocation, deletion, and retention status are demonstrated with synthetic data |

## Cloud and Quality Requirements

| ID | Priority | Requirement | Acceptance criterion |
|---|---|---|---|
| QR-001 | P0 | Represent 2,000 simulated chargers across three tenants | Test evidence identifies logical identities, concurrent connections, and generator limits separately |
| QR-002 | P0 | Sustain the baseline telemetry rate | 200 messages/second is offered for at least 30 minutes with throughput, loss, latency, queue age, and resource results |
| QR-003 | P0 | Evaluate a fivefold peak | 1,000 messages/second is tested for at least five minutes, or the measured limit is reported without unsupported extrapolation |
| QR-004 | P0 | Complete authorization promptly | Correct authorization p95 is below one second at the declared normal workload; p99 is also reported |
| QR-005 | P0 | Tolerate one stateless service instance failure | Killing an API or worker replica causes no committed-operation loss and recovery is measured |
| QR-006 | P0 | Prevent noisy-neighbor data leakage and quantify performance impact | A hot tenant causes no cross-tenant access; control-tenant latency and errors are compared with a baseline |
| QR-007 | P0 | Provide observable operation | Health, request, queue, error, allocation, billing, and tenant-denial signals are available with bounded log retention |
| QR-008 | P0 | Deploy and remove infrastructure reproducibly | Documented deployment and teardown complete without committed credentials or unmanaged residual resources |
| QR-009 | P0 | Support safe evolution | A backward-compatible schema/application upgrade and rollback are tested under an active synthetic session |
| QR-010 | P0 | Restore protected data | A backup is restored in an isolated environment and its key records are reconciled |
| QR-011 | P0 | Protect credentials and traffic | No anonymous broker access, no repository secrets, TLS in the cloud profile, and least-privilege roles are documented |
| QR-012 | P1 | Autoscale useful processing capacity | Scale-out and scale-in are observed with task count, queue age, latency, and stabilization evidence |

## Economic and Lifecycle Requirements

| ID | Priority | Requirement | Acceptance criterion |
|---|---|---|---|
| ER-001 | P0 | Reproduce provider cost calculations | Versioned formulas identify region, date, SKU, quantity, retention, and workload assumptions |
| ER-002 | P0 | Analyze provider revenue and break-even | Revenue, direct cost, support, and development recovery are separated and sensitivity is shown |
| ER-003 | P0 | Analyze customer value | Gross charging sales are separated from operator costs and profit; SaaS and in-house alternatives use equivalent scope |
| ER-004 | P0 | Relate elasticity to cost | Fixed, peak, and autoscaled task-hours are compared using measured or declared utilization |
| LC-001 | P0 | Define operational ownership | Deployment, monitoring, incidents, security, support, backup, and upgrade responsibilities are documented |
| LC-002 | P0 | Manage upgrades | Contract versions, database migrations, compatibility, deployment, and rollback are documented and exercised |
| LC-003 | P0 | Manage end-of-life | Tenant export/deletion, final billing, credential revocation, resource teardown, and financial closure are documented |

## Evidence Rules

- Every performance test records commit, environment, workload, duration, and
  raw result location.
- Means alone are insufficient; p50, p95, p99, errors, throughput, and queue
  behavior are reported where applicable.
- A controlled failure drill supports recovery claims, not long-term uptime.
- A smaller test is not presented as proof of a larger scale.
- Screenshots may illustrate evidence but do not replace machine-readable
  results.
