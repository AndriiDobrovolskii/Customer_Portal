# Impact Analysis: Manage Users (US-3.1 / spec US-011)

**Source spec:** docs/specifications/US-011-manage-users-spec.md
**API design:** docs/designs/api/US-011-{openapi.yaml,api-design.md}
**DB design:** docs/designs/database/US-011-{db-design,entity-model.md}

## Module Placement

This story introduces a **new module, `app/modules/admin_users/`** — not an extension of `app/modules/users/` (already 1554 lines in `service.py` alone). This mirrors the existing precedent set by `app/modules/profile/` (the self-service twin of the same `User` entity, with its own `repository.py` importing `User` from `app.modules.users.models` directly rather than delegating to `users/repository.py`) and `app/modules/roles/` (which does the identical cross-module `User` import in `RoleRepository`/`UserRoleRepository`). No file in `app/modules/users/` needs to change for this story.

## Affected Files by Layer

### New: `app/modules/admin_users/`

| File | Reason |
|---|---|
| `__init__.py` | Empty, per every existing module's convention. |
| `models.py` | `InvitationToken` (new table) — FR-5, FR-18, FR-19 read/write it. |
| `schemas.py` | `UserRead`, `UserListResponse`, `CreateUserRequest`, `UpdateUserRequest`, `DeactivateUserRequest`, `ResendInviteResponse` — request/response shapes per `US-011-openapi.yaml`. |
| `repository.py` | Queries against `User` (imported from `app.modules.users.models`), `InvitationToken` (own model), `AdminAuditLog` (imported from `app.modules.roles.models`), `AccountLifecycleAuditLog` (imported from `app.modules.account.models`) — every FR (FR-1–FR-23) needs a persistence operation on one of these four tables. |
| `service.py` | `AdminUserService` — business logic for FR-1 through FR-23, including the two cross-module calls into `RoleService` below. |
| `router.py` | 7 routes (`GET`/`POST /v1/admin/users`, `GET`/`PATCH`/`POST .../deactivate`/`DELETE`/`POST .../resend-invite` on `/v1/admin/users/{id}`) matching `US-011-openapi.yaml` exactly. Imports `require_scope` from `app.modules.roles.dependencies` directly — see Cross-Module Ripple. |
| `dependencies.py` | `get_admin_user_service` factory + `AdminUserServiceDep`, mirrors every other module's `dependencies.py` (e.g. `roles/dependencies.py`'s `get_role_service`). |
| `exceptions.py` | This module's own `ProblemError` subclasses: `EmailAlreadyRegisteredError` (409, FR-6), `PreconditionRequiredError`/`PreconditionFailedError` (400/412, FR-10), `ImmutableFieldError`/`ValidationFailedError` (422, FR-11), `NotFoundError` (404, FR-12/17b/21/23), `AlreadyDeactivatedError`/`CannotTargetSelfError` (409, FR-14/15), `InvalidStateTransitionError` (409, FR-19), `TooManyAttemptsError` (429, FR-20). Each is a **new class**, not a cross-module import — this codebase's established convention is that every module defines its own exception classes even when the concept repeats elsewhere (`TooManyAttemptsError` is independently defined in both `email_verification/exceptions.py` and `users/exceptions.py` today; `PreconditionRequiredError`/`PreconditionFailedError`/`ImmutableFieldError` currently exist only in `profile/exceptions.py`). `PrivilegeEscalationError` (FR-8) and `LastAdminError` (FR-16) are the two exceptions **not** duplicated here — see below. |

### Modified: existing files

| File | Reason |
|---|---|
| `app/modules/roles/models.py` | `AdminAuditLog` gains 4 nullable columns (`field`, `old_value`, `new_value`, `reason`) per OD-1 — FR-9. |
| `app/modules/roles/service.py` | `RoleService` gains new public method(s) exposing the permission-resolution and last-admin-count logic currently inlined inside `replace_user_roles` (`requested_permissions.issubset(actor_scopes)` via `RoleRepository.get_by_names()`; `UserRoleRepository.count_active_admins_excluding`) — so `admin_users/service.py` can call them for FR-8 (create-user privilege escalation) and FR-16 (deactivate last-admin protection) instead of reimplementing the check. Direction already set by the spec's Open Decision Resolutions ("resolved the same way US-3.2's `RoleService` already resolves it... not a new mapping mechanism"); the exact method signature is for `planner`/`implementation-planner` to fix. `PrivilegeEscalationError`/`LastAdminError` continue to be raised from inside `RoleService` and propagate up through `admin_users/service.py` unchanged — the one deliberate exception to the "each module owns its exceptions" convention noted above, because here the check *logic* itself (not just the concept) is being reused, not reimplemented. |
| `app/modules/account/models.py` | `AccountLifecycleAuditLog` gains 1 nullable column (`reason`) per OD-2 — FR-13. |
| `app/api/v1/router.py` | Registers the new `admin_users_router`, mirroring the existing `account_router`/`email_verification_router`/`profile_router`/`roles_router`/`users_router` registration list. |
| `migrations/env.py` | Gains one model-registration import line (`from app.modules.admin_users import models as admin_users_models  # noqa: F401`), matching the identical pattern every prior new module used (`account_models`, `roles_models`, etc.) — a user-approved exception to `AGENTS.md` §7.9's protection of this file, per the same precedent already used for US-3.2. |

### Not affected

- `app/modules/users/` (models/schemas/repository/service/router/dependencies/exceptions) — no change; the new module owns its own persistence against the shared `User` table.
- `app/core/etag.py` — `compute_profile_etag` is already generic (`dict[str, str | None] -> str`), reused as-is with a different field set, no code change.
- `app/core/email.py` (`EmailSender`) — reused as-is for the invitation email (FR-5) and resend email (FR-18); no new method needed, mirrors how `email_verification`/`profile` already call it.

## Cross-Module Ripple

- **`admin_users.router` → `roles.dependencies.require_scope`** (new cross-module dependency import). `require_scope`'s own docstring already anticipated this: "every `/v1/admin/*` route this story adds needs one, so it's built once here rather than duplicated per route" — not a new architectural fact this story introduces, but confirming the anticipated caller now exists.
- **`admin_users.service` → `roles.service.RoleService`** (new cross-module service call, two call sites): FR-8's privilege-escalation check (create) and FR-16's last-admin check (deactivate). This is the one genuinely new cross-module dependency this story introduces — `roles.service` currently has no caller outside its own router; `users.service` already calls it (established during US-2.5/T4) but `admin_users.service` calling it is new. Requires the new public method(s) on `RoleService` noted above.
- **`roles.service` → `admin_users.*`**: none. The dependency is one-directional (`admin_users` depends on `roles`, not the reverse), consistent with `roles` already being a lower-level, dependency-free module relative to `users`/`profile`.

## Migration/Schema Impact

**Yes, a migration is required.** Per `US-011-db-design.md`:

- New table `invitation_tokens` (6 columns, 2 indexes — unique on `token_hash`, index on `user_id`).
- `admin_audit_log`: 4 new nullable columns (`field`, `old_value`, `new_value`, `reason`). Nullable + no default change to existing rows; no existing `INSERT`/`SELECT` in `roles/repository.py` needs updating since all four are optional and existing code doesn't reference them.
- `account_lifecycle_audit_log`: 1 new nullable column (`reason`). Same "no existing query needs updating" reasoning — `app/modules/account/repository.py`'s existing `create_lifecycle_audit_log_entry`-shaped call (self-service path) is unaffected since it never needs to pass a value for the new column.
- `users`: no column change; 2 new indexes — composite `(status, created_at)`, and a `GIN` trigram index (`gin_trgm_ops`) on `email`/`display_name` for the `q` search (FR-1). The trigram index requires `CREATE EXTENSION IF NOT EXISTS pg_trgm` first — this project's first use of that extension. Both indexes are additive against a live table with existing rows (`CONCURRENTLY` + `autocommit_block()` per `AGENTS.md` §4, per the db-design's own Migration Note) — no existing repository query is affected by adding an index.

## Test-Surface Impact

### New test files

- `tests/unit/modules/admin_users/test_admin_users_service.py` — new module, new file, mirrors every other module's unit-test layout.
- `tests/integration/modules/admin_users/test_admin_users_router.py` — same, for the 7 new routes end-to-end against real Postgres/Valkey.

### Existing test files requiring changes

- `tests/unit/modules/roles/test_roles_service.py` — new test cases for the new public method(s) `RoleService` gains (permission-resolution/last-admin-count wrappers). No existing test in this file needs to change, only new cases added.
- `tests/integration/modules/roles/test_roles_router.py` — **not** affected; no new/changed route on `roles/router.py`, only an internal service-layer addition with no HTTP-surface change.
- No test file under `tests/*/modules/users/` needs to change — `users` module itself is untouched by this story.
