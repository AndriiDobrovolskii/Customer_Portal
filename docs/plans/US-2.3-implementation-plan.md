# Implementation Plan: US-2.3 Refresh Token

**Spec:** `docs/specifications/US-2.3-spec.md` (Pass with Issues, accepted 2026-09-01)
**API:** `docs/designs/api/US-2.3-openapi.yaml`, `US-2.3-api-design.md`
**DB:** `docs/designs/database/US-2.3-db-design.md`, `US-2.3-entity-model.md`
**Impact analysis:** `docs/impact-analysis/US-2.3-impact-analysis.md`

## Goal

Add `POST /v1/auth/refresh` to `app/modules/users/`: single-use rotation with an atomic Postgres check-and-consume (FR-1/FR-7), reuse detection triggering family-wide revocation, a `severity=high` audit entry, and a security email (FR-2), idle/absolute lifetime enforcement (FR-4/FR-5), denial for deactivated/revoked accounts (FR-6), and a per-family rate limit (FR-2's NFR, resolved OD-1) — in that check order.

## Architectural Changes

- **No new module, no new router file.** Everything stays inside the already-scaffolded `app/modules/users/`, extending `cache.py` (new class) rather than creating a `refresh` module — the endpoint is a `users`-module concern exactly like login/logout.
- **New `TokenInvalidError(ProblemError)` in `app/modules/users/exceptions.py`** — `type_slug="token-invalid"`, `status=401`. This is the `users` module's own copy; `email_verification`/`profile` each already hold their own identically-slugged class (this codebase's established per-module-duplication pattern for `ProblemError` subclasses — confirmed via grep, not assumed). Raised uniformly by FR-2, FR-3, and FR-6's branches so the response is byte-identical across all three (FR-3's indistinguishability requirement).
- **New `RefreshRateLimitCache` in `app/modules/users/cache.py`**, mirroring `LoginThrottleCache`'s `_incr_with_ttl`/`_get_count`/`_get_ttl` internals but keyed by `family_id` via a new `refresh_rate_limit_key()` helper in `app/core/cache_keys.py`. Per the spec-review's resolved ordering, this check runs first — immediately after the presented token resolves to a `family_id` — raising the existing `TooManyAttemptsError` (no new exception class; same class login's throttle already raises).
- **New atomic repository method `consume_refresh_token(token_hash)`** implementing `UPDATE refresh_tokens SET consumed_at = now() WHERE token_hash = :hash AND consumed_at IS NULL RETURNING *` (per `US-2.3-db-design.md`'s recommended mechanism — Postgres, not a Valkey Lua script, since the row is already the state's source of truth). FR-7's atomicity requirement is satisfied by the database's own row-level locking on the `UPDATE`, not by application-level coordination.
- **`create_refresh_token`'s existing call site (login, `authenticate_user`) is updated to pass real `ip`/`user_agent`.** `US-2.3-db-design.md` flagged this as a deferred planner decision; resolving it here: `authenticate_user` already receives `ip`/`user_agent` as parameters (used today for `create_auth_audit_log_entry`), so threading them into the same call's `create_refresh_token` invocation is a one-line, zero-new-information change — not doing so would leave every family's very first row permanently missing this metadata until its first rotation, undermining US-2.6's eventual session listing for any user who refreshes rarely within a session. `last_used_at` is deliberately left unset (`None`/`NULL`) at login issuance — per FR-4's design, this is intentional (see `US-2.3-db-design.md`), not an oversight.
- **New `EmailSender.send_refresh_reuse_alert(self, *, to: str) -> None`** in `app/core/email.py`'s protocol and concrete implementation. Called fire-and-forget (resolved same-day spec-review finding) — the `401`/family-revocation/audit-write outcome does not wait on or depend on this call's success, matching the registration verification-email precedent already in this codebase.
- **`create_auth_audit_log_entry` gains a `severity: str | None = None` parameter** (resolved OD-4), threaded explicitly (not relying on the default) at this story's one call site (`event=refresh_reuse_detected, severity="high"`); every pre-existing call site (US-2.1 login, US-2.2 logout) keeps passing `severity=None` explicitly, mirroring how `scope` was added in US-2.2.
- **New `rotate_refresh_token()` service method** is the single place the five-step check order lives (rate limit → exists/not-expired → already-consumed/reuse → account eligibility → idle timeout → atomic consume), so the order is enforced in one function rather than scattered across router/dependency layers. Returns `(RefreshResponse, raw_refresh_token)`, mirroring `authenticate_user`'s existing `(LoginResponse, raw_refresh_token)` shape so the router's cookie-setting code can follow the same pattern `login`'s route already uses.
- **No new auth dependency.** `POST /v1/auth/refresh` reads the `refresh_token` cookie directly via `Cookie()` in the router (same as `logout`'s router function already does) — it is not behind `CurrentUserDep`/`OAuth2PasswordBearer` at all, since a Bearer access token is neither required nor relevant to this endpoint.

## Files To Create

| File | Reason |
|---|---|
| `migrations/versions/<rev>_add_refresh_rotation_columns.py` | New Alembic revision for `refresh_tokens.{consumed_at,last_used_at,ip,user_agent}` and `auth_audit_log.severity` — generated via `migration-manager`, not hand-written here. |

No new module, no new test file beyond extending existing ones (per impact analysis) — this story is additive to an already-scaffolded module.

## Files To Modify

Per `docs/impact-analysis/US-2.3-impact-analysis.md`'s survey (not re-derived here):

| File | Change |
|---|---|
| `app/modules/users/models.py` | `RefreshToken` gains `consumed_at`, `last_used_at`, `ip`, `user_agent`; `AuthAuditLog` gains `severity`. |
| `app/modules/users/schemas.py` | New `RefreshResponse` (`access_token`, `expires_in`) — no request schema (cookie-only, no body). |
| `app/modules/users/repository.py` | New `consume_refresh_token(token_hash)` (atomic). `create_refresh_token` gains optional `ip`/`user_agent`/`last_used_at` params. `create_auth_audit_log_entry` gains `severity` param. `revoke_refresh_token_family` (existing, US-2.2) reused unchanged. |
| `app/modules/users/cache.py` | New `RefreshRateLimitCache` class. |
| `app/core/cache_keys.py` | New `refresh_rate_limit_key(family_id)` helper. |
| `app/core/email.py` | `EmailSender` protocol + implementation gain `send_refresh_reuse_alert`. |
| `app/modules/users/service.py` | New `rotate_refresh_token(raw_token, *, ip, user_agent, request_id)` implementing FR-1–FR-7. `authenticate_user` (existing) updated to pass `ip`/`user_agent` into `create_refresh_token`. |
| `app/modules/users/router.py` | New `POST /auth/refresh` route: reads the `refresh_token` cookie, calls `service.rotate_refresh_token(...)`, sets the rotated cookie (`path="/api/v1/auth", httponly=True, secure=True, samesite="strict"`, matching `login`/`logout`'s existing attributes), returns `RefreshResponse`. |
| `app/modules/users/dependencies.py` | `get_user_service` wires a new `RefreshRateLimitCache(valkey_client)` into `UserService.__init__`. No new auth dependency. |
| `app/modules/users/exceptions.py` | New `TokenInvalidError`. |
| `tests/unit/modules/users/test_users_service.py` | Extend for `rotate_refresh_token()`'s branches; update any existing `create_auth_audit_log_entry`/`create_refresh_token` assertions for the new parameters. |
| `tests/integration/modules/users/test_users_router.py` | Extend for RT-AC1–RT-AC6, including a genuine concurrency test and a `429` test. |

## Protected files — flagged per AGENTS.md §7.9, none touched

`pyproject.toml`, `migrations/env.py`, `.pre-commit-config.yaml` are not modified by this plan. No new third-party dependency is needed (Valkey rate-limiting reuses the existing `redis.asyncio` client already wired for `LoginThrottleCache`/`RevocationCache`).

## Risks

- **The five-step check order is the single highest-risk element of this story.** A misordering silently changes observable security behavior — e.g. checking account-eligibility before reuse-detection would suppress the reuse alert against a deactivated account, reopening the exact ambiguity resolved OD-5 closed. Mitigate: implement the order as a single linear sequence of early-returns in `rotate_refresh_token()`, not as independently-callable checks a future change could reorder; a dedicated unit test asserts the resolved OD-5/spec-review ordering (rate-limit → exists/expired → reuse → eligibility → idle → atomic consume) via a token crafted to hit multiple conditions at once (e.g. both consumed and belonging to a deactivated account → must alert, per OD-5).
- **FR-7's atomicity depends entirely on the `UPDATE ... WHERE consumed_at IS NULL RETURNING` running as one statement.** A read-then-write split (a `SELECT` to check `consumed_at IS NULL` followed by a separate `UPDATE`) reintroduces the exact TOCTOU bug the spec calls out as a hard requirement, not an implementation detail. Mitigate: `consume_refresh_token`'s single `UPDATE ... RETURNING` is the only place this state transitions; `implementation-verifier`/`security-reviewer` should specifically confirm no other code path reads `consumed_at` and then separately writes it.
- **The 10-second concurrent-refresh grace window (RT-AC6) requires distinguishing "just raced" from "genuine reuse" using the losing request's own read of the row's `consumed_at`.** After `consume_refresh_token` returns no row (lost the race), the service must re-fetch the row to compare `now() - consumed_at` against the 10-second threshold before deciding between a plain `401` (race) and FR-2's full reuse-detection path (family revocation + audit + email). Mitigate: this comparison lives in `rotate_refresh_token()` immediately after a failed atomic consume, not duplicated elsewhere.
- **`create_refresh_token`'s signature change touches US-2.1's already-shipped `authenticate_user` call site.** Adding `ip`/`user_agent` arguments there is a compile-time-visible, low-risk change (mypy will flag any stale call site) — but `implementation-verifier` should confirm no existing login test asserts the *absence* of these values on the created row, which would need updating rather than merely continuing to pass.
- **Migration is purely additive** — five nullable-column changes, no backfill, no `ALTER` on a populated `NOT NULL` column. The `AGENTS.md` §4 expand→migrate→contract concern doesn't apply.
- **`EmailSender.send_refresh_reuse_alert` must not block or fail the `401` response.** Per the spec's resolved fire-and-forget requirement, a mitigate: schedule/await it in a way that a raised exception from the email call (e.g. SMTP failure) is caught and logged, never propagated to fail the request — mirroring how registration's `send_verification_email` is already documented as "must succeed regardless of whether the verification email goes out."

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy strict on `app tests`, secret scan, no-mock-in-integration grep — must be green (`gate-enforcer`'s job, not this plan's).
- `lint-imports` — no new file layer is introduced (`cache.py` already exists as a declared layer for this module); the new repository method, cache class, and service method must still respect existing layer boundaries (`service.py` may import `cache.py`/`repository.py`, never `fastapi`/`starlette`/`HTTPException`).
- Migration cycle: `alembic upgrade head` → `downgrade` → `upgrade` proven clean (`migration-manager`'s job) — a pure additive migration, but the read-before-trust rule applies regardless.
- No `.env.example` change expected — the rate limit (60/family/hour) and grace window (10s) are currently hardcoded story constants, not `Settings` fields, matching how the idle-timeout/absolute-cap thresholds (14/30 days) are also not yet `Settings` fields for this codebase; flag to `gate-enforcer` if `service-and-router-builder` decides these should become configurable settings instead.

## Testing Strategy

Per `AGENTS.md` §5's unit/integration split:

- **Unit** (`tests/unit/modules/users/test_users_service.py`, hand-written fakes for `UserRepositoryProtocol`/`RefreshRateLimitCacheProtocol`/`EmailSenderProtocol` — never `MagicMock`): `rotate_refresh_token()` — successful rotation preserves `family_id`/`expires_at` and sets `consumed_at` on the old row (FR-1); reuse triggers family revocation + `severity=high` audit + email, even when the account is already deactivated (FR-2, OD-5's ordering); unknown/expired/revoked-by-logout all produce the identical `TokenInvalidError` (FR-3); idle timeout via `COALESCE(last_used_at, issued_at)` (FR-4); absolute cap via `expires_at` alone (FR-5); deactivated/`revoke_before` account (FR-6); rate limit raises `TooManyAttemptsError` before any DB lookup for a family already over 60/hour (OD-1); a token both expired and consumed resolves via the expired branch, not reuse (spec-review finding, resolved).
- **Integration** (`tests/integration/modules/users/test_users_router.py`, real Postgres + Valkey, `AsyncClient`/`ASGITransport`, no mocking): full request/response cycle for RT-AC1 (`200` + rotated cookie + persisted `consumed_at`), RT-AC2 (`401` + persisted family-wide `revoked_at` + persisted `severity=high` audit row), RT-AC3 (three sub-cases all `401 token-invalid`, identical body), RT-AC4/RT-AC5 (`401` at each threshold), RT-AC6 — a **genuine concurrency test**: two simultaneous requests presenting the same token, asserting exactly one `200` and one `401`, with the family's `revoked_at` still `NULL` afterward (not revoked, since it's a race not an attack). A dedicated `429` test drives a family past 60 requests within the throttle window.
- Coverage floor 85% overall, 90%+ for `service.py`/`router.py` per `AGENTS.md` §5 — `rotate_refresh_token()`'s branch count (6+ distinct outcomes) is the largest in this module since login's `authenticate_user`; the unit-test list above is written to reach full branch coverage without a parametrized sweep, matching how login's own FR-4 state-gating was tested.
