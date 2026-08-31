# Plan Review: US-2.1 Login

**Story ID:** US-005 (spec/plan's own Story ID field; the backlog story is filed as US-2.1)
**Plan Reviewed:** docs/plans/US-005-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-005-task-breakdown.md
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass with Issues (both findings fixed same-day — see each finding's status)

## Summary

Every item `impact-analyzer` identified — including the `refresh_tokens` table added mid-PLANNING via resolved OD-9 — is covered in the plan's Files To Create/Modify, and the task breakdown's dependency chain respects `AGENTS.md` §3's layering direction with no violations. Two Low-severity issues keep this from a clean Pass: T4's "Depends On" column omits an explicit link to T2 (the data-layer task its own dependency T3 already requires), and the plan's Risks section doesn't state the throttle-counter increment's concurrency behavior explicitly, unlike this project's own precedent (US-004 named its concurrent-deactivation atomicity as its own risk item). Neither blocks implementation.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `models.py` (User.last_login_at, AuthAuditLog) | Covered | Files To Modify | |
| `models.py` / db-design addendum: `RefreshToken` (resolved OD-9) | Covered | Files To Modify, Architectural Changes | Correctly folded in after the impact-analysis's own mid-survey finding. |
| `schemas.py` (LoginRequest/LoginResponse) | Covered | Files To Modify | |
| `repository.py` (last_login_at update, AuthAuditLog insert) | Covered | Files To Modify | |
| `repository.py` (RefreshToken insert, resolved OD-9) | Covered | Files To Modify | |
| `cache.py` (new, throttle counters) | Covered | Files To Create | |
| `service.py` (authenticate_user rework) | Covered | Files To Modify, Architectural Changes | |
| `exceptions.py` (InvalidCredentialsError→ProblemError; AccountDeactivatedError; TooManyAttemptsError) | Covered | Files To Modify, Architectural Changes | |
| `router.py` (request_id, client-IP, Set-Cookie) | Covered | Files To Modify | |
| `dependencies.py` (cache gateway injection) | Covered | Files To Modify | |
| `app/core/security.py` (dummy-hash; refresh-token generation) | Covered | Files To Modify, Architectural Changes | |
| `app/core/config.py` (throttle + refresh-TTL settings) | Covered | Files To Modify | |
| `app/core/cache_keys.py` (new key helpers) | Covered | Files To Modify | |
| `app/main.py` (remove bespoke handler) | Covered | Files To Modify | |
| Migration (users.last_login_at, auth_audit_log, refresh_tokens) | Covered | Files To Create | |
| `tests/unit/modules/users/test_users_service.py` (extend) | Covered | Files To Modify, Testing Strategy | |
| `tests/integration/modules/users/test_users_router.py` (extend) | Covered | Files To Modify, Testing Strategy | |
| New Valkey fixture for throttle-counter tests | Covered | Testing Strategy | Correctly identifies the existing US-004 Valkey testcontainer fixture as reusable — no new fixture needed, consistent with the impact analysis's own note. |

No impact-analysis item is Missing or Partially Covered.

## Layering Order (Task Breakdown)

- **[Low, fixed 2026-08-31] T4's "Depends On" omitted T2, though T3 (its listed dependency) already required T2.** Task T4 (service-and-router-builder, service) lists `Depends On: T1, T3, T0c`. T3 (migration-manager) itself depends on T2 (data-layer-builder), so T4's dependency on T2 is only transitive through T3, not stated directly — unlike this project's own precedent in `US-004-task-breakdown.md`'s T6, which explicitly lists both its data-layer task (T3) and its migration task (T5) even though T5 already depends on T3. This doesn't cause an actual ordering violation (T2 will always complete before T4 regardless), but it's a completeness inconsistency worth tightening for a reader scanning the table without tracing transitive chains.

## Risk Realism

- **[Low, fixed 2026-08-31] Throttle-counter increment concurrency was not addressed.** The plan's Risks section covers ordering regression, throttle-check placement relative to Argon2id cost, migration risk, the `InvalidCredentialsError` handler removal, and dummy-hash cost drift — but says nothing about what happens when two concurrent failed-login requests for the same account increment `login_fail:account:{user_id}` at once. This project has direct precedent for naming this kind of thing explicitly: `US-004-implementation-plan.md`'s Clarification #2 treats concurrent-deactivation atomicity as its own named risk, and `US-2.3-refresh-token.md`'s RT-AC6 calls a similar race "the requirement, not an implementation detail." Likely a non-issue in practice (Valkey's `INCR` is atomic by design, so a naive increment-based counter is safe without extra locking), but the plan should say so explicitly rather than leave it unaddressed, so `service-and-router-builder`/`test-writer` don't have to independently re-derive that the counter gateway must use `INCR` rather than a read-then-write pair.

## Test-Strategy Realism

No issues found. The Testing Strategy section names the unit/integration split explicitly (hand-written fakes for `UserRepositoryProtocol`/the cache gateway/`RevocationCacheReaderProtocol` in unit tests; real Postgres+Valkey via `AsyncClient`/`ASGITransport` in integration), lists a concrete test case per FR branch including the two OD-resolution-driven cases (OD-5's per-IP-counter-not-reset, OD-8's empty-password-422), and states the coverage floor. This is specific enough to act on directly.

## Scope Creep

None found. `.env.example`'s inclusion in Files To Modify isn't named by `impact-analyzer` explicitly, but it traces directly to `AGENTS.md` §6.7 ("`.env.example` updated") applied to the new settings the impact analysis's own `config.py` bullet already identifies as needed — not an unsupported addition.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage with no layering-order violation, so this does not rise to Fail. Both Low findings (an incomplete dependency listing; an unstated concurrency assumption) were fixed directly in `docs/plans/US-005-task-breakdown.md` (T4's Depends On now includes T2) and `docs/plans/US-005-implementation-plan.md` (new Risks bullet naming Valkey `INCR` as the required atomic-increment mechanism) immediately after this review, rather than carried forward as open debt. Clear to proceed into TESTS/IMPLEMENTATION.

## Addendum — OD-10 amendment, reviewed 2026-08-31

**Trigger:** after this review, an `advisor()` consultation during the PLANNING→IMPLEMENTATION handoff found FR-4's reactivation gap (OD-10) plus two implementation bugs (deactivation-gate logic; the validation-error handler's non-problem+json shape). The user resolved OD-10 (build reactivation now); the plan, task breakdown, impact analysis, API design, and DB design were all amended accordingly (each carries its own dated addendum).

**Re-check against this review's own criteria:**
- **Impact-analysis coverage:** the amendment added `app/modules/account/service.py`/`repository.py` to impact-analysis's affected-file list, and both now appear in the plan's Files To Modify (T4b/T2b) — coverage remains complete.
- **Layering order:** the new tasks T2b (data-layer-builder, `account/repository.py`) → T4b (service-and-router-builder, `account/service.py`) → T4 (depends on T4b) → T5 correctly sequence the new cross-module dependency; T9 (gate-enforcer)'s Depends On was updated to include T2b/T4b/T6b. No violation introduced.
- **Risk realism:** the plan's Amendments/Risks sections now name reactivation's own concurrency hazard (mirroring `deactivate_if_not_already`'s existing atomic-conditional-update pattern) explicitly — not left implicit.
- **Scope creep:** none — every addition traces to OD-10 (a resolved user decision) or to a confirmed pre-existing bug (deactivation-gate logic, validation-handler shape), both disclosed with citations rather than silently introduced.

**Verdict unchanged:** Pass with Issues stands; this addendum does not introduce a new blocking finding.
