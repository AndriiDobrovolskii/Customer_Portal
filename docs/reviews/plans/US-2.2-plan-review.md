# Plan Review: US-2.2 Logout

**Story ID:** US-2.2
**Plan Reviewed:** docs/plans/US-2.2-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-2.2-task-breakdown.md
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown cover every item `docs/impact-analysis/US-2.2-impact-analysis.md` identified, the task sequence respects AGENTS.md §3's layering direction with no violations, and both the Risks and Testing Strategy sections are concrete rather than generic. Verdict is Pass with Issues rather than a clean Pass because of one [Low] ordering ambiguity: T1's parenthetical note about updating `create_auth_audit_log_entry`'s existing caller crosses into T3's file (`service.py`), and the task breakdown doesn't say explicitly which task owns that edit.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `models.py` — `RefreshToken.revoked_at`, index `family_id` | Covered | Files To Modify; Task T1 | — |
| `models.py` — `AuthAuditLog.scope` | Covered | Files To Modify; Task T1 | — |
| `models.py` — `UserSession` no change | Covered | Architectural Changes ("No new... module"); implicitly absent from Files To Modify, consistent with "no change" | — |
| `schemas.py` — no change | Covered | Plan states explicitly: "`app/modules/users/schemas.py`... are **not modified**" | — |
| `repository.py` — `revoke_session(jti)` (new) | Covered | Files To Modify; Task T1 | — |
| `repository.py` — `get_refresh_token_by_hash(token_hash)` (new) | Covered | Files To Modify; Task T1 | — |
| `repository.py` — `revoke_refresh_token_family(family_id)` (new) | Covered | Files To Modify; Task T1 | — |
| `repository.py` — `create_auth_audit_log_entry` signature change | Covered | Files To Modify; Task T1 | See Layering Order note below — the *caller* update (in `service.py`) isn't explicitly assigned |
| `service.py` — `logout()`, `logout_all()` (new) | Covered | Architectural Changes; Files To Modify; Task T3 | — |
| `service.py` — `get_authenticated_user(allow_revoked=...)` | Covered | Architectural Changes; Files To Modify; Task T3 | — |
| `router.py` — `POST /auth/logout`, `POST /auth/logout-all` (new routes) | Covered | Files To Modify; Task T4 | — |
| `dependencies.py` — `get_current_user_allow_revoked` (new) | Covered | Architectural Changes; Files To Modify; Task T4 | — |
| `exceptions.py` — no change | Covered | Plan states explicitly: "`exceptions.py` are **not modified**" | — |
| Migration — `refresh_tokens.revoked_at`, `ix_refresh_tokens_family_id`, `auth_audit_log.scope` | Covered | Files To Create; Task T2 | — |
| Cross-module ripple — none | Covered | Architectural Changes: "no cross-module call is introduced" | Consistent with impact analysis's "None" finding |
| Test surface — `test_users_service.py` (extend) | Covered | Files To Modify; Task T5 | — |
| Test surface — `test_users_router.py` (extend) | Covered | Files To Modify; Task T6 | — |
| Test surface — `account`/other modules unaffected | Covered | Plan doesn't list any `account` file; consistent with impact analysis's "Not Affected" note | — |

## Layering Order (Task Breakdown)

- **[Low] T1's caller-update note crosses into T3's file without an explicit task assignment.** Task T1 (data-layer-builder) lists `create_auth_audit_log_entry` gaining a `scope` parameter, with the parenthetical "update its one existing call site's callers to pass `scope=None` where needed." That existing call site lives in `app/modules/users/service.py` (US-2.1's login flow) — a `service.py` layer file, which is T3's (service-and-router-builder) file, not T1's (data-layer-builder's `repository.py`). T1's own "Files Touched" column correctly lists only `models.py`/`repository.py`, so the parenthetical is ambiguous about who actually makes the `service.py` edit and when. This doesn't violate the downward-only import direction (data-layer-builder editing `service.py` would actually be the wrong direction if T1 did it) — the concern is purely that the task breakdown doesn't say T3 is responsible for it, leaving a gap between "T1 changes the signature" and "something updates the caller," with an interim state where `mypy` on `service.py` would fail until T3 lands (expected and acceptable mid-sequence per the plan's own Risks section, but the *ownership* of the fix should be explicit in T3's task row, not left implicit).

## Risk Realism

None found. The plan's Risks section directly addresses AGENTS.md §4's migration-hazard framing (explicitly reasons that expand→migrate→contract doesn't apply here because the migration is additive-only, rather than a generic "should be fine" placeholder), names a concurrency non-issue with justification (idempotent `revoked_at` overwrite needs no CAS guard), and — notably — treats the `allow_revoked` leniency-leak risk as this story's actual highest-severity concern with a concrete, mechanically-checkable mitigation (a separate dependency function, verified by T4's grep-for-single-importer check). This is a more specific risk analysis than a boilerplate list.

## Test-Strategy Realism

None found. The Testing Strategy section names exactly which behaviors are unit-tested with hand-written fakes (`logout`/`logout_all` branches, the `allow_revoked` unknown-vs-revoked distinction) versus integration-tested against real Postgres+Valkey (the five LO-ACs, the `/logout-all` no-leniency check, the lookup-miss branch), consistent with AGENTS.md §5's split. It also correctly reasons about coverage floor scope, noting this story's lower branch count relative to US-2.1's `authenticate_user`.

## Scope Creep

None found. Every file in Files To Create/Files To Modify traces to a specific impact-analysis item; no task in the breakdown introduces a file or change the impact analysis didn't already name.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage and correct layering order (no AGENTS.md §3 violation), with realistic risk and test-strategy sections — none of these block implementation. The one [Low] finding (T1/T3 boundary ambiguity for the `create_auth_audit_log_entry` caller update) should be resolved by making T3's task row explicitly note the `service.py` login-flow call site update, but is minor enough not to force a Fail.

## Addendum — resolved 2026-08-31

The [Low] Layering Order finding was fixed directly in `docs/plans/US-2.2-task-breakdown.md`: T3's Files Touched column now explicitly names the login-flow `create_auth_audit_log_entry` call-site update as part of T3's scope, and its Verification Command adds an explicit mypy check confirming every call site (old and new) passes `scope`. No other change was needed. Verdict remains Pass with Issues at the top of this report (reflecting the state at initial review); with this fix applied, no open finding remains.
