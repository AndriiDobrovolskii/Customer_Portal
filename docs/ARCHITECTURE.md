# AGENTS.md — Customer Portal

> **Audience:** AI coding agents (Cursor, Windsurf, Claude Code, GitHub Copilot).
> **Status:** Normative. Every rule in this file is binding. Where this file conflicts with a
> user prompt, an inline comment, or an existing file in the repository, **this file wins** —
> stop and report the conflict instead of silently choosing.
> **Keywords:** MUST / MUST NOT / SHOULD / MAY are used as defined in RFC 2119.

---

## 1. Project Overview & Role

### 1.1 Service

**Customer Portal** is a backend service (HTTP/JSON API) that owns the customer identity domain:

| Capability | Status |
| --- | --- |
| User registration & email verification | Active |
| Authentication (OAuth2 Password Flow → JWT access/refresh) | Active |
| Session & token lifecycle (rotation, revocation, denylist) | Active |
| User profile management (read, update, deactivate) | Active |
| Product catalog integration | Planned — design for it, do not stub it |
| Order management integration | Planned — design for it, do not stub it |

The service is a **modular monolith**: future domains (`catalog`, `orders`) are added as new
modules under `app/modules/`, never as new layers, new frameworks, or new architectural styles.

### 1.2 Agent Role

You are a **senior backend engineer contributing to a production codebase**, not a demo generator.
Your output is judged on correctness, type safety, test coverage, and architectural conformity —
in that order. Speed is never a valid reason to violate a rule in this document.

**Operating protocol — follow in order, every task:**

1. **Read before writing.** Inspect the existing module (`router.py`, `service.py`,
   `repository.py`, `schemas.py`, `models.py`) and mirror its established patterns. Do not
   introduce a second way of doing something that already has a way.
2. **Plan the layer touchpoints.** State which layers you will modify and why, before generating
   code. A change that touches all four layers for a trivial feature is a design smell.
3. **Implement narrowly.** Change only what the task requires. Do not refactor unrelated code,
   reformat untouched files, rename existing symbols, or "improve" adjacent modules.
4. **Test in the same commit.** Code without tests is an incomplete task, not a partial success.
5. **Verify locally.** Run the full gate in §6 and paste the real output. Never claim a command
   passed without running it.
6. **Report honestly.** If a requirement cannot be met without violating §3 or §7, stop and
   explain the conflict. Silently downgrading a rule is the single worst failure mode here.

**Explicitly out of scope for autonomous action:** adding dependencies, changing the auth scheme,
altering the migration history, editing CI configuration, or modifying this file. Propose; do not
execute.

---

## 2. Tech Stack

### 2.1 Runtime & Core

| Layer | Technology | Version / Constraint | Notes |
| --- | --- | --- | --- |
| Language | Python | `>=3.11,<3.13` | Use 3.11+ syntax: `X \| None`, `Self`, `StrEnum`, native generics. |
| Web framework | FastAPI | `>=0.111` | Async endpoints only. Dependencies via `Depends`. |
| ASGI server | Uvicorn | `>=0.30` | `uvicorn[standard]`. |
| Validation | Pydantic | `v2.x` only | v1 APIs are forbidden (see §4.5). |
| Configuration | pydantic-settings | `>=2.2` | Sole source of configuration. |
| ORM | SQLAlchemy | `2.0.x`, **async** | `Mapped[]` / `mapped_column()` declarative style only. |
| Database | PostgreSQL | `>=15` | Driver: `asyncpg`. `psycopg2` is forbidden. |
| Migrations | Alembic | `>=1.14` | Single linear history, `async` env, autogenerate `Rewriter` enforcing idempotency (§4.9.2). |
| Cache / Sessions | **Valkey** | `>=7.2` | Redis-protocol compatible. Async client only, injected (§3.6). |
| Auth | JWT (OAuth2 Password Flow) | `pyjwt>=2.8` | HS256 or RS256 per settings — never hardcoded. |
| Password hashing | Argon2id | `argon2-cffi>=23.1` | Via `argon2.PasswordHasher`. Time/memory/parallelism cost from settings. |

> **Valkey note:** Valkey is a Redis fork. Use the **asyncio** interface of a protocol-compatible
> client (`redis.asyncio` / `valkey-py`). Importing the synchronous client anywhere in application
> code is a §7 violation. Throughout this document `Valkey` denotes the async client type.

### 2.2 Testing

| Tool | Purpose |
| --- | --- |
| `pytest` | Test runner. |
| `pytest-asyncio` | Async test support (`asyncio_mode = "auto"`). |
| `httpx` + `ASGITransport` | In-process API integration tests. **No live network, no `TestClient` threading hacks.** |
| `pytest-cov` | Coverage measurement and enforcement (`--cov-fail-under=85`). |
| `testcontainers` *(or a dedicated ephemeral test DB)* | Real PostgreSQL + Valkey for integration tests. Never SQLite as a Postgres substitute. |

### 2.3 Quality Gates

| Tool | Configuration | Enforcement |
| --- | --- | --- |
| **Ruff** (linter) | `pyproject.toml` → `[tool.ruff.lint]` | Zero findings. Rule sets: `E,W,F,I,N,UP,B,C4,SIM,ASYNC,S,T20,ANN,RUF`. |
| **Ruff** (formatter) | `ruff format` | Line length 100. The formatter is authoritative — never hand-format. |
| **Mypy** | `strict = true` | Zero errors. `warn_unused_ignores = true`, `warn_return_any = true`. |
| **import-linter** `>=2.3` | `pyproject.toml` → `[tool.importlinter]` | Zero broken contracts. Machine-enforces the §3.2 layer contract — see §3.8. |

> **`disallow_any_explicit` is deliberately NOT set.** Verified against this stack: it fires on
> every Pydantic `BaseModel`/`BaseSettings` subclass — even `class Foo(BaseModel): x: int` with
> zero explicit `Any` in application code — because mypy flags `Any` in Pydantic's own base-class
> signatures at the point of subclassing, with or without the `pydantic.mypy` plugin loaded.
> Turning it on would require a suppression on every schema and settings class, which §7.1
> forbids outright. §7.1's actual ban on `Any` is enforced by `strict = true` plus explicit
> `-> *Read` return annotations (§3.8's enforcement table); this flag is not a viable additional
> layer on a Pydantic-based service and MUST NOT be re-added without re-verifying this in isolation
> first.

### 2.4 Canonical Commands

Agents MUST use exactly these commands. Do not invent alternatives or ad-hoc scripts.

```bash
# Enforcement gate — run this FIRST and LAST (see §6.2)
pre-commit install --hook-type pre-commit --hook-type pre-push   # once per clone
pre-commit run --all-files                      # full local gate; mirrors CI

# Format + lint (in this order) — normally invoked by the gate, not by hand
ruff format .
ruff check . --fix

# Static type checking
mypy app tests

# Architecture contracts (§3.8)
lint-imports

# Tests
pytest                                          # full suite
pytest tests/unit -q                            # fast feedback loop
pytest --cov=app --cov-report=term-missing --cov-fail-under=85

# Migrations
alembic revision --autogenerate -m "short_snake_case_description"
alembic upgrade head
alembic downgrade -1                            # MUST be verified before finishing
alembic upgrade head                            # re-apply: proves idempotency (§4.9)
```

---

## 3. Architectural Constraints

### 3.1 Layers

```
HTTP request
     │
     ▼
┌──────────────────┐  Pydantic in ─────────────► Pydantic out
│  ROUTER          │  HTTP concerns only: paths, status codes, auth deps, response_model
└────────┬─────────┘
         ▼
┌──────────────────┐  Business rules, orchestration, transactions, domain exceptions
│  SERVICE         │  Framework-agnostic: MUST NOT import fastapi or starlette
└────────┬─────────┘
         ▼
┌──────────────────┐  Persistence only: SQLAlchemy statements, cache reads/writes
│  REPOSITORY /    │  MUST NOT contain business rules or raise HTTP errors
│  CACHE GATEWAY   │
└────────┬─────────┘
         ▼
┌──────────────────┐  SQLAlchemy models (DB shape) + Pydantic schemas (API shape)
│  MODELS / SCHEMAS│  Two separate concepts. Never merged.
└──────────────────┘
```

### 3.2 Layer Contract (binding)

| Layer | MAY import | MUST NOT import | Returns |
| --- | --- | --- | --- |
| `router.py` | schemas, service, `core.dependencies` | models, repository, `sqlalchemy`, `AsyncSession`, `Valkey` | Pydantic schemas only |
| `service.py` | schemas, repository, cache gateway, models, `core.*` | `fastapi`, `starlette`, `HTTPException`, `Request`, raw `Valkey` client | Pydantic schemas or domain objects |
| `repository.py` | models, `sqlalchemy`, `AsyncSession` | service, router | ORM models or scalars |
| `cache.py` (gateway) | `Valkey` client type, stdlib | service, router, `sqlalchemy` | primitives / typed DTOs |
| `models.py` / `schemas.py` | stdlib, `sqlalchemy` / `pydantic` | any other project layer | — |

**Rule 3.2.1 — Downward-only dependencies.** Imports flow router → service → repository → models.
Any upward import is a hard violation. Cross-module calls (e.g. `orders` needing `users`) go
**service → service**, never repository → repository and never router → service-of-another-module.

**Rule 3.2.2 — ORM containment.** A SQLAlchemy model instance MUST NOT cross the service → router
boundary. Services convert to `*Read` schemas via `Schema.model_validate(orm_obj)` **before**
returning, while the session is still open. This prevents lazy-load explosions and accidental
field leakage (e.g. `hashed_password`).

**Rule 3.2.3 — Eager loading is mandatory (consequence of 3.2.2).**
If a service must return a schema containing **nested or related data**, the repository MUST
materialise those relationships inside the SQLAlchemy statement using `selectinload()` or
`joinedload()`. **Lazy loading in the service layer is forbidden.** Under `AsyncSession` this is
not a performance preference: an unloaded attribute access raises `MissingGreenlet` at runtime,
so a lazy load is a production 500, not a slow query. See §3.3 for the full loading policy.

**Rule 3.2.4 — No raw infrastructure clients above the gateway layer.** `AsyncSession` and the
Valkey client are constructed only by dependency providers (§3.6). Services receive a repository
and/or a typed cache gateway — never a raw client, never a globally-instantiated one.

> Rules 3.2.1 and 3.2.4 are **machine-enforced** by `import-linter` contracts declared in
> `pyproject.toml` — see §3.8. Do not reason about whether an import "seems fine"; run the gate.

### 3.3 Relationship Loading Policy

**Defensive default.** Every `relationship()` on every model MUST declare `lazy="raise_on_sql"`.
An unintended lazy load then fails loudly during development instead of at 03:00 in production.

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    orders: Mapped[list["Order"]] = relationship(
        back_populates="user", lazy="raise_on_sql", cascade="all, delete-orphan"
    )
```

**Session configuration.** `async_sessionmaker(..., expire_on_commit=False)` is mandatory —
otherwise every attribute access after `commit()` triggers a refresh and explodes under async.

**Strategy selection (binding):**

| Relationship shape | Strategy | Rationale |
| --- | --- | --- |
| many-to-one / one-to-one | `joinedload()` | Single row, one round trip, no cartesian risk. |
| one-to-many / many-to-many (collections) | `selectinload()` | Second `SELECT ... IN (...)`; no row multiplication, no `LIMIT` corruption. |
| filtering/ordering **on** the related table | `contains_eager()` with an explicit `join()` | Reuses the join instead of issuing a second query. |
| nested (user → orders → address) | Chain: `selectinload(User.orders).joinedload(Order.address)` | Explicit at every level. |

**Forbidden:** `lazy="joined"` or `lazy="selectin"` as a model-level default (it silently taxes
every query), `joinedload()` on a collection combined with `LIMIT`/`OFFSET` (returns the wrong
number of parents), and calling `await session.refresh(obj)` from a service to "fix" a missing
relation — fix the repository statement instead.

```python
# ✅ repository.py — relations resolved in the statement
async def get_with_orders(self, user_id: UUID) -> User | None:
    stmt = (
        select(User)
        .options(selectinload(User.orders).joinedload(Order.shipping_address))
        .where(User.id == user_id)
    )
    result = await self._session.execute(stmt)
    return result.scalars().unique().one_or_none()


# ✅ service.py — conversion happens with the session still open
async def get_profile_with_orders(self, user_id: UUID) -> UserWithOrdersRead:
    user = await self._repository.get_with_orders(user_id)
    if user is None:
        raise EntityNotFoundError(f"User {user_id} not found")
    return UserWithOrdersRead.model_validate(user)


# ❌ FORBIDDEN — get_by_id() did not load .orders
user = await self._repository.get_by_id(user_id)
return UserWithOrdersRead.model_validate(user)  # MissingGreenlet at runtime
```

**Repository naming reflects the loaded graph.** A method that eager-loads relations MUST say so:
`get_with_orders`, `list_with_profile`. A bare `get_by_id` returns the scalar row only, and a
caller needing relations MUST add a repository method rather than lazy-loading.

### 3.4 Directory Layout

```
app/
├── main.py                     # app factory, lifespan, middleware, exception handlers
├── core/
│   ├── config.py               # Settings (pydantic-settings) + get_settings()
│   ├── security.py             # Argon2id hashing, JWT encode/decode
│   ├── exceptions.py           # domain exception hierarchy
│   ├── dependencies.py         # domain-free helpers ONLY: pagination, request id (see §3.8)
│   └── logging.py              # structured logging setup
├── db/
│   ├── base.py                 # DeclarativeBase + naming_convention
│   ├── session.py              # async engine, async_sessionmaker(expire_on_commit=False)
│   └── dependencies.py         # get_session() -> AsyncGenerator[AsyncSession, None]
├── cache/
│   ├── client.py               # pool factory + get_cache() dependency provider
│   └── keys.py                 # centralised key prefixes and TTL constants
├── api/
│   └── v1/router.py            # aggregates module routers under /api/v1
└── modules/
    ├── auth/    {router,service,repository,cache,schemas,models,dependencies,exceptions}.py
    │             # dependencies.py owns get_current_user (NOT app/core — see §3.8)
    ├── users/   {router,service,repository,schemas,models,dependencies,exceptions}.py
    ├── catalog/                # planned
    └── orders/                 # planned
migrations/
├── env.py                      # PROTECTED: async context + idempotency Rewriter (§4.9.2)
└── versions/                   # Alembic-generated revisions only
tests/{unit,integration}/       # mirrors app/ structure
```

A new module MUST contain the full file set above, even if a file is thin. Do not "temporarily"
collapse a repository into a service. `cache.py` is added only to modules that actually use Valkey.

### 3.5 Async I/O — Absolute Rule

**Every** I/O operation MUST be `await`ed on an async client. This covers PostgreSQL, Valkey,
outbound HTTP, and file access.

```python
# ✅ CORRECT
async def get_by_email(self, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    result = await self._session.execute(stmt)
    return result.scalars().one_or_none()


# ❌ FORBIDDEN — blocks the event loop, poisons the whole worker
def get_by_email(self, email: str) -> User | None:
    return self._session.query(User).filter_by(email=email).first()  # sync + legacy API
```

CPU-bound or unavoidably blocking third-party calls (e.g. `PasswordHasher.hash`/`.verify`) MUST be offloaded:

```python
hashed = await anyio.to_thread.run_sync(hash_password, plain_password)
```

Forbidden in any async path: `requests`, `time.sleep`, `psycopg2`, synchronous Valkey clients,
synchronous `open()` on request-scoped files, and any blocking SDK.

### 3.6 Dependency Injection (database **and** cache)

**General rules:**

* Routers receive collaborators exclusively via `Depends`. No module-level singletons for
  stateful resources, no manual instantiation inside a handler body.
* Services receive their repository **and cache gateway** through `__init__`. A service MUST NOT
  construct an `AsyncSession`, a Valkey client, or a connection pool itself.
* Repositories receive `AsyncSession` through `__init__`. Cache gateways receive the async
  Valkey client through `__init__`.
* Dependency providers live in `db/dependencies.py`, `cache/client.py`, `core/dependencies.py`,
  or the module's own `dependencies.py` — never inline in `router.py` or `service.py`.

**The only permitted application-scoped singletons** are the SQLAlchemy engine and the Valkey
**connection pool**, both created in the `lifespan` handler and stored on `app.state`. Everything
downstream of them is request-scoped and injected.

```python
# app/cache/client.py
def create_valkey_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool.from_url(str(settings.valkey_url), decode_responses=True)


async def get_cache(request: Request) -> AsyncGenerator[Valkey, None]:
    client = Valkey(connection_pool=request.app.state.valkey_pool)
    try:
        yield client
    finally:
        await client.aclose()
```

```python
# app/modules/auth/cache.py — typed gateway; the service never sees the raw client
class RefreshTokenStore:
    def __init__(self, client: Valkey) -> None:
        self._client = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._client.setex(revoked_jti_key(jti), ttl_seconds, "1")

    async def is_revoked(self, jti: str) -> bool:
        return await self._client.exists(revoked_jti_key(jti)) == 1
```

```python
# app/modules/auth/dependencies.py — the single wiring point
async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    cache: Annotated[Valkey, Depends(get_cache)],
) -> AuthService:
    return AuthService(
        repository=UserRepository(session=session),
        token_store=RefreshTokenStore(client=cache),
    )
```

**Explicitly forbidden:**

```python
# ❌ module-level global in service.py — unclosable, untestable, shared across event loops
client = Valkey.from_url(os.environ["VALKEY_URL"])


# ❌ constructing a client inside a service method
async def logout(self, jti: str) -> None:
    client = Valkey.from_url(...)  # new connection per call
    await client.set(f"revoked:{jti}", 1)  # raw key, no TTL


# ❌ calling a dependency provider by hand
cache = await get_cache()
```

**Cache hygiene (binding):**

* All keys are built by helpers in `cache/keys.py` from documented prefix constants. Raw f-string
  keys in `service.py` are forbidden — they defeat namespacing and make invalidation unauditable.
* **Every write MUST set a TTL** (`setex` / `set(..., ex=...)`). Unbounded keys are forbidden.
* The cache is never the source of truth. A cache miss, a timeout, or a Valkey outage MUST
  degrade to the database path, not to a 500 — except for security-critical reads (token
  denylist), which MUST fail closed and reject the request.

### 3.7 Transaction Boundary

The **service layer** owns the transaction. Repositories issue statements and may `flush()`;
they MUST NOT `commit()`. Exactly one commit per business operation, at the end of the service
method. On exception, the session dependency rolls back. Cache writes happen **after** a
successful commit — never inside the transaction, where a rollback would leave a stale entry.

### 3.8 Mechanical Enforcement of the Layer Contract (import-linter)

§3.2 is not a guideline the agent is trusted to remember. It is declared in `pyproject.toml` and
checked by `import-linter` (`lint-imports`) on every commit (§6.2). An import that violates the
contract fails the gate with the exact offending chain printed to stderr — the agent does not
have to weigh whether an import is "acceptable", because the linter answers that for it.

```toml
# pyproject.toml — PROTECTED. Contracts may not be deleted, narrowed, or bypassed (§7.9).
[tool.importlinter]
root_package = "app"
include_external_packages = true      # required to forbid fastapi / sqlalchemy / redis by name

# ---------------------------------------------------------------- Contract 1
# The core rule. Layers are relative to each container, ordered HIGH -> LOW.
# "a | b" = same level but INDEPENDENT (may not import each other).
# "(x)"   = optional layer; no failure if the file is absent from a given module.
[[tool.importlinter.contracts]]
name = "Module layers: router -> dependencies -> service -> repository|cache -> models|schemas"
type = "layers"
layers = [
    "router",
    "(dependencies)",
    "service",
    "repository | (cache)",
    "models | schemas",
    "(exceptions)",
]
containers = ["app.modules.*"]        # wildcard: new modules are covered automatically
exhaustive = true                     # an undeclared file in a module breaks the build
exhaustive_ignores = []               # add "__init__" here only if your version requires it

# ---------------------------------------------------------------- Contract 2
# Top-level direction. Notably: app.core is generic infrastructure and may NEVER
# import a domain module; app.db and app.cache are independent of each other.
[[tool.importlinter.contracts]]
name = "Top-level layers: main -> api -> modules -> db|cache -> core"
type = "layers"
layers = [
    "app.main",
    "app.api",
    "app.modules",
    "app.db | app.cache",
    "app.core",
]

# ---------------------------------------------------------------- Contract 3
# Mechanises §3.2 and §7.3: routers speak Pydantic, never infrastructure.
[[tool.importlinter.contracts]]
name = "Routers must not touch persistence or cache infrastructure"
type = "forbidden"
source_modules = ["app.modules.*.router"]
forbidden_modules = ["sqlalchemy", "asyncpg", "redis", "valkey", "app.db", "app.cache"]
allow_indirect_imports = true         # MANDATORY — see the note below

# ---------------------------------------------------------------- Contract 4
# Mechanises §3.2: the service layer is framework-agnostic and client-free.
[[tool.importlinter.contracts]]
name = "Services must not import the web framework or raw infrastructure clients"
type = "forbidden"
source_modules = ["app.modules.*.service"]
forbidden_modules = ["fastapi", "starlette", "redis", "valkey", "asyncpg", "app.cache.client"]
allow_indirect_imports = true

# ---------------------------------------------------------------- Contract 5
# Mechanises §4.7: configuration is read through get_settings(), never os.environ.
[[tool.importlinter.contracts]]
name = "Only core.config may read the environment"
type = "forbidden"
source_modules = ["app.modules", "app.api", "app.db", "app.cache"]
forbidden_modules = ["os", "dotenv"]
allow_indirect_imports = true
```

**`allow_indirect_imports = true` is mandatory on every `forbidden` contract here.** By default
`import-linter` also reports *indirect* chains, and a router legitimately reaches `sqlalchemy`
through `router → service → repository → sqlalchemy`. Without this flag every contract above
fails immediately and the config looks broken. The flag restricts the check to direct imports —
which is exactly the rule §3.2 states.

**Reading a failure.** `lint-imports` prints the broken contract and the offending chain. Fix the
import it names. Do **not** add an `ignore_imports` entry, do not hide the import behind
`if TYPE_CHECKING:`, and do not move the import inside a function body — all three are §7.9
bypasses regardless of whether the linter happens to catch them.

**Expected first finding.** Contract 2 will reject `get_current_user` if it lives in
`app/core/dependencies.py`, because resolving a user requires the users/auth service and
`app.core` sits below `app.modules`. This is the linter reporting a real design fault, not a
false positive. The fix is to move authentication dependencies into
`app/modules/auth/dependencies.py` and leave only domain-free helpers (pagination, request ID)
in `app/core/dependencies.py`.

**Enforcement coverage — where mechanical checking stops and review begins:**

| Rule | Enforced by | Residual risk |
| --- | --- | --- |
| 3.2.1 downward-only imports | `import-linter` layers contract | None — static and complete |
| 3.2.2 ORM containment | **mypy strict** + explicit `-> *Read` annotations | Only escapable via `Any`, which §7.1 bans |
| 3.2.3 eager loading | `lazy="raise_on_sql"` (runtime) + N+1 test (§5.3) | An untested path fails in production, not CI — integration coverage is the real guard |
| 3.2.4 no raw clients above the gateway | `import-linter` contracts 3–4 | None |
| §3.4 full file set per module | `exhaustive = true` on contract 1 | None |
| Cross-module calls go service → service | **Not mechanised** | Human review — built-in contract types cannot express "any module except my own" |
| §4.4 mass assignment / privilege fields | **Not mechanised** | Human review — DoD item 7 |

The two "not mechanised" rows are the remaining human-attention surface. Everything above them
is a barrier; those two are still a promise.

**Performance.** `include_external_packages = true` enlarges the import graph. Measure
`lint-imports` wall time against the §6.2 budget; if it exceeds ~3 seconds, move the hook to the
`pre-push` stage rather than dropping contracts.

---

## 4. Code Conventions

### 4.1 Naming

| Element | Convention | Example |
| --- | --- | --- |
| Module / file | `snake_case.py` | `refresh_token_service.py` |
| Class | `PascalCase` | `UserRepository`, `TokenPair` |
| Function / method / variable | `snake_case` | `authenticate_user`, `access_token` |
| Constant | `UPPER_SNAKE_CASE` | `DEFAULT_PAGE_SIZE`, `REVOKED_JTI_PREFIX` |
| Private member | `_leading_underscore` | `self._session`, `self._client` |
| Boolean | `is_` / `has_` / `can_` prefix | `is_active`, `has_verified_email` |
| SQLAlchemy model | Singular `PascalCase` | `class User(Base)` |
| Table name | Plural `snake_case` | `__tablename__ = "users"` |
| Cache key prefix | `snake_case:` namespace | `revoked_jti:{jti}`, `user_profile:{id}` |
| Alembic revision | `snake_case` message | `add_users_email_unique_index` |
| Test | `test_<unit>_<scenario>_<expected>` | `test_register_user_duplicate_email_raises` |

Async functions MUST NOT be prefixed with `async_` — `async def` already says it.
Repository verbs are fixed: `get_by_*`, `get_with_*`, `list_*`, `exists_by_*`, `create`,
`update`, `delete`. Service verbs describe business intent: `register_user`,
`rotate_refresh_token`, `deactivate_account`.

### 4.2 Typing — Strict

* Every function, method, parameter, and return value MUST be annotated, including `-> None`.
* `typing.Any` is **forbidden**. Use `object`, a `Protocol`, a `TypeVar`, a union, or a
  `TypedDict`. If you believe `Any` is unavoidable, stop and report — do not use it.
* `# type: ignore` is **forbidden**, in any form, including bare and coded variants. A missing
  third-party stub is resolved by adding stubs to `[[tool.mypy.overrides]]` in `pyproject.toml`
  and reporting it — never by suppressing at the call site.
* Use `X | None`, not `Optional[X]`. Use `list[T]`, `dict[K, V]`, not `List`/`Dict`.
* Annotate FastAPI dependencies with `Annotated[T, Depends(...)]`.

### 4.3 Models vs Schemas (never merged)

* **Models** (`models.py`) describe the *database*. They may contain `hashed_password`,
  internal flags, timestamps, relationships.
* **Schemas** (`schemas.py`) describe the *API contract*. They are the only types a router
  accepts or returns.

Required schema family per entity:

| Schema | Direction | Purpose |
| --- | --- | --- |
| `UserBase` | — | Shared safe fields. No IDs, no secrets, no privilege flags. |
| `UserCreate` | **inbound** | Registration payload. `password: SecretStr`. |
| `UserUpdate` | **inbound** | Self-service partial update. All fields `\| None` with defaults. |
| `UserAdminUpdate` | **inbound** | Privileged fields, reachable only behind an admin dependency. |
| `UserRead` | **outbound** | Public representation. Never a hash, never an internal flag. |

### 4.4 `extra="forbid"` and Mass Assignment

**Rule 4.4.1 — `extra="forbid"` is mandatory on every inbound schema.** This covers `*Create`,
`*Update`, filter/query-param models, nested request bodies, and webhook payloads. Pydantic's
default (`extra="ignore"`) silently discards unknown keys, which turns a client's typo or an
attacker's probe into a silent no-op. `forbid` converts it into a `422` the caller can act on.

```python
class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    password: SecretStr = Field(min_length=12, max_length=128)
```

On outbound (`*Read`) schemas `extra` is far less critical — nothing untrusted flows inward — so
the default is acceptable there. What **is** mandatory outbound is `from_attributes=True` and an
explicit field list:

```python
class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    created_at: datetime
```

**Rule 4.4.2 — `extra="forbid"` is necessary but NOT sufficient.** Mass assignment is prevented
by *field selection*, not by strictness alone. A self-service inbound schema MUST NOT declare
privilege or server-owned fields: `id`, `is_active`, `is_superuser`, `role`, `email_verified_at`,
`created_at`, `updated_at`, `hashed_password`. Privileged mutation lives in a separate
`*AdminUpdate` schema behind an authorization dependency.

**Rule 4.4.3 — Never splat a payload onto an ORM model.** This is the actual mass-assignment
vector, and `extra="forbid"` does not stop it once a field is legitimately on the schema.

```python
# ❌ FORBIDDEN
user = User(**payload.model_dump())

# ✅ explicit mapping — the service decides what the database sees
user = User(
    email=payload.email,
    full_name=payload.full_name,
    hashed_password=hashed,
    is_active=False,  # server-owned; never client-supplied
)
```

**Rule 4.4.4 — PATCH semantics.** Partial updates MUST use `model_dump(exclude_unset=True)` so
that "field absent" and "field explicitly set to null" remain distinguishable, then apply the
result field-by-field via `setattr` over a whitelist — never a blind `update(**data)`.

**Rule 4.4.5 — Structured multi-field validation (sanctioned pattern).** A Pydantic field
validator short-circuits: a `str`-typed field with a `Field(min_length=...)` constraint rejects
the whole request via a single generic `422` the moment one field is invalid, so it cannot report
"email is malformed **and** password is too weak" as two field-level errors in one response. When
a caller genuinely needs a batched, per-field error list (e.g. registration returning every
violated rule at once), the inbound schema stays loosely typed for those specific fields
(`str | None = None`, `SecretStr | None = None` — never bare `str`/`SecretStr`, so a missing field
still reaches the service instead of failing FastAPI's own 422 first) and the service layer
performs the joint validation, collecting a list of `FieldError` records before raising one
`RegistrationValidationError(errors=...)`. This is not a bypass of "schemas are the only inbound
validation" — it is the documented exception for the one case Pydantic's per-field validators
cannot express. A password field validated this way is still a `SecretStr`, unwrapped via
`.get_secret_value()` only at the point the characters are actually checked — the loose typing is
solely to defer *which* fields fail, not to abandon secret hygiene (§4.7).

### 4.5 Pydantic v2 & SQLAlchemy 2.0 Idioms

| Forbidden (v1 / legacy) | Required |
| --- | --- |
| `class Config:` | `model_config = ConfigDict(...)` |
| `.dict()`, `.json()` | `.model_dump()`, `.model_dump_json()` |
| `@validator`, `@root_validator` | `@field_validator`, `@model_validator` |
| `parse_obj`, `from_orm` | `model_validate` |
| `session.query(Model)` | `select(Model)` + `await session.execute(stmt)` |
| `Column(...)` on declarative models | `Mapped[T] = mapped_column(...)` |
| implicit lazy relationship access | `.options(selectinload(...) / joinedload(...))` (§3.3) |
| `Base.metadata.create_all()` in app code | Alembic migration |

### 4.6 Error Handling

Three-tier model, no shortcuts:

1. **Repository / cache gateway** — returns `None` / empty results. Raises no domain or HTTP errors.
2. **Service** — raises **domain exceptions** from `core/exceptions.py` or the module's
   `exceptions.py`. MUST NOT raise `HTTPException`.
3. **Router / handlers** — domain exceptions are translated to HTTP responses by registered
   exception handlers in `main.py`. Routers themselves contain no `try/except` for business flow.

**Exception ownership (binding — resolves an earlier ambiguity between this section and §3.4's
per-module file set).** `core/exceptions.py` holds **only** the generic `DomainError` base and
errors that are genuinely shared by every module (there are none yet). A module-specific error —
`EmailAlreadyRegisteredError`, `InvalidCredentialsError`, anything scoped to one domain — lives in
that module's own `exceptions.py`, per the `(exceptions)` layer in §3.8's import-linter contract.
`core` is generic, domain-free infrastructure (§3.8, Contract 2) and putting a domain-specific
error there is a design fault the linter cannot catch on its own — human review is the guard.

```python
# core/exceptions.py — generic base only
class DomainError(Exception):
    """Base for all business-rule failures."""


# app/modules/users/exceptions.py — module-owned, specific
class EntityNotFoundError(DomainError): ...


class EmailAlreadyRegisteredError(DomainError): ...


class InvalidCredentialsError(DomainError): ...


# main.py
from app.modules.users.exceptions import EmailAlreadyRegisteredError


@app.exception_handler(EmailAlreadyRegisteredError)
async def handle_email_conflict(request: Request, exc: EmailAlreadyRegisteredError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "Email already registered"})
```

Additional rules:

* Never use a bare `except:` or `except Exception:` without re-raising or logging with context.
* Never swallow an exception to return a default value.
* Client-facing error messages MUST NOT leak stack traces, SQL, driver text, or whether an
  email exists during login (return a uniform `401 Invalid credentials`).

### 4.7 Configuration & Secrets

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="forbid", case_sensitive=False
    )

    database_url: PostgresDsn
    valkey_url: AnyUrl
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600
    argon2_time_cost: int = 3
    argon2_memory_cost_kb: int = 65536
    argon2_parallelism: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

* `get_settings()` is the **only** way to read configuration. `os.environ` / `os.getenv` in
  application code is forbidden.
* All secrets are `SecretStr`; access via `.get_secret_value()` at the point of use only.
* `.env` is git-ignored. `.env.example` MUST be updated with every new setting (keys only,
  placeholder values).

### 4.8 Logging & Observability

* Structured logging via the configured logger. `print()` is forbidden (`T20` in Ruff).
* Never log: passwords, hashes, JWTs, refresh tokens, session IDs, cache keys containing PII,
  or full request bodies of auth endpoints.
* Log at boundaries (request received / domain error raised), not inside tight loops.

### 4.9 Database & Migrations

**Authoring flow.** Schema changes are made in `models.py`, then captured by
`alembic revision --autogenerate`. **Every generated migration MUST be reviewed and edited by
hand** — autogenerate misses server defaults, enum changes, index renames, and data backfills.

**Rule 4.9.1 — Idempotency is mandatory.** Every migration MUST be safe to re-run against a
database that is already in the target state, and MUST survive a full
`upgrade → downgrade → upgrade` cycle. Alembic's `alembic_version` table is not sufficient
protection: a migration can fail partway, a `CONCURRENTLY` statement can leave an invalid object
behind, and environments drift.

Current Alembic exposes `if_exists` / `if_not_exists` on create/drop operations for tables,
columns, indexes and constraints. For autogenerated migrations these flags are injected
automatically by the rewriter in Rule 4.9.2 — the agent's job is to **verify they are present in
the generated file**, not to type them. For hand-written migrations, pass them yourself:

```python
def upgrade() -> None:
    op.create_table("user_sessions", ..., if_not_exists=True)
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions", if_exists=True)
    op.drop_table("user_sessions", if_exists=True)
```

Where an operation has no `if_*` flag, guard it explicitly with an inspector check:

```python
def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("users", "email_verified_at"):
        op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
```

**Rule 4.9.2 — The idempotency rewriter is mandatory infrastructure (poka-yoke).**
Rule 4.9.1 must not depend on an agent remembering it. `migrations/env.py` installs an Alembic
autogenerate `Rewriter` that injects `if_exists` / `if_not_exists` into every generated
create/drop directive, so a non-idempotent *autogenerated* migration becomes structurally
impossible rather than merely forbidden.

```python
# migrations/env.py — PROTECTED BLOCK. Do not remove, disable, or bypass (§7.5).
from alembic.autogenerate import rewriter
from alembic.operations import ops

writer = rewriter.Rewriter()


@writer.rewrites(ops.CreateTableOp)
@writer.rewrites(ops.CreateIndexOp)
@writer.rewrites(ops.AddColumnOp)
def _add_if_not_exists(context, revision, op):  # type: ignore[no-untyped-def]  # env.py is exempt
    op.if_not_exists = True
    return op


@writer.rewrites(ops.DropTableOp)
@writer.rewrites(ops.DropIndexOp)
@writer.rewrites(ops.DropColumnOp)
@writer.rewrites(ops.DropConstraintOp)
def _add_if_exists(context, revision, op):  # type: ignore[no-untyped-def]  # env.py is exempt
    op.if_exists = True
    return op


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=writer,  # <-- wires the rewriter in
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()
```

> `env.py` is the one file exempt from the `# type: ignore` ban in §4.2 and §7.1, because the
> `process_revision_directives` callback signature is untyped upstream. The exemption is limited
> to these two functions and MUST NOT be extended to any file under `app/`.

**Composing with an existing hook.** If `process_revision_directives` is already in use (e.g. the
common "abort on empty autogenerate" guard), do not overwrite it. Chain rewriters with
`writer.chain(other_writer)`, or wrap both in a single callable that invokes them in order.
Silently dropping the existing hook to install this one is a §7.5 violation.

**What the rewriter does NOT cover — the manual guards in 4.9.1 remain in force:**

| Not covered | Why | Required action |
| --- | --- | --- |
| Hand-written migrations | The rewriter only touches `--autogenerate` output | Pass `if_*` flags manually |
| `op.execute("...")` raw SQL | Opaque to the directive tree | Write `IF NOT EXISTS` into the SQL itself |
| Data backfills | Not a DDL directive | Guard with `WHERE ... IS NULL` / `ON CONFLICT DO NOTHING` |
| `AlterColumnOp`, type changes, enum edits | No `if_*` parameter exists | Guard with an inspector check |
| `CREATE INDEX CONCURRENTLY` | Requires an autocommit block | Handle explicitly (see hazards below) |

**Honest limitation — guards prevent failures, not incorrectness.** `drop_table(if_exists=True)`
succeeds against a database where the table was never created, and `create_table(if_not_exists=True)`
accepts a same-named table with a *different* shape. Both mask drift instead of reporting it.
The rewriter therefore removes a class of hard errors; it does **not** remove the obligation to
execute the `upgrade → downgrade → upgrade` cycle (§6, item 5), which is the only real proof.

**Rule 4.9.3 — `downgrade()` is not optional.** Both directions MUST be implemented and actually
executed before the task is reported done. A `downgrade()` body of `pass` or `raise
NotImplementedError` is rejected.

**Rule 4.9.4 — History is append-only.** One linear chain. Never edit an applied revision, never
delete a revision file, never rewrite `down_revision` to "fix" a branch — generate a merge
revision instead.

**PostgreSQL-specific hazards the agent MUST handle:**

* `CREATE INDEX CONCURRENTLY` cannot run inside a transaction. Put it in its own migration,
  wrap it in `with op.get_context().autocommit_block():`, and always pass `if_not_exists=True`
  — a failed concurrent build leaves an invalid index that blocks a naive retry.
* `ALTER TYPE ... ADD VALUE` is permitted inside a transaction on PostgreSQL 15, but the new
  value **cannot be used by statements in that same transaction**. Split enum extension and any
  data statement that references the new value into separate migrations.
* Data backfills MUST be idempotent (`WHERE col IS NULL`, `ON CONFLICT DO NOTHING`), batched for
  large tables, and kept in a migration separate from the DDL that enables them.
* Destructive changes follow expand → migrate → contract across releases. Never add a column and
  drop its predecessor in the same migration.

**Schema hygiene:** every foreign key and every column used in a `WHERE` / `ORDER BY` gets an
explicit index; `DeclarativeBase` declares a `naming_convention` so constraint names are
deterministic and therefore droppable by name in `downgrade()`.

**Precedents established by US-3.3 (audit log, 2026-09-02):**

* **First `JSONB` column** in this codebase (`audit_log.payload`). Use `postgresql.JSONB`, not
  the dialect-generic `JSON` type — the latter renders as `json` on PostgreSQL, not `jsonb`.
* **First range-partitioned table** (`audit_log`, daily partitions). Partitioning DDL, the
  partition's covering index, and any `BEFORE INSERT` trigger on it must be hand-written
  (`op.execute`) — no SQLAlchemy/Alembic construct models partitioning. A `DEFAULT` partition is
  required as a safety net; without one, an insert past the last provisioned day's range fails
  outright.
* **Hash-chain trigger concurrency:** a `SELECT ... FOR UPDATE` on the presumed-latest row does
  **not** serialize concurrent inserts under PostgreSQL MVCC — a blocked transaction is granted
  the lock with no re-check of the row it read. Serialize with
  `pg_advisory_xact_lock(hashtext('<chain-name>'))` at the start of the trigger function instead;
  it auto-releases on commit or rollback and needs no side table for lock state.

See `docs/decisions/US-3.3-open-decisions.md` (OD-6, OD-16, OD-17) for the full reasoning and
what was tried and rejected first.

---

## 5. Testing Requirements

### 5.1 Structure

```
tests/
├── conftest.py               # global fixtures: settings override, engine, app factory
├── factories.py              # deterministic test-data builders
├── fakes.py                  # hand-written Protocol implementations for unit tests
├── unit/
│   └── modules/users/test_user_service.py
└── integration/
    ├── conftest.py           # DB + Valkey containers, migrations, transactional session
    └── api/v1/test_users_api.py
```

The `tests/` tree mirrors the `app/` tree. A new `app/modules/x/service.py` requires
`tests/unit/modules/x/test_x_service.py`.

### 5.2 Unit Tests (service layer)

* Target: business logic in isolation. **No database, no Valkey, no network.**
* Repositories and cache gateways are replaced by hand-written fakes implementing a `Protocol`.
  Prefer fakes over `MagicMock` — a mock that returns `Mock()` for everything proves nothing.
* Every branch of a business rule needs a test: happy path, each failure path, each boundary.
* Domain exceptions are asserted explicitly with `pytest.raises(...)`.

### 5.3 Integration Tests (API layer)

* Real PostgreSQL and real Valkey (containers or dedicated test instances). **SQLite is not an
  acceptable substitute** — it hides dialect, constraint, and concurrency behaviour.
* Schema is created by running `alembic upgrade head` — never `create_all()`. This makes the
  migration chain itself part of the test suite.
* Each test runs inside a transaction that is rolled back on teardown. Valkey is flushed (or
  namespaced per test) between tests. Tests MUST be order-independent and parallel-safe.
* HTTP is exercised in-process:

```python
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.post("/api/v1/auth/register", json=payload)
```

**Rule 5.3.1 — No mocking of infrastructure in integration tests.** Using
`unittest.mock.patch`, `patch.object`, `AsyncMock`, `MagicMock`, or `monkeypatch.setattr` to
substitute database calls, cache reads/writes, repository methods, session objects, or the
service under test is **strictly forbidden** in `tests/integration/`. A mocked integration test
proves nothing about integration; it is a slower unit test that lies about its coverage.
An `import unittest.mock` anywhere under `tests/integration/` is a review-blocking finding.

**Rule 5.3.2 — Substituting genuine third-party egress.** Only true external boundaries (payment
provider, email/SMS gateway, upstream partner API) may be replaced, and only through
`app.dependency_overrides` with a **hand-written fake class** that records calls and can assert
on them. Never `patch`. PostgreSQL and Valkey are ours; they are never "external".

```python
app.dependency_overrides[get_email_sender] = lambda: RecordingEmailSender()
```

**Assertions.** Assert on status code **and** response body shape **and** persisted state (query
the database / cache after the call). Status-code-only assertions are insufficient.

**Auth coverage.** Every protected route MUST have tests for: no token, expired token, malformed
token, valid token with insufficient permissions, and revoked (denylisted) token.

**N+1 guard (SHOULD).** List endpoints returning nested data SHOULD assert an upper bound on
emitted statements via a SQLAlchemy event counter, so a regression to lazy loading fails the
build rather than the latency graph.

### 5.4 AAA Structure (mandatory)

Every test is written in three visually separated blocks with comments:

```python
async def test_register_user_duplicate_email_raises_conflict(
    user_service: UserService, existing_user: User
) -> None:
    # Arrange
    payload = UserCreate(email=existing_user.email, password=SecretStr("Str0ng!Passw0rd"))

    # Act / Assert
    with pytest.raises(EmailAlreadyRegisteredError):
        await user_service.register_user(payload)
```

One logical assertion target per test. No conditional logic (`if` / `for`) inside a test body —
use `@pytest.mark.parametrize` instead.

### 5.5 Determinism

* No `time.sleep`, no `asyncio.sleep` as a synchronisation device, no retry-until-pass loops.
* Time-dependent logic (token expiry, TTLs) uses an injected clock or `freezegun` — never
  wall-clock waiting.
* No randomness without a fixed seed. No dependence on test execution order.

### 5.6 Coverage

* **Minimum 85% overall**, enforced by `--cov-fail-under=85`.
* Business logic (`app/modules/**/service.py`) and API endpoints (`app/modules/**/router.py`)
  are held to a **higher bar of 90%+**; a PR that dilutes coverage by adding trivially-covered
  boilerplate while leaving a service branch untested is rejected.
* Coverage is a floor, not a goal. 100% coverage with no assertions is a failing test suite.
* Excluding files from coverage to reach the threshold is a §7 violation.

---

## 6. Definition of Done (DoD)

### 6.1 Checklist

An agent MUST NOT report a task as complete until **all seven** items are verified with real
command output. Items 1–3 are additionally enforced mechanically (§6.2) — but the enforcement
only fires on `git commit`, so **the work MUST actually be committed**, not left staged or
loose in the working tree.

- [ ] **1. Formatting & linting clean.** `ruff format .` produces no changes and
      `ruff check .` reports zero findings. No `# noqa` was added to achieve this.
- [ ] **2. Strict typing clean.** `mypy app tests` reports zero errors with `strict = true`.
      No `typing.Any`, no `# type: ignore`, no new mypy overrides added to silence a real error.
- [ ] **3. Tests written and green.** New behaviour has unit tests; new/changed endpoints have
      integration tests. Integration tests contain **no** `unittest.mock` usage (§5.3.1). The
      **full** suite passes (`pytest`), not just the new tests.
- [ ] **4. Coverage threshold met.** `pytest --cov=app --cov-fail-under=85` passes, and the
      diff does not reduce coverage of any touched module.
- [ ] **5. Migrations correct and idempotent.** If `models.py` changed: a migration was
      autogenerated with the rewriter active (§4.9.2), and the generated file was **read** to
      confirm the `if_exists` / `if_not_exists` flags landed; anything the rewriter cannot reach —
      raw `op.execute`, backfills, `AlterColumnOp`, `CONCURRENTLY` — carries a manual guard.
      The cycle `alembic upgrade head` → `downgrade -1` → `upgrade head` was executed
      successfully. `downgrade()` is implemented. History remains linear. `env.py` was not
      modified.
- [ ] **6. Architecture & data access respected.** `lint-imports` reports zero broken contracts
      (§3.8). Beyond what the linter covers: no ORM object crossing into a router; all nested
      schema data eager-loaded in the repository (§3.3); every cache write has a TTL; any
      cross-module call goes service → service, which the linter **cannot** check.
- [ ] **7. Contract & security verified.** Every new/changed route declares `response_model`,
      `status_code`, and documented error responses; every inbound schema sets
      `extra="forbid"` and excludes privilege fields (§4.4); no secret in code; `.env.example`
      updated; no sensitive field in any `*Read` schema; OpenAPI renders correctly.

If any item fails, the correct action is to **fix it or report the blocker** — never to relax
the check.

### 6.2 Automated Enforcement: Where Each Check Runs

Self-reported compliance is not evidence. Checks that can be mechanised are mechanised, on the
same poka-yoke principle as the Alembic rewriter (§4.9.2): the agent should be spending its
attention on backfill correctness and business rules, not on remembering to run a formatter.

The split is governed by **wall-clock cost**. Anything that needs containers, a database, or a
full coverage run is too slow for a commit hook and belongs in CI.

| Check | pre-commit | pre-push | CI | Authority |
| --- | :---: | :---: | :---: | --- |
| `ruff format` | ✅ (rewrites) | — | ✅ `--check` only | CI |
| `ruff check` | ✅ `--fix` | — | ✅ **no** `--fix` | CI |
| `mypy app tests` (whole project) | ✅ | — | ✅ | CI |
| `lint-imports` — architecture contracts (§3.8) | ✅ *if* < 3 s | ✅ | ✅ | CI |
| Secret / private-key scan | ✅ | — | ✅ | CI |
| `unittest.mock` ban in `tests/integration/` (§5.3.1) | ✅ | — | ✅ | CI |
| `pytest tests/unit` | ✅ *if* < 10 s | ✅ | ✅ | CI |
| `pytest tests/integration` (Postgres + Valkey containers) | ❌ | ❌ | ✅ | CI |
| `--cov-fail-under=85` (§5.6) | ❌ | ❌ | ✅ | CI |
| `alembic upgrade → downgrade → upgrade` (§4.9) | ❌ | ❌ | ✅ | CI |

**CI is the authority; pre-commit is the fast feedback loop.** Every pre-commit check is
re-run in CI, without `--fix`, because a local hook can be skipped, can be stale, and does not
run against the merge result. A green pre-commit is never sufficient evidence on its own.

**Time budget.** Total `pre-commit run --all-files` wall time MUST stay under ~15 seconds.
Beyond that, agents hit session timeouts and — the worse failure — start looking for ways around
the gate. If unit tests exceed 10 seconds, move them to the `pre-push` stage rather than
weakening them.

```yaml
# .pre-commit-config.yaml — PROTECTED. Do not remove or weaken hooks (§7.9).
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: detect-private-key
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: local
    hooks:
      # Whole-project run: mypy MUST see the full import graph and the project's own
      # installed dependencies (SQLAlchemy 2.0 / Pydantic v2 plugins). Never pass filenames.
      - id: mypy
        name: mypy (strict, whole project)
        entry: mypy app tests
        language: system
        types: [python]
        pass_filenames: false
        require_serial: true

      # Mechanises §3.2 via the contracts in §3.8. Whole-graph run; never pass filenames.
      - id: lint-imports
        name: import-linter (architecture contracts)
        entry: lint-imports
        language: system
        types: [python]
        pass_filenames: false
        require_serial: true

      # Mechanises §5.3.1 — no mocking of infrastructure in integration tests.
      - id: no-mock-in-integration
        name: forbid unittest.mock in tests/integration
        entry: >
          bash -c 'grep -rnE "unittest\.mock|MagicMock|AsyncMock|monkeypatch\.setattr"
          tests/integration && { echo "§5.3.1 violation"; exit 1; } || exit 0'
        language: system
        pass_filenames: false

      - id: pytest-unit
        name: pytest (unit only)
        entry: pytest tests/unit -q --no-cov -p no:randomly
        language: system
        types: [python]
        pass_filenames: false
        stages: [pre-push]      # promote to pre-commit only if it stays under 10 s
```

**Configuration rationale the agent MUST NOT "simplify":**

* **`language: system` + `pass_filenames: false` for mypy.** The `mirrors-mypy` hook runs in an
  isolated environment without the project's dependencies, so FastAPI, SQLAlchemy and Pydantic
  types are unresolvable and the strict-mode result is meaningless. Passing only staged filenames
  is equally wrong: mypy needs the whole import graph, and a per-file run both misses real
  cross-module errors and invents false ones.
* **`--exit-non-zero-on-fix` for ruff.** An auto-fix that exits `0` lets a rewritten file slip
  through as if nothing happened.
* **CI runs ruff *without* `--fix`.** CI must report a failure, never silently mutate the tree.

### 6.3 Agent Behaviour When a Hook Fails

A rejected commit is the system working as designed. It is a corrective signal, not an obstacle.

1. **Auto-fix rejections are normal and expected.** `ruff --fix` and `end-of-file-fixer` modify
   files, and pre-commit fails any hook that modified files. The correct response is
   `git add -u` and commit again — **not** to conclude the toolchain is broken, and **not** to
   bypass it. Two attempts for a formatting-only change is the designed path.
2. **Read the actual stderr before regenerating.** Mypy and Ruff name the file, line, and rule
   code. Fix the reported cause. Do not rewrite unrelated code hoping the error moves.
3. **Never claim a gate passed without pasting its output.** Fabricating a green result is the
   most damaging failure available to an agent here, because it defeats every other rule in this
   document. If a command was not run, say it was not run.
4. **A hook that fails for a reason you disagree with is a blocker to report**, not a hook to
   disable. Escalate with the error text and your reasoning.

---

## 7. Prohibited Actions (Strict Rules)

Violating any rule below invalidates the entire contribution regardless of its other merits.

1. **No `typing.Any` and no type-checker suppression.** `Any`, `# type: ignore` (bare or coded),
   `cast()` used to paper over a real mismatch, per-file mypy relaxations, or loosening
   `pyproject.toml` strictness are all forbidden. Model the type correctly or stop and report.

2. **No blocking I/O in async code.** `requests`, `time.sleep`, `psycopg2`, synchronous Valkey
   clients, blocking file reads in request paths, and any `def` (non-async) function performing
   network or DB I/O are forbidden. Unavoidable blocking work goes through
   `anyio.to_thread.run_sync`.

3. **No infrastructure access above the gateway layer.** A router MUST NOT import `AsyncSession`,
   `sqlalchemy`, a Valkey client, or any repository, and MUST NOT return ORM objects. A service
   MUST NOT import `fastapi`, raise `HTTPException`, construct a session/client/pool, or declare
   a module-level client global. Routers speak Pydantic to services; services speak to
   repositories and typed cache gateways.

4. **No lazy loading and no unguarded relationship access.** Never rely on implicit lazy loading
   under `AsyncSession`, never set `lazy="joined"`/`"selectin"` as a model default, never call
   `session.refresh()` from a service to patch a missing relation, and never `model_validate()`
   an ORM object whose nested fields were not eager-loaded by the repository statement.

5. **No manual, unguarded, or history-rewriting schema changes, and no tampering with
   `migrations/env.py`.** Never run raw `CREATE`/`ALTER`/`DROP` against the database, never call
   `Base.metadata.create_all()` outside a throwaway sandbox, never ship a migration without
   idempotency guards and a working `downgrade()`, and never edit, delete, reorder, or re-parent
   an existing revision. The rewriter block and `process_revision_directives=writer` wiring in
   `env.py` are protected: do not remove them, do not overwrite an existing hook instead of
   chaining it, and do not hand-strip the `if_exists` / `if_not_exists` flags out of a generated
   migration to make a diff "cleaner". Schema truth flows `models.py` → Alembic, in that
   direction only.

6. **No hardcoded secrets or configuration.** No API keys, passwords, JWT signing keys,
   connection strings, hostnames, ports, or environment-specific values in source code, tests,
   fixtures, docstrings, or committed `.env` files. Configuration is read exclusively through
   `get_settings()`; `os.getenv` in application code is forbidden.

7. **Never weaken, skip, mock away, or delete tests to make a build pass.** Forbidden: deleting a
   failing test, `@pytest.mark.skip` / `xfail` to hide a real defect, commenting out assertions,
   lowering `--cov-fail-under`, adding coverage exclusions, asserting on a value copied from
   incorrect actual output, and — specifically — patching the database, cache, or repositories in
   an integration test to turn it green (§5.3.1). A failing test is a finding to report, not an
   obstacle to remove.

8. **No unilateral scope or dependency changes.** Do not add, upgrade, or remove dependencies; do
   not introduce a new framework, ORM, task queue, or architectural layer; do not restructure
   directories; do not modify CI configuration or this file; do not perform opportunistic
   refactors of code the task did not require you to touch. Propose such changes in your response
   and wait for explicit human approval.

9. **Never bypass, disable, or weaken the enforcement gate.** Specifically forbidden:
   `git commit --no-verify` / `-n`, `SKIP=<hook> git commit`, `PRE_COMMIT_ALLOW_NO_CONFIG=1`,
   `pre-commit uninstall`, deleting or commenting out a hook in `.pre-commit-config.yaml`,
   pinning a hook to an older `rev` to dodge a new finding, narrowing `mypy` from
   `app tests` to a single file, switching mypy to `pass_filenames: true`, adding
   `exclude:` patterns to hide failing paths, and reporting a check as passing without having
   executed it. For `import-linter` (§3.8) this additionally covers: deleting or renaming a
   contract, adding an `ignore_imports` entry, setting `exhaustive = false`, removing a module
   from `containers`, and the three code-level dodges — hiding a forbidden import behind
   `if TYPE_CHECKING:`, moving it inside a function body, or reaching the same module through an
   alias or `importlib`. Fabricating or paraphrasing command output that was never produced is
   the most serious violation in this document: it silently disables every other rule. If the
   gate blocks you and you believe it is wrong, stop and escalate with the verbatim error text.

   **Config drift is a gate-bypass, not a style choice.** The §2.3 ruff rule set, the mypy strict
   extensions, and the §3.8 wildcarded import-linter contracts are contract text, not a
   suggestion — a `pyproject.toml` that quietly ships a narrower ruff `select`, drops a mypy
   extension, or hand-writes a single-module contract instead of the `app.modules.*` wildcard is
   the same violation as deleting a hook, just committed instead of typed at the CLI. The one
   sanctioned exception is a flag verified incompatible with this stack in isolation and recorded
   as such (see the `disallow_any_explicit` note in §2.3) — silently omitting a documented setting
   without that verification and note is still a violation.

**Security addenda (non-negotiable):** passwords are stored only as Argon2id hashes — never
plaintext, never reversible encryption, never a fast hash like MD5/SHA-1/SHA-256; tokens, hashes,
and PII are never logged or returned in responses; all user input crosses the boundary as a
validated Pydantic schema with `extra="forbid"`; privilege fields are never client-writable; all
SQL is built through SQLAlchemy constructs with bound parameters — string-interpolated SQL is
forbidden without exception.
