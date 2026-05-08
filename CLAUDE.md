# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Full-stack OSINT + pentesting investigation platform. React 18 + Vite SPA frontend, FastAPI Python backend, with PostgreSQL, Redis, Neo4j, and MinIO. Celery handles async scan tasks.

The app is accessed via nginx at `http://localhost:8080` (host port 8080 → container port 80).

## Commands

### Development

```bash
make dev              # Start full dev environment (all Docker services)
make prod             # Start production build
make logs             # Stream container logs
make shell            # SSH into API container
make clean            # Remove all containers/volumes (destructive)
make seed             # Seed default admin users into the database
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

| Service       | Port  | Purpose                                     |
|---------------|-------|---------------------------------------------|
| nginx         | 8080  | Reverse proxy (host-facing)                 |
| frontend      | 5173  | Vite dev server                             |
| api           | 8000  | FastAPI (4 Uvicorn workers)                 |
| worker        | —     | Celery heavy tasks (Playwright)             |
| worker-light  | —     | Celery light tasks (concurrency 4)          |
| flower        | 5555  | Celery monitoring (basic auth required)     |
| postgres      | 5432  | Primary database                            |
| redis         | 6379  | Cache + Celery broker + circuit breakers    |
| neo4j         | 7687  | Graph database for entity linking           |
| minio         | 9000  | S3-compatible object storage                |

### Backend (`backend/src/`)

Layered architecture: **Router → API handler → Use cases → Adapters → Repositories**

- `main.py` — App factory, middleware stack, `_ROUTER_REGISTRY` (auto-discovers all routers at startup; in `DEBUG=true` mode, import failures are logged and skipped rather than crashing)
- `dependencies.py` — FastAPI DI providers: `get_db` (yields `AsyncSession`, commits on success, rolls back on exception), `get_app_settings`
- `config.py` — All configuration via environment variables (Pydantic Settings)
- `api/v1/` — FastAPI routers grouped by domain
- `api/v1/auth/` — Login, register, refresh, TOTP, WebAuthn, sessions, SSO, ToS
- `api/v1/investigations/` — Core investigation CRUD, graph, fork, diff, comments, reports
- `api/graphql/` — Alternative GraphQL interface
- `core/` — Domain models, ports (interfaces), and use cases (business logic)
- `core/domain/entities/types.py` — `ScanInputType` and `ScanStatus` enums used throughout
- `adapters/` — External integrations: DB (SQLAlchemy), cache (Redis), search (Elasticsearch), scanners, AI, security
- `adapters/scanners/` — 127+ OSINT scanners registered via `registry.py`
- `workers/` — Celery task definitions and beat schedule
- `workers/celery_app.py` — Celery config, queue routing, beat schedule

**Key patterns:**
- Async-first: SQLAlchemy 2.0 + asyncpg throughout
- Bulkhead queue pattern: `heavy` (Playwright), `light` (API calls), `graph` (Neo4j), `pentest_heavy`, `pentest_light`
- Redis-backed circuit breakers per scanner (`adapters/scanners/circuit_breaker.py`)
- Structured logging via `structlog` (JSON output); use `log = structlog.get_logger(__name__)`
- Rate limiting per task type via Celery `task_annotations`

### Scanner System

Every scanner lives in `adapters/scanners/` and must:
1. Subclass `BaseOsintScanner` (`adapters/scanners/base.py`)
2. Define `scanner_name: str`, `supported_input_types: frozenset[ScanInputType]`
3. Implement `async _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]`
4. Optionally override `_extract_identifiers`, `_compute_confidence`, `source_confidence`, `cache_ttl`, `scan_timeout`
5. Register an instance in `create_default_registry()` in `adapters/scanners/registry.py`

`BaseOsintScanner.scan()` handles: cache lookup → circuit breaker check → timeout enforcement → `_do_scan` → content-hash deduplication → cache write → metrics.

Scanner exceptions: `RateLimitError`, `ScanAuthError`, `ScannerNotFoundError`, `ScannerQuotaExceededError`, `ScannerUnavailableError` (from `adapters/scanners/exceptions.py`).

### Frontend (`frontend/src/`)

Feature-based SPA with React Router.

Each feature under `features/` follows a consistent structure:
- `api.ts` — raw API call functions (Axios)
- `hooks.ts` — TanStack Query hooks wrapping `api.ts`
- `types.ts` — TypeScript interfaces/types for the feature
- `schemas.ts` — Zod validation schemas (where forms exist)
- `*Page.tsx` — top-level page components
- `components/` — sub-components for the feature

Key features: `graph/`, `investigations/`, `auth/`, `settings/`, `chat/`, `dashboard/`, `payments/`, `image-checker/`, `doc-metadata/`, `email-headers/`, `mac-lookup/`, `domain-permutation/`, `cloud-exposure/`, `stealer-logs/`, `supply-chain/`, `fediverse/`

`shared/api/client.ts` — Axios instance with JWT auto-refresh: on 401, queues failed requests, refreshes token, retries all queued requests.

**State management:**
- TanStack Query v5 — server state; staleTime constants in `shared/api/queryConfig.ts`
- Zustand — minimal client-side state (auth store: `user` + `isAuthenticated` persisted, `accessToken` not persisted)
- React Hook Form + Zod — all form validation
- React Query DevTools shown in DEV mode

**Graph visualization** (`features/graph/`):
- ReactFlow for rendering nodes/edges
- Custom node types in `components/nodes/` (IP, Domain, Email, Person, ASN, Certificate, Vulnerability, Breach, etc.)
- `useGraphLayout.ts` — layout algorithms
- `hooks.ts` — data fetching and state management for graph

### Authentication Flow

1. Login → JWT access token + httpOnly refresh cookie
2. Axios interceptor attaches `Authorization: Bearer {token}` to every request
3. On 401 → token refresh triggered via `_refreshClient`, failed requests queued and retried
4. WebAuthn (passkeys) and TOTP supported as 2FA
5. Access token is NOT persisted to storage — rehydrated on reload via refresh cookie

Default dev users (after `make seed`): `admin@osint.platform` / `admin`

## Environment Variables

Copy `.env.example` to `.env`. Key variables:
- `DATABASE_URL` — PostgreSQL async URL (`postgresql+asyncpg://...`)
- `REDIS_URL` — Redis connection
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`
- `FLOWER_USER`, `FLOWER_PASSWORD` — Flower basic auth
- `PROXY_MODE` — `direct` (default, exposes server IP), `tor`, or `socks5` (recommended for production)
- `DEBUG` — set `true` to allow missing router modules to be skipped at startup instead of crashing
- `SCANNER_RATE_LIMIT_COUNTS_AS_FAILURE` — whether rate limit errors open the circuit breaker
- External API keys: `SHODAN_API_KEY`, `HIBP_API_KEY`, `VIRUSTOTAL_API_KEY`, etc.
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
