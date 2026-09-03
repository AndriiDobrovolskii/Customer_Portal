# Plan Review: Manage Roles (US-3.2 / spec US-3.2)

**Story ID:** US-3.2 (spec US-3.2)
**Plan Reviewed:** docs/plans/US-3.2-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-3.2-task-breakdown.md
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown cover every file `impact-analysis.md` named, including both of its user-resolved items (role-to-scope seed mapping, the FR-7 cross-module exception). Task ordering respects `AGENTS.md` §3's downward-only direction and the migration-before-model-use rule with no violations. Risk and test-strategy sections are concrete rather than generic. Two minor issues keep this from a clean Pass: T4's stated dependencies omit an explicit link to T2 (transitively satisfied via T3, but not stated directly), and the task breakdown's own Notes section proposes closing two spec-review-carried-forward edge cases (empty/duplicate `roles` array) with a default choice inside T4 rather than treating them as still-open — worth an explicit confirmation before T4 executes, not a silent default.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/roles/__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `dependencies.py`, `exceptions.py` | Covered | Files To Create; Task Breakdown T1, T2, T4, T5 | |
| `app/core/cache_keys.py` (`perm_epoch_key`) | Covered | Files To Modify; T2 | |
| New `PermissionEpochCache` (file choice left open by impact-analysis) | Covered | Architectural Changes §2 resolves it into `app/core/revocation_cache.py`; T2 | Planner made the call impact-analysis explicitly deferred — reasonable, cites the sibling-primitive rationale. |
| `app/core/security.py` (`scopes` claim) | Covered | Files To Modify; T2 | |
| `app/core/config.py` (perm_epoch TTL) | Covered | Files To Modify; T2 | |
| `.env.example` | Covered | Files To Modify; T2 | |
| `app/modules/users/service.py` (perm_epoch check; scopes lookup at login/refresh) | Covered | Files To Modify; T6 | |
| `app/api/v1/router.py` (register roles router) | Covered | Files To Modify; T5's Files Touched | |
| Migration: `roles`, `permissions`, `role_permissions`, `user_roles` (+ seed data) | Covered | Files To Create; T3 | Role-to-scope seed values resolved (2026-09-01) and reflected in T3. |
| `tests/unit/modules/roles/test_roles_service.py` (new) | Covered | Files To Create; T7 | |
| `tests/integration/modules/roles/test_roles_router.py` (new) | Covered | Files To Create; T8 | |
| `tests/unit/modules/users/test_users_service.py` (existing, modify) | Covered | Files To Modify; T7 | |
| `tests/integration/modules/users/test_users_router.py` (existing, modify) | Covered | Files To Modify; T8 | |
| `tests/conftest.py` (existing, modify) | Covered | Files To Modify; T8 | |
| `roles.service` → `users` cross-module tension (FR-7 atomicity) | Covered | Architectural Changes §5; resolved 2026-09-01 as documented exception; T2 | |
| `users` → `roles` new cross-module dependency (login scopes lookup) | Covered | Files To Modify (`users/service.py` row); T6 | |

## Layering Order (Task Breakdown)

No violation of `AGENTS.md` §3's downward-only direction or the migration-before-model-use rule was found. One completeness nit, not a violation:

- **[Low] T4's `Depends On` omits an explicit T2 entry** — T4 (`service-and-router-builder`, service) lists `Depends On: T1, T3`. T4's `service.py` directly imports and calls `repository.py`, which is T2's output, not T3's — the dependency is only satisfied because T3 itself depends on T2 (transitively correct, no actual ordering bug), but the stated column doesn't reflect the direct reason T4 needs T2's work done. A reader relying on the `Depends On` column alone to understand *why* a task waits would miss that T4 needs `repository.py`, not just the live migration.

## Risk Realism

None found — the Risks section (migration seed correctness, the FR-7 cross-module transaction boundary, `encode_access_token`'s signature-change blast radius, FR-7 concurrency/row-locking, and the carried-forward spec/design gaps) concretely covers the hazards this story's own impact analysis and DB design imply. No generic "testing will catch issues" placeholder language.

## Test-Strategy Realism

None found — Testing Strategy names the unit/integration split concretely (hand-written fakes for `RoleService` guard logic vs. real-PostgreSQL+Valkey integration for all seven MR-ACs, explicitly including the MR-AC7 concurrency case and the MR-AC2 token-stale→refresh cross-module flow), per `AGENTS.md` §5.

## Scope Creep

- **[Low] Task-breakdown Notes proposes a default resolution for two still-open spec-review findings** — Task-breakdown says: *"The remaining unresolved items are implementation-detail-level and are left for T4 ... to make a documented, conservative choice on as it's written (e.g. reject empty/duplicate arrays with 422 validation-failed ...)."* Neither the spec, the spec-review, nor the API design decided empty-array/duplicate-role behavior — they're explicitly listed as unresolved in all three upstream artifacts. Proposing T4 close them silently during coding, rather than as an explicit pre-implementation decision, risks the same kind of undisclosed scope-filling this project's clarification/spec-review stages exist to prevent — even though the note itself is transparent about doing this (it names the gap and its proposed default rather than hiding it), so it's Low rather than Medium.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage with no Missing/Partially Covered items, and no actual layering-order violation — the two findings above are a documentation-completeness nit (T4's dependency list) and a transparency/process nit (T4 self-authorizing a default for two still-open edge cases rather than having that default explicitly confirmed first). Neither blocks implementation, but the second is worth a quick user confirmation before T4 runs, consistent with how this project has handled every other open item in this story's pipeline so far.
