# Impact Analysis: US-2.1 Login

**Spec:** `docs/specifications/US-005-login-spec.md` (Pass with Issues, accepted 2026-08-31)
**API:** `docs/designs/api/US-005-openapi.yaml`, `US-005-api-design.md`
**DB:** `docs/designs/database/US-005-db-design.md`, `US-005-entity-model.md`

## Architectural fact found during this survey — resolved 2026-08-31 (OD-9)

**Status: Resolved.** User chose to build a minimal `refresh_tokens` table now. Folded into `docs/designs/database/US-005-db-design.md` and `US-005-entity-model.md`; `docs/decisions/US-2.1-open-decisions.md` OD-9. The finding is kept below verbatim for traceability.

**`refresh_tokens` table is required by this story and was not modeled in the original DB design.** `docs/stories/US-2.1-login.md`'s own Data Model Notes section never mentions a refresh-token table — only `users.last_login_at` and `auth_audit_log` — which is why `db-designer` didn't model one (per its own constraint: don't invent an entity the spec doesn't support). But `docs/stories/US-2.3-refresh-token.md`'s **Out of Scope** section states explicitly: *"Initial token issuance (US-2.1)"* — i.e. US-2.3 itself asserts that creating the very first refresh token is this story's job, not its own. US-2.3's Data Model Notes define the shape that token eventually needs: `refresh_tokens` (`token_hash` SHA-256 unique, `family_id`, `user_id`, `issued_at`, `consumed_at`, `expires_at`, plus `ip`/`user_agent`/`last_used_at` for US-2.6). No `refresh_tokens` table, or any refresh-token generation code, exists anywhere in `app/` today (`grep -i refresh_token` across `app/` returns nothing).

This is not something to decide here — same escape hatch US-004's `openapi-designer` used for its revocation-substrate question — but it does mean the DESIGN stage's output is incomplete on this one point and should be revisited before or during PLANNING: either (a) `db-designer` adds a minimal `refresh_tokens` row shape now (token_hash/family_id/user_id/issued_at/expires_at, deferring `consumed_at`'s rotation semantics and the `ip`/`user_agent`/`last_used_at` columns to US-2.3/US-2.6 since this story doesn't need to read them), or (b) this story issues an opaque, unvalidated cookie value with no backing table and US-2.3 introduces the table when it starts actually consuming/rotating tokens. Recommend surfacing to the user before `planner` commits to file-level changes, since it changes both the migration and the service-layer work.

## Affected files, by layer

### `models.py` — `app/modules/users/models.py` (existing file, modified)
- Add `User.last_login_at: Mapped[datetime | None]` — FR-1 needs to persist it.
- Add new `AuthAuditLog` model (per `US-005-entity-model.md`) — FR-1–FR-4 each write a row.
- Add new `RefreshToken` model (resolved OD-9, per `US-005-entity-model.md`) — FR-1 inserts a row on every successful login.

### `schemas.py` — `app/modules/users/schemas.py` (existing file, modified)
- `LoginRequest.password` needs `min_length=1` (resolved OD-8 — currently just `SecretStr`, no length constraint) — FR-6.
- `LoginResponse` needs `token_type: Literal["Bearer"]` (currently `str = "bearer"`, lowercase — a breaking shape change from the existing minimal endpoint) and a new `expires_in: int` field — FR-1.
- New response/request schemas are not needed beyond these two — no new endpoint, only the existing one's shapes change.

### `repository.py` — `app/modules/users/repository.py` (existing file, modified)
- New method to set `users.last_login_at` (FR-1) — today's `UserRepository` has no update method touching `users` at all beyond `create()`.
- New method(s) to insert an `AuthAuditLog` row (FR-1–FR-4).
- New method to insert a `RefreshToken` row (resolved OD-9, FR-1).
- `get_by_email` (existing, unchanged) is reused as-is for the credential lookup.

### `cache.py` — new file, `app/modules/users/cache.py` (module currently has none)
- Throttle-counter gateway: increment/read/reset `login_fail:account:{user_id}` and `login_fail:ip:{ip}` (FR-5). This is new Valkey surface for the `users` module — today only `app.core.revocation_cache.RevocationCache` touches Valkey, and it's deliberately core-owned (cross-module), whereas the throttle counters are login-specific and belong in the module per `AGENTS.md`'s per-module `cache.py` convention.

### `service.py` — `app/modules/users/service.py` (existing file, modified)
`authenticate_user` needs substantial rework — every branch below is new or changed relative to today's implementation:
- Dummy Argon2id verification on unknown email (FR-3) — today's code raises `InvalidCredentialsError` immediately when `user is None`, with no comparable-cost operation.
- Deactivated-account gating (FR-4) — today's code checks only `email_verified`, never `UserStatus.DEACTIVATED`. **Found during PLANNING→IMPLEMENTATION handoff:** nothing in the codebase ever writes `users.status = "active"` anywhere (confirmed via repo-wide grep) — `register_user` writes `PENDING_VERIFICATION` and never updates it; email verification only sets `email_verified=True`; deactivation is gated on `User.status != "deactivated"`, not on an `"active"` value. The deactivation check here MUST therefore test `user.status == UserStatus.DEACTIVATED.value` (or equivalently `user.deactivated_at is not None`), never `status != UserStatus.ACTIVE` — the latter would 403 every real user, since `status` never actually reaches `"active"` today.
- Reactivation branch (resolved OD-10) — see the new Cross-module ripple entry and the new `account/service.py`/`repository.py` bullets above.
- Ordering: credential check → throttle check → state-gate check, per FR-4's "credential verification runs first" guarantee — needs explicit sequencing, not just new branches bolted onto the existing structure.
- Brute-force throttle check and counter increment/reset (FR-5).
- `auth_audit_log` writes on every terminal branch except `429`/`422` (FR-1–FR-4, resolved OD-3/OD-4/OD-6).
- `users.last_login_at` update on success (FR-1).
- Refresh-token issuance (`secrets.token_urlsafe(32)`-style raw value, SHA-256 hash stored per resolved OD-9, matching US-2.3's Assumption #5 token design) and cookie-setting.
- `LoginResponse` construction needs `token_type="Bearer"`/`expires_in` added.

### `exceptions.py` — `app/modules/users/exceptions.py` (existing file, modified)
- `InvalidCredentialsError` currently extends `DomainError`, not `ProblemError` — no `type_slug`/`status`/`title`/`detail` set. It needs to become a `ProblemError` subclass (`type_slug="invalid-credentials"`, `status=401`) to render the RFC 7807 body FR-2/FR-3 require; today it's rendered by a bespoke handler in `app/main.py` that returns `{"detail": ...}`, not a problem+json body at all.
- New `AccountDeactivatedError(ProblemError)` (`type_slug="account-deactivated"`, `status=403`) — FR-4's deactivated branch. Distinct from `app/modules/account/exceptions.py:AlreadyDeactivatedError` (409, a different story's different error) — do not conflate the two.
- New `TooManyAttemptsError(ProblemError)` (`type_slug="too-many-attempts"`, `status=429`, needs a `headers={"Retry-After": ...}` override matching `UnauthenticatedError`'s existing pattern of setting `headers` in `__init__`) — FR-5.
- `EmailNotVerifiedError` (existing, unchanged) is reused as-is.

### `router.py` — `app/modules/users/router.py` (existing file, modified)
- `login` handler needs new dependencies injected: `get_request_id` (`app.core.dependencies`, already exists and used by `profile/router.py` — reusable as-is, resolves the DB design's open question about `request_id` non-nullability: it's a per-route `Depends()`, not global middleware, so it works fine on this unauthenticated route too), plus a new client-IP extraction dependency (no existing helper for this — new) and `request.headers.get("User-Agent")`.
- Needs to set the `Set-Cookie` response header (FR-1) — no existing endpoint in this codebase sets a cookie today; this is new response-construction code, not a copy of an existing pattern.

### `dependencies.py` — `app/modules/users/dependencies.py` (existing file, modified)
- `get_user_service` needs to inject the new `cache.py` gateway (mirroring how `RevocationCache` is already injected) and the throttle-config settings.
- Possibly a new `get_client_ip` dependency, if not added directly in `router.py`.

### `app/core/security.py` (existing file, modified)
- New helper for the dummy Argon2id verification path (FR-3) — e.g. a module-level fixed hash constant plus a `verify_password`-shaped call against it, so the cost is comparable to a real verification. Nothing in this file today supports a "verify against nothing" path.

### `app/core/config.py` (existing file, modified)
- New settings: account-level and IP-level failure thresholds and window (`10`/`15min`, `20`/`15min` per FR-5) — none of today's `Settings` fields cover rate limiting.
- New setting: refresh-token TTL (resolved OD-9; recommend reusing US-2.3's 30-day absolute-cap figure as this story's `expires_at` — flagged in `US-005-db-design.md` as a `planner`-level call, not fixed here).

### `app/core/cache_keys.py` (existing file, modified)
- New key-helper functions `login_fail_account_key(user_id)` / `login_fail_ip_key(ip)`, alongside the existing `revoke_before_key`.

### `app/main.py` (existing file, modified)
- Remove or repurpose the bespoke `invalid_credentials_error_handler` (lines 90–94) once `InvalidCredentialsError` becomes a `ProblemError` subclass — it would otherwise shadow the generic `problem_error_handler` and keep returning the old non-problem+json body.
- No new handler needed for `AccountDeactivatedError`/`TooManyAttemptsError` — both flow through the existing generic `problem_error_handler` once they're `ProblemError` subclasses, same as `EmailNotVerifiedError` already does.
- **Found during PLANNING→IMPLEMENTATION handoff (advisor consultation):** `request_validation_error_handler` (lines 97–108) renders `{"detail": [...]}`, not RFC 7807 `problem+json` — FR-6 requires `type=".../errors/validation-failed"` plus an `errors` array naming fields. This handler needs rework (or `LoginRequest`'s Pydantic validation errors need routing through a `ValidationFailedError(ProblemError)` instead of FastAPI's default `RequestValidationError` path) — this is a pre-existing gap the earlier impact-analysis pass missed, not new scope. Affects FR-6 and OD-8's empty-password case, both of which rely on this handler's shape.

### `app/modules/account/service.py`, `repository.py` (existing files, modified — resolved OD-10)
- `AccountService`: new `reactivate_account(user_id)` method — the reactivation counterpart to `deactivate_account`, called cross-module by `users/service.py`.
- `AccountRepository`: new method, the mirror image of `deactivate_if_not_already` — an atomic conditional update reactivating the account only if it's within the 30-day grace period, returning `None` otherwise (so the caller knows whether reactivation actually happened vs. the account being past-grace or already active).
- `app/modules/account/dependencies.py`: `AccountService`'s constructor signature is unchanged (it already takes a repository + cache); no new dependency wiring needed here, but `users/dependencies.py` needs to construct/inject an `AccountService`-typed collaborator into `UserService`.

### Migration
- New Alembic revision needed. Confirmed changes: `users.last_login_at` (additive, nullable — safe), new `auth_audit_log` table, new `refresh_tokens` table (resolved OD-9) with an FK to `users.id` (`ondelete="CASCADE"`).

## Cross-module ripple

**Addendum 2026-08-31 (resolved OD-10):** `authenticate_user` (`users/service.py`) now calls a new collaborator, `AccountService.reactivate_account(user_id)` (`account/service.py`), when FR-4's reactivation branch fires. This is a genuine new cross-module dependency — `users` calling `account` — injected as a `Protocol`-typed collaborator into `UserService.__init__`, mirroring the existing `revoke_other_sessions` cross-module pattern (`profile` → `users`, added for US-1.3's email-change flow). Caller: `UserService.authenticate_user` (`app/modules/users/service.py`). Callee: a new `AccountService.reactivate_account` method (`app/modules/account/service.py`), which needs its own new repository method (`AccountRepository`, an atomic "reactivate if within grace period" update — the mirror image of the existing `deactivate_if_not_already`) and writes the `account_lifecycle_audit_log` entry itself, so `account` stays the sole owner of writes to its own audit table (`users` never touches `account_lifecycle_audit_log` directly).

Originally (before this addendum): none found. `authenticate_user` otherwise calls only `UserRepository`, the new `cache.py` gateway, and `app.core.security`/`app.core.config` — all within the `users` module or core.

## Test-surface impact

### Existing files that must change
- `tests/unit/modules/users/test_users_service.py` — the existing `authenticate_user` unit tests (covering VE-AC5/VE-AC6 only) will need rewriting/extending for every new branch: unknown-email timing, deactivated gating, throttling, audit-log writes, `last_login_at` update, refresh-token issuance.
- `tests/integration/modules/users/test_users_router.py` — the existing login integration test(s) need extending for the full LI-AC1–LI-AC6 set (response shape, cookie, headers, status codes, problem+json bodies).

### New test surface
- A Valkey-backed fixture for the throttle counters (`tests/conftest.py` already has a Valkey fixture, added for US-004's `RevocationCache` — reusable, not new infrastructure, but the throttle-specific setup/teardown around it is new).
- Unit tests for the new `cache.py` gateway (`app/modules/users/cache.py`).
- Unit tests for the dummy-verification helper in `app/core/security.py`.

## Not modeled here (explicitly out of scope for this analysis)

- Sequencing/execution order of the changes above — that's `planner`/`implementation-planner`.
