# Local Development

## Prerequisites

- Python 3.12 or later
- uv 0.11 or later
- Docker Engine with Compose v2 for service integration
- Node.js 22 or later for the operator dashboard

The current Windows workstation has Python, uv, and Node.js but does not have
Docker. Backend unit checks can run locally; service integration must run in CI
or on a team machine with Docker until that prerequisite is installed.

## Backend Setup

```powershell
uv sync --all-groups
uv run ruff check backend
uv run ruff format --check backend
uv run mypy
uv run pytest
```

Run the API:

```powershell
uv run herbie-api
```

The OpenAPI page is available at `http://127.0.0.1:8000/docs` and liveness at
`http://127.0.0.1:8000/health/live`.

## Local Services

Copy `.env.example` to an untracked `.env` only when values need to change.
The checked-in defaults are development-only credentials.

```powershell
docker compose up -d postgres rabbitmq dynamodb minio
docker compose --profile app up --build
```

The telemetry worker fails closed when `HERBIE_REGISTERED_DEVICES` is empty.
For a local device, set it to a JSON list of canonical identities before
starting the app profile:

```text
HERBIE_REGISTERED_DEVICES=["<tenant UUID>/<charger UUID>"]
```

The `worker` service consumes MQTT-derived telemetry and writes DynamoDB. The
single `archive-worker` service drains archive-pending records to MinIO. Do not
scale `archive-worker` beyond one instance until a durable batch-claim protocol
exists.

After device users and exact topic permissions are provisioned, publish a
bounded deterministic scenario with:

```powershell
$env:HERBIE_SIMULATOR_MQTT_PASSWORD = "<untracked device password>"
uv run herbie-simulator --mqtt --mqtt-host localhost `
  --tenants 1 --chargers-per-tenant 1 --rounds 1 `
  --connection-count 1 --message-rate 1 --reporting-mode synchronized
```

The default username is `device-{charger_id}`. The simulator output reports
PUBACKs as broker acceptance and explicitly labels durable ingestion as
unmeasured. Confirm DynamoDB and archive state separately before making an
end-to-end claim. Use `--mqtt-tls --mqtt-ca-file <path>` for a TLS listener;
add `--mqtt-cert-file` and `--mqtt-key-file` together for mutual TLS targets.

Messaging topology:

| Resource | Purpose |
|---|---|
| `amq.topic` | MQTT/AMQP topic exchange supplied by RabbitMQ |
| `herbie.telemetry.v1` | Durable classic telemetry work queue |
| `herbie.control.v1` | Separate future control-response queue |
| `herbie.telemetry.retry.v1` | Bounded delayed storage retry queue |
| `herbie.telemetry.dead.v1` | Poison, security, clock, conflict, and exhausted-retry queue |

Local service endpoints:

| Service | Endpoint |
|---|---|
| API container | `http://localhost:8080` |
| PostgreSQL | `localhost:5432` |
| MQTT | `localhost:1883` |
| RabbitMQ management | `http://localhost:15672` |
| RabbitMQ metrics | `http://localhost:15692/metrics` |
| DynamoDB Local | `http://localhost:8001` |
| MinIO API | `http://localhost:9000` |
| MinIO console | `http://localhost:9001` |

## Operator Dashboard

Install and run the frontend outside Docker with:

```powershell
npm install
npm run dev:web
```

The dashboard is available at `http://127.0.0.1:5173`. Until live API wiring is
implemented, every operational value on the screen is visibly identified as
synthetic seed data.

Run its checks with:

```powershell
npm run lint:web
npm run test:web
npm run build:web
```

## Reset

The following removes local service data. Never run it against a shared or
cloud environment.

```powershell
docker compose --profile app down --volumes --remove-orphans
```

## Success Check

The foundation is healthy when all backend checks pass; PostgreSQL, RabbitMQ,
and the API report healthy on a Docker-enabled machine; DynamoDB and MinIO
respond at their listed loopback endpoints; and `/api/v1/meta` identifies the
expected version and protocol. Worker container health checks remain disabled
because those roles do not expose HTTP; dependency-aware readiness is tracked
as operations work rather than being inferred from process existence.
