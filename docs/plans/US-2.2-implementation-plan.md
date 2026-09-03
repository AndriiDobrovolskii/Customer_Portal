# Implementation Plan: US-2.2 Logout

**Spec:** `docs/specifications/US-2.2-spec.md` (Pass with Issues, accepted 2026-08-31)
**API:** `docs/designs/api/US-2.2-openapi.yaml`, `US-2.2-api-design.md`
**DB:** `docs/designs/database/US-2.2-db-design.md`, `US-2.2-entity-model.md`
**Impact analysis:** `docs/impact-analysis/US-2.2-impact-analysis.md`

## Goal

Add `POST /v1/auth/logout` and `POST /v1/auth/logout-all` to the existing `app/modules/users/` module: single-device revocation via the existing `user_sessions.revoked_at` mechanism (FR-1, resolved OD-1), whole-family refresh-token revocation via two new `refresh_tokens` capabilities (FR-1, resolved OD-3), account-wide revocation via the existing `RevocationCache`/`revoke_before` mechanism (FR-2, unchanged from US-1.4/US-2.1), a logout-only idempotency carve-out for an already-revoked jti (FR-4, resolved OD-2), and a `scope`-labeled `auth_audit_log` entry per call (FR-1/FR-2, resolved OD-5).

## Architectural Changes

- **No new error class, no new Valkey key, no new module.** Unlike US-2.1, this story adds no `cache.py` gateway and no cross-module call — everything stays inside `app/modules/users/` and reuses infrastructure US-2.1 already built (`user_sessions.revoked_at`, `RevocationCache`, `UnauthenticatedError`).
- **`get_authenticated_user` gains an `allow_revoked: bool = False` parameter** (resolved OD-2 / `US-2.2-api-design.md` Open Question #1). When `True`, a jti whose `user_sessions.revoked_at` is already set still resolves to an `AuthenticatedUser` instead of returning `None`; a jti with **no matching session row at all** still returns `None` regardless of `allow_revoked` (Open Question #2's recommendation — "revoked" and "never existed" are different failure modes, and only the former gets leniency). Every existing call site (the shared `get_current_user` dependency used by every route except logout) keeps the default `False`, so no other endpoint's behavior changes.
- **New dependency `get_current_user_allow_revoked`** (`app/modules/users/dependencies.py`) — a near-duplicate of `get_current_user` that passes `allow_revoked=True`, used only by the `POST /v1/auth/logout` router function. `POST /v1/auth/logout-all` continues to use the existing `CurrentUserDep`/`get_current_user` (standard, no leniency — FR-5).
- **`create_auth_audit_log_entry` gains a `scope: str | None` parameter** (resolved OD-5), threaded through from `service.py`. Every existing US-2.1 login-flow call site passes `scope=None` explicitly (not a default that silently applies) so the signature change is visible at every call site during review, matching this project's existing style of explicit keyword arguments over relying on defaults for state that varies by branch.
- **`refresh_tokens` gains two repository-level query shapes it never needed before**: a lookup by `token_hash` (point lookup, existing unique index) and a bulk `UPDATE ... WHERE family_id = :family_id` (new index, per DB design). Both are plain `sqlalchemy` statements in `UserRepository`, mirroring the existing `revoke_sessions_except` bulk-update style — no new abstraction is introduced.

## Files To Create

| File | Reason |
|---|---|
| `migrations/versions/<rev>_add_logout_revocation_columns.py` | New Alembic revision for `refresh_tokens.revoked_at`, `ix_refresh_tokens_family_id`, `auth_audit_log.scope` — generated via `migration-manager`, not hand-written here. |

No new module, no new `cache.py`, no new test file beyond extending existing ones (per impact analysis) — this story is additive to an already-scaffolded module.

## Files To Modify

Per `docs/impact-analysis/US-2.2-impact-analysis.md`'s survey (not re-derived here):

| File | Change |
|---|---|
| `app/modules/users/models.py` | `RefreshToken` gains `revoked_at` and an index on `family_id`; `AuthAuditLog` gains `scope`. |
| `app/modules/users/repository.py` | New methods: `revoke_session(jti)`, `get_refresh_token_by_hash(token_hash)`, `revoke_refresh_token_family(family_id)`. `create_auth_audit_log_entry` gains `scope` parameter. |
| `app/modules/users/service.py` | New methods `logout(access_token, refresh_cookie)` and `logout_all(user_id)`. `get_authenticated_user` gains `allow_revoked` parameter. |
| `app/modules/users/router.py` | New routes `POST /auth/logout` (uses `get_current_user_allow_revoked`), `POST /auth/logout-all` (uses existing `CurrentUserDep`). Both return `204`, no response body. `/logout` conditionally sets a clearing `Set-Cookie` only when a refresh cookie was present on the request. |
| `app/modules/users/dependencies.py` | New `get_current_user_allow_revoked` dependency, scoped only to the logout route. |
| `tests/unit/modules/users/test_users_service.py` | Extend for `logout`/`logout_all`'s branches; update any existing `create_auth_audit_log_entry` assertion for the new `scope` argument. |
| `tests/integration/modules/users/test_users_router.py` | Extend for LO-AC1–LO-AC5. |

`app/modules/users/schemas.py` and `app/modules/users/exceptions.py` are **not modified** — no request/response body schema is needed (both endpoints are `204` with no body), and `UnauthenticatedError` (existing) covers both `401` cases with no new `type` slug.

## Protected files — flagged per AGENTS.md §7.9, none touched

`pyproject.toml`, `migrations/env.py`, `.pre-commit-config.yaml` are not modified by this plan. No new third-party dependency is needed.

## Risks

- **The `allow_revoked` carve-out must not leak into any other route.** This is the single highest-risk element of this story: if `CurrentUserDep` itself defaulted to `allow_revoked=True`, or if `get_current_user_allow_revoked` were reused by any route besides `/logout`, every other endpoint's revocation guarantee (FR-5, and by extension US-1.4's deactivation invariant and US-2.1's `revoke_before` check) would silently weaken. Mitigate: keep `get_current_user_allow_revoked` a separate, single-purpose dependency function (not a query-param-controlled flag on the shared one), so an accidental reuse is a visible, reviewable import rather than a call-site typo (e.g. a stray `allow_revoked=True` at a call site nobody reviews closely). `implementation-verifier`/`security-reviewer` should specifically confirm no other router function imports it.
- **`/logout-all` must NOT get the same leniency as `/logout`.** FR-5/resolved OD-2 draw this line explicitly: only `/logout` tolerates a revoked jti. `/logout-all` uses the existing `CurrentUserDep`, unchanged — a dedicated integration test should assert `/logout-all` still `401`s on an already-revoked jti, distinct from `/logout`'s `204`.
- **Refresh-token lookup-miss must not become an enumeration or state-confirmation oracle.** Per the spec-review resolution, a stale/tampered/deleted `token_hash` must produce a response byte-for-byte identical to the matched case — same `204`, same conditional cookie-clear-if-cookie-was-present logic (the cookie clears based on whether one was *sent*, not on whether it *matched*), same audit entry. Mitigate: the lookup-miss branch skips only the `revoke_refresh_token_family` call, nothing else in `logout()`'s control flow forks on match/no-match.
- **Migration is purely additive** — three nullable/index changes, no backfill, no `ALTER` on a populated `NOT NULL` column. The `AGENTS.md` §4 expand→migrate→contract concern doesn't apply; this is a single-step additive migration.
- **`create_auth_audit_log_entry` signature change touches US-2.1's already-shipped, already-tested login call sites.** Every existing call in the login flow needs an explicit `scope=None` argument added — a mechanical, compile-time-visible change (mypy/the function signature will fail any call site that isn't updated), not a behavior change to any existing login test's expected outcome.
- **Idempotent re-revocation of `user_sessions.revoked_at` (FR-4) relies on the column's existing semantics, not new logic.** Setting `revoked_at = now()` on a row that already has `revoked_at` set is a harmless overwrite — no repository-level "only if NULL" guard is needed, since nothing reads the column's exact timestamp value, only whether it `IS NOT NULL`. Flagged so `service-and-router-builder` doesn't add unneeded conditional-update complexity here.

## Validation Strategy

- `pre-commit run --all-files` — Ruff format/lint, mypy strict on `app tests`, secret scan, no-mock-in-integration grep — must be green (`gate-enforcer`'s job, not this plan's).
- `lint-imports` — no new file layer is introduced (no new `cache.py`/module), so the existing `users` module's import contract is unaffected; the new dependency function and repository methods must still respect the existing layer boundaries (`dependencies.py` may import `service.py`, not the reverse).
- Migration cycle: `alembic upgrade head` → `downgrade` → `upgrade` proven clean (`migration-manager`'s job) — a pure additive migration, but the read-before-trust rule applies regardless.
- No `.env.example` change expected — this story adds no new setting (unlike US-2.1's throttle/TTL settings); flag to `gate-enforcer` if the plan is wrong about this once implementation starts.

## Testing Strategy

Per `AGENTS.md` §5's unit/integration split:

- **Unit** (`tests/unit/modules/users/test_users_service.py`, hand-written fakes for `UserRepositoryProtocol` — never `MagicMock`): `logout()` — revokes the session (FR-1), revokes the refresh family when the cookie matches a row (FR-1), skips family revocation silently on a lookup miss (spec-review resolution), still returns success on a repeat call against an already-revoked session (FR-4), writes `scope=session`. `logout_all()` — calls `RevocationCache.set_revoke_before`, writes `scope=all_sessions` (FR-2). `get_authenticated_user(allow_revoked=True)` — resolves a revoked-but-existing jti; still returns `None` for a jti with no session row at all (Open Question #2's resolution) and for a jti belonging to a different `user_id` (existing guard, unaffected).
- **Integration** (`tests/integration/modules/users/test_users_router.py`, real Postgres + Valkey, `AsyncClient`/`ASGITransport`, no mocking): full request/response cycle for LO-AC1–LO-AC5 — `204` + persisted `user_sessions.revoked_at` + persisted `refresh_tokens.revoked_at` across the whole family + cleared `Set-Cookie` (LO-AC1); `204` + `revoke_before` set + a second endpoint call with a pre-existing token now `401`s (LO-AC2); no token → `401` (LO-AC3); repeat `/logout` with the same access token → `204` again, not `401` (LO-AC4); any *other* authenticated endpoint called with the pre-logout access token → `401` (LO-AC5). A dedicated test asserts `/logout-all` does **not** share `/logout`'s leniency (revoked jti → `401` there). A dedicated test covers the refresh-cookie lookup-miss branch (garbage cookie value → still `204`, family-revocation step verifiably not invoked via no row changes).
- Coverage floor 85% overall, 90%+ for `service.py`/`router.py` per AGENTS.md §5 — this story's branch count is small (no throttling, no multi-state gating like login's FR-4), so the unit-test list above should reach full branch coverage without needing a parametrized sweep the way US-2.1's `authenticate_user` did.
