# Plan Review: Deactivate Account

**Story ID:** US-1.4
**Plan Reviewed:** docs/plans/US-1.4-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-1.4-task-breakdown.md
**Reviewed:** 2026-08-30 (re-review, replaces prior Fail verdict on this path)
**Overall Verdict:** Pass

## Summary

Re-review after the plan was revised in response to this file's prior Fail verdict. The blocking finding (Architectural Change 6's cross-module import of `app.modules.users.exceptions.InvalidCredentialsError`) is resolved: `account/exceptions.py` now defines a local `InvalidPasswordError`, no cross-module import. The two non-blocking findings from the prior review are also addressed: the Testing Strategy now explicitly names the audit-log write assertion, and `impact-analysis.md` has an addendum recording `app/core/cache_keys.py`. All impact-analysis items are covered, task ordering respects `AGENTS.md` §3, and no new issues were introduced by the fix.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/account/models.py` | Covered | T3 | |
| `app/modules/account/schemas.py` | Covered | T1 | |
| `app/modules/account/repository.py` | Covered | T3 | |
| `app/modules/account/cache.py` | Covered | T3 | |
| `app/modules/account/service.py` | Covered | T6 | |
| `app/modules/account/router.py` | Covered | T8 | |
| `app/modules/account/dependencies.py` | Covered | T8 | |
| `app/modules/account/exceptions.py` | Covered | T6 | Now `AlreadyDeactivatedError` + local `InvalidPasswordError`, no cross-module import — prior finding resolved |
| `app/modules/users/models.py` (deactivated_at) | Covered | T4 | |
| `app/modules/users/schemas.py` (UserStatus) | Covered | T2 | |
| `app/modules/users/service.py` (get_authenticated_user) | Covered | T7 | |
| `app/modules/users/dependencies.py` (get_user_service) | Covered | T9 | |
| `app/core/config.py` (valkey_url) | Covered | T0b | |
| `app/main.py` (lifespan) | Covered | T0c | |
| `app/db/dependencies.py` (get_valkey_client) | Covered | T0d | |
| `pyproject.toml` (new dependency) | Covered | T0a | Sign-off obtained (redis>=5.0) |
| `tests/conftest.py` (Valkey fixture) | Covered | T10 | |
| `app/core/cache_keys.py` *(addendum)* | Covered | T0e | Now recorded in impact-analysis.md's addendum |

Full coverage — no impact-analysis item is Missing or Partially Covered.

## Layering Order (Task Breakdown)

No issues. The prior High finding (cross-module `service.py` → sibling `exceptions.py` import, violating `AGENTS.md` §3's allowed-import set for `service.py` and the service→service cross-module rule) is resolved: T6's Files Touched now reads "`AlreadyDeactivatedError`, `InvalidPasswordError` — both local, no cross-module import," and its Verification Command was strengthened to `grep confirms zero app.modules.users imports anywhere in account/`, which gate-enforcer/CI can actually check. Remaining task ordering (T0a→T0e infra chain, data-layer-builder before migration-manager, migration before service, service before router) still respects `AGENTS.md` §3's downward-only direction and this project's migration-before-model-use rule — unchanged from the first review, where this was already correct.

## Risk Realism

No issues — unchanged from the prior review, which found the plan's five risks (dependency sign-off, concurrency semantics, migration hazard classification, auth-path regression, non-migration enum extension) concretely traceable to `AGENTS.md` §4/DB-design content.

**Observation (non-blocking, not a finding):** the corrected `InvalidPasswordError` follows the RFC 7807 `ProblemError` shape, consistent with `profile/exceptions.py` and `email_verification`'s exception style, but diverges from `users/exceptions.py`'s `InvalidCredentialsError` (a plain `DomainError` with a bespoke `{"detail": ...}` handler in `main.py`) for the same underlying "wrong password" semantics. This is a pre-existing inconsistency between `users` and the newer modules, not something this plan introduces or is required to fix — noting it so it doesn't get mistaken for a defect in this story's design later.

## Test-Strategy Realism

No issues. The prior Medium finding (FR-1's audit-log write not named as an explicit unit-test target) is resolved — the plan's Testing Strategy now has an explicit bullet requiring the success-path unit test to assert the audit-log fake recorded one `event=deactivated, actor=self` entry, alongside the status/cache-write assertions already present.

## Scope Creep

No issues. The prior Low finding (`app/core/cache_keys.py` absent from `impact-analysis.md`) is resolved via the addendum added to that file.

## Verdict Rationale

All items from the prior Fail verdict are resolved with concrete, verifiable changes (grep-checkable for the layering fix, an explicit assertion target for the test gap, a recorded addendum for the scope-creep note), no new issues were introduced, and every other dimension (impact-analysis coverage, task ordering, risk realism) was already correct in the first review. **Pass** — implementation may proceed.
