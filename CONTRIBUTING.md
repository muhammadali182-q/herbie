# Contributing

## Workflow

1. Start from an up-to-date `main` branch.
2. Use a short-lived branch named `feat/<topic>`, `fix/<topic>`,
   `docs/<topic>`, `test/<topic>`, or `chore/<topic>`.
3. Keep each commit focused, tested, reviewable, and independently revertible.
4. Update tests and relevant documentation in the same commit as behavior.
5. Update `docs/ENGINEERING_JOURNAL.md` for every meaningful change.
6. Push one to three validated commits at a time or at the end of a workday.

## Commit Messages

Use Conventional Commits with a useful scope, for example:

```text
feat(ingestion): persist idempotent charger telemetry
test(tenancy): prove cross-tenant access is denied
docs(architecture): record telemetry ownership decision
```

The commit body should explain why a non-obvious change is needed and cite its
requirement, issue, or ADR where applicable.

## Quality Gate

Before committing:

- Review `git diff` and the staged file list.
- Run formatting, linting, type checks, and affected tests.
- Validate schemas, migrations, and infrastructure when changed.
- Confirm no credentials, private keys, state files, or personal data are
  included.
- Record meaningful decisions, verification, limitations, and follow-up work.

## Review Expectations

Tenant isolation, identity, billing, allocation safety, destructive data
migrations, and cloud teardown require another team member's review. A change
is complete only when its acceptance criteria and documentation are satisfied.

## Evidence

Performance and reliability claims must identify the tested commit,
environment, workload, duration, and raw result. Clearly label statements as
measured, modeled, assumed, or cloud-provider claimed.
