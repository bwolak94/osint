# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack OSINT investigation platform. React 18 + Vite SPA frontend, FastAPI Python backend, with PostgreSQL, Redis, Neo4j, and MinIO. Celery handles async scan tasks.

## Commands

### Development

```bash
make dev              # Start full dev environment (all Docker services)
make prod             # Start production build
make logs             # Stream container logs
make shell            # SSH into API container
make clean            # Remove all containers/volumes (destructive)
```

### Testing

```bash
make test             # Run all tests (backend + frontend)
make test-backend     # pytest with coverage inside Docker
make test-frontend    # Vitest inside Docker

# Run a single backend test
docker compose exec api pytest backend/tests/unit/path/to/test_file.py::test_name -v

# Run a single frontend test
docker compose exec frontend npm run test -- --testPathPattern=ComponentName
```

### Linting & Type Checking

```bash
make lint                                    # ruff (Python) + eslint (JS)
docker compose exec api ruff check src/      # Python lint only
docker compose exec frontend npm run type-check  # TypeScript strict check
```

### Database Migrations

```bash
make migrate                                 # Run alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "description"
```

## Architecture

### System Stack

| Service       | Port  | Purpose                           |
|---------------|-------|-----------------------------------|
| nginx         | 80    | Reverse proxy                     |
| frontend      | 5173  | Vite dev server                   |
| api           | 8000  | FastAPI (4 Uvicorn workers)       |
| worker        | —     | Celery heavy tasks (Playwright)   |
| worker-light  | —     | Celery light tasks (concurrency 4)|
| flower        | 5555  | Celery monitoring                 |
| postgres      | 5432  | Primary database                  |
| redis         | 6379  | Cache + Celery broker             |
| neo4j         | 7687  | Graph database for entity linking |
| minio         | 9000  | S3-compatible object storage      |

### Backend (`backend/src/`)

Layered architecture: **Router → API handler → Use cases → Adapters → Repositories**

- `api/v1/` — FastAPI routers grouped by domain (investigations, graph, auth, search, etc.)
- `api/v1/investigations/` — Core investigation CRUD, graph, fork, diff
- `api/graphql/` — Alternative GraphQL interface
- `core/` — Domain models and use cases (business logic)
- `adapters/` — External integrations: DB (SQLAlchemy), cache (Redis), search (Elasticsearch), scanners, AI, security
- `adapters/scanners/` — OSINT scanners (Shodan, GitHub, Telegram, ASN, subdomain, etc.) registered via `registry.py`
- `workers/` — Celery task definitions; three queue classes: `light`, `heavy`, `graph`
- `config.py` — All configuration via environment variables (Pydantic Settings)
- `main.py` — App factory, middleware stack, router registration

**Key patterns:**
- Async-first: SQLAlchemy 2.0 + asyncpg throughout
- Bulkhead queue pattern: heavy (Playwright) vs light (API calls) vs graph tasks
- Structured logging via `structlog` (JSON output)
- Rate limiting per task type via middleware

### Frontend (`frontend/src/`)

Feature-based SPA with React Router.

- `features/graph/` — Core graph visualization using ReactFlow; nodes, edges, layout, hooks
- `features/investigations/` — Investigation list, bulk actions
- `features/settings/` — Passkey, sessions, sidebar settings
- `features/chat/` — AI chat interface
- `features/dashboard/` — Main dashboard
- `shared/api/client.ts` — Axios instance with JWT auto-refresh (queues failed requests on 401, retries with new token)

**State management:**
- TanStack Query — server state / data fetching
- Zustand — minimal client-side state
- React Hook Form + Zod — all form validation

**Graph visualization** (`features/graph/`):
- ReactFlow for rendering nodes/edges
- Multiple custom node types in `components/nodes/` (IP, Domain, Email, Person, ASN, Certificate, etc.)
- `useGraphLayout.ts` — layout algorithms
- `hooks.ts` — data fetching and state management for graph

### Authentication Flow

1. Login → JWT access token + httpOnly refresh cookie
2. Axios interceptor attaches `Authorization: Bearer {token}` to every request
3. On 401 → token refresh triggered, failed requests queued and retried
4. WebAuthn (passkeys) and TOTP supported as 2FA

### Scanner System

Scanners in `adapters/scanners/` implement a common interface and register via `registry.py`. New scanners must be registered there. Triggered via API endpoints that enqueue Celery tasks.

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `DATABASE_URL` — PostgreSQL async URL (`postgresql+asyncpg://...`)
- `REDIS_URL` — Redis connection
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`
- `MINIO_*` — S3 object storage config
- External API keys: `SHODAN_API_KEY`, `HIBP_API_KEY`, `VIRUSTOTAL_API_KEY`
- `CORS_ORIGINS` — allowed frontend origins

## Testing Patterns

**Backend** (`backend/tests/`):
- `asyncio_mode = "auto"` — all async tests work without decorators
- Shared fixtures in `conftest.py` files
- Unit tests mock external adapters; integration tests use real DB via Docker

**Frontend** (`frontend/src/`):
- Vitest + Testing Library
- MSW 2.x for API mocking
- Test files colocated with features or in `tests/` subdirectories
