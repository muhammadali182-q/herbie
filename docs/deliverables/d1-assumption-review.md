# Assignment 1 Assumption Review

This review supplements, but does not rewrite, the submitted Assignment 1 PDF.
It identifies calculations and architecture claims that must be corrected or
validated in D2-D4.

## Workload

The baseline calculation is valid:

```text
2,000 chargers / 10 seconds = 200 messages/second
200 * 2,592,000 seconds in 30 days = 518.4 million messages/month
```

The separate fivefold peak assumption conflicts with that monthly total. If
200 messages/second runs for 20 hours and 1,000 messages/second runs for four
hours each day:

```text
30 * 3,600 * ((20 * 200) + (4 * 1,000)) = 864 million messages/month
```

Therefore D2 must define whether 200 messages/second is a continuous baseline,
a daily average, or an off-peak rate. It must also distinguish message-rate
peaks, connection peaks, synchronized timer bursts, and reconnect storms.

## Storage and Request Cost

The PDF states that every reading is written to DynamoDB and quotes $1.25 per
million writes. At 518.4 million readings, writes alone would be approximately
$648/month before relational database, storage, reads, indexes, backups, or
peak volume. This cannot fit inside the stated $243 total database line.

Likewise, one S3 object per event would create 518.4 million PUT requests per
month. The implementation will instead batch events into compressed NDJSON
objects and measure events per object, compressed bytes, and request count.

The revised model must include:

- DynamoDB item size, writes, reads, indexes, TTL, and backup assumptions.
- S3 batch size, compression, PUT/GET requests, retained bytes, and lifecycle.
- CloudWatch log ingestion and retention.
- Broker disks and replication.
- Load balancer capacity, networking, public IPv4, NAT or endpoint costs.
- RDS instance, storage, backup, and deployment topology.
- KMS, secrets, support, tax, and operations labor boundaries.

## Broker Availability

Two broker containers behind a network load balancer do not by themselves
replicate MQTT sessions, subscriptions, commands, or queued messages. Existing
TCP connections do not migrate when a broker fails. The implementation will
demonstrate worker and stateless service recovery and will document a
three-voter broker cluster or managed MQTT service as the target design.

## Availability

The approximately $4,000 avoided-revenue calculation is mathematically
consistent with its assumptions, but the 99.0%, 99.9%, uniform hourly revenue,
and 50% lost-session values are not measured evidence. A short failure drill
can establish recovery time and data loss for a declared fault; it cannot prove
monthly or annual availability.

The final report will separate:

- Provider-published service availability.
- Architectural redundancy.
- Controlled recovery measurements.
- Longitudinal synthetic availability, if enough observation time exists.

## Provider and Customer Economics

The fee calculation is correct under the stated usage:

```text
$6 + (60 sessions * $0.08) = $10.80 per charger/month
2,000 chargers * $10.80 = $21,600 monthly platform revenue
```

However, $444 per charger is gross charging sales, not operator profit. It
excludes energy, demand charges, payment fees, tax, rent, hardware,
maintenance, depreciation, and failed sessions. The reported 95% provider
margin excludes support and other business costs, while the later $12,472
figure should not be called net profit without sales, administration, tax,
ongoing development, and financing.

The approximate staff-inclusive break-even under fixed assumptions is:

```text
($1,128 + $8,000) / $10.80 = 845.2 chargers
```

The 725, 750, and 9,100 charger crossover claims cannot be reproduced from one
published cost point. D2 will provide fixed, variable, and stepwise cost curves
before retaining those claims.

## Claim Corrections

| Original idea | Required wording until verified |
|---|---|
| Built on AWS | Designed for AWS; deployed evidence will identify the actual profile |
| Scalable to 2,000 chargers | Target; report measured connection and message limits separately |
| Highly available / 99.9% | Architectural objective; report provider claims and measured recovery separately |
| One tenant cannot affect another | Security and performance-isolation objective requiring separate tests |
| Cloud costs $1,128/month | Preliminary model requiring a reproducible bill of materials and workload correction |
| OCPP compatible | Simplified MQTT inspired by central-system flows; mapping only unless interoperability is tested |

## D2-D4 Resolution

- D2 will freeze the workload contract, architecture bill of materials,
  scaling policy, SLOs, threat model, and reproducible economic formulas.
- D3 will retain raw functional, load, isolation, failure, security, and cost
  evidence tied to a fixed release.
- D4 will compare expected and observed results, reassess alternatives, explain
  limitations, and evaluate upgrades, offboarding, and end-of-life.
