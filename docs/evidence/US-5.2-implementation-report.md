---
artifact_type: implementation_report
story: US-5.2
version: 1
status: DRAFT
created_at: "2026-09-08T17:00:00Z"
updated_at: "2026-09-08T17:00:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/tests/US-5.2-ac-test-matrix.md
    version: 1
supersedes: null
---

# US-5.2 — Implementation Report (frontend track)

Source of record for "what was actually built": `docs/catalog/US-5.2-pipeline-status.md`
(v2, `story-orchestrator`), which tracks two `frontend-builder` attempts under
`IMPLEMENTATION`, and `docs/evidence/US-5.2-test-generation-report.md` (v2,
`test-writer`), which tracks the two `TEST_WRITING` attempts (including one
loop-back triggered by four test-file defects `frontend-builder` isolated in
its own attempt 1). This report restates that record against
`task_breakdown`'s T1-T12 (T13 is this stage) for `implementation-verifier`,
`security-reviewer`, `reconciliation-reviewer`, and `pr-preparer` to consume.

## Summary

Building on US-5.1's existing `frontend/` scaffold, this Story adds account
self-service: profile edit (write-only interim, ETag/`If-Match` conflict
handling), email verification and email-change confirmation, TOTP MFA
enroll/activate/disable, and account deactivation, plus the store/API-client
plumbing those flows need (`httpPatch`, `mfaEnabled` on the auth store, new
DTOs). `frontend-builder` attempt 1 delivered the full T1-T12 file set and
ran clean on `lint`/`type-check`/`format:check`, but 4 of 190 tests failed —
all four isolated and root-caused to defects in `test-writer`'s own test
files (clipboard-stub interaction with `@testing-library/user-event`,
missing test isolation, an unsatisfiable text-matcher regex), not to any
implementation gap — so `test:coverage` could not produce a report at all
(`@vitest/coverage-v8`'s `reportOnFailure: false` default) and the attempt
reported `CHANGES_REQUIRED` (`changes_required_tests`), looping back to
`TEST_WRITING`. `test-writer` fixed all four defects without touching any
AC mapping or asserted behavior (test-generation-report v2). `frontend-builder`
attempt 2 then found the full suite green but function coverage at 84.91%
(below the 85% floor), traced to `store/queryClient.ts` (a shared TanStack
Query singleton never imported by any test, because `test-utils.tsx`
deliberately builds its own isolated `QueryClient` per test) sitting at 0%;
added one small, genuinely-behavioral test file
(`store/queryClient.test.ts`) rather than excluding the module, closing the
gap to 85.39%. This stage independently re-ran all four gate scripts and got
the same figures both upstream reports claim: 44 files / 192 tests, 96.71%
statements, 94.57% branches, 85.39% functions, 96.71% lines — see
`docs/evidence/US-5.2-quality-gate-report.md`.

## Architecture notes worth flagging to downstream reviewers

- **`api/httpClient.ts`'s `httpDelete` gained an additive `body?: unknown`
  option**, beyond the implementation plan's literal "only `httpPatch` is
  new" wording (Architectural Change 1) — FR-6's `DELETE /auth/mfa` needs a
  request body (`current_password`, `code`) the pre-existing zero-body
  `httpDelete<T>` could not express. The existing `revokeSession` call site
  (US-5.1) is confirmed unmodified/still valid. Flagged by test-writer as a
  collaborator-shape decision it had to make, not fixed by any design doc
  (API_DESIGN is `NOT_APPLICABLE` for this Story).
- **`store/authStore.tsx`'s `AuthStateSeed`/`SetSessionPayload` gained a
  required `mfaEnabled: boolean` field** (Plan Change 6, deliberately
  required rather than optional so `tsc --noEmit` catches any forgotten call
  site). This is why three *pre-existing* US-5.1 test files
  (`hooks/useLogout.test.ts`, `hooks/useLogoutAll.test.ts`,
  `hooks/refreshCoordinator.integration.test.tsx`) needed an additive
  `mfaEnabled: false` at their own `setSession(...)` Arrange calls to keep
  compiling — zero assertion changes in any of the three.
- **`screens/LoginScreen.tsx` was modified beyond the plan's own Files To
  Modify list** — it now reads an optional `location.state.message` and
  renders it in a `<p role="status">`. Required by FR-7/PS-AC7 ("lands on
  `/login` with a confirmation message" after deactivation) and named
  directly in `task_breakdown` T10's own verification bullet.
  `DeactivateAccountScreen.tsx` navigates here with
  `{ state: { message: "Your account has been deactivated." } }`. All 7
  pre-existing `LoginScreen.test.tsx` assertions confirmed still passing.
- **`prettier --write .` was run once** during attempt 1 to reach
  `format:check` green, reformatting 14 files (whitespace/line-wrap only,
  including several not-yet-Prettier-formatted test-writer files) — no
  assertion text changed in any of them.
- **Four test-file defects found and fixed** (not implementation defects —
  see Summary above and `docs/evidence/US-5.2-test-generation-report.md`'s
  "Attempt 2 delta" for full root-cause detail on each):
  `components/RecoveryCodesDisplay.test.tsx` (2 assertions,
  `userEvent.setup()`'s own clipboard stub silently shadowing the test's
  `Object.assign(navigator, {clipboard: ...})` mock),
  `components/MfaEnrollmentBanner.test.tsx` (1 assertion, missing
  `sessionStorage.clear()` between tests), `screens/DeactivateAccountScreen.test.tsx`
  (1 assertion, a `/deactivat/i` text query structurally ambiguous against
  the test harness's own always-rendered route-probe and the mandatory
  confirm-button text).
- **`store/queryClient.ts` closed a coverage gap with a genuine test, not an
  exclude.** `frontend-builder`/`test-writer` explicitly considered and
  rejected excluding the file from coverage — it is hand-written
  application code with real configuration logic
  (`getDefaultOptions().queries.retry`/`mutations.retry`), so an exclusion
  would have hidden a real untested-module gap rather than corrected a false
  positive.

## Per-task status against `docs/plans/US-5.2-task-breakdown.md`

| Task | Scope | Status | Evidence |
|---|---|---|---|
| T1 | `api/` | Done | `httpClient.ts` (+`httpPatch<T>`, +`body?` on `httpDelete`), `types.ts` (new DTOs + `SUPPORTED_LOCALES`), `profileApi.ts`, `mfaApi.ts`, `accountApi.ts` (new), `authApi.ts` (+`verifyEmail`/`resendVerificationEmail`), `mswHandlers.ts` (one handler per new endpoint). Grep confirms zero React/TanStack imports in `api/`; `httpGet`/`httpPost`/existing `httpDelete` callers unchanged. |
| T2 | `store/` (auth state) | Done | `authStore.tsx` — `mfaEnabled: boolean` on `AuthStateSeed`/`SetSessionPayload`, `SET_MFA_ENABLED` reducer case, `setMfaEnabled` action. `grep -rl "from \"\.\./api\|from \"\.\./hooks" src/store` returns no `.ts`/`.tsx` import match (comment-only reference). |
| T3 | `components/` (shared helper) | Done | `apiErrorHelpers.ts` (+`getErrorStatus`, +test). No direct `api/` import. |
| T4 | `hooks/` | Done | `useProfileUpdate`, `useConfirmEmailChange`, `useVerifyEmail`, `useResendVerificationEmail`, `useMfaEnroll`, `useMfaActivate`, `useMfaDisable`, `useAccountDeactivate` (each + `.test.ts`, all green); `useLogin.ts`/`useMfaVerify.ts` modified to pass `mfaEnabled`. Store writes confirmed inside `onSuccess` only (quality-gate-report check 7). |
| T5 | `components/` (new UI) | Done | `RecoveryCodesDisplay.tsx`, `QrCode.tsx` (+tests). `qrcode.react@^4.1.0` added to `package.json` per the recorded human sign-off (implementation_plan Change 9/Risk 2) and installed cleanly. No storage/console/third-party leak of `secret`/`otpauth_uri`/`recovery_codes` (grep-confirmed this stage). |
| T6 | `screens/ProfileScreen` | Done | 13 tests green (PS-AC2/FR-2 edit-only submit + ETag/If-Match/412 conflict states; PS-AC3/FR-3 202 pending-email state; FR-9 locale/timezone membership; XC-AC1-3). No direct `api/` import in the screen. |
| T7 | `screens/EmailVerificationScreen` | Done | 9 tests green (PS-AC4/FR-4 success/expired/invalid + generic resend confirmation; XC-AC1-3). |
| T8 | `screens/ConfirmEmailChangeScreen` | Done | 5 tests green, rendered both authenticated and unauthenticated (PS-AC3/FR-3, Plan Risk 9). |
| T9 | `screens/SecurityScreen` | Done | 15 tests green, rendered with `mfaEnabled=false` (enroll flow: `current_password` required, local QR render, one-time recovery-codes display gated on explicit confirmation) and `mfaEnabled=true` (disable flow: `current_password`+`code` required, session-revocation consequence named, `setMfaEnabled(false)` verified). |
| T10 | `screens/DeactivateAccountScreen` | Done | 6 tests green (PS-AC7/FR-7: unconditional `current_password`, `clearSession()` + landing on `/login` with confirmation message via a real route tree, no `vi.mock('react-router-dom')`). |
| T11 | `routes/AppRoutes` | Done | Adds `/settings/profile`, `/settings/security`, `/settings/deactivate` inside `ProtectedRoute`; `/verify-email`, `/confirm-email-change` outside both guards. Redirect + both-direction rendering assertions pass; no `api/` import in `routes/`. |
| T12 | `components/MfaEnrollmentBanner` (modify) | Done | Additive `<a href="/settings/security">` link; all 3 pre-existing dismiss-behavior assertions still pass unchanged; +1 new link-target assertion. |
| T13 | Quality gate | This report + `docs/evidence/US-5.2-quality-gate-report.md` | See quality gate report — PASS. |

Test-file total: 44 files / 192 tests (114 `it()` cases newly written across
17 new test files + 4 additive edits to existing files, plus
`store/queryClient.test.ts` added in `frontend-builder` attempt 2 to close a
coverage gap — matching `docs/evidence/US-5.2-test-generation-report.md`'s
own count of new/edited test files plus that one gate-driven addition).

## Open items carried forward (not blocking, not resolved here)

- OD-3, OD-5, OD-6, OD-7 remain `OPEN` per
  `docs/decisions/US-5.2-open-decisions.md` v2; each was implemented per the
  approved implementation plan's documented default (banner-link-only for
  OD-3; `SUPPORTED_LOCALES` constant for OD-6;
  `Intl.supportedValuesOf("timeZone")`-derived combobox for OD-7; OD-5 is the
  missing backend `GET /profile` endpoint, scoped out per the story's own
  Dependencies & Blockers #1) — none resolved by this delivery, only
  designed around, consistent with the approved plan.
- PS-AC1 ("profile view") has no test and cannot be built — no
  `GET /profile`/`GET /users/me` endpoint exists on the backend. The approved
  spec's own deferral; `docs/tests/US-5.2-ac-test-matrix.md` carries an
  explicit PS-AC1 row stating why, and
  `ProfileScreen.test.tsx::test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values`
  pins the write-only interim as a positive assertion instead.
- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical)
  in dev-dependency transitive packages — not triaged this pass, same
  finding recorded by US-5.1's own pipeline status.

## Not this report's job

Whether the built screens/tests actually satisfy each PS-AC/FE-AC's business
intent is `reconciliation-reviewer`'s check against
`docs/tests/US-5.2-ac-test-matrix.md`; whether the code meets every
AGENTS.md technical rule beyond this stage's Part B′ spot-checks is
`implementation-verifier`'s Definition-of-Done pass; this report only
restates what was built and its per-task gate status.
