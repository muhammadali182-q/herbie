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
