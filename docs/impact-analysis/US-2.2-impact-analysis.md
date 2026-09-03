# Impact Analysis: US-2.2 Logout

**Spec:** `docs/specifications/US-2.2-spec.md`
**API design:** `docs/designs/api/US-2.2-openapi.yaml`, `US-2.2-api-design.md`
**DB design:** `docs/designs/database/US-2.2-db-design.md`, `US-2.2-entity-model.md`

## Affected files, by layer

### `models.py` — `app/modules/users/models.py`

- `RefreshToken` — add `revoked_at: Mapped[datetime | None]` column; add `index=True` to the existing `family_id` column. Touched because FR-1 (per resolved OD-3) requires revoking a whole refresh-token family.
- `AuthAuditLog` — add `scope: Mapped[str | None]` column. Touched because FR-1/FR-2 (per resolved OD-5) require recording `session`/`all_sessions` on logout audit rows.
- `UserSession` — **no change.** FR-1/FR-4/FR-5 write/read the existing `revoked_at` column (added by US-2.1); no new column is needed here.

### `schemas.py` — `app/modules/users/schemas.py`

- **No change.** Both endpoints (`POST /v1/auth/logout`, `POST /v1/auth/logout-all`) have no request body and a `204` response with no body (per `US-2.2-openapi.yaml`) — no new Pydantic schema class is needed.

### `repository.py` — `app/modules/users/repository.py`

- `revoke_session(jti)` *(new method)* — sets `revoked_at = now()` on the single `user_sessions` row matching `jti`. Touched because no existing method performs a single-row revoke by `jti`; `revoke_sessions_except` (existing) is a bulk, user-scoped operation and is the wrong shape for FR-1's single-jti revoke.
- `get_refresh_token_by_hash(token_hash)` *(new method)* — resolves a raw refresh cookie's `token_hash` to its `refresh_tokens` row. Touched because FR-1 needs to find the row before it can revoke its family; no lookup-by-hash method exists today (only `create_refresh_token` exists).
- `revoke_refresh_token_family(family_id)` *(new method)* — bulk-sets `revoked_at = now()` on every `refresh_tokens` row sharing `family_id`. Touched because FR-1 revokes the whole rotation family, not just the presented token (resolved OD-3); mirrors the existing `revoke_sessions_except` bulk-update pattern.
- `create_auth_audit_log_entry(...)` *(existing method, signature change)* — add a `scope: str | None` parameter. Touched because FR-1/FR-2 need to pass `scope` alongside the existing `event`/`reason`/`actor_id`/etc. arguments (resolved OD-5); every existing call site in `service.py`'s login flow (FR-1–FR-4 of US-2.1) passes `scope=None` after this change.

### `service.py` — `app/modules/users/service.py`

- `logout(access_token, refresh_cookie)` *(new method)* — implements FR-1/FR-4: revokes the session by jti, resolves and revokes the refresh-token family if a cookie was presented (skipping silently on a lookup miss, per the spec-review resolution), writes the `scope=session` audit entry.
- `logout_all(user_id)` *(new method)* — implements FR-2: calls the existing `RevocationCache.set_revoke_before`, writes the `scope=all_sessions` audit entry.
- `get_authenticated_user(token, *, allow_revoked=False)` *(existing method, signature change)* — per `US-2.2-api-design.md`'s Open Question #1, add an opt-in parameter so `POST /v1/auth/logout`'s dependency can resolve a caller whose jti is already revoked (FR-4/resolved OD-2) without weakening every other authenticated route, which continues to call this method with the default `allow_revoked=False`.

### `router.py` — `app/modules/users/router.py`

- `POST /auth/logout` *(new route)* — calls `service.logout(...)`, returns `204`.
- `POST /auth/logout-all` *(new route)* — calls `service.logout_all(...)`, returns `204`.

### `dependencies.py` — `app/modules/users/dependencies.py`

- `get_current_user_allow_revoked` *(new dependency)* or an equivalent parameterization of the existing `get_current_user` — touched because FR-4's leniency (resolved OD-2) must apply only to the `/logout` route's dependency chain, not the shared `CurrentUserDep` every other route uses. Exact shape (new function vs. a `Depends()`-injected flag) is an `implementation-planner`/`service-and-router-builder` decision, not resolved here.

### `exceptions.py` — `app/modules/users/exceptions.py`

- **No change.** `UnauthenticatedError` (existing, `type_slug="unauthenticated"`) is reused as-is for both endpoints' `401` — no new error class needed (spec NFR: no new error `type` slugs).

## Cross-module ripple

**None.** Both endpoints stay entirely within `app/modules/users/`. Unlike US-2.1 (login), which called `account.service.AccountService.reactivate_account()` for OD-10's reactivation branch, logout has no functional requirement that touches `account`, `profile`, or `email_verification`. No new cross-module service→service call is introduced by this story.

## Migration/schema impact

**Yes, a migration is required.** Three additive, nullable changes — no existing row's data is affected, no existing `INSERT`/`UPDATE` statement needs to change to satisfy a new `NOT NULL` constraint:

- `ALTER TABLE refresh_tokens ADD COLUMN revoked_at TIMESTAMPTZ NULL`
- `CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens (family_id)`
- `ALTER TABLE auth_audit_log ADD COLUMN scope VARCHAR(32) NULL`

No existing repository query is affected: `create_refresh_token` (existing) doesn't set `revoked_at`, so it defaults to `NULL` correctly with no code change; `create_auth_audit_log_entry`'s existing call sites (US-2.1's login flow) need one new keyword argument (`scope=None`) to keep compiling once the method signature changes, but no *behavior* of those existing rows changes.

## Test-surface impact

### New test files

- `tests/unit/modules/users/test_users_service_logout.py` *(or added to the existing `test_users_service.py`)* — unit tests for `logout()`/`logout_all()`'s revocation logic, the `allow_revoked` carve-out, and the refresh-token lookup-miss branch.
- Integration coverage for `POST /v1/auth/logout` and `POST /v1/auth/logout-all` — added to the existing `tests/integration/modules/users/test_users_router.py` (matches how US-2.1's login tests were added to this same file rather than a new one).

### Existing test files that change

- `tests/unit/modules/users/test_users_service.py` — any existing test that calls `create_auth_audit_log_entry` or asserts on its call arguments needs updating for the new `scope` parameter (signature change, not behavior change, for every pre-existing login-flow assertion).
- `tests/integration/modules/users/test_users_router.py` — no existing test's *behavior* changes, but a fixture/helper that logs a user in to obtain a token may need reuse or extension to also exercise logout in the same flow.

### Not affected

- `tests/unit/modules/account/test_account_service.py` — no cross-module ripple into `account`, per above.
- Migration test cycle (upgrade/downgrade/upgrade) — new test coverage is required by `migration-manager`'s own workflow, not a pre-existing file to modify.
