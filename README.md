# Customer Portal

Customer Portal is a backend system that lets customers register, authenticate, manage their profile, sessions, and MFA, and contact support. It's a FastAPI backend (`app/`) with an async PostgreSQL + Redis/Valkey data layer, an Alembic migration chain, and a React/TypeScript frontend (`frontend/`) that consumes its API. The project follows API-first, spec-driven development.

## Status

Spec-driven, artifact-driven delivery: 23 stories across 5 epics (identity, authentication, sessions/MFA, support, navigation) are tracked in [`docs/catalog/stories.yaml`](docs/catalog/stories.yaml). 22 are delivered (`COMPLETED`/`ARCHIVED`); one is `IN_PROGRESS`, sitting at the `READY_FOR_PR` human gate. See [`docs/workflow/workflow-state.yaml`](docs/workflow/workflow-state.yaml) for the current pipeline stage.

## Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) (dependency manager — the project is not `pip install`-able without it)
- PostgreSQL 14+ running locally (or reachable), with a database created for the app
- Redis or [Valkey](https://valkey.io/) running locally (used for caching, rate limiting, MFA/session state)
- Node.js 20+ and npm (for the frontend)

There is no Docker Compose file in this repo — Postgres and Redis/Valkey must be installed and running yourself, or provided via any Postgres/Redis instance you already have.

## Backend setup

1. **Install dependencies**

   ```bash
   uv sync --extra dev
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` — at minimum, point `DATABASE_URL` and `RUNTIME_DATABASE_URL` at your local Postgres, and `VALKEY_URL` at your local Redis/Valkey. Replace every `change-me-in-every-real-environment` value with a real secret before using this outside of local dev. `RUNTIME_DATABASE_URL` is the low-privilege connection the running app uses; `DATABASE_URL` (an owner-role connection) is what migrations run as.

   `GEOIP_DATABASE_PATH` points at a MaxMind GeoLite2 City `.mmdb` file that is **not** included in this repo (licensing). If it's absent, the app logs it and simply omits session geolocation — no setup required unless you want that feature.

3. **Create the database** (if it doesn't already exist)

   ```bash
   createdb customer_portal
   ```

4. **Run migrations**

   ```bash
   uv run alembic upgrade head
   ```

5. **Provision the runtime role** (one-time per database — grants the low-privilege `app_runtime` role used by `RUNTIME_DATABASE_URL` the access it needs; must run after migrations have created the tables)

   ```bash
   psql "$DATABASE_URL" -f scripts/db/provision_runtime_role.sql
   ```

   In every real environment, follow up with `ALTER ROLE app_runtime WITH PASSWORD '<a-real-secret>'` — the script only seeds a dev placeholder.

6. **Run the API**

   ```bash
   uv run uvicorn app.main:app --reload
   ```

   The API is served at `http://localhost:8000`.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://localhost:8000` (see `frontend/vite.config.ts`), so run the backend first. The frontend dev server prints its own local URL (typically `http://localhost:5173`).

## Running tests

```bash
# Backend — unit tests only (no external services)
uv run pytest -m unit

# Backend — full suite, including integration tests (spins up ephemeral
# Postgres/Redis containers via testcontainers; requires Docker)
uv run pytest

# Frontend
cd frontend && npm test
```

## Quality gates

```bash
uv run ruff check .        # lint
uv run mypy .               # type check
uv run lint-imports         # import-linter architecture contracts
uv run pre-commit run --all-files
```

## Repository layout

- [`app/`](app) — FastAPI backend, organized by module under `app/modules/*` (router → service → repository/cache → models/schemas), with shared infrastructure in `app/core/` and `app/db/`.
- [`frontend/`](frontend) — React/TypeScript SPA that consumes the API.
- [`migrations/`](migrations) — Alembic migration chain.
- [`scripts/`](scripts) — operational scripts (DB role provisioning, data retention/purge jobs, audit chain verification).
- [`tests/`](tests) — backend test suite (`unit` and `integration` markers).
- [`AGENTS.md`](AGENTS.md) — engineering rules and conventions for the codebase (architecture, layering, testing, quality gates).
- [`docs/product/`](docs/product) — product vision, epic map, business glossary/rules, personas, non-functional requirements.
- [`docs/stories/`](docs/stories) — user stories with acceptance criteria.
- [`docs/specifications/`](docs/specifications) — formal specs derived from the stories.
- [`docs/reviews/specifications/`](docs/reviews/specifications) — spec review reports.
- [`docs/designs/`](docs/designs), [`docs/decisions/`](docs/decisions), [`docs/plans/`](docs/plans), [`docs/impact-analysis/`](docs/impact-analysis), [`docs/verification/`](docs/verification) — downstream artifact-driven-development stages (API/DB design, open decisions, implementation plans, impact analysis, verification), populated per story as it progresses.
- [`docs/catalog/stories.yaml`](docs/catalog/stories.yaml) — canonical lifecycle status of every story.
- [`docs/workflow/`](docs/workflow) — which story is currently active and at what stage.
- [`.claude/skills/`](.claude/skills) — Claude Code skills used to author and review specs, designs, plans, and tests for this project.
