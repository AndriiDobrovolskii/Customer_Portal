# Plan Review: US-2.3 Refresh Token

**Story ID:** US-007
**Plan Reviewed:** docs/plans/US-007-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-007-task-breakdown.md
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown cover every item `docs/impact-analysis/US-007-impact-analysis.md` identified, the task sequence respects AGENTS.md §3's layering direction with no violations, and both the Risks and Testing Strategy sections are concrete rather than generic. Verdict is Pass with Issues rather than a clean Pass because of one [Low] ordering gap, the same class of finding US-006's own plan review caught: the plan states that `create_auth_audit_log_entry`'s pre-existing (login/logout) call sites need an explicit `severity=None` argument once the parameter is added, but no task in the breakdown assigns that edit to a specific task/file.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `models.py` — `RefreshToken` gains `consumed_at`, `last_used_at`, `ip`, `user_agent` | Covered | Files To Modify; Task T2 | — |
| `models.py` — `AuthAuditLog` gains `severity` | Covered | Files To Modify; Task T2 | — |
| `schemas.py` — new `RefreshResponse` | Covered | Files To Modify; Task T1 | — |
| `repository.py` — `consume_refresh_token(token_hash)` (new) | Covered | Files To Modify; Task T2 | — |
| `repository.py` — `create_refresh_token` signature change | Covered | Files To Modify; Task T2 | Caller update (login's `authenticate_user`) explicitly assigned to T4 — no ambiguity here, unlike the finding below |
| `repository.py` — `revoke_refresh_token_family` reused unchanged | Covered | Files To Modify; Task T2 ("reused unchanged from US-2.2") | — |
| `repository.py` — `create_auth_audit_log_entry` signature change | Covered | Files To Modify; Task T2 | Caller update for *pre-existing* call sites not assigned — see Layering Order note below |
| `cache.py` — `RefreshRateLimitCache` (new) | Covered | Files To Modify; Task T2 | — |
| `app/core/cache_keys.py` — `refresh_rate_limit_key` (new) | Covered | Files To Modify; Task T2 | — |
| `app/core/email.py` — `EmailSender.send_refresh_reuse_alert` (new) | Covered | Files To Modify; Task T4 | — |
| `service.py` — `rotate_refresh_token()` (new) | Covered | Architectural Changes; Files To Modify; Task T4 | — |
| `service.py` — `authenticate_user` updated (ip/user_agent) | Covered | Architectural Changes; Files To Modify; Task T4 | — |
| `router.py` — `POST /auth/refresh` (new route) | Covered | Files To Modify; Task T5 | — |
| `dependencies.py` — `get_user_service` wires `RefreshRateLimitCache` | Covered | Files To Modify; Task T5 | — |
| `exceptions.py` — `TokenInvalidError` (new) | Covered | Architectural Changes; Files To Modify; Task T4 | — |
| Migration — 5 additive nullable columns | Covered | Files To Create; Task T3 | — |
| Cross-module ripple — none | Covered | Architectural Changes: "No new module... everything stays inside the already-scaffolded `app/modules/users/`" | Consistent with impact analysis's "None" finding |
| Test surface — `test_users_service.py` (extend) | Covered | Files To Modify; Task T6 | — |
| Test surface — `test_users_router.py` (extend) | Covered | Files To Modify; Task T7 | — |
| Test surface — `account`/`profile`/`email_verification` unaffected | Covered | Plan doesn't list any file in those modules; consistent with impact analysis's "Not Affected" note | — |

## Layering Order (Task Breakdown)

- **[Low] Pre-existing `create_auth_audit_log_entry` call sites' `severity=None` update has no assigned task.** The plan's Architectural Changes section states: "every pre-existing call site (US-2.1 login, US-2.2 logout) keeps passing `severity=None` explicitly, mirroring how `scope` was added in US-2.2." Both of those call sites live in `app/modules/users/service.py` — a file T4 (service-and-router-builder) owns — but T4's Files Touched column only lists the *new* `rotate_refresh_token()` method and the `authenticate_user` ip/user_agent change; it doesn't mention touching the login/logout flows' existing `create_auth_audit_log_entry` calls. This is the identical gap class US-006's own plan review found and fixed for its `scope` parameter's equivalent caller update (see that review's Addendum). It doesn't violate the downward-only import direction — T2 (repository) correctly owns the signature change, and T4 (service) is the right task to own the caller update — the concern is purely that T4's row doesn't say so explicitly, leaving an interim state where `mypy` on `service.py` would fail until someone makes this edit, with no task row naming who.

## Risk Realism

None found. The plan's Risks section directly addresses `AGENTS.md` §4's migration-hazard framing (explicitly reasons the migration is purely additive, no expand→migrate→contract needed), names FR-7's atomicity as a specific TOCTOU hazard with a concrete single-statement mitigation, separately calls out the 10-second grace-window race-vs-reuse distinction as its own risk (not folded generically into "atomicity"), and treats the five-step check-order as the story's highest-severity risk with a mechanically-checkable mitigation (a unit test asserting the OD-5 ordering via a token crafted to hit two conditions at once) — a more specific analysis than a boilerplate list, matching the bar US-006's plan review set.

## Test-Strategy Realism

None found. The Testing Strategy section names exactly which behaviors are unit-tested with hand-written fakes (all six `rotate_refresh_token()` branches, including the check-order interaction and the rate-limit-before-lookup ordering) versus integration-tested against real Postgres+Valkey (RT-AC1–RT-AC6, with an explicit "genuine concurrency test" for RT-AC6 rather than a single-request approximation, plus a dedicated `429` test), consistent with `AGENTS.md` §5's split.

## Scope Creep

None found. Every file in Files To Create/Files To Modify traces to a specific impact-analysis item; the one architectural decision made at this stage (updating login's `authenticate_user` call site to also pass `ip`/`user_agent`) was already flagged as an explicit deferred item by `US-007-db-design.md`, not invented here.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage and correct layering order (no AGENTS.md §3 violation), with realistic risk and test-strategy sections — none of these block implementation. The one [Low] finding (T4's missing explicit ownership of the pre-existing `create_auth_audit_log_entry` caller updates) should be fixed by naming it in T4's task row, same fix pattern as US-006's own addendum, but is minor enough not to force a Fail.

## Addendum — resolved 2026-09-01

The [Low] Layering Order finding was fixed directly in `docs/plans/US-007-task-breakdown.md`: T4's Files Touched column now explicitly names the login/logout flows' pre-existing `create_auth_audit_log_entry` call-site updates as part of T4's scope, and its Verification Command adds an explicit mypy check confirming every call site (old and new) passes `severity`. No other change was needed. Verdict remains Pass with Issues at the top of this report (reflecting the state at initial review); with this fix applied, no open finding remains.
