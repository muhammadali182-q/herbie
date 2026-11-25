# Engineering Journal

This append-only journal explains what was built, how it was verified, why
important choices were made, and what remains uncertain. It records concise,
auditable engineering rationale rather than private scratch work or hidden
chain-of-thought.

## Entry Template

```markdown
## YYYY-MM-DD - Change title

- Branch or commit:
- Requirements:
- Related ADRs:

### Summary

What changed in architectural and operational terms.

### Rationale

The problem, constraints, alternatives considered, and reason for the choice.

### Implementation

Affected components, interfaces, data, infrastructure, and procedures.

### Verification

Commands, tests, environment, result, and evidence location.

### Impact

Security, tenant isolation, cost, reliability, and operational consequences.

### Limitations and Follow-up

Known gaps and the requirement or issue that tracks each one.
```

## 2026-11-24 - Repository baseline and implementation plan

- Branch or commit: `docs/project-foundation`
- Requirements: all project requirements at planning level
- Related ADRs: ADR-0001, ADR-0002, ADR-0003

### Summary

The original repository contained a two-line README, an MIT license, and the
eight-page Assignment 1 PDF. No implementation, infrastructure definition,
tests, calculation source, CI workflow, or operational runbook existed. The
repository was cloned at commit `33aa200` and a documentation foundation was
created before application development.

### Rationale

The course requires technical and economic decisions to be supported by
quantitative evidence across the service lifecycle. Building without explicit
requirements and evidence ownership would make it easy to produce a working
demo that does not substantiate the report's claims. The team also has under
three weeks and free-tier-only AWS access, so scope and claim discipline must
be fixed before implementation.

The selected strategy is a modular Python application with separate API,
worker, job, simulator, and web process roles. This retains deployable scaling
boundaries without the coordination and operations cost of many independent
microservices. Development will use local service equivalents, while AWS
deployment will use a cost-controlled demonstrator and a separately documented
target architecture.

### Implementation

The documentation now defines:

- The semester MVP and explicit non-goals.
- Requirement identifiers and measurable acceptance criteria.
- Traceability from requirements to design, implementation, tests, and final
  evidence.
- A fifteen-working-day delivery sequence with stop/go gates.
- Initial architecture decisions for component boundaries, messaging, and
  data ownership.
- A correction register for workload, availability, storage, and economic
  assumptions in Assignment 1.
- Git, review, documentation, and verification rules.

### Verification

- Confirmed the cloned branch matches `origin/main` at `33aa200` before edits.
- Confirmed the active GitHub account has write permission to the repository.
- Parsed and reviewed all eight pages of `docs/Project Description.pdf`.
- Confirmed the original repository had two commits and no source code.

### Impact

No runtime behavior or cloud resources changed. The updated README no longer
presents scalability and high availability as already delivered facts. The
original PDF is retained unchanged; corrections are additive and traceable.

### Limitations and Follow-up

- The RabbitMQ MQTT approach remains proposed until an integration spike
  confirms protocol, routing, and resource behavior.
- Docker and Terraform are not installed on the current workstation. The
  repository will provide reproducible definitions, but container and IaC
  execution needs another environment or installation approval.
- Free-tier eligibility and AWS service quotas must be audited before any
  deployment.
- Detailed D2-D4 rubrics were not supplied, so traceability uses the project
  brief and CLO mapping as the authority.

## 2026-11-24 - Reproducible backend and service foundation

- Branch or commit: `feat/mvp-foundation`
- Requirements: QR-007, QR-008, QR-011
- Related ADRs: ADR-0001, ADR-0002, ADR-0003

### Summary

Added a typed Python platform package with independent API and worker entry
points, structured JSON logging, safe local settings, health contracts, local
service definitions, tests, and a clean-development runbook.

### Rationale

The domain will need independent HTTP and asynchronous processing capacity,
but both process roles should share one package and configuration contract.
Local PostgreSQL, RabbitMQ, DynamoDB, and S3-compatible services preserve the
target data and messaging boundaries without spending AWS credits during daily
development.

### Implementation

- `pyproject.toml` defines Python 3.12 compatibility, runtime dependencies,
  strict type/lint settings, scripts, and a 90% branch-coverage gate.
- The FastAPI factory exposes liveness, readiness, and versioned metadata.
- The worker has a signal-aware process lifecycle ready for message consumers.
- Docker Compose defines PostgreSQL, RabbitMQ with MQTT and Prometheus plugins,
  DynamoDB Local, MinIO, and optional application processes.
- Environment examples contain only documented local-development values.
- Git attributes, ignore rules, and a non-root backend image improve
  reproducibility and secret hygiene.

### Verification

The foundation is verified locally with `uv lock`, Python compilation, pytest
with branch coverage, Markdown linting, documentation link checks, and YAML
parsing. Ruff and mypy are locked for CI, but their large wheels could not be
downloaded through this workstation's package-host connection. Docker
configuration is reviewed statically because Docker is unavailable here.

### Impact

No cloud resource is created. The Compose broker remains single-node and is not
availability evidence. Readiness is intentionally static until real dependency
adapters exist, preventing a misleading partial check.

### Limitations and Follow-up

- Execute the Compose integration on Docker-enabled CI or a team machine.
- Complete the ADR-0002 broker spike when MQTT consumers are implemented.
- Add dependency-aware readiness only when all required adapters can be
  checked consistently.

## 2026-11-24 - Operator console foundation

- Branch or commit: `feat/mvp-foundation`
- Requirements: FR-008, QR-007
- Related ADRs: ADR-0001

### Summary

Added the responsive React operator-console shell, frontend lint/test/build
tooling, and an Nginx runtime image. The interface presents fleet, session,
load, tenant-lane, and site-allocation concepts needed by the final demo.

### Rationale

The course demonstration benefits from a visual operational surface, but UI
scope must not compete with tenant isolation and allocation correctness. A
single focused console establishes the visual language and information
hierarchy before API wiring, while driver behavior remains in the simulator.

### Implementation

- The monorepo uses npm workspaces with Node.js 22 as the supported baseline.
- The console uses semantic HTML, responsive layouts, high-contrast industrial
  styling, and reduced-motion support without external font dependencies.
- Every displayed metric is visibly marked as deterministic synthetic data.
- Frontend tests assert both the claim labeling and operator navigation.
- The production frontend image serves static assets through a hardened Nginx
  configuration and supports client-side routes.

### Verification

The frontend is verified with ESLint, Vitest, TypeScript, and a production Vite
build. Its Compose definition is parsed with the rest of the service topology.
`npm audit --omit=dev` reports zero production vulnerabilities. The complete
audit reports four low-severity findings in the Markdown lint toolchain; no
moderate, high, or critical findings are present.

### Impact

The dashboard currently has no authentication or live data and therefore does
not demonstrate tenant isolation. The explicit synthetic labels prevent sample
numbers from being reused as performance or availability evidence.

### Limitations and Follow-up

- Replace seed values with tenant-scoped API queries after authentication and
  contracts are implemented.
- Add automated accessibility checks during dashboard integration.
- The Nginx security policy will be tightened after the required API origins
  and asset behavior are known.

## 2026-11-24 - Automated quality and repository security gates

- Branch or commit: `feat/mvp-foundation`
- Requirements: QR-008, QR-011
- Related ADRs: ADR-0001

### Summary

Added pull-request quality automation for documentation, backend, frontend,
container definitions, production dependency auditing, and secret scanning.
Added dependency-update policy, a security reporting policy, and a review
template for tenant, data, operations, and cost impact.

### Rationale

The project will change quickly under a short deadline. Automated gates prevent
speed from silently weakening tests, tenant controls, documentation, or secret
hygiene. Separate jobs make failures attributable and allow independent work to
proceed without combining unrelated checks.

### Implementation

- Python CI installs the committed uv lock, runs Ruff, formatting, strict mypy,
  and the coverage-gated test suite on Python 3.12.
- Frontend CI installs the npm lock, then lints, tests, builds, and audits
  runtime dependencies.
- Container CI validates the Compose model and builds both runtime images.
- Gitleaks scans complete Git history with read-only repository permission.
- Dependabot monitors Python, npm, GitHub Actions, and both Dockerfiles weekly.

### Verification

Workflow YAML is parsed locally. Backend tests, frontend lint/tests/build,
Markdown lint, Compose YAML parsing, and the runtime npm audit pass locally.
Ruff 0.17.6 and strict mypy 1.20.2 also pass locally after obtaining their
artifacts through source/release fallbacks. The first GitHub-hosted workflow run
will validate Linux, Docker, and action integration that this workstation
cannot execute completely.

### Impact

The workflow has `contents: read` permission and grants no cloud credentials.
Deployment remains a separate future workflow requiring an explicit protected
environment and short-lived AWS identity.

### Limitations and Follow-up

- Replace action version tags with immutable commit SHAs before a production
  release.
- Add schema compatibility, database integration, and infrastructure security
  jobs when those artifacts exist.
- Review the first hosted run and correct environment-specific failures before
  marking the foundation gate complete.

## 2026-11-24 - Foundation review and hardening

- Branch or commit: `feat/mvp-foundation`
- Requirements: QR-007, QR-008, QR-011
- Related ADRs: ADR-0001, ADR-0002, ADR-0003

### Summary

An independent code review found no critical or high-severity issue. The
medium-severity configuration, reproducibility, and accessibility findings were
fixed before beginning domain implementation.

### Rationale

Local-only credentials are safe only when services are also local-only. A
generic API image health check cannot apply to a non-HTTP worker. Reproducible
locks and action revisions must be enforced rather than merely documented.
Interface accessibility claims also require measured contrast and semantic
state, not visual appearance alone.

### Implementation

- Bound all local service ports to loopback and aligned local S3 credentials.
- Disabled the inherited API health check for the worker process.
- Excluded environment files, caches, coverage, and build output from Docker
  contexts.
- Enforced lock freshness, pinned action revisions and uv, and pinned available
  container manifest digests.
- Made settings immutable, corrected CORS/runtime configuration behavior, and
  made signal registration directly testable.
- Increased text contrast, added a two-color focus indicator, exposed chart
  values to assistive technology, marked the active page, and disabled
  unavailable controls.
- Added an actionable private vulnerability-reporting channel.

### Verification

Ruff, strict mypy, backend tests, frontend lint/tests/build, Markdown lint,
runtime npm audit, workflow parsing, and Compose parsing pass after this
change. The GitHub-hosted quality jobs will be rerun after push. The test suite
directly asserts immutable settings and signal-handler registration.

### Impact

Local services are no longer reachable from other hosts by default. The worker
will no longer be permanently marked unhealthy. Docker builds receive a
smaller, safer context. Dependency and workflow changes now fail when their
locks or pinned revisions are stale.

### Limitations and Follow-up

- The MinIO image remains pinned by release tag because a public manifest
  digest was not available through the inspected registry endpoint.
- Dynamic Compose startup remains pending on a Docker-enabled runner.
- Browser-level accessibility and responsive checks remain part of dashboard
  integration.

## 2026-11-24 - Versioned telemetry core and deterministic simulator

- Branch or commit: `feat/telemetry-slice`
- Requirements: FR-001, FR-005, QR-001
- Related ADRs: ADR-0001, ADR-0002, ADR-0003

### Summary

Added the first functional domain slice: a v1 charger telemetry contract, MQTT
topic parsing, duplicate-safe ingestion, tenant-scoped latest-state behavior,
an initial archive port, and a deterministic multi-tenant scenario generator.

### Rationale

Message identity, ordering, and idempotency must be correct before coupling the
system to a broker or cloud database. Pure ports and in-memory adapters allow
those semantics to be tested exhaustively and reused by later RabbitMQ,
DynamoDB, and S3 adapters. A deterministic simulator prevents demo and load
results from depending on uncontrolled random inputs.

### Implementation

- Pydantic contracts reject unknown fields, naive timestamps, negative
  measurements, unsupported schema versions, and invalid connector numbers.
- Topic parsing derives trusted tenant/charger identity and rejects envelope
  identity forgery.
- Event keys are scoped by tenant, charger, and message ID. Exact retries are
  duplicates; reused IDs with changed content are errors.
- Older events remain accepted for audit/archive purposes but cannot replace a
  newer latest-state record.
- The initial service called an idempotent archive port after hot persistence;
  the independent review below replaces this with a durable archive outbox.
- UUID5-based scenario generation produces stable three-tenant fixtures with
  monotonic per-device sequences and cumulative meter values.

### Verification

Contract, topic, duplicate, collision, stale-order, tenant-scope, immutability,
simulator determinism, CLI, Ruff, mypy, and coverage tests pass. The contract
document explicitly separates logical charger representation from concurrent
connection evidence.

### Impact

No broker, database, API, or cloud behavior is claimed by this commit. The
ports define what those adapters must preserve. The in-memory repository uses
an asynchronous lock so concurrent local requests exercise one-write behavior.

### Limitations and Follow-up

- Add generated JSON Schema and compatibility checks before external producers
  consume the contract.
- Implement RabbitMQ routing/redelivery and durable telemetry/archive adapters.
- Add authenticated tenant-scoped query APIs before exposing latest state to
  the dashboard.
- Extend the simulator with real MQTT connections and calibrated load modes.

## 2026-11-24 - Telemetry invariant review and redesign

- Branch or commit: `feat/telemetry-slice`
- Requirements: FR-001, FR-005, QR-001, QR-005, QR-010
- Related ADRs: ADR-0003, ADR-0004

### Summary

An independent review identified five high-severity integration blockers in the
first telemetry core: ambiguous chronology, no durable archive-pending state,
no explicit authenticated device identity input, simulator ID reuse across
changed scenarios, and coercive wire validation. The core was redesigned before
adding RabbitMQ or cloud storage.

### Rationale

Infrastructure adapters amplify domain mistakes. Ordering must not depend on
random UUIDs or a device clock alone, and successful hot persistence cannot
depend on the broker redelivering forever to repair S3. A topic selected by a
publisher is also not proof of device identity. Correcting these boundaries now
keeps later adapter failures observable and recoverable.

### Implementation

- Added a separate trusted `DeviceIdentity` input for broker-authenticated
  tenant/charger identity.
- Made wire numbers strict, UUID strings canonical, timestamps RFC 3339-only,
  and all accepted times UTC-normalized with temporal and future-skew checks.
- Added `boot_started_at`; sequence orders one boot and boot start orders reboots.
- Enforced one message identity per boot sequence and connector-level latest
  state without UUID tie-breaking.
- Replaced direct archive calls with an atomically pending archive outbox.
- Added deterministic canonical gzip NDJSON batching, content-derived object
  keys, checksums, immutable sink semantics, receipts, retry, and reconciliation
  state.
- Included all content-shaping scenario parameters in run identity, interleaved
  tenant generation, bounded scenario size, and corrected cumulative energy
  truncation.
- Extended coverage and Ruff CI to the simulator package.

### Verification

Tests now cover strict wire parsing, UTC normalization, timestamp order, future
skew, concurrent duplicate delivery, message and sequence conflicts, clock
rollback, reordered boots, independent connectors, tenant boundaries,
deterministic archive bytes, failed-object retry, archive receipts, scenario ID
separation, interleaving, bounds, and exact energy vectors. Ruff, strict mypy,
coverage, and Markdown lint pass locally; hosted CI will be rerun after push.

### Impact

The MQTT adapter must supply identity established from a broker principal and
cannot construct it from the payload. DynamoDB must transactionally preserve
event, sequence owner, replay marker, latest condition, and archive-pending
state. S3 is a canonical validated-event archive rather than exact wire-byte
storage.

### Limitations and Follow-up

- Device credential provisioning and topic ACL enforcement remain broker work.
- Durable adapter transactions and conformance tests remain mandatory.
- Invalid payload quarantine needs an explicit size, retention, and redaction
  policy.
- The 180-day replay-marker target must be checked against final billing and
  retention policy.

## 2026-11-25 - Durable telemetry and canonical archive adapters

- Branch or commit: `feat/telemetry-slice`
- Requirements: FR-001, FR-005, QR-005, QR-010, ER-001
- Related ADRs: ADR-0003, ADR-0004

### Summary

Added DynamoDB and S3 implementations of the telemetry persistence ports. An
accepted event, replay marker, immutable boot identity, boot-sequence owner,
archive-pending state, and eligible latest-state replacement now commit in one
DynamoDB transaction. A separate adapter writes canonical gzip NDJSON batches
to immutable, encrypted S3 objects and verifies retries by checksum metadata.

### Rationale

The in-memory telemetry core established ordering and idempotency semantics but
could not survive a process restart. Writing the hot event and latest state in
separate operations would expose partially accepted messages, while overwriting
an S3 key could silently replace audit data. DynamoDB transactions and S3
conditional writes preserve those boundaries without introducing a distributed
transaction between the stores.

The archive remains explicitly at-least-once. Content-derived keys make an
identical batch retry idempotent, and stable message IDs make overlap detectable
during reconciliation. Global exactly-once object membership was not claimed;
it would require a durable cross-process batch-claim manifest. The current
service therefore serializes flushes within one process and does not support
multiple archive schedulers.

### Implementation

- Connector-scoped DynamoDB partitions hold immutable events, replay markers,
  boot ownership, sequence ownership, and latest state. Tenant and archive
  access use separate GSIs.
- Transactional conflict reads distinguish exact retries from message, boot,
  and sequence identity conflicts. Bounded retries handle latest-state and
  transactional-read races.
- Same-boot sequence and cross-boot start time remain the only chronology.
  Boot start is immutable and sequence is bounded to a signed 64-bit integer.
- Pending events do not activate their hot-event TTL until an archive receipt
  is stored. Replay, boot, and sequence markers use the longer configured
  retention, and bootstrap enables the `expires_at` table TTL.
- Existing table bootstrap validates key types, both GSI schemas and
  projections, on-demand billing, and the TTL attribute before accepting the
  resource.
- S3 writes use `If-None-Match: *`, canonical SHA-256 metadata, gzip NDJSON
  metadata, AES-256 server-side encryption by default, and optional KMS keys.
  Precondition failures verify existing content; conditional-write conflicts
  receive bounded retries.
- Bucket bootstrap rejects access-denied responses as absence and applies all
  four S3 public-access-block controls.
- Runtime dependencies include boto3, while boto3 typing packages and Moto
  remain development-only. Runtime adapter imports do not require type stubs.
- Settings and the environment template expose table and retention controls,
  with replay retention validated as at least 180 days and longer than hot
  event retention.

### Verification

Verification ran locally on Windows with Python 3.14.0 and uv 0.11.26; Python
3.12 remains the project and hosted-CI target.

- `uv lock --check`: passed with 65 locked packages resolved.
- `uv run ruff check backend simulator`: passed.
- `uv run ruff format --check backend simulator`: 27 files formatted.
- `uv run mypy`: no issues in 27 source files.
- `uv run pytest`: 80 tests passed with 92.16% total branch coverage, above the
  90% gate. One pre-existing Starlette `TestClient` deprecation warning remains.
- `uv run --no-sync pytest backend/tests/telemetry/test_durable_adapters.py -q
  --no-cov`: 12 adapter tests passed.
- `npm run lint:docs`: zero Markdown issues after this entry was appended.
- A runtime import probe blocked all `mypy_boto3_*` modules and successfully
  imported both production adapters.

Moto 5.2.6 exercised injected transaction conflicts, idempotency, ordering,
tenant and connector scope, TTL configuration, receipt immutability, bootstrap
validation, S3 preconditions, a synthetic S3 409 race, encryption metadata, and
end-to-end DynamoDB-to-S3 flushing. These are functional emulator results, not
measured AWS service evidence.

### Impact

Tenant IDs remain present in DynamoDB partition keys, latest-state GSI keys, and
S3 object prefixes. Conditional writes prevent accepted event mutation and S3
replacement. Public access is blocked at bucket bootstrap, and object
encryption is requested on every write. Pending state makes object-store
failure visible and retryable without requiring broker redelivery.

The design incurs several DynamoDB writes per accepted event and therefore does
not rehabilitate the original per-message database cost estimate. Canonical
batching avoids the explicitly infeasible one-S3-object-per-event pattern, but
batch size, request cost, and retention still require measured workload data.

### Limitations and Follow-up

- Docker is unavailable locally, so ADR-0004 conformance against DynamoDB Local
  and compatibility against the configured MinIO image remain unverified.
- Moto transactions use unsynchronized whole-table rollback and cannot provide
  valid concurrent-write evidence; concurrent duplicate/latest tests remain a
  DynamoDB Local requirement rather than a flaky emulator assertion.
- No AWS resource was deployed. Transaction, GSI propagation, TTL deletion,
  encryption, KMS, public-access, durability, latency, and availability claims
  remain unmeasured on AWS.
- DynamoDB GSIs are eventually consistent, and TTL deletion is asynchronous.
- Replay markers can expire after the configured window even if an extreme
  archive backlog remains pending; queue-age monitoring and reconciliation must
  keep lag well below that window.
- Archive membership is at-least-once after process crashes. Add a durable batch
  manifest before running multiple archive schedulers or claiming global
  exactly-once membership.
- The adapters are not yet wired into the worker. RabbitMQ identity, routing,
  acknowledgement, dead-lettering, bounded prefetch, and crash-redelivery work
  remains separate.
- The S3 encryption and public-access APIs used here require a Docker-enabled
  MinIO integration run before they can be claimed compatible with local
  Compose.
- Replace synchronous boto3 calls in worker threads only if measured queue age
  or thread saturation justifies an async client migration.

## 2026-11-25 - Telemetry storage evidence reconciliation

- Branch or commit: `feat/telemetry-slice` at implementation baseline
  `8dccb85cfad5788f1ac352a2ea3ffc75c19c62bf`
- Requirements: FR-005, QR-001, QR-005, QR-008, QR-011
- Related ADRs: ADR-0002, ADR-0004

### Summary

Reconciled traceability and planning documents with the implemented telemetry
contract, deterministic simulator, DynamoDB adapter, S3 adapter, and archive
outbox. Added a fixed evidence record linking the implementation commit,
hosted CI run, source tests, measured results, and unverified boundaries.

### Verification

GitHub Actions run
[`45566373644`](https://github.com/muhammadali182-q/herbie/actions/runs/45566373644)
tested the exact implementation SHA on Ubuntu 26.04.1 with Python 3.12.16 and
uv 0.11.26. All five jobs passed. The backend collected 80 tests and reported
92.56% total branch coverage with one Starlette deprecation warning. The
previous 92.16% figure remains a separate local Windows/Python 3.14.0 result
and is not presented as the hosted measurement.

### Evidence Boundary

The strict contract, deterministic logical generator, transaction and archive
adapters, and canonical batch behavior are implemented. Adapter verification
used Moto 5.2.6. MQTT transport, broker ACLs, worker acknowledgement behavior,
DynamoDB Local concurrency, MinIO compatibility, and AWS behavior remain
unverified and are not marked complete by this documentation update.

## 2026-11-25 - Durable RabbitMQ telemetry consumer

- Branch or commit: `feat/mqtt-ingestion`
- Requirements: FR-001, FR-005, QR-005, QR-006, QR-011
- Related ADRs: ADR-0002, ADR-0004

### Summary

Added the runtime messaging boundary between RabbitMQ's MQTT plugin and the
existing duplicate-safe DynamoDB ingestion service. The worker now supports
separate telemetry and archive process roles. The telemetry role declares a
durable classic queue, bounded prefetch, dead-letter path, and delayed retry
path; the archive role is the single scheduler that drains durable pending
records to S3-compatible storage.

### Safety Decisions

- RabbitMQ's slash-to-dot topic conversion is reversed only in the messaging
  adapter. The resulting exact topic must exist in a fail-closed device
  registry before it becomes a `DeviceIdentity`.
- Valid new events and exact duplicates are ACKed only after the DynamoDB
  repository returns. Contract, identity, future-clock, and identity-conflict
  failures are rejected without requeue and therefore dead-lettered.
- Storage failures use a publisher-confirmed TTL retry queue. The original
  delivery is ACKed only after retry publication succeeds. Exhausted attempts
  are dead-lettered; a failed retry publication requeues the original.
- Retry counts come from RabbitMQ `x-death` entries for the retry queue, not
  from an arbitrary producer header.
- The demo queue is explicitly classic and single-node. A three-node quorum
  queue remains target architecture rather than demonstrated HA.
- MQTT packets are capped at 131,072 bytes and application payloads at 65,536
  bytes. The worker checks payload size before JSON parsing.

### Verification

Local Windows verification used Python 3.14.0 and uv 0.11.26:

- `uv lock --check`: 72 packages resolved.
- `uv run ruff check backend simulator`: passed.
- `uv run mypy`: no issues in 33 source files.
- `uv run pytest`: 113 tests passed with 92.40% total branch coverage. One
  pre-existing Starlette `TestClient` deprecation warning remains.
- Messaging tests cover ACK-after-store, duplicate ACK, malformed and oversized
  rejection, unregistered and mismatched identity, clock skew, sequence
  conflict, confirmed retry, retry exhaustion, retry-publish failure, topology,
  reconnect, shutdown, and runtime composition.

Docker is not installed on this workstation, so `docker compose config`, real
RabbitMQ, DynamoDB Local, MinIO, ACL, TLS, and crash-redelivery verification are
not claimed by this commit. ADR-0002 remains `Proposed` pending those system
tests.

## 2026-11-25 - Deterministic MQTT simulator transport

- Branch or commit: `feat/mqtt-ingestion`
- Requirements: FR-005, QR-001, QR-002, QR-003, QR-011
- Related ADRs: ADR-0002

### Summary

Extended the deterministic simulator with an explicit Paho MQTT transport while
preserving the existing stdout fixture mode. Selected logical chargers use
stable client IDs and independent connections, publish MQTT 5 or 3.1.1 at QoS
1, wait for PUBACK, and never treat broker acknowledgement as durable-ingestion
evidence.

### Implementation

- Connection count is independent from represented device count; deterministic
  selection makes smaller connection experiments reproducible.
- Per-device usernames render from tenant and charger identity. Passwords come
  from an environment variable rather than CLI arguments, payloads, or logs. A
  shared synthetic username remains possible by selecting a constant template
  for a benchmark profile.
- Server-authenticated TLS and optional client certificate/key files are
  configurable. MQTT 5 is the default and MQTT 3.1.1 remains available.
- Connection retry uses bounded exponential backoff with deterministic jitter.
  Stable scenario seed, client identity, and reporting jitter support replay.
- Synchronized mode creates timer bursts. Jittered mode spreads each round
  through a cycle whose duration honors both the reporting interval and maximum
  average message rate.
- Results separate represented devices, connected clients, offered messages,
  PUBACKs, failures, and elapsed generator time. Worker receipts, DynamoDB
  writes, and archived events require independent measurement.

### Verification

Local Windows verification used Python 3.14.0 and uv 0.11.26:

- `uv run ruff check backend simulator`: passed.
- `uv run mypy`: no issues in 35 source files.
- `uv run pytest`: 140 tests passed with 92.77% total branch coverage. One
  pre-existing Starlette `TestClient` deprecation warning remains.
- Simulator tests cover credentials, bounds, TLS setup, stable IDs, QoS 1,
  PUBACK timeout, reconnect exhaustion and jitter, connection selection,
  synchronized pacing, deterministic timer jitter, failed PUBACK accounting,
  secret lookup, and result labeling.

No real broker connection or load measurement was performed locally because
Docker is unavailable. The implementation does not yet support a distributed
generator, and no 2,000-connection or throughput claim is made by this commit.

## 2026-11-25 - Compose-backed MQTT system evidence harness

- Branch or commit: `feat/mqtt-ingestion`
- Requirements: FR-001, FR-005, QR-005, QR-011
- Related ADRs: ADR-0002, ADR-0004

### Summary

Added an opt-in system test and dedicated hosted-CI job using RabbitMQ's MQTT
plugin, DynamoDB Local, and MinIO. The test provisions one device user at
runtime with both ordinary resource permissions and exact `amq.topic`
permissions. Credentials and resource names are limited to the disposable test
environment.

### Covered Procedure

The harness starts a normal telemetry worker, publishes through the Paho
simulator connection, verifies one durable event after a duplicate, starts the
archive role, and checks one canonical gzip NDJSON membership in MinIO. It then
proves that Device A cannot publish to Device B's topic or subscribe to Device
B's command topic, verifies malformed input reaches the DLQ, and runs a helper
worker that exits after DynamoDB commit but before ACK. A restarted normal
worker must drain the redelivery without creating a second event.

The test distinguishes MQTT PUBACK, queue delivery, DynamoDB acceptance, and
S3-compatible archive evidence. RabbitMQ management counters and store contents
are checked independently rather than inferring durable ingestion from PUBACK.

### Local Verification Boundary

Docker remains unavailable on the Windows workstation. Local checks therefore
collected 141 passing tests, one intentionally skipped system test, and 92.81%
branch coverage; Ruff, formatting, and strict mypy over 37 source files pass.
The real-service result is pending the hosted `MQTT system` job and is not yet
recorded as passing.
ADR-0002 remains `Proposed` until that result and the remaining TLS/control-path
criteria are evaluated.

### First Hosted Attempt

GitHub Actions run
[`45585700340`](https://github.com/muhammadali182-q/herbie/actions/runs/45585700340)
passed backend, frontend, documentation, container-build, and secret-scan jobs.
The MQTT system job stopped before service startup because Quay returned HTTP
401 for the previously configured MinIO image. No system test executed, so the
run provides no MQTT or storage-behavior evidence.

The local emulator was changed to the publicly pullable multi-architecture
`bitnamilegacy/minio:2025.7.23-debian-12-r5` manifest pinned at digest
`sha256:6dabb4a2088c9a79908de3bc05f4586c23ad2182c8908e7e3acbf61c1467fb20`.
This legacy mirror is acceptable for bounded S3-compatibility tests but is not a
recommended production image and receives no availability or support claim.

The next hosted attempt reached application setup and verified RabbitMQ,
DynamoDB Local, and the initial MQTT publication path. MinIO then rejected
`PutPublicAccessBlock` with `MalformedXML`. The bucket bootstrap now tolerates
only the observed unsupported API codes and only when an explicit local-emulator
setting is enabled. The default remains fail-closed, and AWS profiles must not
set the compatibility option.
