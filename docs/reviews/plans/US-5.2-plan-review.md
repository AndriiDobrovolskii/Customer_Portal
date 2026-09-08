---
artifact_type: plan_review
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T00:00:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.2-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: null
---

# Plan Review: Account & Profile Self-Service (Frontend)

**Story ID:** US-5.2
**Plan Reviewed:** docs/plans/US-5.2-implementation-plan.md (version 1)
**Task Breakdown Reviewed:** docs/plans/US-5.2-task-breakdown.md (version 1)
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Summary

The implementation plan and task breakdown were checked against the approved spec (v2, APPROVED), the spec review (v2, APPROVED), the impact analysis (v1, DRAFT, PASS), and AGENTS.md §3/§4/§5's Frontend subsections. Every affected-file item the impact analysis named has a corresponding entry in the plan's Files To Create/Files To Modify. The task breakdown's ordering (T1 `api/`/T2 `store/`/T3 `components/` helper → T4 `hooks/` → T5 `components/` new UI → T6-T10 `screens/` → T11 `routes/` → T12 `components/` banner link → T13 gate) respects AGENTS.md §3's Frontend downward-only layer direction with no violation found. Risk and test-strategy sections are concrete rather than placeholder ("testing will catch it") language, and correctly cover the frontend-analogue of the concurrent-401 race (by explicitly reusing `httpClient.ts`'s existing `performRequest` internals unchanged, Risk 6) plus every blast-radius-altering Open Decision (OD-3, OD-6, OD-7) the impact analysis flagged. The new QR-rendering dependency (candidate `qrcode.react`) and its required AGENTS.md §7.8 human sign-off are surfaced clearly and consistently across the plan (Change 9, Risk 2, Validation Strategy) and the task breakdown (T5 explicitly marked blocked; a dedicated Notes entry), so `HUMAN_PLAN_APPROVAL` has what it needs to act on it. One minor documentation gap (queryClient.ts's placement decision) is noted as non-blocking.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `frontend/src/api/httpClient.ts` (add header-exposing verb) | Covered | Architectural Change 1; Files To Modify | Additive `httpPatch<T>` only; existing verbs untouched, matching impact analysis's stated constraint. |
| `frontend/src/api/types.ts` (new DTOs) | Covered | Architectural Change 5; Files To Modify | |
| `frontend/src/api/profileApi.ts` (new) | Covered | Architectural Change 5; Files To Create | |
| `frontend/src/api/mfaApi.ts` (new) | Covered | Architectural Change 5; Files To Create | |
| `frontend/src/api/accountApi.ts` (new) | Covered | Architectural Change 5; Files To Create | |
| `frontend/src/components/apiErrorHelpers.ts` (status-exposing helper) | Covered | Architectural Change 4; Files To Modify | |
| `frontend/src/hooks/useProfileUpdate.ts` (new) | Covered | Architectural Change 3; Files To Create | |
| `frontend/src/hooks/useConfirmEmailChange.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useVerifyEmail.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useResendVerificationEmail.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useMfaEnroll.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useMfaActivate.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useMfaDisable.ts` (new) | Covered | Files To Create | |
| `frontend/src/hooks/useAccountDeactivate.ts` (new) | Covered | Files To Create | |
| `frontend/src/store/queryClient.ts` (candidate ETag location) | Partially Covered (documented, not tabulated) | Architectural Change 2 | Impact analysis left this an open placement decision. The plan resolves it (a dedicated non-fetching query key on the existing client; file itself not edited) but does not list `queryClient.ts` in the "Not modified, confirmed" enumeration alongside the other checked-not-affected files. Substance is covered; formal traceability is thin. See Non-Blocking Findings. |
| `frontend/src/screens/ProfileScreen.tsx` (new) | Covered | Files To Create | |
| `frontend/src/screens/EmailVerificationScreen.tsx` (new) | Covered | Files To Create | |
| `frontend/src/screens/SecurityScreen.tsx` (new) | Covered | Files To Create; Architectural Change 6 | |
| `frontend/src/screens/DeactivateAccountScreen.tsx` (new) | Covered | Files To Create | |
| `frontend/src/components/MfaEnrollmentBanner.tsx` (link into enrollment) | Covered | Files To Modify | Additive-only, existing dismiss/test coverage preserved per Risk 7. |
| `frontend/src/components/RecoveryCodesDisplay.tsx` (new) | Covered | Files To Create | |
| Bundled QR-rendering component (new) | Covered | Architectural Change 9; Files To Create (`QrCode.tsx`) | New dependency correctly flagged for §7.8 sign-off rather than silently added. |
| `frontend/src/routes/AppRoutes.tsx` (new routes) | Covered | Architectural Change 10; Files To Modify | |
| `frontend/package.json` (new QR dependency) | Covered | Architectural Change 9; Files To Modify | Sign-off gate stated explicitly (Risk 2, Validation Strategy). |
| `frontend/src/components/MfaEnrollmentBanner.test.tsx` (existing test, additive) | Covered | Testing Strategy; task breakdown T12 | |
| `frontend/src/routes/AppRoutes.test.tsx` (existing test, additive) | Covered | Testing Strategy; task breakdown T11 | |
| `frontend/src/test/mswHandlers.ts` (baseline handlers) | Covered | Testing Strategy ("New test infrastructure"); task breakdown T1 note | Explicitly bundled into T1 rather than a separate task, with rationale stated. |
| `httpClient.ts`'s own missing test file | Covered | Testing Strategy (Unit); task breakdown T1 | New `httpClient.test.ts` named explicitly. |
| New screen/hook/component test files (net-new) | Covered | Testing Strategy; task breakdown T4-T10 | |
| a11y test pass on Profile/Security/DeactivateAccount screens | Covered | Testing Strategy; task breakdown T6, T9, T10 | |
| `frontend/src/store/authStore.tsx`, `useLogin.ts`, `useMfaVerify.ts` — impact analysis scored "not affected" | Covered, with an explicit, justified correction | Architectural Change 6; Files To Modify; Risk 1 | The plan explicitly documents overturning impact analysis's "not affected" finding (FR-5/FR-6 need a real MFA-status signal; a naive default risks silently overwriting an already-enrolled user's TOTP secret, per direct reading of `service.py`'s `enroll_mfa`). This is a traced, reasoned extension, not undocumented scope creep. |
| `ConfirmEmailChangeScreen.tsx` — not named in impact analysis's illustrative screens list | Covered, with an explicit, justified addition | Files To Create | Plan states directly: "Addition beyond `impact_analysis`'s illustrative screens list" — justified because `useConfirmEmailChange.ts` (already in the survey) needs a rendering target, and traces to FR-3/spec Traceability Matrix. |

No impact-analysis item was found Missing from the plan.

## Layering Order (Task Breakdown)

No violation found. `T1` (`api/`) and `T2` (`store/`) have no dependencies and both precede `T4` (`hooks/`), which correctly depends on `T1, T2` — matching AGENTS.md §3 Frontend table's `hooks/` row ("May import: `api/`, store, TanStack Query"). `T3` (`components/` shared helper) also has no dependency and precedes the screens (`T6`-`T10`) that consume it, consistent with `screens/`'s row ("May import: hooks, store (read-only), shared UI components"). `T5` (`components/` new UI) has no dependency and is correctly flagged parallel-eligible. `T6`-`T10` (`screens/`) each depend only on the subset of `T1`-`T5` they actually need, never on each other, and all precede `T11` (`routes/`), which needs the screen components to exist before `AppRoutes.tsx` can reference them. `T12` (banner link, `components/`) correctly depends on `T11` since the link target route must exist first. `T13` (gate-enforcer) depends on `T1`-`T12`, correctly sequenced last.

## Risk Realism

No gap found. Risk 6 explicitly addresses the frontend analogue of the concurrent-401/single-in-flight-refresh race by keeping `performRequest`'s existing 401→refresh→retry internals untouched and additive-only — the correct mitigation for a story that does not need to change that mechanism. Risks 1, 4, and 5 concretely cover the three Open Decisions (OD-5's MFA-status-signal gap, OD-6/OD-7's content-not-existence gating, OD-3's non-blocking scope) the impact analysis's "Notes for Downstream Stages" flagged as blast-radius-altering. Risk 2 states the new-dependency sign-off requirement plainly, not buried in prose. Risks 3, 7, 8, 9 are specific and each names the exact hazard (OD-1 wording breadth, banner test regression, sensitive-value storage, guard-shape routing) rather than a generic placeholder.

## Test-Strategy Realism

No gap found. The Testing Strategy section names the unit/integration split precisely per AGENTS.md §5's Frontend subsection (Vitest unit for hooks/pure functions and validation rules; RTL+MSW integration per screen; no `vi.mock()` of the unit under test; 85% coverage floor via `test:coverage`, CI-enforced) and enumerates concrete assertions per AC (e.g., PS-AC2's four ETag branches, PS-AC5/PS-AC6's enroll-vs-disable branch distinguished by `authStore.mfaEnabled`, the two-direction guard assertions for `/verify-email` and `/confirm-email-change`). This is actionable, not vague.

## Scope Creep

None found. The two additions beyond impact analysis's literal item list (`ConfirmEmailChangeScreen.tsx`; the `authStore.tsx`/`useLogin.ts`/`useMfaVerify.ts` correction) are each explicitly flagged as such in the plan's own text and traced to a specific FR/AC (FR-3; FR-5/FR-6/PS-AC6) rather than invented or left implicit.

## Non-Blocking Findings

- **[Low] `frontend/src/store/queryClient.ts`'s placement decision is resolved in prose (Architectural Change 2) but not tabulated.** Impact analysis explicitly flagged this file as a candidate location requiring a planner decision. The plan makes that decision (use the existing `QueryClient` instance's cache via a dedicated non-fetching query key; the file itself is not edited) but does not add `queryClient.ts` to the "Not modified, confirmed by `impact_analysis`'s 'Checked — Not Affected' section" list the way it does for `errorNormalization.ts`, `ErrorState.tsx`, etc. Recommend `implementation_plan`'s next revision (if any) add `queryClient.ts` to that confirmation list for a complete formal trace, though this does not block `IMPLEMENTATION` since the substantive decision is already made and unambiguous.

## Verdict Rationale

Full impact-analysis coverage (one item resolved in prose but not formally tabulated, logged as a Low non-blocking finding rather than Missing/Partially Covered), correct AGENTS.md §3 Frontend layering order throughout the task breakdown, concrete and AGENTS.md §4/§5-aligned risk and test-strategy sections, and no undocumented scope creep — all of which meet the bar for PASS. The new QR-rendering dependency and its required AGENTS.md §7.8 human sign-off are surfaced prominently and consistently (plan Change 9/Risk 2/Validation Strategy; task breakdown T5's explicit block and dedicated Notes entry), giving `HUMAN_PLAN_APPROVAL` a clear, unambiguous decision to make.
