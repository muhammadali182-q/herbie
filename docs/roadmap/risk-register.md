# Risk Register

| ID | Risk | Probability | Impact | Mitigation and trigger |
|---|---|---|---|---|
| R-001 | MQTT clustering and command routing are more complex than the schedule permits | High | High | Timebox ADR-0002 spike; use a single clearly labeled demo broker and managed/three-node target |
| R-002 | Tenant data leaks through API, SQL, storage keys, or topics | Medium | Critical | Identity-derived tenant context, RLS, scoped repositories, ACLs, adversarial test matrix; any leak blocks release |
| R-003 | Duplicate/out-of-order telemetry corrupts billing | High | High | Stable event IDs, conditional writes, monotonic meter checkpoints, golden reconciliation tests |
| R-004 | DynamoDB and S3 request patterns invalidate the cost model | High | High | Hot TTL, compressed archive batches, explicit request formulas, measured payload/batch sizes |
| R-005 | Free-tier AWS account cannot support target services | High | High | Audit eligibility and quotas before apply; provide demo-lite and target profiles; require cost approval |
| R-006 | Current workstation lacks Docker and Terraform | Certain | Medium | Keep definitions portable, run non-container tests locally, use CI or a team machine for integration |
| R-007 | Dashboard consumes time needed for core correctness | Medium | High | Build only fleet, session, allocation, usage, and invoice workflows after API contracts stabilize |
| R-008 | 2,000-client generator saturates before the platform | Medium | High | Record generator resource use, calibrate against a simple endpoint, support multiple generator processes |
| R-009 | A short test is misreported as 99.9% availability proof | Medium | High | Label recovery evidence separately from provider SLA and modeled availability |
| R-010 | Cloud credentials or Terraform state enter Git | Low | Critical | Example-only environment files, secret scans, OIDC, remote encrypted state, staged-diff review |
| R-011 | Multi-store partial failures leave inconsistent state | Medium | High | Define authority, outbox, retries, visible pending states, and reconciliation procedures |
| R-012 | Team changes create merge conflicts or knowledge silos | Medium | Medium | Short branches, daily pushes, second owners, journal entries, and clean-machine handover |
| R-013 | Full OCPP or payment scope is added late | Medium | High | Keep explicit non-goals and require an approved scope change with schedule impact |

Risks are reviewed at each phase gate. Probability or impact changes must be
recorded in the engineering journal.
