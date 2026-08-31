# Impact Analysis: US-004 Deactivate Account

**Inputs:** `docs/specifications/US-004-deactivate-account-spec.md` (Pass), `docs/designs/api/US-004-*`, `docs/designs/database/US-004-*`.
**Scope decision carried in:** per user decision 2026-08-30, US-004 introduces the Valkey `revoke_before:{user_id}` mechanism now (not the `user_sessions.revoked_at` alternative) — this analysis reflects that.

## 1. Affected files, by layer

### New module: `app/modules/account/`

No existing module fits `POST /v1/account/deactivate` (not registration/login, not self-service profile fields) — per `US-004-db-design.md` §4's recommendation, confirmed here as a new module.

| File | Layer | Reason |
|---|---|---|
| `app/modules/account/models.py` | models | New `AccountLifecycleAuditLog` ORM class (`US-004-entity-model.md`). |
| `app/modules/account/schemas.py` | schemas | `DeactivateAccountRequest`/`DeactivateAccountResponse` per `US-004-openapi.yaml`. |
| `app/modules/account/repository.py` | repository | Conditional `UPDATE users SET status='deactivated', deactivated_at=now() WHERE id=:id AND status='active'` (Clarification #2 atomicity); insert into `account_lifecycle_audit_log`. |
| `app/modules/account/cache.py` | cache gateway | New: writes `revoke_before:{user_id}` to Valkey with a TTL (per `AGENTS.md` "every cache write sets a TTL" — TTL choice is a `planner`/implementation decision, e.g. matching the longest-lived token's lifetime). |
| `app/modules/account/service.py` | service | Orchestrates: verify password (reuse `app.core.security.verify_password`) → repository conditional update → cache write → audit log insert → commit ordering per `AGENTS.md` §3 ("cache writes happen after commit"). |
| `app/modules/account/router.py` | router | `POST /v1/account/deactivate`, using `CurrentUserDep`. |
| `app/modules/account/dependencies.py` | dependencies | `AccountServiceDep`, wiring repository + cache gateway. |
| `app/modules/account/exceptions.py` | exceptions | `AlreadyDeactivatedError` (409), reuse existing `InvalidCredentialsError`-equivalent for 401 or reuse `app.modules.users.exceptions.InvalidCredentialsError` — **decision needed at PLANNING**: reuse the users-module exception (creates a cross-module import into a sibling module's exceptions, unusual) or define a local equivalent problem type (duplicates the 401 shape). Flagged, not decided here. |

### Existing files modified

| File | Layer | Reason |
|---|---|---|
| `app/modules/users/models.py` | models | Add `User.deactivated_at` column (`US-004-entity-model.md`). No `status` column change (already free-text). |
| `app/modules/users/schemas.py` | schemas | Extend `UserStatus` enum with `ACTIVE`/`DEACTIVATED` values (currently only `PENDING_VERIFICATION` exists) — needed so the service layer doesn't compare against a magic string. |
| `app/modules/users/service.py` | service | `get_authenticated_user` (line 180-192) must check the token's issued-at against `revoke_before:{user_id}` before accepting a token — this is FR-4's shared-middleware requirement and it lives in the one place all authenticated requests already funnel through. Requires injecting a cache-read collaborator into `UserService`, which today only takes a repository/issuer/email_sender. |
| `app/modules/users/dependencies.py` | dependencies | `get_user_service` (line 15-21) must be given the new cache-gateway dependency to pass into `UserService.__init__`. |
| `app/core/config.py` | config | New setting(s) for the Valkey connection (e.g. `valkey_url`) — none exist today (confirmed via grep — zero Valkey references anywhere in `app/`). |
| `app/main.py` | app wiring | `lifespan` (line 20-27) must create the Valkey connection pool as an app-scoped singleton alongside the existing DB engine, per `AGENTS.md` §3 ("the Valkey connection pool are the only app-scoped singletons, created in lifespan"). Currently absent entirely. |
| `app/db/dependencies.py` (or a new `app/core/cache_client.py`) | dependencies | A `get_valkey_client`-style request-scoped dependency mirroring `get_db_session`'s pattern (`app/db/dependencies.py:6-9`) — doesn't exist yet. |
| `pyproject.toml` | infra | New runtime dependency: an async Valkey/Redis-protocol client (none is currently listed — `dependencies` array has no redis/valkey package). Also: `dev` extra's `testcontainers[postgres]` needs a Valkey-capable extra/container added, since `AGENTS.md` requires integration tests to run against real Valkey, and no such fixture exists yet in `tests/conftest.py`. |
| `tests/conftest.py` | test infra | New fixture(s) for a real Valkey instance (testcontainers) and/or a Valkey client override, alongside the existing DB fixtures. |

### Addendum (post-planning, per `docs/reviews/plans/US-004-plan-review.md`)

- `app/core/cache_keys.py` *(new)* — shared `revoke_before:{user_id}` prefix helper, stdlib/no business logic. Introduced during `planner`'s Architectural Change 4 to avoid a `users → account` cross-module import; not identified during the original survey above, added here for traceability.

### Addendum 2 (during IMPLEMENTATION — two items missed by both the original survey and the plan)

- `app/core/revocation_cache.py` *(new)* — the `RevocationCache` gateway class itself, not just the key-prefix helper. Originally planned as `app/modules/account/cache.py`; moving the prefix helper to `core` (Addendum above) didn't by itself avoid a `users → account` import, since `users/dependencies.py` still needed to construct the gateway — the class had to move too. `account/cache.py` was never created (deleted immediately after being written, once this was caught).
- `app/api/v1/router.py` *(modified, missed entirely)* — the new `account_router` must be registered here (`router.include_router(...)`) or `POST /v1/account/deactivate` 404s. Neither the original impact analysis nor the plan's Files To Modify listed this file, which is why `plan-reviewer`'s coverage table didn't catch it (it was absent from both sides of that comparison). Caught during T8's implementation instead.

## 2. Cross-module ripple

- **New:** `app.modules.account.service.AccountService` → no outbound service→service call is required by this story's own FRs (FR-10's admin path is out of scope; it belongs to US-011's admin service, which will itself need to call *this* module's revocation logic — see below).
- **New, inbound (future):** `US-011`'s admin-deactivation service (`US-3.1.4`, not yet built) will need to call into whatever this story exposes for "revoke + audit" so FR-10's invariant holds without duplicating the conditional-update/cache-write logic. Recommend `AccountService` expose a service-level method (not just the router) that both the self-service router and a future admin caller can inject, mirroring the existing precedent of `UserService.revoke_other_sessions` being a cross-module collaborator for the profile module (`app/modules/users/service.py:194-204`). This is a `planner`-level API-shape decision, not a code change here.
- **Existing, modified:** `app.modules.users.service.UserService.get_authenticated_user` gains a dependency on the new cache gateway — this is the one existing cross-cutting touch point every other authenticated module's router indirectly depends on via `CurrentUserDep`. No module's *code* other than `users/dependencies.py` and `users/service.py` changes, but the behavior (token rejection after any revocation) becomes live for every existing authenticated endpoint (`profile`) the moment this ships — flagged as a behavior-impact even though no file in `profile/` changes.

## 3. Migration/schema impact

**Yes, a migration is required.**

- `ALTER TABLE users ADD COLUMN deactivated_at TIMESTAMPTZ NULL` — nullable, no backfill needed, no existing-row impact (matches `AGENTS.md` §4's simple-nullable-add case, no `CONCURRENTLY`/batching concern).
- `CREATE TABLE account_lifecycle_audit_log (...)` — new table, no existing-row impact.
- `CREATE INDEX ON account_lifecycle_audit_log (user_id)` — new table, safe to create inline (not `CONCURRENTLY`-worthy on an empty table, per `migration-manager`'s own guidance that `CONCURRENTLY` is for existing large tables).
- No existing repository query is affected by the new nullable column (no `SELECT *` relying on column count observed in `app/modules/users/repository.py` — confirm at implementation time, not assumed here).

## 4. Test-surface impact

### New test files
- `tests/unit/modules/account/test_account_service.py` — password verification, conditional-update success/already-deactivated paths, cache write, audit log write (fakes per `AGENTS.md` §"Unit").
- `tests/integration/modules/account/test_account_router.py` — `POST /v1/account/deactivate` 200/401/409 against real PG + real Valkey.
- `tests/unit/modules/account/__init__.py`, `tests/integration/modules/account/__init__.py` — new package inits, mechanical.

### Existing test files that must change
- `tests/unit/modules/users/test_users_service.py` — `get_authenticated_user` gains a new branch (revoke_before check); existing test fakes for `UserRepositoryProtocol` won't need to change, but a new fake/protocol for the cache-read collaborator must be added and existing happy-path tests must supply it.
- `tests/integration/modules/users/test_users_router.py` — needs the new Valkey testcontainer fixture wired in if any existing test exercises an authenticated route end-to-end (confirm which do at implementation time).
- `tests/conftest.py` — as noted in §1, needs the new Valkey fixture; this is shared infra so every existing integration test file that uses `AsyncClient`/`CurrentUserDep`-gated routes is indirectly affected by fixture setup, even though their test bodies don't change.

**Not affected:** `tests/unit/modules/profile/*`, `tests/unit/modules/email_verification/*` — no behavior in those modules changes; only the shared auth dependency they rely on (`CurrentUserDep`) changes underneath them, and that's covered by the `users` module's own tests, not theirs.
