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

The foundation is healthy when all backend checks pass, the Compose services
report healthy on a Docker-enabled machine, and `/api/v1/meta` identifies the
expected version and protocol.
