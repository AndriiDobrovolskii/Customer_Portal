# Plan Review: Manage Users (US-3.1 / spec US-3.1)

**Story ID:** US-3.1
**Plan Reviewed:** docs/plans/US-3.1-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-3.1-task-breakdown.md
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown fully cover every item `impact-analyzer` identified, correctly place the new `admin_users` module and the two cross-module `RoleService` additions, and respect `AGENTS.md` §3's layering order throughout. Two Medium risk-realism findings keep this from a clean Pass: T3's single migration bundles a `CONCURRENTLY` trigram-index build with ordinary transactional DDL, contradicting this project's own established precedent (US-2.6's identical situation used two separate migrations, one "deliberately alone"); and T2's assignment of the `migrations/env.py` model-registration line to `data-layer-builder` exceeds that skill's own declared scope and contradicts how this exact situation was actually handled for US-3.2 (done as an out-of-band, explicitly-approved step, not baked into a task's file list).

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| New `app/modules/admin_users/` (`__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `dependencies.py`, `exceptions.py`) | Covered | Files To Create; T1, T2, T5, T6 | — |
| `app/modules/roles/models.py` (`AdminAuditLog` +4 columns, OD-1) | Covered | Files To Modify; T2b | — |
| `app/modules/roles/service.py` (new public methods for FR-8/FR-16 reuse) | Covered | Architectural Change #2; Files To Modify; T4 | — |
| `app/modules/account/models.py` (`AccountLifecycleAuditLog` +1 column, OD-2) | Covered | Files To Modify; T2b | — |
| `app/api/v1/router.py` (register `admin_users_router`) | Covered | Files To Modify; T6 | — |
| `migrations/env.py` (model-registration import) | Partially Covered | Files To Modify (protected-file flag); T2 | Flagged for sign-off (good), but assigned to `data-layer-builder`'s file list despite exceeding that skill's own declared scope — see Risk Realism. |
| `app/modules/users/*` — explicitly not affected | Covered | Files To Create/Modify tables correctly omit it | — |
| `app/core/etag.py`, `app/core/email.py` — explicitly not affected | Covered | "Not affected" section, reused as-is | — |
| Cross-module ripple: `admin_users.router` → `roles.dependencies.require_scope` | Covered | Files To Create (T6: "imports `require_scope`") | — |
| Cross-module ripple: `admin_users.service` → `roles.service.RoleService` | Covered | Architectural Change #2; T4, T5 | — |
| Migration: new table + 5 nullable columns + 2 new `users` indexes (incl. first `pg_trgm` use) | Partially Covered | Files To Create (single migration file); T3 | Bundles a `CREATE INDEX CONCURRENTLY` build with ordinary DDL in one migration — see Risk Realism. |
| Test surface: new `tests/{unit,integration}/modules/admin_users/` | Covered | Files To Create; T7, T8 | — |
| Test surface: `tests/unit/modules/roles/test_roles_service.py` (new cases only) | Covered | Files To Modify; T7 | — |
| Test surface: `tests/integration/modules/roles/test_roles_router.py` — explicitly not affected | Covered | Not listed anywhere in the plan/task breakdown (correctly absent) | — |

## Layering Order (Task Breakdown)

None found. T1/T2/T2b/T4 are correctly parallel-eligible (no shared dependency); T3 correctly waits on T2/T2b (migration-before-model-use in reverse — models exist before the migration that creates their table is generated); T5 correctly waits on T1 (schemas), T2 (own repository), T3 (schema live), and T4 (the `RoleService` methods it calls); T6 (router) correctly waits on T5 (service). `gate-enforcer` (T9) is the sole final task, depending on T1–T8. No task depends on a layer built after it.

## Risk Realism

- **[Medium, found+fixed same-day] `replace_user_roles`'s originally-drafted refactor was not behavior-preserving.** Architectural Change #2's first draft wired both new `RoleService` methods into `replace_user_roles`, including `raise_if_last_admin` — but that method's trigger (target holds `admin` and is the last one) is broader than what `replace_user_roles` actually checks today (only when the *new* set excludes `admin`). Confirmed against `app/modules/roles/service.py` lines 180-187: an unconditional `raise_if_last_admin` call would reject `{admin}` → `{admin, auditor}` for the sole admin, a request that succeeds today with no test currently exercising that exact case to catch the regression. Fixed same-day: `raise_if_last_admin` is now additive-only (called solely from `admin_users/service.py`'s `deactivate_user`), not wired into `replace_user_roles`; only `check_no_privilege_escalation` is a true extraction.
- **[Medium] T3 bundles a `CONCURRENTLY` index build with transactional DDL in one migration, contradicting this project's own precedent.** Plan's Files To Create says: "`migrations/versions/<rev>_admin_users_invitation_tokens_and_audit_columns.py` | New `invitation_tokens` table; `admin_audit_log` +4 nullable columns; `account_lifecycle_audit_log` +1 nullable column; `users` gains `(status, created_at)` composite index and a `pg_trgm` `GIN` index on `email`/`display_name` (with `CREATE EXTENSION IF NOT EXISTS pg_trgm`)." `AGENTS.md` §4 requires `CREATE INDEX CONCURRENTLY` to run inside its own `autocommit_block()`, and this codebase's own precedent for the identical situation — US-2.6's `refresh_tokens` lookup index — used **two separate migrations** (`5dccea7a3749_add_session_management_columns.py` for ordinary DDL, `db8cbd5e3697_add_refresh_tokens_family_lookup_index_.py` for the concurrent index alone), with that second migration's own docstring stating "this migration is deliberately alone (plan-review finding, US-2.6-plan-review.md)." T3 as written repeats the pattern that story's own plan review already flagged and corrected once; this plan should split T3 into two migration tasks (ordinary DDL: table + 5 columns + composite index; a second, standalone migration: `pg_trgm` extension + concurrent trigram index) rather than one.
- **[Medium] T2's `migrations/env.py` touch is assigned to a skill whose own declared scope excludes it, and contradicts how this exact situation was actually handled last time.** Task breakdown's T2 lists `migrations/env.py` under `data-layer-builder`'s Files Touched (with a sign-off flag). But `data-layer-builder`'s own operational scope is stated (in this session's available-skills listing) as producing "only `app/modules/<module>/models.py`, `repository.py`, and `cache.py`" — `migrations/env.py` isn't in that list, and `migration-manager` explicitly states it "never touches `migrations/env.py`" either. Neither of the two skills whose tasks precede T3 is actually scoped to make this edit. This project's own precedent for the identical situation (`US-3.2-implementation-plan.md`, registering the brand-new `roles` module) states outright: "No file under `AGENTS.md` §7.9 protection... is touched by **this plan**" — yet `migrations/env.py` today does contain the `roles`-registration import, per `docs/workflow/workflow-state.yaml`'s own history ("One user-approved exception: `migrations/env.py` gained one model-registration import line... not part of the original US-3.2 design"). In other words, this project's actual practice is to handle this as an **out-of-band, explicitly-approved step outside the planned task sequence**, not to fold it into any execution skill's file list. T2 should drop `migrations/env.py` from its Files Touched and this touch should instead be called out as a standalone, unassigned step requiring the user's explicit sign-off at the point `migration-manager` needs the new module registered to autogenerate against it (i.e., just before T3).

## Test-Strategy Realism

None found. The plan's Testing Strategy explicitly separates hand-written-fake unit tests (`admin_users/service.py`'s six methods; `roles/service.py`'s two new methods plus `replace_user_roles`'s existing cases) from real-Postgres/Valkey integration tests (all 21 MU-ACs + FR-17b/FR-22/FR-23 via the router; MU-AC16's explicit concurrency test; FR-6's concurrent-duplicate-email test; the search index's actual behavior) — matching `AGENTS.md` §5's unit/integration split concretely, not just by name.

## Scope Creep

None found. Every file in Files To Create/Modify traces to a specific item in `impact-analysis.md`; the two design-doc amendments (`US-3.1-openapi.yaml`'s `UpdateUserRequest.reason`, already applied) trace to Architectural Change #4's explicit, documented rationale rather than being introduced silently.

## Verdict Rationale

Pass with Issues: impact-analysis coverage is complete and the task breakdown's layering order is correct throughout, so nothing here blocks implementation outright. The two Medium risk-realism findings — T3's migration bundling and T2's misattributed `env.py` touch — should be corrected before `migration-manager`/`data-layer-builder` execute those tasks, since both reproduce mistakes this project has already made and fixed once before (US-2.6's migration split; US-3.2's out-of-band `env.py` handling) rather than learning from either precedent.
