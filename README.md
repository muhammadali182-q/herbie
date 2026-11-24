# H.E.R.B.I.E.

H.E.R.B.I.E. is a multi-tenant EV charging management platform being developed
for the SE 315 Cloud Computing project. It explores how multiple charging
operators can share a cloud platform while retaining isolated data,
tenant-specific configuration, safe site power allocation, usage metering, and
billing.

The project is currently under implementation. Scalability, availability, and
cost figures are targets or models until they are linked to measured evidence.

## Project Scope

- Track B: Solutions on Cloud
- Three simulated charging operators
- Simplified, versioned MQTT charger protocol
- Operator dashboard and cloud-hosted API
- Per-tenant sites, chargers, tariffs, and power limits
- Session authorization, metering, allocation, and billing
- Reproducible deployment, monitoring, upgrade, and teardown procedures

Real charger hardware, payment processing, and full OCPP conformance are
outside the semester prototype. See [the project scope](docs/product/scope.md)
for the complete boundary.

## Documentation

- [Documentation index](docs/README.md)
- [Requirements and acceptance criteria](docs/product/requirements.md)
- [Requirements traceability](docs/product/traceability.md)
- [Architecture overview](docs/architecture/overview.md)
- [Semester implementation plan](docs/roadmap/semester-plan.md)
- [Engineering journal](docs/ENGINEERING_JOURNAL.md)
- [Assignment 1 assumption review](docs/deliverables/d1-assumption-review.md)
- [Architecture decision records](docs/adr/README.md)

## Status

The repository started with the Assignment 1 report. Implementation will be
delivered in verified vertical slices. Each meaningful change must update the
engineering journal and its corresponding tests or evidence.

## License

This project is available under the [MIT License](LICENSE).
