# Implementation Plan: Manage Roles (US-3.2 / spec US-3.2)

**Spec:** docs/specifications/US-3.2-spec.md
**API design:** docs/designs/api/US-3.2-openapi.yaml, US-3.2-api-design.md
**DB design:** docs/designs/database/US-3.2-db-design.md, US-3.2-entity-model.md
**Impact analysis:** docs/impact-analysis/US-3.2-impact-analysis.md (including its 2026-09-01 user-resolved items)

## Goal

Give the system a role/permission model for the first time: a fixed, seeded role catalogue; an endpoint to read it; an endpoint for an admin to replace a target user's role set with the guard rails FR-4–FR-7 require; and propagation of a role change to live sessions via `perm_epoch`, without forcing re-login. This is the foundational piece US-2.5 (MFA/TOTP) and US-3.1/US-3.3 are blocked on.

## Architectural Changes

1. **New module `app/modules/roles/`** — the first module owning role/permission persistence, following the standard `router → dependencies → service → repository → models/schemas` layering (`AGENTS.md` §3), consistent with every existing module.
2. **New cross-cutting cache primitive, `PermissionEpochCache`**, placed in `app/core/revocation_cache.py` alongside `RevocationCache` (same file, not a new one — the two are natural siblings: both are single-key-per-user Valkey primitives read by the shared auth path and written by different domain modules, and `revocation_cache.py`'s own docstring already states the "core, not module-owned" rationale that applies identically here). Its key: `perm_epoch:{user_id}`, added to `app/core/cache_keys.py` next to `revoke_before_key`.
3. **JWT payload gains a `scopes` claim.** `app/core/security.py`'s `AccessTokenClaims`, `encode_access_token()`, and `decode_access_token()` are extended to carry/decode `scopes: list[str]`. This is a breaking signature change to a function called at login and at refresh — every call site updates in the same task (see Files To Modify).
4. **The shared authenticated-request path gains a `perm_epoch` check**, alongside the existing `revoke_before` check in `app/modules/users/service.py` (confirmed at lines 487-496), returning `401 token-stale` (FR-2) when `session.issued_at <= perm_epoch`.
5. **Documented cross-module exception for FR-7's last-admin check** (impact-analysis resolution, user-approved 2026-09-01): `roles/repository.py`'s last-admin count query joins `user_roles` against `users.status` directly, inside the same transaction as the role-set update. This is a deliberate, narrow exception to "cross-module calls go service → service," justified by FR-7's explicit one-transaction atomicity requirement, and must be documented in the repository code itself (mirroring how `revocation_cache.py` documents its own placement exception) so a future reader doesn't mistake it for an accidental layering violation.

## Files To Create

| File | Purpose |
|---|---|
| `app/modules/roles/__init__.py` | New module. |
| `app/modules/roles/models.py` | `Role`, `Permission`, `RolePermission`, `UserRole` per `US-3.2-entity-model.md`. |
| `app/modules/roles/schemas.py` | `RoleRead`, `RoleCatalogueResponse`, `ReplaceUserRolesRequest`, `ReplaceUserRolesResponse`, `extra="forbid"` on the inbound request per `AGENTS.md` §4. |
| `app/modules/roles/repository.py` | `RoleRepository.list_all_with_permissions()` (FR-3, `selectinload(Role.permissions)`); `UserRoleRepository.list_by_user()`, `.replace_for_user()` (FR-1), `.count_active_admins_excluding()` (FR-7, the documented cross-module exception). |
| `app/modules/roles/service.py` | `RoleService.list_catalogue()` (FR-3); `RoleService.replace_user_roles()` orchestrating FR-1, FR-4 (unknown role → 422), FR-5 (self-target → 403), FR-6 (privilege escalation → 403), FR-7 (last-admin → 409), the `perm_epoch` write, and the `admin_audit_log` write. |
| `app/modules/roles/router.py` | `GET /v1/admin/roles`, `PUT /v1/admin/users/{id}/roles` per `US-3.2-openapi.yaml`; `response_model`/`status_code` declared on both per `AGENTS.md` §6.7. |
| `app/modules/roles/dependencies.py` | `RoleServiceDep`; scope-check dependencies for `users:read` (GET) and `roles:write` (PUT), reading the `scopes` claim off the decoded access token. |
| `app/modules/roles/exceptions.py` | `CannotTargetSelfError`, `PrivilegeEscalationError`, `LastAdminError`, `UnknownRoleError` — `ProblemError` subclasses per `AGENTS.md` §3 (services raise these, never `HTTPException`). |
| `migrations/versions/<rev>_add_roles_and_permissions.py` | New tables + seed `INSERT`s for `roles` (4 rows) and `permissions` (6 rows) and `role_permissions` (per the 2026-09-01 minimal-per-persona resolution: `customer`→none, `support_agent`→`tickets:read`+`tickets:write`, `auditor`→`audit:read`, `admin`→all six). |
| `tests/unit/modules/roles/test_roles_service.py` | Unit tests, hand-written fakes for `UserRoleRepository`/`RoleRepository`/`PermissionEpochCache`, no `MagicMock`. |
| `tests/integration/modules/roles/test_roles_router.py` | Integration tests against real PostgreSQL + Valkey, no `unittest.mock`. |

## Files To Modify

| File | Change |
|---|---|
| `app/core/cache_keys.py` | Add `perm_epoch_key(user_id: uuid.UUID) -> str`. |
| `app/core/revocation_cache.py` | Add `PermissionEpochCache` class (get/set `perm_epoch`), same shape as `RevocationCache`, same fail-closed discipline (no swallowed Valkey errors). |
| `app/core/security.py` | `AccessTokenClaims` gains `scopes: list[str]`; `encode_access_token()` gains a required `scopes` parameter; `decode_access_token()` decodes and returns it. |
| `app/modules/users/service.py` | (a) The token-validation path gains the `perm_epoch` check alongside the existing `revoke_before` check. (b) Every `encode_access_token()` call site (login, and the refresh-rotation call site) is updated to pass the caller's current `scopes`, sourced from a new `RoleService`/`UserRoleRepository` read (`User.roles` → `Role.permissions`, `selectinload`) — this is the new `users` → `roles` cross-module call impact-analysis flagged. |
| `app/core/config.py` | New setting for `perm_epoch`'s Valkey TTL, matching the existing one-setting-per-TTL-write convention (`refresh_token_ttl_seconds`, etc.). |
| `.env.example` | Add the corresponding entry, per `AGENTS.md` §4. |
| `app/api/v1/router.py` | Register the new `roles` router. |
| `tests/unit/modules/users/test_users_service.py` | Add `perm_epoch`-stale coverage mirroring the existing `revoke_before` test cases; update any test constructing tokens via `encode_access_token()` for the new `scopes` parameter. |
| `tests/integration/modules/users/test_users_router.py` | Update any test that decodes/asserts on JWT claims for the new `scopes` field. |
| `tests/conftest.py` | Add a fixture/fake extension to seed a test user's role assignment, needed to exercise both privileged and non-privileged authorization paths this story introduces. |

No file under `AGENTS.md` §7.9 protection (`migrations/env.py`, `pyproject.toml` contracts, `.pre-commit-config.yaml`) is touched by this plan — the OD-1 resolution moved the permission-completeness check to a standalone CI test (see Testing Strategy), not a migration hook.

## Risks

- **Migration seed correctness.** The `role_permissions` seed encodes a security-critical mapping (which role gets which scope) directly into the migration. A wrong seed value is a privilege bug that ships silently unless caught by the new CI completeness test (see Testing Strategy) or by integration tests exercising FR-6.
- **Cross-module transaction boundary (FR-7).** The documented exception (roles' repository reading `users.status` inside its own transaction) must not become a precedent silently copied elsewhere — the plan text and the repository code both need to state it's narrow and FR-7-specific.
- **`encode_access_token()` signature change blast radius.** Every existing caller (login, refresh) must be updated in the same change; a missed call site is a hard runtime failure (missing required argument), not a silent bug, so this is a build-time risk more than a correctness one — but the search for all call sites must be exhaustive.
- **Concurrency on FR-7.** Two simultaneous requests removing the `admin` role from the last two admins must not both succeed — requires row locking (`SELECT ... FOR UPDATE` or equivalent) inside the transaction; the Enforcement Matrix's own `[gate]` marker calls for a dedicated concurrency test.
- **Open spec/design gaps not resolved by this plan** (carried forward, not decided here — see `US-3.2-spec-review.md` and `US-3.2-api-design.md`): 404 for a non-existent target user, empty-`roles`-array semantics, duplicate-role handling, missing/stale `If-Match` response, check-precedence order among the four negative paths, and initial-ETag acquisition given `GET /v1/admin/users/{id}` (US-3.1) doesn't exist yet. `implementation-planner`/`plan-reviewer` should decide whether any of these need resolving before coding starts or can ship as documented gaps, consistent with this project's established pattern of deferring non-blocking spec-review findings.

## Validation Strategy

- `pre-commit run --all-files` green (7/7 hooks), mypy strict clean on every new/changed file, `lint-imports` clean — the new `roles` module's own per-container layering (Contract 1) is checked automatically (wildcarded), and no contract file changes.
- Migration: `upgrade → downgrade → upgrade` proven via a real PostgreSQL instance, per `AGENTS.md` §4/§6, including the seed data.
- **New standalone CI check (OD-1 resolution):** a test asserting every scope referenced in `app/modules/roles/dependencies.py`'s scope-check dependencies, and every `role_permissions` seed row, has a corresponding `permissions` catalogue row — the CI-test equivalent of the story's originally-stated (and rejected, per OD-1) `env.py` hook.
- Coverage floor 85% overall, 90%+ on `roles/service.py` and `roles/router.py`, per `AGENTS.md` §6/NFR-009 — no touched module may lose coverage.

## Testing Strategy

- **Unit (hand-written fakes, no `MagicMock`):** `RoleService.replace_user_roles()` — self-target, privilege-escalation, unknown-role, last-admin guard logic, `perm_epoch` write, audit-log write, all against fake repositories/cache. `RoleService.list_catalogue()`.
- **Integration (real PostgreSQL + Valkey, no `unittest.mock`):** all seven MR-ACs end-to-end through the router; MR-AC2's `token-stale` → `/auth/refresh` → new-scopes flow (crosses into the `users` module's refresh endpoint); MR-AC7's concurrency case (two simultaneous requests against the last two admins) per the Enforcement Matrix's `[gate]` marker on that specific AC.
- **Regression:** the full existing suite must stay green, particularly `users` module tests touched by the `encode_access_token()` signature change and the new `perm_epoch` check.
