# Implementation Plan: Manage Users (US-3.1 / spec US-011)

**Spec:** docs/specifications/US-011-manage-users-spec.md
**API design:** docs/designs/api/US-011-openapi.yaml, US-011-api-design.md
**DB design:** docs/designs/database/US-011-db-design.md, US-011-entity-model.md
**Impact analysis:** docs/impact-analysis/US-011-impact-analysis.md

## Goal

Add the admin user-management surface (search/list, fetch, invite-create, whitelisted-field update, deactivate, resend-invite; no hard delete) as a new module, `app/modules/admin_users/`, reusing this project's existing ETag, permission-scope, and role-service precedents rather than reinventing them.

## Architectural Changes

1. **New module `app/modules/admin_users/`, not an extension of `app/modules/users/`.** Confirmed by `impact-analyzer`: mirrors `profile`'s and `roles`' precedent of a separate module with its own `repository.py` importing `User` from `app.modules.users.models` directly. No file in `app/modules/users/` changes.

2. **`RoleService` gains two new public methods; only one of them is wired into `replace_user_roles`** — resolving the two cross-module dependencies `impact-analyzer` flagged (FR-8, FR-16), without changing `replace_user_roles`'s existing behavior:
   - `check_no_privilege_escalation(actor_scopes: set[str], role_names: list[str]) -> None` — resolves `role_names` to their flattened permission set via the existing `RoleRepository.get_by_names()` path and raises `PrivilegeEscalationError` if any permission isn't in `actor_scopes`. Extracted verbatim from `replace_user_roles`'s current inline check (lines 162-176), called from the exact point that check used to run — a true, behavior-preserving extraction. `replace_user_roles` calls this method for both US-3.2's role replacement and this story's FR-8 create-user check.
   - `raise_if_last_admin(target_user_id: uuid.UUID) -> None` — reads the target's current roles, and if `admin` is among them, calls the existing `count_active_admins_excluding` and raises `LastAdminError` if zero remain. **Additive only — not called from `replace_user_roles`.** `replace_user_roles`'s existing inline check (lines 180-187) is conditioned on "the *new* role set excludes admin" (an unconditional `raise_if_last_admin` would incorrectly reject replacing `{admin}` → `{admin, auditor}` for the sole admin — a case that succeeds today, since admin isn't being removed); this story's FR-16 need is conditioned on "the account is being deactivated entirely," a different, target-state-only check. Caught during `plan-reviewer`'s advisor cross-check 2026-09-02 — the original draft of this plan wired both methods into `replace_user_roles`, which would have been a real regression. `raise_if_last_admin` is used only by `admin_users/service.py`'s `deactivate_user` (FR-16); `replace_user_roles`'s own inline last-admin check is left untouched.
   - Both exceptions (`PrivilegeEscalationError`, `LastAdminError`) continue to be defined and raised only in `roles/exceptions.py`/`roles/service.py` and propagate up through `admin_users/service.py` unchanged — the one deliberate exception to "each module owns its own exceptions" (see `impact-analyzer`'s reasoning: the check *logic* is shared, not just the concept).

3. **`AdminAuditLogRepository` write path gains an optional field-level shape.** `RoleService`'s existing `UserRoleRepositoryProtocol.create_admin_audit_log_entry(...)` (currently: `event`, `actor_id`, `target_id`, `old_roles`, `new_roles`, `severity`, `request_id`) is **not** reused directly by `admin_users` — a new, separate write path is added on `admin_users/repository.py` for the per-field Update rows (`event="user_field_updated"`, `field`, `old_value`, `new_value`, `reason`, leaving `old_roles`/`new_roles`/`severity` `NULL`), writing to the same `admin_audit_log` table via a plain SQLAlchemy insert against the (already cross-module-imported) `AdminAuditLog` model — mirroring how `roles/repository.py` already imports `User` directly rather than calling into `users/repository.py` for it. No change to `RoleRepository`'s own protocol/method signature.

4. **Resolves API-design Open Question 9 (`PATCH`'s missing `reason` field): `UpdateUserRequest` gains a required `reason: str` field.** MU-AC9 states each `admin_audit_log` row carries a `reason`; leaving it optional would make the new column silently always-`NULL` in practice, defeating OD-1's purpose. Decision: required, mirroring `DeactivateUserRequest`'s existing mandatory `{reason}`. **`docs/designs/api/US-011-openapi.yaml` is amended** (`UpdateUserRequest.required` gains `reason`; a new `properties.reason: {type: string, minLength: 1}`) as part of this plan, not left as an unresolved gap for implementation to guess at.

5. **Resolves DB-design Known Gap (FR-18's "invalidated" mechanism): reuse `consumed_at`.** A resend sets the prior outstanding row's `consumed_at` to now (same column setup completion uses) rather than adding an `invalidated_at` column — no schema addition, and no story requirement needs to distinguish "used to complete setup" from "invalidated by a resend" after the fact (both mean "not usable"; `admin_audit_log`'s `event=invitation_resent` row is what makes a resend distinguishable in the audit trail, not the token row itself).

6. **`q`'s matched columns (API-design Open Question 3): `email` and `display_name`, confirmed.** The trigram `GIN` index already assumes this in the DB design; no change needed, just formal confirmation before the migration is written.

7. **`ResendInviteResponse` stays an empty object**, per the story's "a generic body" and the API design's own note — no further decision needed.

## Files To Create

| File | Purpose |
|---|---|
| `app/modules/admin_users/__init__.py` | Empty, per module convention. |
| `app/modules/admin_users/models.py` | `InvitationToken` (new table, per `US-011-entity-model.md`). |
| `app/modules/admin_users/schemas.py` | `UserRead`, `UserListResponse`, `CreateUserRequest`, `UpdateUserRequest` (incl. required `reason`, per Architectural Change #4), `DeactivateUserRequest`, `ResendInviteResponse`. |
| `app/modules/admin_users/repository.py` | Queries against `User` (imported), `InvitationToken` (own), `AdminAuditLog` (imported, field-level write path per Architectural Change #3), `AccountLifecycleAuditLog` (imported, `reason`-writing path per OD-2). |
| `app/modules/admin_users/service.py` | `AdminUserService`: `list_users`, `get_user`, `create_user`, `update_user`, `deactivate_user`, `resend_invite`. Calls `RoleService.check_no_privilege_escalation` (create) and `RoleService.raise_if_last_admin` (deactivate). |
| `app/modules/admin_users/router.py` | 7 routes per `US-011-openapi.yaml`; imports `require_scope` from `app.modules.roles.dependencies`. |
| `app/modules/admin_users/dependencies.py` | `get_admin_user_service` / `AdminUserServiceDep`. |
| `app/modules/admin_users/exceptions.py` | `EmailAlreadyRegisteredError`, `PreconditionRequiredError`, `PreconditionFailedError`, `ImmutableFieldError`, `ValidationFailedError`, `NotFoundError`, `AlreadyDeactivatedError`, `CannotTargetSelfError`, `InvalidStateTransitionError`, `TooManyAttemptsError`. |
| `migrations/versions/<rev>_admin_users_invitation_tokens_and_audit_columns.py` | New `invitation_tokens` table; `admin_audit_log` +4 nullable columns; `account_lifecycle_audit_log` +1 nullable column; `users` gains a `(status, created_at)` composite index. |
| `migrations/versions/<rev>_admin_users_email_display_name_trgm_index.py` | **Deliberately a separate migration** (plan-review correction, 2026-09-02): `CREATE EXTENSION IF NOT EXISTS pg_trgm` + a concurrent `GIN` trigram index on `email`/`display_name`, matching the US-2.6 precedent of never bundling a `CONCURRENTLY` build with transactional DDL. |
| `tests/unit/modules/admin_users/test_admin_users_service.py` | Unit tests, hand-written fakes. |
| `tests/integration/modules/admin_users/test_admin_users_router.py` | Integration tests, real PostgreSQL + Valkey. |

## Files To Modify

| File | Change |
|---|---|
| `app/modules/roles/models.py` | `AdminAuditLog` gains 4 nullable columns (`field`, `old_value`, `new_value`, `reason`) — OD-1. |
| `app/modules/roles/service.py` | New `check_no_privilege_escalation` (extracted from, and now called by, `replace_user_roles`) and `raise_if_last_admin` (additive only, not called by `replace_user_roles` — see Architectural Change #2) — behavior-preserving, covered by existing `test_roles_service.py` cases plus new ones. |
| `app/modules/account/models.py` | `AccountLifecycleAuditLog` gains 1 nullable column (`reason`) — OD-2. |
| `app/modules/account/repository.py` | Its lifecycle-audit-log write method gains an optional `reason: str \| None = None` parameter; existing self-service caller passes nothing (stays `NULL`), no behavior change for that path. |
| `app/api/v1/router.py` | Registers `admin_users_router`. |
| `docs/designs/api/US-011-openapi.yaml` | `UpdateUserRequest` gains required `reason` (Architectural Change #4) — design-doc amendment, not application code. |
| `tests/unit/modules/roles/test_roles_service.py` | New cases for `check_no_privilege_escalation`/`raise_if_last_admin`; existing `replace_user_roles` cases re-verified unchanged after the refactor (regression, not new behavior). |

**Protected-file flag (`AGENTS.md` §7.9):** `migrations/env.py` needs one model-registration import line (`from app.modules.admin_users import models as admin_users_models  # noqa: F401`) — the identical pattern already used for every prior new module (`account`, `roles`, etc.), and the same exception the user already approved for US-3.2. Still flagged here explicitly per this skill's own rule rather than silently included; **execution should request the user's explicit sign-off before touching this file**, not treat the US-3.2 precedent as blanket pre-approval for this story.

## Risks

- **`replace_user_roles`'s extraction of `check_no_privilege_escalation` (Architectural Change #2) must be behavior-preserving.** Mitigate by running `test_roles_service.py`'s existing `replace_user_roles` test cases unchanged immediately after the extraction, before writing any new `admin_users` code — a regression here would be silent (still passes its own new tests, breaks the older ones) unless caught early.
- **`raise_if_last_admin` must stay unwired from `replace_user_roles`.** An earlier draft of this plan called both new methods from `replace_user_roles`; caught during review because `raise_if_last_admin` fires whenever the target holds admin and is the last one, while `replace_user_roles`'s real requirement is narrower (only when the *new* set excludes admin) — wiring it in would reject `{admin}` → `{admin, auditor}` for the sole admin, which succeeds today. `raise_if_last_admin` is additive-only, called from `admin_users/service.py`'s `deactivate_user` alone, and needs its own dedicated test coverage (target holds admin + is the last one → raises; target holds admin + is not the last one → passes; target doesn't hold admin at all → passes without querying the count) — not reuse of `replace_user_roles`'s fixtures.
- **`pg_trgm` extension creation** may require elevated database privileges depending on the deployment target (some managed PostgreSQL providers restrict `CREATE EXTENSION` to a privileged role) — this project's first use of the extension, so unlike every other migration in this codebase's history, this one has an environmental precondition worth confirming works in whatever environment `migration-manager` proves the upgrade/downgrade cycle against.
- **Concurrent `GIN`-index build on a live `users` table** — per `AGENTS.md` §4, must use `CONCURRENTLY` + `autocommit_block()`; a non-concurrent index build would lock `users` for writes for the duration, affecting every other story's login/registration/profile-update paths, not just this one.
- **`admin_users/repository.py`'s field-level `admin_audit_log` write path duplicates, rather than reuses, `roles/repository.py`'s existing `create_admin_audit_log_entry`** (Architectural Change #3) — an intentional choice (different column set populated), but means two write paths into the same table exist going forward; a future column addition to `admin_audit_log` needs to consider both.

## Validation Strategy

- `pre-commit run --all-files` green (7/7 hooks), mypy strict clean on every new/changed file, `lint-imports` clean — confirm `admin_users → roles` is an allowed import direction (no cycle back from `roles` into `admin_users`).
- Migration: `upgrade → downgrade → upgrade` proven against real PostgreSQL, including the `pg_trgm` extension creation and the concurrent index builds.
- Coverage floor 85% overall, 90%+ on `admin_users/service.py` and `admin_users/router.py` (this module's own incumbent floor from day one, per `AGENTS.md` §6/NFR-009).
- A dedicated test proving `replace_user_roles`'s behavior is unchanged after the Architectural Change #2 refactor (existing `test_roles_service.py` suite passing is necessary but not sufficient — add an explicit before/after equivalence note in the PR description if any existing test needed to change at all).

## Testing Strategy

- **Unit (hand-written fakes, no `MagicMock`):** `admin_users/service.py`'s six methods, each covering its FRs' success/error branches (FR-1–FR-23) against a fake repository and a fake `RoleService`/`EmailSender`. `roles/service.py`'s two new methods, plus `replace_user_roles`'s existing cases re-run to confirm the refactor is behavior-preserving.
- **Integration (real PostgreSQL + Valkey, no `unittest.mock`):** all 21 MU-ACs plus FR-17b/FR-22/FR-23 end-to-end through the router, per the spec's Enforcement Matrix `[gate]` markers; MU-AC16's concurrency test (two simultaneous deactivations of the last two admins, per the spec's explicit Enforcement Matrix line); FR-6's concurrent duplicate-email creation (two simultaneous `POST /v1/admin/users` for the same email); the search index actually returning results for `q` against both `email` and `display_name`.
- **Regression:** full existing suite green, particularly `roles` module tests (Architectural Change #2's refactor) and the `app/api/v1/router.py` registration (a wiring smoke test via `app.openapi()` listing all 7 new routes, mirroring how US-2.5's T6 confirmed its new routes the same way).
