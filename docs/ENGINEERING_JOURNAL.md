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
