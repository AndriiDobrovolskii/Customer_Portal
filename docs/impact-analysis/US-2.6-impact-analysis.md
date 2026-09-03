# Impact Analysis: US-2.6 Active Session Management

**Spec:** `docs/specifications/US-2.6-spec.md`
**API design:** `docs/designs/api/US-2.6-openapi.yaml`, `US-2.6-api-design.md`
**DB design:** `docs/designs/database/US-2.6-db-design.md`, `US-2.6-entity-model.md`

## Affected files, by layer

### `models.py` — `app/modules/users/models.py`

- `RefreshToken` — **no column change.** `family_id`, `ip`, `user_agent`, `last_used_at`, `revoked_at`, `issued_at`, `expires_at`, `consumed_at` all already exist (added by US-2.1/US-2.2/US-2.3). Touched only in the sense that the new composite index (below) is declared on this class via `Index(...)` in `__table_args__` or an inline `index=True`/`Index` construct — no `mapped_column()` line changes.
- `AuthAuditLog` — add `target_family: Mapped[uuid.UUID | None]` column. Touched because FR-2 (`event=session_revoked`) and FR-7 (`event=session_evicted`) both need to record which family was affected, and neither existing `reason`/`scope` column (both `String(32)`) can hold a UUID or carries the right semantics (per `US-2.6-db-design.md`).

### `schemas.py` — `app/modules/users/schemas.py`

- `SessionEntry` *(new schema)* — `family_id`, `created_at`, `last_used_at`, `location` (nested, nullable), `device_label`, `is_current`. Touched because FR-1's response shape has no existing schema to reuse.
- `SessionListResponse` *(new schema)* — `sessions: list[SessionEntry]`. Touched because `GET /v1/auth/sessions`'s `200` body has no existing schema.
- No new request schema — both endpoints have no request body (`US-2.6-openapi.yaml`).

### `repository.py` — `app/modules/users/repository.py`

- `list_live_families_for_user(user_id)` *(new method)* — runs the `DISTINCT ON (family_id)` query for each live family's current-state row (`US-2.6-entity-model.md` query (1)). Touched because no existing method groups `refresh_tokens` rows by `family_id`; every existing method (`create_refresh_token`, `consume_refresh_token`, `get_refresh_token_by_hash`) operates on a single row.
- `get_family_created_at_for_user(user_id)` *(new method, or folded into the above as a second column via a window function)* — the `MIN(issued_at) GROUP BY family_id` query (query (2)). Touched for the same reason as above; `implementation-planner` decides whether this is a separate query or a single query using `MIN(issued_at) OVER (PARTITION BY family_id)`.
- `get_refresh_token_by_hash(token_hash)` *(existing method, from US-2.2)* — reused, not changed, to resolve the caller's `refresh_token` cookie value to its `family_id` for the "current session" mechanism (FR-1/FR-6). Touched only as a call site, no signature change.
- `revoke_refresh_token_family(family_id)` *(existing method, from US-2.2)* — reused as-is for FR-2's revoke and FR-7's eviction. No signature change; FR-7 calls it with the oldest family's `family_id` instead of a caller-specified one.
- `lock_families_for_user(user_id)` *(new method)* — `SELECT ... FOR UPDATE` scoped to the user's `refresh_tokens` rows, ahead of FR-7's count-and-evict check. Touched because no existing method acquires a row lock; this is new locking behavior this story introduces (per the spec-review resolution).
- `get_oldest_family_for_user(user_id)` *(new method)* — the `ORDER BY created_at ASC LIMIT 1` variant of query (2), used only by FR-7. Could be the same method as `get_family_created_at_for_user` with a different ordering/limit — an `implementation-planner` decision.
- `create_auth_audit_log_entry(...)` *(existing method, signature change)* — add a `target_family: uuid.UUID | None` parameter. Touched because FR-2/FR-7 need to pass it alongside the existing arguments; every other existing call site (login, logout, MFA) passes `target_family=None` after this change.

### `service.py` — `app/modules/users/service.py`

- `list_sessions(user, refresh_cookie)` *(new method)* — implements FR-1: calls the two new repository methods, resolves `is_current` via the cookie lookup, calls the geo-IP and device-label helpers (below) per entry, assembles `SessionListResponse`.
- `revoke_session(user, family_id, refresh_cookie)` *(new method)* — implements FR-2/FR-3/FR-4/FR-6: resolves ownership and the current-session cookie match, raises `SessionNotFoundError` (404) or `CurrentSessionError` (409) as appropriate, otherwise revokes via the existing `revoke_refresh_token_family` and writes the audit entry.
- `create_refresh_token_family(...)` *(existing method, US-2.1's login path — exact name TBD by `implementation-planner`)* — extended for FR-7: before inserting the new family's first row, acquires the row lock (`lock_families_for_user`), counts live families, and if the count would exceed 20, evicts the oldest via `revoke_refresh_token_family` plus the `session_evicted` audit write. This is a change to the **login** flow, not a new session-management method — flagged explicitly since it's easy to miss that FR-7 lives here, not in a new `sessions`-prefixed method.

### `router.py` — `app/modules/users/router.py`

- `GET /auth/sessions` *(new route)* — reads the optional `refresh_token` cookie (`Cookie()`, mirroring `/auth/refresh`'s existing parameter), calls `service.list_sessions(...)`, returns `200` with `SessionListResponse`.
- `DELETE /auth/sessions/{family_id}` *(new route)* — reads the same optional cookie, calls `service.revoke_session(...)`, returns `204`.

### `dependencies.py` — `app/modules/users/dependencies.py`

- **No change.** Both routes use the existing `CurrentUserDep`/`get_current_user` — no auth leniency or scoping variant is needed (unlike `/logout`'s `allow_revoked` or MFA's `allow_enrollment_scoped`), per `US-2.6-api-design.md`.

### `exceptions.py` — `app/modules/users/exceptions.py`

- `SessionNotFoundError` *(new)* — `type_slug="not-found"`, `status=404`. Touched because FR-3 needs a `404` distinct from every other module's not-found usage but reusing the shared slug per the story's own Error Envelope section.
- `CurrentSessionError` *(new)* — `type_slug="current-session"`, `status=409`. Touched because FR-6 introduces this slug (disclosed scope addition, OD-1).

### `config.py` — `app/core/config.py`

- New settings: `max_live_sessions_per_user` (FR-7's 20-family cap, named rather than a bare literal per this project's config-over-literal convention), `geoip_license_key`, `geoip_database_path`. Touched because FR-7's cap and OD-4's GeoLite2 lookup both need configurable values, and none of the three exists today.
- `.env.example` — gains the two new `geoip_*` settings. Touched per this project's established convention (every prior story with new settings updates this file 1:1, e.g. US-2.5).

### New non-DB helper module

- `app/core/geoip.py` *(new)* — wraps the bundled local MaxMind GeoLite2-City database lookup (OD-4). Touched because no geo-IP capability exists anywhere in this codebase today; placed in `app/core/` per this project's established precedent for a cross-cutting primitive with no module ownership (mirrors `app/core/crypto.py`'s placement for US-2.5's AES-GCM helper).
- `app/core/device.py` *(new, or folded into `geoip.py` as a single `session_metadata.py`)* — wraps the `user-agents` library call and the `"{browser} on {OS}"` formatting/fallback (OD-3). Same placement rationale as above; `implementation-planner` decides one file vs. two.

## Cross-module ripple

**None.** Both endpoints and the login-path eviction change (FR-7) stay entirely within `app/modules/users/`. Neither `roles`, `account`, nor `email_verification` is called by any new code this story introduces — unlike US-2.5, which called into `roles.service` for scope resolution.

## Migration/schema impact

**Yes, a migration is required.** Two additive, nullable/index-only changes — no existing row's data is affected, no existing `INSERT` needs to change to satisfy a new `NOT NULL` constraint:

- `ALTER TABLE auth_audit_log ADD COLUMN target_family UUID NULL`
- `CREATE INDEX ix_refresh_tokens_user_id_family_id_issued_at ON refresh_tokens (user_id, family_id, issued_at)`

No existing repository query is affected: `create_refresh_token` (existing) doesn't set `target_family` (that column lives on a different table entirely), and `create_auth_audit_log_entry`'s existing call sites (login, logout, MFA flows) need one new keyword argument (`target_family=None`) to keep compiling once the method signature changes, but no *behavior* of those existing rows changes.

## Test-surface impact

### New test files

- `tests/unit/modules/users/test_users_service_sessions.py` *(or added to the existing `test_users_service.py`)* — unit tests for `list_sessions()`/`revoke_session()`'s cookie-matching, ownership, idempotency, and eviction-trigger logic, plus `app/core/geoip.py`/`app/core/device.py`'s fallback behavior (missing/unparseable input).
- Integration coverage for `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{family_id}` — added to the existing `tests/integration/modules/users/test_users_router.py` (matches this project's established pattern of appending new-endpoint coverage to the module's one router-test file rather than creating a new one per story).
- Integration coverage for FR-7's eviction — a login-flow test asserting that a 21st concurrent family triggers eviction of the oldest, added to the existing login test coverage (`test_users_router.py` or wherever US-2.1's login integration tests live) rather than a new sessions-specific file, since the trigger is the login endpoint.
- A concurrency test for the row-locking spec-review resolution (two simultaneous logins racing past the cap) — new, no existing precedent test file to extend; likely needs the same two-connections-in-one-test technique used for US-3.2's FR-7 concurrency fix, if that test exists to model from.

### Existing test files that change

- `tests/unit/modules/users/test_users_service.py` — any existing test that calls `create_auth_audit_log_entry` or asserts on its call arguments needs updating for the new `target_family` parameter (signature change, not behavior change, for every pre-existing call site's assertions).
- Existing login-flow unit/integration tests — any test asserting on the exact set of `RefreshToken` rows created by a login needs awareness that a 21st family now triggers a side-effect (eviction) it may not have anticipated, though this only matters for tests that already push a user past 20 concurrent logins (unlikely in existing fixtures, but worth a check).

### Not affected

- `tests/unit/modules/roles/*`, `tests/integration/modules/roles/*` — no cross-module ripple into `roles`, per above.
- `tests/unit/core/test_crypto.py`, `test_security.py` — unrelated primitives; the new `app/core/geoip.py`/`device.py` get their own new test files, not additions to these.
- Migration test cycle (upgrade/downgrade/upgrade) — new test coverage is required by `migration-manager`'s own workflow, not a pre-existing file to modify.
