# Plan Review: Multi-Factor Authentication / TOTP (US-2.5 / spec US-009)

**Story ID:** US-2.5 (spec US-009)
**Plan Reviewed:** docs/plans/US-009-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-009-task-breakdown.md
**Reviewed:** 2026-09-01
**Overall Verdict:** Pass with Issues

## Summary

The plan and task breakdown cover every file `US-009-impact-analysis.md` named, including resolving both of its open architectural tensions (enrolment-scoped-token mechanism, `mfa_token` mechanism) with clear, precedent-based rationale. Task ordering respects `AGENTS.md` §3's downward-only direction and the migration-before-model-use rule with no violations. Risk and test-strategy sections are concrete. Two issues keep this from a clean Pass: `app/api/v1/router.py`, which impact-analysis flagged as "likely no change — confirm at PLANNING," is never explicitly confirmed either way in the plan (silently omitted rather than stated), and the Risks section doesn't address the concurrency shape of the two new single-use Valkey primitives this story itself introduces (`mfa_token` `GETDEL`, the replay-protection key), despite `AGENTS.md` §4's concurrency-hazard expectation and this project's own precedent (US-012's plan review flagged the equivalent gap for FR-7's row-locking).

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/users/models.py` (4 new columns, `MfaRecoveryCode`) | Covered | Files To Modify; T2 | |
| `app/modules/users/schemas.py` | Covered | Files To Modify; T1 | |
| `app/modules/users/repository.py` | Covered | Files To Modify; T2 | |
| `app/modules/users/cache.py` | Covered | Files To Modify; T2 | |
| `app/modules/users/service.py` | Covered | Files To Modify; T5 | |
| `app/modules/users/exceptions.py` | Covered | Files To Modify; T5 | |
| `app/modules/users/router.py` | Covered | Files To Modify; T6 | |
| `app/modules/users/dependencies.py` | Covered | Files To Modify; T6 | |
| `app/core/security.py` | Covered | Files To Modify; T5 | Correctly placed under the service task per the corrected US-012 precedent (`app/core/*` is never `data-layer-builder`'s to touch). |
| New crypto utility | Covered | Architectural Change #4 (`app/core/crypto.py`); Files To Create; T5 | |
| `app/core/config.py` | Covered | Files To Modify; T5 | |
| `app/core/cache_keys.py` | Covered | Files To Modify; T5 | |
| `.env.example` | Covered | Files To Modify; T5 | |
| `app/modules/roles/models.py` (`granted_at`) | Covered | Files To Modify; T2b | |
| `app/modules/roles/repository.py` (`replace_for_user` write) | Covered | Files To Modify; T2b | |
| `app/modules/roles/service.py` (`get_role_names_for_user`) | Covered | Architectural Change #5, refined to `get_role_grants_for_user` returning name+`granted_at` pairs; Files To Modify; T4 | Legitimate refinement, not scope creep — impact-analysis itself flagged that whether the method needed to return `granted_at` too was undecided; the plan resolves it rather than leaving it open. |
| Open tension: enrolment-scoped-token mechanism | Covered | Architectural Change #2 (JWT claim, default-deny at `get_authenticated_user`, mirrors `get_current_user_allow_revoked`) | |
| Open tension: `mfa_token` mechanism | Covered | Architectural Change #3 (Valkey-backed opaque token, `GETDEL`) | |
| `app/api/v1/router.py` (impact-analysis: "likely none — confirm at PLANNING") | Covered (implicit) | Absent from Files To Modify | Never explicitly confirmed either way — see Layering Order/Scope note below. |
| Migration: 4 `users` columns, `mfa_recovery_codes`, `user_roles.granted_at` | Covered | Files To Create; T3 | |
| New unit/integration test files | Covered | Files To Create; T7, T8 | |
| Existing test files (`test_security.py`, `test_users_service.py`, `test_users_router.py`, `test_roles_service.py`, `test_roles_router.py`, `conftest.py`) | Covered | Files To Modify; T7, T8 | `test_roles_router.py` correctly absent — impact-analysis itself said "otherwise unaffected." |

## Layering Order (Task Breakdown)

No violation of `AGENTS.md` §3's downward-only direction or the migration-before-model-use rule was found. T1/T2/T2b parallel with no interdependency; T3 correctly gates on both T2 and T2b; T4/T5/T6 each state direct, traceable reasons for their dependencies (an improvement over US-012's T4, which the prior plan review flagged for an indirect-only dependency link — this task breakdown doesn't repeat that gap).

- **[Low] `app/api/v1/router.py` is neither confirmed unaffected nor assigned a task.** Impact-analysis explicitly asked for this to be "confirmed at PLANNING, not assumed" (its §2, last bullet). The plan's silence reads as an implicit "no change needed" (correct, most likely — `users.router` is already registered, per the plan's own module-extension framing), but nothing in `docs/plans/US-009-implementation-plan.md` or the task breakdown states this explicitly the way impact-analysis asked for. Not a layering violation — the sequence itself has no gap — but a traceability nit.

## Risk Realism

- **[Medium] No concurrency risk stated for the two new single-use Valkey primitives this story introduces.** The plan's Architectural Change #3 introduces `mfa_token` consumption via `GETDEL` and a replay-protection key (`mfa_used_step`), and Architectural Change #3 also describes a shared failed-attempt counter that deletes the `mfa_token` key on the 5th failure — but the Risks section never states the concurrency shape of these operations (e.g., two simultaneous `/verify` calls with the same `mfa_token`, one succeeding and one racing against the attempt-counter delete). `AGENTS.md` §4 calls out concurrency as a standard hazard category, and this project's own precedent (`docs/reviews/plans/US-012-plan-review.md`'s Risk Realism section — the FR-7 row-locking risk) treats a new single-use/atomicity mechanism as needing its own named concurrency risk, not just an implicit "Valkey handles it." `GETDEL`'s atomicity likely makes this benign (a genuine race resolves to "second caller sees no token," which is the correct single-use outcome), but the plan should say so rather than leave it unstated.

## Test-Strategy Realism

None found — Testing Strategy names the unit/integration split concretely (hand-written fakes for `enroll_mfa`/`activate_mfa`/`verify_mfa`/`disable_mfa`/`_resolve_enrollment_scoping` and `crypto.py`'s round-trip, vs. real-PostgreSQL+Valkey integration for all 7 MF-ACs plus the full enrolment-scoped-token flow end-to-end), per `AGENTS.md` §5. The plan also explicitly calls out the single most important test in the story (the default-deny check's both-directions coverage), which is a stronger-than-usual risk-to-test traceability link.

## Scope Creep

None found. Every planned file change and task traces to a specific impact-analysis item or a documented, precedent-cited resolution of one of impact-analysis's two open tensions.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage with no Missing/Partially-Covered items, and no layering-order violation — both Fail-forcing conditions are absent. The two findings above (the unconfirmed `app/api/v1/router.py` traceability nit, and the missing concurrency-risk statement for the new Valkey single-use primitives) are worth a quick fix before T5/T6 execute, consistent with how this project resolved the equivalent-severity findings in `US-012-plan-review.md`, but neither blocks implementation on its own.
