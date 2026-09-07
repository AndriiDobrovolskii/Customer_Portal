---
artifact_type: plan_review
story: US-5.1
version: 1
status: ARCHIVED
created_at: "2026-09-07T19:00:00Z"
updated_at: "2026-09-07T19:15:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.1-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
supersedes: null
---

# Plan Review: Authentication & Session Management (Frontend)

**Story ID:** US-5.1
**Plan Reviewed:** docs/plans/US-5.1-implementation-plan.md (v1)
**Task Breakdown Reviewed:** docs/plans/US-5.1-task-breakdown.md (v1)
**Reviewed:** 2026-09-07
**Overall Verdict:** Pass with Issues

## Summary

The implementation plan and task breakdown together give complete, traceable coverage of every affected-file group `impact-analyzer` named for this frontend-only Story: the first-ever `frontend/` scaffold, the `api/`/`store/` layers, routing/guards/layouts, all seven screens, shared UI, and the wholly-new test infrastructure. The task breakdown's 17-task sequence respects `AGENTS.md` §3's Frontend layer table's downward-only direction (`api/`/`store/` before `hooks/`, `hooks/` before `screens/`) with no ordering violation. Risk coverage is unusually thorough — every one of the nine Open Decisions is either designed around (the single-flight refresh coordinator for OD-2/OD-3, the error-normalization branch for OD-4) or explicitly named as a pre-`IMPLEMENTATION` sign-off gate (the `react-router-dom` and a11y-check dependencies) rather than silently assumed. Verdict is "Pass with Issues," not a clean Pass, because of two minor, non-blocking gaps: one file (`layouts/AppShell.tsx`) is planned to host logic (the logout/logout-all control) that arguably needs a `hooks/` import the `AGENTS.md` §3 Frontend table does not explicitly authorize for the `routes/ (guards + layout)` row, and impact-analysis's own implied "one full FR-2 login flow, one full FR-3 MFA flow" end-to-end test has no task/file naming it in the breakdown.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx` | Covered | Files To Create → Project scaffold / build config; Task T1 | Plan adds `App.tsx`, `vite-env.d.ts`, `tsconfig.node.json`, `.eslintrc.cjs`/`.prettierrc` — standard scaffold boilerplate implied by "stand up the React+Vite+TS stack," not scope creep. |
| `vite.config.ts` dev-server proxy (OD-1 gated) | Covered | Files To Create scaffold bullet 2; Risk 2; Task T1 | Plan fixes a same-origin `server.proxy` default and explicitly documents what changes if OD-1 resolves toward a backend CORS change instead. |
| `frontend/src/api/httpClient.ts` | Covered | Files To Create → API-client layer; Task T2 | — |
| `frontend/src/api/authApi.ts` | Covered | Files To Create → API-client layer; Task T2 | — |
| `frontend/src/api/errorNormalization.ts` | Covered | Files To Create → API-client layer; Architectural Change 8; Task T2 | Register's two non-RFC7807 shapes (OD-4) explicitly branched, not deferred. |
| `frontend/src/api/refreshCoordinator.ts` (OD-2/OD-3 gated) | Covered | Architectural Change 3; Files To Create; Task T2 (unit), Task T6 (integration) | Single-flight design fixed regardless of how OD-2 resolves; OD-3 (proactive refresh) explicitly out of scope by design, not silently dropped. |
| `frontend/src/auth/authStore.ts` (→ `store/authStore.tsx`) | Covered | Architectural Change 4; Files To Create → Auth state layer; Task T3 | React Context chosen over a new store dependency (Zustand), justified against `AGENTS.md` §7.8. |
| `frontend/src/auth/queryClient.ts` (→ `store/queryClient.ts`) | Covered | Files To Create → Auth state layer; Task T3 | — |
| `frontend/src/routes/ProtectedRoute.tsx` | Covered | Files To Create → Routing/guards/layout; Task T7 | — |
| `frontend/src/routes/GuestOnlyRoute.tsx` | Covered | Files To Create → Routing/guards/layout; Task T7 | — |
| `frontend/src/layouts/AuthLayout.tsx` | Covered | Files To Create → Routing/guards/layout; Task T7 | Closes the v1 spec-review Major finding, as the plan itself notes. |
| `frontend/src/layouts/AppShell.tsx` (placeholder) | Covered, with a layering note | Files To Create → Routing/guards/layout; Task T7 | See Layering Order finding below — hosting the logout/logout-all control here implies a `hooks/` import this layer's `AGENTS.md` §3 row does not explicitly list. |
| `frontend/src/pages/*.tsx` (7 screens) | Covered | Files To Create → Screens; Tasks T9–T15 | Deliberately renamed `pages/` → `screens/` (Architectural Change 2) to match `AGENTS.md` §3 and keep `.pre-commit-config.yaml`'s `frontend-vi-mock-in-integration-tests` hook scoped correctly — an improvement over impact-analysis's illustrative naming, not a deviation from its intent. |
| A logout/logout-all trigger | Covered | Files To Create → `layouts/AppShell.tsx`; Task T7's verification command | Impact-analysis left placement as an `ARCHITECTURE_PLANNING` call; plan resolves it into `AppShell.tsx` — see Layering Order note. |
| An MFA-enrollment-deadline banner component | Covered | Files To Create → Shared components (`MfaEnrollmentBanner.tsx`); Task T8 | Copy/dismissal content correctly left pending OD-7, structure fixed. |
| Per-screen form + validation-schema pairs | Covered, different grouping | Architectural Change 7; Files To Create → Screens; Testing Strategy (Unit) | Plan folds form/validation logic into each screen's own `useForm` rules rather than separate form files — an explicit, justified architectural choice (avoids a schema-resolver dependency, per Assumption #1/`AGENTS.md` §2), not an omission. |
| A generic error-state component (`ErrorState.tsx`) | Covered | Files To Create → Shared components; Task T8 | — |
| A field-level error renderer (`FieldError.tsx`) | Covered | Files To Create → Shared components; Task T8 | — |
| Cross-repo edge: `authApi.ts` → backend `/auth/*` | Covered | Architectural Changes 1–3; Files To Create → API-client layer | — |
| Browser's automatic `httpOnly` cookie handling | Covered | Architectural Changes 3, 5; NFR discussion throughout | Gated on OD-1 as impact-analysis itself notes; not resolved, correctly carried forward as Risk 2. |
| Migration / Schema Impact: **None** | Covered (N/A) | Files To Modify: "None" | Consistent — plan makes zero backend file changes, matching `DB_DESIGN`'s `NOT_APPLICABLE`. |
| FE-AC1–3, FE-AC5–7 component/integration tests (MSW) | Covered | Testing Strategy (Integration); Tasks T9–T15; `test/mswHandlers.ts` (Task T4) | — |
| FE-AC6 dedicated list+revoke test | Covered | Testing Strategy (Integration); Task T14 | Revoke-affordance behavior explicitly asserted per the OD-6 default in force, not left implicit. |
| FE-AC4 dedicated 401-mid-session integration test | Covered | Testing Strategy (Integration); Task T6 (`refreshCoordinator.integration.test.tsx`) | Task breakdown's own Notes section flags this file's path as the breakdown's placement, not plan-fixed — appropriately surfaced, not hidden. |
| FE-AC8 form-level unit tests | Covered | Testing Strategy (Unit); Tasks T9, T13 (validation cases), Task T2 hook tests | Explicit test that server-only checks (breach, differs-from-current) are *not* simulated client-side. |
| FE-AC9 problem+json / Register-special-case tests | Covered | Testing Strategy (Unit + Integration); Task T2 (`errorNormalization.test.ts`) | — |
| FE-AC10 route-guard tests | Covered | Testing Strategy (Integration); Tasks T7, T16 | — |
| FE-AC11 network/5xx tests | Covered | Testing Strategy (Integration); Tasks T9–T15 | — |
| a11y-bar automated check | Covered, flagged pending sign-off | Risk 1 / Architectural Change 9; Task breakdown Notes (gates a11y assertion inside T9–T15) | Correctly named as a new dependency requiring `AGENTS.md` §7.8 sign-off, not silently added — same treatment as `react-router-dom`. |
| Implied full FR-2 login-flow / FR-3 MFA-flow end-to-end test | **Partially covered** | Testing Strategy (Integration, individual per-screen/per-route rows only) | No task or file names a single continuous multi-screen flow test (login → placeholder-home; MFA-challenge → verify → placeholder-home). Impact-analysis itself hedged this as "beyond the Matrix's per-AC rows, but implied," and no Enforcement Matrix row requires it — see Test-Strategy Realism finding below; not escalated to a blocking gap. |
| OD-1 (CORS) blast-radius-altering finding | Covered / carried forward | Risk 2 | Explicitly not resolved, correctly flagged as conditionally invalidating the plan's zero-backend-file-change premise. |
| OD-4 (Register's non-uniform error shapes) finding | Covered / carried forward | Architectural Change 8; Risk 5 | Absorbed into `errorNormalization.ts`'s design regardless of how OD-4 resolves. |

## Layering Order (Task Breakdown)

- **[Low] `AppShell.tsx`'s logout control may need a `hooks/` import the `routes/ (guards + layout)` row doesn't list** — Task T7 (`layouts/AppShell.tsx`) is verified in part by "Log out calls `useLogout`/`POST /auth/logout` ... Log out everywhere calls `useLogoutAll`" (task_breakdown, T7's Verification Command). `AGENTS.md` §3's Frontend table gives `routes/ (guards + layout)` "May import: store (to check auth), layout components" and does not list `hooks/` — `hooks/` import is only explicitly authorized for `screens/`, `components/`. This is not a sequencing violation (T7 depends on T3 `store/` and T5 `hooks/`, both built earlier, so the downward-only *order* is respected) but it is a categorization ambiguity worth resolving before `IMPLEMENTATION`: either treat `AppShell.tsx`'s interactive logout control as a `components/`-layer child component consumed by the layout (clearly authorized), or confirm that "layout components" in the table's `routes/` row is meant to include this case. Not escalated to Fail because the dependency graph itself has no ordering defect and `AGENTS.md` §3 states there is no `lint-imports` equivalent yet — this is exactly the class of thing that section says "is on you" to check by reading the diff, which `implementation-verifier`/`security-reviewer` will still do downstream.

## Test-Strategy Realism

- **[Low] No task/file names the implied full-flow (multi-screen) integration test** — impact-analysis's Test-Surface Impact section names "an end-to-end or integration-level test path ... exercising at least one full FR-2 login→placeholder-home flow and one FR-3 MFA-challenge→verify flow ... beyond the Matrix's per-AC rows, but implied by their combination." The plan's Testing Strategy and the task breakdown's T9–T16 verification commands test each screen and each route guard individually (e.g., T10 tests `LoginScreen.test.tsx` in isolation, T16 tests `AppRoutes.test.tsx`'s two redirect directions) but none is phrased as a single continuous flow spanning login submission through landing on the placeholder home, or MFA challenge through verify through landing. Since impact-analyzer itself flagged this as implied rather than Enforcement-Matrix-mandated, this is not forced to Fail — but `test-writer` at `TEST_WRITING` should explicitly decide whether the per-screen/per-route tests already satisfy this implied need or whether a dedicated flow test is still owed.

## Verdict Rationale

No impact-analysis item is Missing from the plan, and the task breakdown's dependency sequencing contains no violation of `AGENTS.md` §3's Frontend downward-only direction, so this stage's harness verdict is `PASS` rather than `CHANGES_REQUIRED`/`BLOCKED`. The verdict carries two Low-severity, non-blocking findings (an import-layer categorization question for `AppShell.tsx`, and an implied end-to-end test not yet named as its own task) rather than being a clean Pass, consistent with "Pass with Issues, but no missing coverage or ordering violation" under this skill's own rubric.
