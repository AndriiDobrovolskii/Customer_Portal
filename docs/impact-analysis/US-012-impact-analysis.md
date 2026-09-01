# Impact Analysis: Manage Roles (US-3.2 / spec US-012)

**Spec:** docs/specifications/US-012-manage-roles-spec.md
**API design:** docs/designs/api/US-012-openapi.yaml, US-012-api-design.md
**DB design:** docs/designs/database/US-012-db-design.md, US-012-entity-model.md

## 1. Affected Files, by Layer

This story has no existing module to extend — it is the first role/permission code in the repository. A new module, `app/modules/roles/`, is created.

### New — `app/modules/roles/`

| File | Layer | Reason |
|---|---|---|
| `__init__.py` | — | New module. |
| `models.py` | models | `Role`, `Permission`, `RolePermission`, `UserRole` per `docs/designs/database/US-012-entity-model.md`. |
| `schemas.py` | schemas | `RoleRead`, `RoleCatalogueResponse`, `ReplaceUserRolesRequest`, `ReplaceUserRolesResponse` per `US-012-openapi.yaml`'s component schemas. |
| `repository.py` | repository | `RoleRepository` (catalogue reads with `selectinload(Role.permissions)` per FR-3/FR-6) and `UserRoleRepository` (`list_by_user`, `replace_for_user`, a `role_id`-keyed count query for FR-7's last-admin check). |
| `service.py` | service | `RoleService.list_catalogue()` (FR-3) and `RoleService.replace_user_roles()` (FR-1, FR-4-FR-7 guard logic). |
| `router.py` | router | `GET /v1/admin/roles`, `PUT /v1/admin/users/{id}/roles` per `US-012-openapi.yaml`. |
| `dependencies.py` | dependencies | `RoleServiceDep`; scope-check dependencies for `users:read`/`roles:write` (unless a shared scope-check dependency is placed in `app.core` instead — see §2). |
| `exceptions.py` | exceptions | `CannotTargetSelfError` (FR-5), `PrivilegeEscalationError` (FR-6), `LastAdminError` (FR-7), `UnknownRoleError`→422 (FR-4). |

### Modified — cross-cutting (`app.core`)

| File | Reason |
|---|---|
| `app/core/cache_keys.py` | Add `perm_epoch_key(user_id)`, mirroring the existing `revoke_before_key(user_id)` (line 4-5) — same file, same pattern, both keys are per-user Valkey namespacing. |
| A new `PermissionEpochCache` class (either added to `app/core/revocation_cache.py` or a sibling `app/core/permission_cache.py`) | `perm_epoch:{user_id}` needs the identical "single read/write surface, fails closed, no swallowed connection errors" treatment `RevocationCache`'s own docstring describes for `revoke_before` — and for the same stated reason: multiple modules touch it (`roles` writes it on every `PUT .../roles`; `users` reads it on every authenticated request), so it belongs in `app.core`, not owned by the new `roles` module. **Decision of which file (new vs. extend `revocation_cache.py`) is left to `planner`, not decided here.** |
| `app/core/security.py` | `AccessTokenClaims` (currently `user_id`, `jti`, `exp` only — confirmed by reading the file) needs a `scopes: list[str]` field; `encode_access_token()` needs a `scopes` parameter to embed it in the JWT payload; `decode_access_token()` needs to surface it. This is a signature change to a function every access-token-minting call site uses. |
| `app/core/config.py` | A new setting is needed for `perm_epoch`'s Valkey TTL (mirrors `refresh_token_ttl_seconds`/`password_reset_token_ttl_minutes`'s existing pattern of one setting per TTL-bearing cache write) — exact value left to `planner`. |
| `.env.example` | Must be updated to match the new setting, per `AGENTS.md` §4's "Config & secrets" rule. |

### Modified — existing modules

| File | Reason |
|---|---|
| `app/modules/users/service.py` | The existing token-validation path (confirmed at lines 487-496: `revoke_before = await self._revocation_cache.get_revoke_before(...)`, compared against `session.issued_at`) must gain an identical `perm_epoch` comparison, returning `401 token-stale` (FR-2) when `session.issued_at <= perm_epoch`. This is the shared auth dependency every authenticated endpoint in the app goes through — the single highest-blast-radius change in this story. |
| `app/modules/users/service.py` (login flow) | Wherever `encode_access_token()` is currently called (login, and any refresh-token-rotation call site) must be updated to pass the user's current `scopes`, which requires reading `User.roles` → `Role.permissions` (`selectinload`, per DB design) at token-issuance time. This is new: today's login flow has no role/scope lookup at all. |
| `app/api/v1/router.py` | Register the new `roles` router (`app.include_router(roles.router, prefix="/v1/admin")` or equivalent, matching this file's existing aggregation pattern). |

## 2. Cross-Module Ripple

- **`roles.service` → `users` data, for FR-7 (last-admin check).** The check ("the only active account holding the admin role") needs `user_roles.role_id = <admin>` joined against `users.status = 'active'` — one table from each module. Per `AGENTS.md` §3's "cross-module calls go service → service" discipline, `roles.repository` should not directly import `users.models`. But FR-7 also requires the check and the update to "run in one transaction" (spec, verbatim) — a `roles.service` → `users.service` call would cross a transaction boundary each service manages independently (per this project's "service owns the transaction, one commit per business operation" convention), which cannot satisfy FR-7's atomicity requirement as stated. **This is a genuine architectural tension, not decided here** — flagged for `planner` to resolve (candidates include: a read-only cross-module repository query as a documented, narrow exception; or `users` exposing a service method that accepts an already-open transaction/session).
- **`roles.service` reads `User.roles` at login time**, called from `users.service`'s login flow (`users` → `roles`, the reverse direction of the above). This is a new cross-module dependency that doesn't exist today — flagged as a new architectural fact, not just an in-module change.
- **`account.service`** (self-deactivation, per the earlier grep of `revoke_before` call sites) is **not** affected by this story — role-aware last-admin protection for deactivation belongs to US-3.1's MU-AC16, a different, not-yet-built story.

### Resolution (user, 2026-09-01)

- **Role-to-scope mapping:** minimal per-persona, matching `docs/product/personas.md`. `customer`: no scopes. `support_agent`: `tickets:read`, `tickets:write`. `auditor`: `audit:read`. `admin`: all six scopes (`users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`). This is the `role_permissions` seed migration's data.
- **FR-7 cross-module atomicity:** resolved as a narrow, explicitly documented exception — `roles.repository`'s last-admin count query reads `users.status` directly via a join within the same transaction as the role-set update, justified by FR-7's explicit one-transaction requirement. Document this exception in `roles/repository.py` the same way `app/core/revocation_cache.py`'s docstring documents its own deliberate placement exception, so a future reader doesn't mistake it for an accidental layering violation.

## 3. Migration/Schema Impact

**Yes, a migration is required.** New tables only — no existing table's columns change:
- `roles` (new)
- `permissions` (new)
- `role_permissions` (new)
- `user_roles` (new)

No existing repository query is affected by a schema change (no column added to `users` or any other existing table). The migration also needs seed `INSERT`s for `roles` (4 rows) and `permissions` (6 rows) — both fully determined by the spec's Background section. The `role_permissions` seed `INSERT` (which permissions each role grants) **cannot be written yet** — the spec's own Open Question ("which permission scopes does each of the four seeded roles grant?") is unresolved; this blocks that one seed step, not the rest of the migration.

## 4. Test-Surface Impact

### New test files
- `tests/unit/modules/roles/test_roles_service.py`
- `tests/integration/modules/roles/test_roles_router.py`

### Existing test files that must change
- `tests/unit/modules/users/test_users_service.py` — the token-validation unit tests must gain `perm_epoch`-stale coverage (mirroring the existing `revoke_before` test cases), and any test that calls `encode_access_token()` (directly or via the login/refresh flow under test) needs updating for the new `scopes` parameter.
- `tests/integration/modules/users/test_users_router.py` — login's response/JWT-decoding assertions may need updating if any integration test decodes and inspects token claims.
- `tests/conftest.py` — likely needs a fixture or fake extension for seeding a test user's role assignment (to test both the privileged and non-privileged authorization paths this story introduces), similar to how existing fixtures seed other per-user state.
