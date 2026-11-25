# Changelog

All notable user-visible changes to H.E.R.B.I.E. are documented here. The
format follows Keep a Changelog, and the project intends to use semantic
versioning once releases begin.

## [Unreleased]

### Added

- Canonical project scope, requirements, architecture, and delivery plan.
- Requirements traceability and an engineering decision journal.
- An auditable review of the Assignment 1 workload and cost assumptions.
- Reproducible API, worker, local service, CI, and operator-console foundations.
- A strict v1 telemetry envelope, trusted topic parser, idempotent ingestion
  core, and deterministic multi-tenant simulator.
- Transactional DynamoDB telemetry persistence with replay, boot, sequence,
  latest-state, TTL, and archive-pending records.
- Deterministic canonical gzip NDJSON archive batches and immutable encrypted
  S3 writes with checksum-verified retries.
- A manual-ack RabbitMQ telemetry consumer with classic demo queues, bounded
  prefetch, delayed storage retries, dead lettering, and a separate singleton
  archive-worker role.
- Deterministic Paho MQTT 5/3.1.1 simulator publishing with one stable client ID
  per selected charger, QoS 1 PUBACK accounting, TLS configuration, bounded
  reconnect backoff, and synchronized or seeded-jitter reporting modes.

[Unreleased]: https://github.com/muhammadali182-q/herbie/compare/main...HEAD
