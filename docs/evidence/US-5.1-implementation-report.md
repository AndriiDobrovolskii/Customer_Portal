---
artifact_type: implementation_report
story: US-5.1
version: 1
status: DRAFT
created_at: "2026-09-07T06:47:57Z"
updated_at: "2026-09-07T06:47:57Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/tests/US-5.1-ac-test-matrix.md
    version: 1
supersedes: null
---

# US-5.1 — Implementation Report (frontend track)

Source of record for "what was actually built": `docs/catalog/US-5.1-pipeline-status.md`
(v2, `story-orchestrator`), which tracks two `frontend-builder` attempts under
`IMPLEMENTATION`. This report restates that record against `task_breakdown`'s
T1-T16 (T17 is this stage) for `implementation-verifier`,
`security-reviewer`, `reconciliation-reviewer`, and `pr-preparer` to consume.

## Summary

A brand-new `frontend/` directory (React 18 + Vite + TypeScript, TanStack
Query, React Hook Form, React Router, MSW/Vitest/RTL for tests) was scaffolded
and built out to cover every in-scope screen and flow named in the Story.
Attempt 1 delivered the full file set (~49 files) but left verification
incomplete and had one real bug (an infinite-redirect loop in
`ProtectedRoute.tsx`, initially misdiagnosed as a sandbox OOM). Attempt 2
root-caused and fixed that bug, added the missing `vitest-axe` a11y
assertions, fixed a Vitest-2.x type-signature issue, and ran/confirmed all
four gate commands. `story-orchestrator` independently re-ran all four gates
after attempt 2 and got the same numbers this stage's own run (see
`docs/evidence/US-5.1-quality-gate-report.md`) reproduced: 26/26 test files,
89/89 tests, coverage 95.78%/96.24%/86.66%/95.78% (stmt/branch/func/line).

## Architecture notes worth flagging to downstream reviewers

- **New module not in the original plan's file list:** `src/session/sessionBridge.ts`.
  Added by `frontend-builder` so `api/httpClient.ts` can read the live access
  token and react to a refresh outcome without `api/` importing `store/` (or
  vice versa) — both directions are forbidden by `AGENTS.md` §3's Frontend
  layer table (`api/` may import only `fetch` + shared types; `store/` may
  import neither `api/` nor `hooks/`). This is a legitimate third, neutral
  module sitting below both, not a layering violation — worth
  `implementation-verifier`/`security-reviewer` confirming independently
  rather than taking this report's word for it.
- **`ProtectedRoute.tsx` fix (attempt 2):** the guard previously passed a
  freshly-constructed `{ from: location }` object into `<Navigate
  state={...}>` on every render; `react-router-dom`'s `Navigate` re-invokes
  `navigate()` inside a `useEffect` keyed on referential equality of `state`,
  so an unstable object reference re-fired the redirect indefinitely whenever
  the guard rendered directly (its own unit test's exact scenario). Fixed
  with a ref that captures `from` once when auth is lost and resets when auth
  is regained. This was a genuine bug, not a test or environment artifact —
  worth independent confirmation given attempt 1 spent significant effort
  mischaracterizing it as a V8 heap-size ceiling.
- **`components/LogoutControls.tsx`** was split out of `layouts/AppShell.tsx`
  per a Low finding from `plan_review`: `AppShell.tsx` itself must not import
  `hooks/` (layout components render children, not perform mutations), so the
  logout/logout-all controls live in their own component that `AppShell`
  renders as a child.
- **Test-file correction:** `src/hooks/refreshCoordinator.integration.test.tsx`'s
  first test originally called `useSessions()` twice with an identical static
  query key, which TanStack Query correctly deduplicated into one fetch,
  collapsing the "two concurrent authenticated requests" scenario the test
  intended for FE-AC4/OD-2. The second consumer was changed to a distinct
  query key against the same `listSessions` endpoint; the test's assertions
  were not altered.
- **Task-breakdown path correction:** T6's verification command names
  `frontend/src/api/refreshCoordinator.integration.test.tsx`; the actual file
  (per `test-writer`'s own documented relocation) lives at
  `frontend/src/hooks/refreshCoordinator.integration.test.tsx`.

## Per-task status against `docs/plans/US-5.1-task-breakdown.md`

| Task | Scope | Status | Evidence |
|---|---|---|---|
| T1 | Scaffold/build config | Done | `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `.eslintrc.cjs`, `.prettierrc`, `.prettierignore`, `.env.example`, `.gitignore`, `src/vite-env.d.ts`, `src/main.tsx`, `src/App.tsx` present; `lint`/`format:check`/`type-check` all pass on the full tree (this stage's own run). |
| T2 | `api/` | Done | `types.ts`, `errorNormalization.ts` (+test), `refreshCoordinator.ts` (+test), `httpClient.ts`, `authApi.ts`. Grep confirms zero React/TanStack imports in `api/`. |
| T3 | `store/` (auth state) | Done, with one finding | `authStore.tsx`, `queryClient.ts`. Grep confirms `store/` imports nothing from `hooks/`, but does have one type-only import from `api/`: `store/authStore.tsx:13: import type { UserRead } from "../api/types"` — erased at compile time, no runtime coupling, but contradicts the file's own header comment and the letter of T3's verification command / `AGENTS.md` §3's layer table. See `docs/evidence/US-5.1-quality-gate-report.md`'s non-blocking findings. |
| T4 | `test/` infrastructure | Done | `setup.ts`, `mswServer.ts`, `mswHandlers.ts` (test-utils folded into `test/`); MSW handlers cover all 10 `/auth/*` operations plus Register's two non-RFC7807 shapes. |
| T5 | `hooks/` | Done | `useRegister`, `useLogin`, `useMfaVerify`, `useLogout`, `useLogoutAll`, `useSessions`, `useRevokeSession`, `useRequestPasswordReset`, `useConfirmPasswordReset` (each + `.test.ts`), all green. Store writes confirmed inside each mutation's `onSuccess` only (this stage's Part B′ check 7). |
| T6 | `hooks/`/`api/` boundary integration (FE-AC4) | Done | `hooks/refreshCoordinator.integration.test.tsx` — 2 tests, both passing (single-flight refresh on concurrent 401s; refresh-failure clears session and redirects once). |
| T7 | `routes/` guards + `layouts/` | Done | `ProtectedRoute.tsx` (+ infinite-redirect fix, attempt 2), `GuestOnlyRoute.tsx`, `AuthLayout.tsx`, `AppShell.tsx` (+ `LogoutControls.tsx` split-out). All route/layout tests green (3+2+2 tests). Gated dependency (`react-router-dom`) sign-off recorded as granted by the user during the `/so:next` run per pipeline-status attempt 1. |
| T8 | `components/` shared UI | Done | `ErrorState.tsx`, `FieldError.tsx`, `MfaEnrollmentBanner.tsx`, `apiErrorHelpers.ts` (+ tests). Grep confirms zero `fetch`/`axios` in `components/`. |
| T9 | `screens/RegisterScreen` | Done | 10 tests green (FE-AC1, FE-AC8, FE-AC9 both non-RFC7807 shapes, FE-AC11, a11y). |
| T10 | `screens/LoginScreen` | Done | 7 tests green (FE-AC2, FE-AC3's first branch, FE-AC9, FE-AC11, a11y). |
| T11 | `screens/MfaVerifyScreen` | Done | 6 tests green (FE-AC3's second step, TOTP + recovery code, a11y). |
| T12 | `screens/ForgotPasswordScreen` | Done | 4 tests green (FE-AC7 request half, FE-AC9, FE-AC11, a11y). |
| T13 | `screens/ResetPasswordScreen` | Done | 7 tests green (FE-AC7 confirm half, FE-AC8's 12-char rule, explicit tests that breach-check/differs-from-current are NOT client-simulated, FE-AC9, FE-AC11). |
| T14 | `screens/SessionsScreen` | Done | 6 tests green (FE-AC6 list+revoke+current-session marker, a11y). |
| T15 | `screens/PlaceholderHomeScreen` | Done | 4 tests green (post-login landing, `MfaEnrollmentBanner` surfaced when `mfa_enrollment_deadline` present, a11y). |
| T16 | `routes/AppRoutes` (route table) | Done | 4 tests green (FE-AC10 both directions rendered in a real `MemoryRouter`, no `vi.mock('react-router-dom')`; full MFA-challenge flow end-to-end). Gated dependency (`react-router-dom`) sign-off same as T7. |
| T17 | Quality gate | This report + `docs/evidence/US-5.1-quality-gate-report.md` | See quality gate report — PASS. |

Test-file total: 26 files / 89 tests, matching the file list above
(scaffold/config files T1 carry no test files of their own beyond what's
exercised through the other 25).

## Open items carried forward (not blocking, not resolved here)

- OD-1, OD-5, OD-6, OD-7, OD-8 were implemented per the implementation plan's
  documented defaults (same-origin `/api/v1` dev proxy; 8-char Register /
  12-char Reset-Password client rules; current-session revoke control
  disabled; structural-only `MfaEnrollmentBanner`; minimal
  `PlaceholderHomeScreen`) — none of these Open Decisions were resolved by
  this delivery, only designed around, consistent with the approved plan.
- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical) in
  dev-dependency transitive packages, not triaged in this pass — worth a
  follow-up `npm audit` review, not a gate blocker (dev-only dependencies,
  not shipped to the browser bundle).

## Not this report's job

Whether the built screens/tests actually satisfy each FE-AC's business intent
is `reconciliation-reviewer`'s check against
`docs/tests/US-5.1-ac-test-matrix.md`; whether the code meets every AGENTS.md
technical rule beyond this stage's Part B′ spot-checks is
`implementation-verifier`'s Definition-of-Done pass; this report only
restates what was built and its per-task gate status.
