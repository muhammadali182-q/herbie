# Security Policy

## Supported Versions

The project is pre-release. Security fixes are applied to the latest commit on
the active implementation branch and included in the next tagged release.

## Reporting a Vulnerability

Do not open a public issue containing an exploitable vulnerability, credential,
private key, personal data, or unredacted cloud identifier. Contact the project
team privately and include:

- Affected commit or release.
- Preconditions and reproduction steps.
- Expected and observed impact.
- Any evidence needed to validate the report without exposing real secrets.

The team will acknowledge a report within two working days, assign an owner,
and communicate remediation status. Academic deadlines do not justify leaving
a known critical or high-severity issue undocumented.

## Credential Exposure

If a credential is exposed:

1. Revoke or disable it immediately.
2. Review provider and application audit logs for use.
3. Rotate dependent credentials and invalidate active sessions where needed.
4. Remove the value from the current tree.
5. Coordinate history cleanup only after containment.
6. Record the incident and preventive action without copying the secret.

Never commit AWS keys, GitHub tokens, database passwords, device private keys,
real tenant data, Terraform state, database dumps, or unredacted logs.

## Security Boundaries

- Human users and chargers use separate identity mechanisms.
- Tenant membership is resolved from trusted identity, not request data alone.
- Tenant isolation must be enforced and tested independently in PostgreSQL,
  telemetry storage, object storage, broker topics, exports, and logs.
- The public repository uses synthetic data only.
