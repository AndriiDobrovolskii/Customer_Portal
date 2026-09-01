# Impact Analysis: US-2.3 Refresh Token

**Spec:** `docs/specifications/US-007-refresh-token-spec.md`
**API design:** `docs/designs/api/US-007-openapi.yaml`, `US-007-api-design.md`
**DB design:** `docs/designs/database/US-007-db-design.md`, `US-007-entity-model.md`

## Affected files, by layer

### `models.py` — `app/modules/users/models.py`

- `RefreshToken` — add `consumed_at`, `last_used_at`, `ip`, `user_agent` (all `Mapped[... | None]`, nullable). Touched because FR-1 (rotation), FR-2 (reuse signal), FR-4 (idle-timeout reference), FR-7 (atomic consume guard), and the story's Data Model Notes (`ip`/`user_agent` for US-2.6) all read/write these.
- `AuthAuditLog` — add `severity: Mapped[str | None]`. Touched because FR-2 (resolved OD-4) requires `severity=high` on `refresh_reuse_detected` rows.

### `schemas.py` — `app/modules/users/schemas.py`

- `RefreshResponse` *(new schema)* — `access_token: str`, `expires_in: int`. Touched because `POST /v1/auth/refresh`'s `200` body (per `US-007-openapi.yaml`) is a new, distinct shape from `LoginResponse` (no `token_type` field, per the source story's own API Contract table).

### `repository.py` — `app/modules/users/repository.py`

- `consume_refresh_token(token_hash)` *(new method)* — the atomic `UPDATE refresh_tokens SET consumed_at = now() WHERE token_hash = :hash AND consumed_at IS NULL RETURNING *`. Touched because no existing method performs this check-and-consume; `get_refresh_token_by_hash` (existing, US-2.2) is read-only and cannot serve FR-7's atomicity requirement.
- `create_refresh_token(...)` *(existing method, signature change)* — add optional `ip: str | None = None`, `user_agent: str | None = None`, `last_used_at: datetime | None = None` keyword parameters. Touched because FR-1's rotation populates these on the new row; kept optional (not required) so the existing login call site (US-2.1) keeps compiling unchanged — whether login's own call site is updated to pass real values is a `planner` decision (per `US-007-db-design.md`'s deferred item #1), not assumed here.
- `revoke_refresh_token_family(family_id)` *(existing, US-2.2, unchanged)* — reused as-is by FR-2's reuse-detected family revocation; no signature change needed.
- `create_auth_audit_log_entry(...)` *(existing method, signature change)* — add a `severity: str | None = None` keyword parameter. Touched because FR-2 needs `severity="high"` alongside the existing `event`/`reason`/`scope`/etc. arguments; every existing call site (US-2.1's login flow, US-2.2's logout flow) keeps compiling via the new parameter's default.

### `cache.py` — `app/modules/users/cache.py`

- `RefreshRateLimitCache` *(new class)* — `family_id`-keyed request counter with TTL, mirroring `LoginThrottleCache`'s `_incr_with_ttl`/`_get_count`/`_get_ttl` pattern. Touched because OD-1's 60/family/hour rate limit needs a Valkey-backed counter that doesn't exist today; `LoginThrottleCache` is IP/account-keyed and the wrong shape for a `family_id` key.

### `app/core/cache_keys.py`

- `refresh_rate_limit_key(family_id: uuid.UUID) -> str` *(new function)* — `f"refresh_rate_limit:{family_id}"`, following the existing `login_fail:*` prefix convention. Touched because `RefreshRateLimitCache` needs a documented key-prefix helper (`AGENTS.md` §3's "cache keys come from documented prefix helpers" rule).

### `app/core/email.py`

- `EmailSender` protocol — add `send_refresh_reuse_alert(self, *, to: str) -> None`. Touched because FR-2 requires a security-notification email with no existing method that fits (`send_verification_email`, `send_email_change_confirmation`, `send_email_change_notice` all serve different, workflow-continuation purposes, not a security alert).
- The concrete `EmailSender` implementation — add the matching method body. Same file, same reason.

### `service.py` — `app/modules/users/service.py`

- `rotate_refresh_token(raw_token, *, ip, user_agent, request_id) -> tuple[RefreshResponse, str]` *(new method)* — implements the full FR-1–FR-7 check order: rate limit (OD-1) → hash lookup / expiry (FR-3, folds in FR-5's absolute cap) → already-consumed / reuse (FR-2) → account eligibility (FR-6) → idle timeout (FR-4) → atomic consume-and-rotate (FR-1/FR-7). Returns the raw rotated token alongside the response so the router can set the cookie, mirroring `authenticate_user`'s existing `(LoginResponse, raw_refresh_token)` return shape.
- `TooManyAttemptsError` *(existing exception, reused)* — raised by the new rate-limit check, same class login's throttle already raises; no new exception class needed for this path.

### `router.py` — `app/modules/users/router.py`

- `POST /auth/refresh` *(new route)* — reads the `refresh_token` cookie (`Cookie()`, optional — a missing cookie is FR-3's "unknown" case, not a `422`), calls `service.rotate_refresh_token(...)`, sets the rotated cookie (same `path="/api/v1/auth", httponly=True, secure=True, samesite="strict"` attributes `login`/`logout` already use — per `US-007-api-design.md`'s Open Question #1, this design carries the attributes forward rather than treating their absence from the spec as license to omit them), returns `RefreshResponse`.

### `dependencies.py` — `app/modules/users/dependencies.py`

- `get_user_service(...)` *(existing factory, signature change)* — inject a new `RefreshRateLimitCache` instance (constructed from the existing `valkey_client` dependency, same pattern as `LoginThrottleCache`) into `UserService.__init__`.
- **No new auth dependency.** Unlike `logout`'s `CurrentUserAllowRevokedDep`, `/v1/auth/refresh` is not behind `CurrentUserDep`/`OAuth2PasswordBearer` at all — its sole credential is the refresh cookie itself (per `US-007-api-design.md`'s `refreshCookieAuth` scheme), read directly in the router via `Cookie()`, the same way `logout`'s router function already reads `refresh_token` today.

### `exceptions.py` — `app/modules/users/exceptions.py`

- `TokenInvalidError(ProblemError)` *(new class)* — `type_slug="token-invalid"`, `status=401`. Touched because this is the first use of this slug in the `users` module; `email_verification` and `profile` each already define their own copy (this codebase's established per-module-duplication pattern for `ProblemError` subclasses, not a shared `core` class) — this story adds the `users` module's own copy rather than importing a sibling module's.

## Cross-module ripple

**None.** All of FR-1–FR-7 stay entirely within `app/modules/users/` and `app/core/` (cache keys, email protocol — both already cross-cut every module, not a new dependency this story introduces). No functional requirement calls `account`, `profile`, or `email_verification` services. Unlike US-2.1 (login → `account.service` for reactivation), this story introduces no new cross-module service→service call.

## Migration/schema impact

**Yes, a migration is required.** Five additive, nullable changes — no existing row's data is affected, no existing `INSERT`/`UPDATE` statement needs to change to satisfy a new `NOT NULL` constraint:

- `ALTER TABLE refresh_tokens ADD COLUMN consumed_at TIMESTAMPTZ NULL`
- `ALTER TABLE refresh_tokens ADD COLUMN last_used_at TIMESTAMPTZ NULL`
- `ALTER TABLE refresh_tokens ADD COLUMN ip VARCHAR(45) NULL`
- `ALTER TABLE refresh_tokens ADD COLUMN user_agent TEXT NULL`
- `ALTER TABLE auth_audit_log ADD COLUMN severity VARCHAR(16) NULL`

No new index (per `US-007-db-design.md` — the existing unique `token_hash` index and `ix_refresh_tokens_family_id` from US-2.2 already serve every query this story adds).

Existing repository queries affected: `create_refresh_token`'s existing call site (`service.py`'s `authenticate_user`, US-2.1's login flow) keeps compiling unchanged since the three new parameters are optional with `None` defaults; `create_auth_audit_log_entry`'s existing call sites (login's and logout's flows) need no source change, since `severity` defaults to `None`, same as how US-2.2's `scope` parameter was added without touching pre-existing call sites' behavior.

## Test-surface impact

### New test files / new coverage

- `tests/unit/modules/users/test_users_service.py` *(extended)* — unit tests for `rotate_refresh_token()`'s branches: successful rotation, reuse detection (family revocation + audit + email), expired/unknown/revoked-by-logout (identical response), idle timeout, account ineligibility, and the check-order interactions the spec review's addendum resolved (rate-limit-before-lookup, expired-and-reused precedence).
- `tests/integration/modules/users/test_users_router.py` *(extended)* — full HTTP round trip for RT-AC1–RT-AC6, including a genuine concurrency test for RT-AC6 (two simultaneous requests presenting the same token) and a `429` test for OD-1's rate limit.
- New or extended fakes for `RefreshRateLimitCache` (unit) — this project's "fakes over `MagicMock`" rule (`AGENTS.md` §5) applies the same way `LoginThrottleCacheProtocol`'s fake already does for login's tests.

### Existing test files that change

- `tests/unit/modules/users/test_users_service.py` — any existing test asserting on `create_auth_audit_log_entry`'s call arguments needs to account for the new `severity` keyword (signature change, not behavior change, for every pre-existing login/logout-flow assertion) — same class of update US-2.2's `scope` addition already required.
- `tests/integration/modules/users/test_users_router.py` — no existing test's behavior changes; a login-then-refresh chained-request helper may be added/reused (this codebase's login-cookie-into-a-second-request pattern, established by US-2.2's own `conftest.py` fix).

### Not affected

- `tests/unit/modules/account/`, `tests/unit/modules/profile/`, `tests/unit/modules/email_verification/` — no cross-module ripple, per above.
- Migration test cycle (upgrade/downgrade/upgrade) — required by `migration-manager`'s own workflow, not a pre-existing file to modify.
