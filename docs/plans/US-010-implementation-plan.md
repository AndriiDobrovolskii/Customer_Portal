# Implementation Plan: Active Session Management (US-2.6 / spec US-010)

**Spec:** `docs/specifications/US-010-active-session-management-spec.md`
**Impact analysis:** `docs/impact-analysis/US-010-impact-analysis.md`
**Written:** 2026-09-02

## Goal

Add `GET /v1/auth/sessions` and `DELETE /v1/auth/sessions/{family_id}` to the existing `users` module, per FR-1–FR-6, plus a login-path change for FR-7's cap eviction, with no new module and no cross-module coupling.

## Architectural Changes

1. **"Session" is a derived view over `refresh_tokens`, not a new entity.** Per `db-design.md`, no `refresh_token_families` table is introduced. `repository.py` gains two read queries (current-state-per-family via `DISTINCT ON`, and `MIN(issued_at)` per family for `created_at`/oldest-family ordering) plus the row-lock query for FR-7. This is the single largest architectural decision in this story — everything else follows from treating a family as a query result, not a row.

2. **"Current session" is resolved from the `refresh_token` cookie, not the JWT.** Per the spec-review resolution: both new routes accept the same optional `refresh_token` cookie `/v1/auth/refresh`/`/v1/auth/logout` already read (`Cookie()`), hash it, and look up its `family_id` via the existing `get_refresh_token_by_hash` repository method (US-2.2). No JWT claim is added. Absence of the cookie degrades gracefully (no `is_current: true` anywhere, FR-6's `409` never triggers) rather than erroring.

3. **FR-7's cap eviction lives in the login flow, not a new endpoint.** The existing family-creation call site in `service.py`'s login path (US-2.1) gains a pre-insert check: lock the user's `refresh_tokens` rows (`SELECT...FOR UPDATE`), count live families, and if inserting the new one would exceed 20, revoke the oldest via the existing `revoke_refresh_token_family` (US-2.2) plus a new `session_evicted` audit write. This makes FR-7 a login-service change, easy to mis-scope as sessions-only work if not called out explicitly (impact-analyzer already flagged this).

4. **Two new geo-IP/device-label primitives in `app/core/`, not `users/`.** Neither has any per-module state or dependency on `users`' models — mirrors `app/core/crypto.py`'s placement (US-2.5) for a cross-cutting primitive with a single current caller. `app/core/geoip.py` wraps a local MaxMind GeoLite2-City lookup; `app/core/device.py` wraps `user-agents` parsing. Both return `None`/a fallback string rather than raising, so a lookup failure never fails the request (per FR-1 and OD-3/OD-4).

5. **Two new `ProblemError` subclasses, one new column.** `SessionNotFoundError` (404, reuses the shared `not-found` slug) and `CurrentSessionError` (409, new `current-session` slug) in `users/exceptions.py`. `AuthAuditLog.target_family` (new nullable UUID column) — `reason`/`scope` are the wrong size/semantics per `db-design.md`.

6. **No cross-module calls.** Confirmed by impact-analyzer: unlike US-2.5, no call into `roles.service` or any other module's service.

## Files To Create

- `app/core/geoip.py` (new file, per Architectural Change #4)
- `app/core/device.py` (new file, per Architectural Change #4)

No GeoLite2 database file is created in this repository — it's fetched at build/deploy time, per the Risks section below.

## Files To Modify

Per `impact-analysis.md`'s survey — reason given only where it adds detail beyond that survey:

- `app/modules/users/models.py` — add `AuthAuditLog.target_family`; add the new composite index on `RefreshToken`.
- `app/modules/users/schemas.py` — add `SessionEntry`, `SessionListResponse`.
- `app/modules/users/repository.py` — add `list_live_families_for_user`, the family-`created_at`/oldest-family query, `lock_families_for_user`; reuse existing `get_refresh_token_by_hash`, `revoke_refresh_token_family`; extend `create_auth_audit_log_entry`'s signature with `target_family`.
- `app/modules/users/service.py` — add `list_sessions()`, `revoke_session()`; extend the existing login-path family-creation call site for FR-7 (Architectural Change #3).
- `app/modules/users/exceptions.py` — add `SessionNotFoundError`, `CurrentSessionError`.
- `app/modules/users/router.py` — add the two routes, both reading the optional `refresh_token` cookie.
- `app/modules/users/dependencies.py` — **no change** (confirmed by impact-analyzer: both routes use the existing `CurrentUserDep`).
- `app/core/config.py` — three new settings: `max_live_sessions_per_user` (the 20-family cap, currently a bare literal in the spec — should be named, not hardcoded, per this project's existing config-over-literal convention), `geoip_license_key`, `geoip_database_path`.
- `.env.example` — gains `geoip_license_key` and `geoip_database_path` (plan-review finding, fixed same-day: this file was previously only mentioned in Risks, not itemized here).
- `tests/unit/modules/users/test_users_service.py` (or a new `test_users_service_sessions.py`), `tests/unit/core/test_geoip.py`, `tests/unit/core/test_device.py`, `tests/integration/modules/users/test_users_router.py` — extended/new (see Testing Strategy).
- New migration under `migrations/versions/` (additive only — see Risks).

**`pyproject.toml` needs a change — approved by the user 2026-09-02.** Two new dependencies: `user-agents` and `geoip2` (MaxMind's own official reader library, chosen over the lower-level `maxminddb` per the user's explicit preference). Both to be pinned to their latest stable versions at the time `data-layer-builder` runs `uv add`.

## Risks

- **Migration risk: low for the column, needs a guard for the index (plan-review finding, fixed same-day).** The additive nullable `auth_audit_log.target_family` column is low-risk — no `ALTER` narrows an existing column, no backfill needed. The new `ix_refresh_tokens_user_id_family_id_issued_at` index is a different hazard class: `refresh_tokens` is written on every login and every refresh rotation across the whole application, so a plain `CREATE INDEX` would take a lock blocking those writes for the build duration. `migration-manager` must guard this with `CREATE INDEX CONCURRENTLY` (`op.get_bind()` autocommit-block check, `if_not_exists=True`), per `AGENTS.md` §4's explicit hazard list for changes the Rewriter cannot reach. Both changes must still be proven `upgrade → downgrade → upgrade`.
- **Concurrency risk: addressed by design, but the locking scope needs care.** The `SELECT...FOR UPDATE` in Architectural Change #3 must lock the *user's* rows, not a global table lock — over-broad locking here would serialize logins across unrelated users and blow the login endpoint's own latency budget (a regression this story must not cause). `implementation-planner`/`service-and-router-builder` should scope the lock to `WHERE user_id = :user_id`, matching how `AGENTS.md`'s row-locking guidance is applied elsewhere (US-3.2's FR-7 fix locked the specific user's role rows, not the whole `user_roles` table).
- **GeoLite2 licensing/distribution — resolved by the user 2026-09-02.** The `.mmdb` file is fetched at build/deploy time, not committed to git — a new `geoip_license_key` setting (`app/core/config.py`, read from environment, matching this project's "no hardcoded environment-specific values" rule) drives the fetch step. `implementation-planner` needs to place the fetch in the deploy pipeline (or a documented manual/CI step) and `app/core/geoip.py` needs a defined behavior for local dev / CI when the file is absent — recommend the same graceful-`None` fallback FR-1 already specifies for an unresolvable IP, so the app runs without the database present, it just never returns a location. `.env.example` gains `geoip_license_key` and a `geoip_database_path` setting.
- **Performance risk on `GET /v1/auth/sessions` (NFR: p95 ≤ 200 ms).** Per-entry geo-IP and UA-parsing calls run synchronously today (no caching layer proposed) — with the 20-family cap, that's at most 20 in-process lookups per request. Both libraries are expected to be sub-millisecond in-process (no I/O), so this should comfortably clear the budget, but `implementation-verifier`/`gate-enforcer` should confirm with a real timing assertion rather than assuming.
- **`created_at` semantics ambiguity resolved here, worth restating at implementation time.** A family's `created_at` (FR-1) is `MIN(issued_at)` across its rotation chain, not the current row's own `issued_at` — an implementer reading only `RefreshToken.issued_at`'s docstring/column name could easily default to the wrong (current-row) value, since every other place in this codebase that reads `issued_at` today means "this specific row's issue time," not "the family's origin time." Worth an explicit code comment at the query site.
- **`create_auth_audit_log_entry` signature ripple.** Adding `target_family` breaks compilation of every existing call site until updated (login, logout, MFA) — already anticipated in Files To Modify, same class of gap US-2.4's `EmailSender` Protocol ripple and US-2.5's identical audit-signature change both already hit in this project's history.

## Validation Strategy

- `pre-commit run --all-files` clean (7/7 hooks), matching every prior Epic 2 story.
- `mypy --strict` clean across all modified/new files.
- `lint-imports` clean — `app/core/geoip.py`/`device.py` are new leaf modules with no import into `app/modules/`; `users/service.py` importing them is a downward `core`-import, the same shape every other `app/core/*` helper this project already has.
- Migration cycle (`upgrade → downgrade → upgrade`) proven against a real Postgres instance before IMPLEMENTATION's gate, per `AGENTS.md` §4.
- A real timing assertion for the `GET /v1/auth/sessions` p95 ≤ 200 ms budget (NFR), not just a functional pass, given the Performance risk above.

## Testing Strategy

- **Unit (`tests/unit/modules/users/test_users_service.py` or a new file, plus `tests/unit/core/test_geoip.py`/`test_device.py`):** hand-written fakes, no `MagicMock`, per `AGENTS.md` §5 — extend `FakeUserRepository` with family-listing/locking/eviction seeding methods; cover `list_sessions()`/`revoke_session()`'s cookie-matching, ownership, idempotency (FR-4), self-revoke rejection (FR-6), and eviction-trigger logic (FR-7) in isolation from the real DB. `geoip.py`/`device.py` get their own unit tests for the fallback paths (missing/unparseable input, private IP, no DB entry) independent of the real bundled data file where feasible (a small test fixture DB, or a mock reader — implementation-planner's call).
- **Integration (`tests/integration/modules/users/test_users_router.py`):** real Postgres + Valkey via testcontainers, no `unittest.mock`, per `AGENTS.md` §5 — both endpoints' full request/response cycle (FR-1 through FR-6), plus a login-flow integration test proving FR-7's eviction fires on the 21st family and writes `session_evicted`. A genuine concurrent-login test (`asyncio.gather`, two logins racing past the cap) proving the row lock holds — mirrors US-3.2's own FR-7 concurrency proof technique.
- Coverage floor 85% overall, 90%+ for `service.py`/`router.py`, per `AGENTS.md` §6/§7.7 — not a target, a floor.
