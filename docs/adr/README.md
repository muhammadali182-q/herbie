# Architecture Decision Records

ADRs preserve significant decisions and their consequences. Accepted records
are not rewritten to hide history; a later decision supersedes them.

| ADR | Status | Decision |
|---|---|---|
| [ADR-0001](0001-modular-monolith-process-roles.md) | Accepted | Use a modular monolith with independently runnable process roles |
| [ADR-0002](0002-mqtt-and-durable-work.md) | Proposed | Validate RabbitMQ as the MQTT endpoint and durable work broker |
| [ADR-0003](0003-data-ownership.md) | Accepted | Separate control, hot telemetry, and archive ownership |
| [ADR-0004](0004-telemetry-ordering-and-archive-outbox.md) | Accepted | Use explicit boot/sequence ordering and a durable canonical archive outbox |

Statuses are `Proposed`, `Accepted`, `Rejected`, `Deprecated`, and
`Superseded`.
