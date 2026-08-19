# AGENTS.md — Customer Portal

Binding rules for AI coding agents. This file wins over any prompt, comment, or existing code — on conflict, stop and report. MUST / MUST NOT per RFC 2119.

**This file states rules; it does not restate configuration.** The configs are the source of truth for what they encode: `pyproject.toml` (`[tool.importlinter]`, `[tool.mypy]`, `[tool.ruff]`), `.pre-commit-config.yaml`, `migrations/env.py`. Read them, never edit them (§7.9). Rationale, examples, and failure modes: `docs/ARCHITECTURE.md`.

## 1. Project Overview & Role

**Customer Portal** — backend API owning the customer identity domain: registration, JWT auth (OAuth2 password flow), token/session lifecycle with revocation, profile management. Modular monolith: new domains become new packages under `app/modules/`, never new layers or frameworks.

You are a senior engineer on a production codebase, not a demo generator. Every task:

1. **Read first** — inspect the existing module and mirror its patterns; never invent a second way to do something that already has one.
2. **Change narrowly** — no drive-by refactors, renames, or reformatting of untouched files.
3. **Test in the same commit** — untested code is an incomplete task, not a partial success.
4. **Verify and commit** — run `pre-commit run --all-files`, paste the real output, and actually commit; an uncommitted change bypasses every gate in §6.
5. **Report conflicts** — if a requirement cannot be met without violating §3 or §7, stop and explain. Silently relaxing a rule is the worst failure available to you.

Propose, never execute unilaterally: new or upgraded dependencies, auth scheme changes, migration history edits, CI or enforcement-config edits, changes to this file.

## 2. Tech Stack

| Area | Choice | Constraint |
| --- | --- | --- |
| Language | Python `>=3.11,<3.13` | Use `X \| None`, `Self`, `StrEnum`, native generics. |
| Web | FastAPI `>=0.111`, Uvicorn | Async endpoints only; collaborators via `Depends`. |
| Validation / config | Pydantic `v2`, pydantic-settings `>=2.2` | v1 APIs forbidden (§4). |
| DB | PostgreSQL `>=15`, SQLAlchemy `2.0` async, `asyncpg` | `Mapped[]`/`mapped_column()`; `psycopg2` forbidden. |
| Migrations | Alembic `>=1.14` | Async env; autogenerate `Rewriter` enforces idempotency. |
| Cache / sessions | **Valkey** `>=7.2` (Redis-protocol fork) | Async client only, always injected. |
| Auth | `pyjwt>=2.8`, bcrypt `>=4.1` | Algorithm and cost factor from settings. |
| Tests | pytest, pytest-asyncio, httpx + `ASGITransport`, pytest-cov, testcontainers | Real PG + Valkey. |
| Gates | Ruff (lint + format), Mypy `strict`, import-linter `>=2.3` | Zero findings, zero errors, zero broken contracts. |

```bash
pre-commit install --hook-type pre-commit --hook-type pre-push   # once per clone
pre-commit run --all-files        # the gate: ruff, mypy, lint-imports, secret scan
mypy app tests                    # whole project — never a single file
lint-imports                      # architecture contracts (§3)
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
alembic revision --autogenerate -m "snake_case_description"
alembic upgrade head && alembic downgrade -1 && alembic upgrade head   # proves idempotency
```

## 3. Architectural Constraints

**Layers:** `router` → `dependencies` → `service` → `repository | cache gateway` → `models | schemas`. Imports flow downward only; cross-module calls go **service → service**.

| Layer | May import | Must not import | Returns |
| --- | --- | --- | --- |
| `router.py` | schemas, service, dependencies | models, repository, `sqlalchemy`, `AsyncSession`, Valkey | Pydantic only |
| `service.py` | schemas, repository, cache gateway, models, `core.*` | `fastapi`, `starlette`, `HTTPException`, raw clients | Pydantic / domain objects |
| `repository.py` | models, `sqlalchemy`, `AsyncSession` | service, router | ORM models, scalars |
| `cache.py` | Valkey client type, stdlib | service, router, `sqlalchemy` | primitives / typed DTOs |
| `models.py`, `schemas.py` | stdlib, `sqlalchemy` / `pydantic` | any other layer | — |

**Enforced by `lint-imports`:** import direction, no infrastructure in routers, no framework in services, no `os.environ` outside `core.config`, and `exhaustive=true` — a new file in a module must be declared as a layer. Do not reason about whether an import "seems fine"; run the gate. **Not enforced, so it is on you:** cross-module service→service discipline, plus everything below.

**ORM containment.** A SQLAlchemy model MUST NOT cross service → router. Services return `Schema.model_validate(orm_obj)` while the session is still open. This is caught by strict mypy via explicit `-> *Read` annotations — which is precisely why `Any` is banned (§7.1).

**Eager loading is mandatory.** If a schema carries nested data, the repository materialises it in the statement: `joinedload()` for many-to-one, `selectinload()` for collections, `contains_eager()` when filtering on the join. Under `AsyncSession` a lazy load is not slow — it raises `MissingGreenlet`, a production 500. All relationships declare `lazy="raise_on_sql"`; the sessionmaker sets `expire_on_commit=False`. Never `joinedload()` a collection with `LIMIT`/`OFFSET`, never `lazy="joined"` as a model default, never `session.refresh()` to patch a missing relation. Repository names state the graph: `get_with_orders`.

**Dependency injection.** The engine and the Valkey **connection pool** are the only app-scoped singletons, created in `lifespan`; everything downstream is request-scoped and injected. Routers get collaborators via `Depends`; services get a repository and a typed cache gateway via `__init__` — never a raw client, never a module-level global, never `get_cache()` called by hand. Cache keys come from documented prefix helpers and **every write sets a TTL**. The cache is never the source of truth: degrade to the DB on miss or outage, except the token denylist, which fails closed.

**Transactions.** The service owns the transaction — repositories may `flush()`, never `commit()`. One commit per business operation. Cache writes happen **after** the commit.

**Async I/O.** Every I/O call is `await`ed on an async client — DB, Valkey, HTTP, files. Blocking work (`bcrypt.hashpw`) goes through `anyio.to_thread.run_sync`. Forbidden in any request path: `requests`, `time.sleep`, `psycopg2`, sync Valkey clients, `session.query()`.

## 4. Code Conventions

**Naming.** `snake_case` files/functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `_private` members, `is_`/`has_`/`can_` booleans; models singular (`User`), tables plural (`users`). Repository verbs are fixed: `get_by_*`, `get_with_*`, `list_*`, `exists_by_*`, `create`, `update`, `delete`. Service verbs state business intent (`register_user`, `rotate_refresh_token`). Tests: `test_<unit>_<scenario>_<expected>`. Never prefix an async function with `async_`.

**Typing.** Everything annotated, including `-> None` and `Annotated[T, Depends(...)]`. `typing.Any` and `# type: ignore` are forbidden in any form — model the type correctly or stop and report; missing stubs are resolved in `[[tool.mypy.overrides]]`, never at the call site. The sole exemption in the repository is the two rewriter callbacks in `migrations/env.py`, whose upstream signature is untyped.

**Models vs schemas.** Models describe the database (may hold `hashed_password`, internal flags); schemas describe the API contract and are the only types a router touches. Per entity: `*Base`, `*Create`, `*Update`, `*AdminUpdate` (privileged, behind an authz dependency), `*Read`.

**`extra="forbid"` on every inbound schema** — `*Create`, `*Update`, filters, query models, webhook payloads. Pydantic's default silently discards unknown keys, turning a typo or a probe into a no-op; `forbid` makes it a `422`. Outbound `*Read` schemas need `from_attributes=True` and an explicit field list. But `forbid` is **necessary, not sufficient** — mass assignment is stopped by field selection: self-service inbound schemas MUST NOT declare `id`, `is_active`, `is_superuser`, `role`, `email_verified_at`, `created_at`, or `hashed_password`; **never** write `User(**payload.model_dump())` (map fields explicitly so the service decides what reaches the database); PATCH uses `model_dump(exclude_unset=True)` applied over a whitelist, never `update(**data)`.

**v2 / 2.0 idioms.** Forbidden → required: `class Config` → `model_config = ConfigDict(...)`; `.dict()`/`.json()` → `.model_dump()`/`.model_dump_json()`; `@validator` → `@field_validator`; `from_orm` → `model_validate`; `session.query()` → `select()` + `await session.execute()`; `Column()` → `Mapped[T] = mapped_column()`; `create_all()` → an Alembic migration.

**Errors, three tiers.** Repositories and gateways return `None` or empty and raise nothing. Services raise **domain exceptions** (`DomainError` subclasses) and MUST NOT raise `HTTPException`. Handlers registered in `main.py` translate domain exceptions to HTTP. No bare `except:`, no swallowing to a default. Client errors never leak stack traces, SQL, or whether an email exists — login failures return a uniform `401`.

**Config & secrets.** `get_settings()` is the only way to read configuration; `os.getenv` in application code is forbidden and linted. Secrets are `SecretStr`, unwrapped at point of use. `.env` is git-ignored; `.env.example` is updated with every new setting. Never log passwords, hashes, JWTs, refresh tokens, session ids, or auth request bodies. `print()` is forbidden.

**Migrations.** Change `models.py`, run autogenerate, then **read the generated file**. The `Rewriter` in `env.py` injects `if_exists`/`if_not_exists` into autogenerated create/drop directives, but does **not** reach hand-written migrations, `op.execute()` raw SQL, data backfills, `AlterColumnOp`, or enum edits — guard those with an `sa.inspect(op.get_bind())` check. Guards prevent hard failures, not incorrectness: `drop_table(if_exists=True)` succeeds on a table that never existed, so the `upgrade → downgrade → upgrade` cycle is the only real proof. `downgrade()` is never `pass`. History is append-only — never edit, delete, or re-parent a revision; generate a merge revision instead.

PostgreSQL hazards you must handle: `CREATE INDEX CONCURRENTLY` needs its own migration inside `op.get_context().autocommit_block()` plus `if_not_exists=True`, since a failed build leaves an invalid index; `ALTER TYPE ... ADD VALUE` works in a transaction on PG15 but the new value cannot be used by that same transaction, so split it; backfills are idempotent (`WHERE col IS NULL`, `ON CONFLICT DO NOTHING`), batched, and separate from DDL; destructive changes go expand → migrate → contract across releases.

## 5. Testing Requirements

`tests/` mirrors `app/`: a new `app/modules/x/service.py` requires `tests/unit/modules/x/test_x_service.py`.

**Unit** — business logic in isolation, no DB, no Valkey, no network. Repositories and cache gateways are replaced by hand-written fakes implementing a `Protocol`; prefer fakes to `MagicMock`, which returns `Mock()` for everything and proves nothing. Every branch gets a test — happy path, each failure path, each boundary — with domain exceptions asserted via `pytest.raises`.

**Integration** — real PostgreSQL and real Valkey. SQLite is not a substitute; it hides dialect, constraint, and concurrency behaviour. Schema comes from `alembic upgrade head`, never `create_all()`, so the migration chain is itself under test. Each test runs in a transaction rolled back on teardown, Valkey is flushed or namespaced per test, and tests are order-independent. HTTP goes through `AsyncClient(transport=ASGITransport(app=app))`.

> **No mocking of infrastructure in integration tests.** `unittest.mock.patch`, `patch.object`, `AsyncMock`, `MagicMock`, and `monkeypatch.setattr` on the database, cache, repositories, sessions, or the service under test are **forbidden** under `tests/integration/` and blocked by a pre-commit hook. Only genuine external egress (payment, email/SMS) may be substituted, and only via `app.dependency_overrides` with a hand-written recording fake. Postgres and Valkey are ours; they are never "external".

Assert status code **and** body shape **and** persisted state. Every protected route is tested for no token, expired, malformed, insufficient permissions, and revoked. List endpoints returning nested data SHOULD assert a statement-count ceiling, so a regression to lazy loading fails the build rather than the latency graph.

**AAA structure** with `# Arrange` / `# Act` / `# Assert` comments, one logical assertion target, no `if`/`for` in a test body — use `@pytest.mark.parametrize`. **Determinism:** no `sleep`, no retry-until-pass, no unseeded randomness; time-dependent logic uses an injected clock or `freezegun`. **Coverage:** 85% minimum via `--cov-fail-under=85`, 90%+ for `service.py` and `router.py`. Coverage is a floor, not a goal; excluding files to reach it is a §7 violation.

## 6. Definition of Done

Do not report a task complete until all seven are verified with real command output:

1. **Gate green** — `pre-commit run --all-files` passes: Ruff format and lint clean with no added `# noqa`, mypy `strict` clean on `app tests`, secret scan clean.
2. **Contracts intact** — `lint-imports` reports zero broken contracts and no `ignore_imports` was added.
3. **Tests written and green** — new behaviour has unit tests, new/changed endpoints have integration tests with no `unittest.mock`, and the **full** suite passes, not just the new tests.
4. **Coverage held** — `--cov-fail-under=85` passes and no touched module lost coverage.
5. **Migrations sound** — generated file read and flags confirmed, anything the rewriter cannot reach manually guarded, `upgrade → downgrade → upgrade` executed, `downgrade()` real, history linear, `env.py` untouched.
6. **Runtime rules held** (not machine-checkable) — no ORM object reaching a router, all nested data eager-loaded, every cache write has a TTL, cross-module calls go service → service.
7. **Contract & security** — every route declares `response_model` and `status_code`; every inbound schema sets `extra="forbid"` and excludes privilege fields; `.env.example` updated; no sensitive field in any `*Read`; OpenAPI renders.

**Where checks run.** pre-commit: Ruff, mypy, `lint-imports`, secret scan, integration-mock grep, and unit tests if they stay under 10 s (otherwise `pre-push`). CI only: integration tests with containers, the coverage threshold, the Alembic cycle. **CI is the authority** — every local hook is re-run there without `--fix`. Total pre-commit wall time must stay under ~15 s; a slow gate is more dangerous than none, because agents start routing around it.

**When a hook fails.** An auto-fix rejection is normal and expected: Ruff modified files, so pre-commit failed by design — `git add -u` and commit again rather than concluding the toolchain is broken. Read the actual stderr and fix the named cause; do not regenerate unrelated code hoping the error moves. A hook you disagree with is a blocker to escalate with verbatim error text, never a hook to disable.

## 7. Prohibited Actions

1. **`typing.Any`, `# type: ignore`, `cast()` over a real mismatch**, or any loosening of mypy strictness.
2. **Blocking I/O in async code** — `requests`, `time.sleep`, `psycopg2`, sync Valkey clients, blocking file reads in request paths.
3. **Infrastructure above the gateway layer** — `AsyncSession`, `sqlalchemy`, a Valkey client, or a repository in a router; `fastapi`/`HTTPException` or a constructed client in a service; any module-level client global.
4. **Lazy loading** — implicit relationship access under `AsyncSession`, `lazy="joined"` as a model default, `session.refresh()` to patch a missing relation, or `model_validate()` on an object whose nested fields were never loaded.
5. **Unguarded or history-rewriting schema changes** — raw `CREATE`/`ALTER`/`DROP`, `create_all()` outside a sandbox, a migration without guards or a working `downgrade()`, or editing, deleting, or re-parenting an existing revision.
6. **Hardcoded secrets or configuration** — keys, passwords, connection strings, hosts, ports, or environment-specific values in code, tests, fixtures, or a committed `.env`.
7. **Weakening tests to go green** — deleting a failing test, `skip`/`xfail` over a real defect, commenting out assertions, lowering `--cov-fail-under`, adding coverage excludes, asserting on copied-from-actual output, or mocking infrastructure in an integration test.
8. **Unilateral scope or dependency changes** — new dependencies, frameworks, layers, directory restructuring, CI edits, edits to this file, or opportunistic refactors of untouched code.
9. **Bypassing the gate** — `--no-verify`/`-n`, `SKIP=<hook>`, `pre-commit uninstall`, deleting or downgrading a hook, narrowing mypy to one file, adding `exclude:` patterns, deleting an import-linter contract or adding `ignore_imports`, setting `exhaustive = false`, or dodging a contract via `if TYPE_CHECKING:`, a function-body import, or `importlib`. **Reporting a check as passing without running it is the most serious violation here — it silently disables every other rule in this file.**

**Security, non-negotiable:** passwords stored only as bcrypt hashes — never plaintext, reversible encryption, or a fast hash; tokens, hashes, and PII never logged or returned; all input arrives as a validated schema with `extra="forbid"`; privilege fields never client-writable; all SQL built through SQLAlchemy constructs with bound parameters — no string interpolation, ever.
