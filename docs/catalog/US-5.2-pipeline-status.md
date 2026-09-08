---
artifact_type: pipeline_status
story: US-5.2
version: 2
status: DRAFT
created_at: "2026-09-08T15:00:00Z"
updated_at: "2026-09-08T16:30:00Z"
produced_by: frontend-builder
inputs:
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/evidence/US-5.2-test-generation-report.md
    version: 2
supersedes: null
---

# US-5.2 — IMPLEMENTATION Pipeline Status

Track: `frontend`. Per `stage-map.yaml` `IMPLEMENTATION.skills_by_track.frontend`,
this stage has a single sub-step: `frontend-builder`, covering T1-T12 from
`docs/plans/US-5.2-task-breakdown.md` (T13 belongs to `gate-enforcer` at
`QUALITY_GATE`).

## Sub-step: frontend-builder

| Attempt | Verdict | Recorded at | Notes |
|---|---|---|---|
| 1 | CHANGES_REQUIRED (`changes_required_tests`) | 2026-09-08T15:00:00Z | T1-T12 fully implemented (files listed below). `qrcode.react@^4.1.0` added to `frontend/package.json` per the human-approved sign-off (implementation_plan Change 9/Risk 2) and installed cleanly. `npm run lint`, `npm run type-check`, and `npm run format:check` all exit 0. Full-suite `vitest run`: **186/190 tests pass** (43 files, 40 fully green). Four assertions fail, all four root-caused to defects in test-writer's own test files (or an environment/library interaction the test author did not anticipate), not to any gap in this pass's implementation — see "Test defects found" below, each with isolation-run evidence. Because the suite is not 100% green, `@vitest/coverage-v8` (`reportOnFailure: false` by default) produced **no coverage report at all** (`coverage/` was never written) — `test:coverage`, one of the four load-bearing gate scripts, cannot be verified this pass. That is a genuine, gate-blocking consequence of the four test defects, not a cosmetic gap, so this attempt reports `CHANGES_REQUIRED` rather than `PASS`. |
| 2 | PASS | 2026-09-08T16:30:00Z | Continuation pass, T1-T12 implementation unchanged. test-writer fixed all four attempt-1 defects (`docs/evidence/US-5.2-test-generation-report.md` v2); full suite now green (43 files / 190 tests) so `test:coverage` produced a report for the first time, exiting 1 on the 85% function-coverage floor: **functions 84.91% (152/179)**, statements 96.55%, branches 94.44%, lines 96.55%. Root cause: `frontend/src/store/queryClient.ts` (the shared TanStack Query client singleton, wired into `App.tsx`) was never imported by any test — `frontend/src/test/test-utils.tsx` deliberately builds its own local, isolated `QueryClient` per render/hook (so query-cache state never leaks between tests) rather than importing the shared singleton — so the module's own `new QueryClient(...)` construction never executed under coverage instrumentation, leaving it at 0% (lines 1-12). Fix: added `frontend/src/store/queryClient.test.ts` (new file, 2 tests) that imports `queryClient` directly and asserts on `getDefaultOptions()` (`queries.retry === 1`, `mutations.retry === 0`) and an empty initial `getQueryCache()` — genuine behavioral coverage of a real shared module, not a threshold-gaming stub. `test-utils.tsx` was **not** modified (its per-test isolation is intentional and orthogonal to this gap). Did not consider excluding `queryClient.ts` from coverage: it is hand-written, non-generated, non-type-only application code with real (if small) configuration logic, so an explicit exclusion would hide a genuine untested-module gap rather than correct a false positive. Re-ran `npm run test:coverage` after the fix: **exit 0**, 44 files / 192 tests all passing, functions 85.39% (152/178), statements 96.71%, branches 94.57%, lines 96.71%. Re-ran `npm run lint` (exit 0, 0 warnings), `npm run type-check` (exit 0), `npm run format:check` (exit 0, "All matched files use Prettier code style!") — all four gate scripts genuinely green with fresh output this pass. Self-check (SKILL.md step 8) re-run: zero real `fetch(`/`axios` matches in `screens/`/`components/` (`SessionsScreen.tsx`'s `.refetch()` remains the known substring false positive), zero `react`/`@tanstack/react-query` imports in `api/`, zero `localStorage`/`sessionStorage` references in the new file. `git status` confirms every changed/added path this pass is under `frontend/`, and the only file touched beyond attempt 1's own diff is the new `frontend/src/store/queryClient.test.ts`. No source-level (non-test) file was modified this pass. |

### Files created (T1-T12)

`api/`: `profileApi.ts`, `mfaApi.ts`, `accountApi.ts`.

`hooks/`: `useProfileUpdate.ts`, `useConfirmEmailChange.ts`, `useVerifyEmail.ts`,
`useResendVerificationEmail.ts`, `useMfaEnroll.ts`, `useMfaActivate.ts`,
`useMfaDisable.ts`, `useAccountDeactivate.ts`.

`components/`: `RecoveryCodesDisplay.tsx`, `QrCode.tsx`.

`screens/`: `ProfileScreen.tsx`, `EmailVerificationScreen.tsx`,
`ConfirmEmailChangeScreen.tsx`, `SecurityScreen.tsx`, `DeactivateAccountScreen.tsx`.

### Files modified (T1-T12)

- `api/httpClient.ts` — additive `httpPatch<T>` (Change 1: resolves
  `{data, status, headers}`, threads `If-Match` only when supplied); additive
  `body?: unknown` option on `httpDelete` (test-strategy's own documented
  collaborator-shape finding, needed for FR-6's `DELETE /auth/mfa` body).
  `httpGet`/`httpPost`/existing `httpDelete` callers unchanged; `performRequest`/
  `parseResponse` untouched.
- `api/types.ts` — additive new DTOs (`ProfileRead`, `ProfileUpdateRequest`,
  `EmailChangeRequest`, `ConfirmEmailChangeRequest/Response`,
  `VerifyEmailRequest/Response`, `ResendVerificationRequest/Response`,
  `MfaEnrollRequest/Response`, `MfaActivateRequest/Response`,
  `MfaDisableRequest`, `AccountDeactivateRequest/Response`) plus
  `SUPPORTED_LOCALES`/`SupportedLocale` (Change 7).
- `api/authApi.ts` — additive `verifyEmail`, `resendVerificationEmail`.
- `components/apiErrorHelpers.ts` — additive `getErrorStatus` (Change 4).
- `components/MfaEnrollmentBanner.tsx` — additive `<a href="/settings/security">`
  link; existing dismiss/sessionStorage behavior untouched.
- `store/authStore.tsx` — additive `mfaEnabled: boolean` on `AuthStateSeed` and
  `SetSessionPayload` (required field, per Change 6's deliberate design), new
  `SET_MFA_ENABLED` reducer case, new `setMfaEnabled` action.
- `hooks/useLogin.ts` — additive: passes `mfaEnabled: false` into `setSession`.
- `hooks/useMfaVerify.ts` — additive: passes `mfaEnabled: true` into `setSession`.
- `routes/AppRoutes.tsx` — adds `/settings/profile`, `/settings/security`,
  `/settings/deactivate` inside the existing `ProtectedRoute` group; adds
  `/verify-email`, `/confirm-email-change` outside both guards (Change 10).
- `test/mswHandlers.ts` — one baseline handler per new endpoint (bundled into
  T1 per the task breakdown's own note).
- `package.json` — `qrcode.react` dependency (T5, human-approved).

**Beyond the plan's own Files To Modify list** — declared here per
`reconciliation-reviewer`'s own concern about coding-time drift:

- `screens/LoginScreen.tsx` — additive: reads an optional
  `location.state.message` and renders it in a `<p role="status">` when
  present. Not named in `implementation_plan`'s Files To Modify, but required
  by FR-7/PS-AC7 ("lands on `/login` with a confirmation message") and named
  directly in `task_breakdown` T10's own verification bullet
  ("the test asserts landing on `/login` with the confirmation message").
  `DeactivateAccountScreen.tsx` navigates here with
  `{ state: { message: "Your account has been deactivated." } }`. Existing
  `LoginScreen.test.tsx` assertions unaffected (verified: all 7 still pass).
- `hooks/useLogout.test.ts`, `hooks/useLogoutAll.test.ts`,
  `hooks/refreshCoordinator.integration.test.tsx` — each calls
  `authStore.setSession(...)` directly in its own Arrange step; once
  `SetSessionPayload.mfaEnabled` became required (Change 6, deliberately, so
  `tsc --noEmit` catches a forgotten call site), these three pre-existing
  US-5.1 test files failed to compile. Fixed by adding `mfaEnabled: false` to
  each call — additive field only, zero assertion changes.
- `prettier --write .` was run once to reach `format:check` green; it
  reformatted 14 files (whitespace/line-wrap only), including several
  test-writer test files (`httpClient.test.ts`, `QrCode.test.tsx`,
  `useMfaDisable.test.ts`, `ConfirmEmailChangeScreen.test.tsx`,
  `DeactivateAccountScreen.test.tsx`, `SecurityScreen.test.tsx`) that were not
  yet Prettier-formatted. No assertion text changed.

### Gate scripts run this pass

- `npm run lint` — 0 errors/warnings.
- `npm run type-check` — 0 errors.
- `npm run format:check` — clean (after the one `format:write` pass above).
- `npm run test:coverage` — **could not be verified**: the underlying
  `vitest run --coverage` does not fail with a distinct error, but produces no
  `coverage/` output and no coverage table at all, because `@vitest/coverage-v8`
  defaults `reportOnFailure` to `false` and 4 of 190 tests fail (see below).
  This is expected to resolve once those four test-file defects are fixed —
  no source-level change is expected to be required.

### Self-check (SKILL.md step 8)

- `grep -rn "fetch(\|axios" src/screens/*.tsx src/components/*.tsx` (excluding
  `.test.` files) — zero real matches (`SessionsScreen.tsx`'s `.refetch()` is a
  substring false positive, not a `fetch(` call).
- `grep -rln "from \"react\"\|@tanstack/react-query" src/api/*.ts` (excluding
  `.test.` files) — zero matches.
- `grep -rn "localStorage\|sessionStorage" src/api src/hooks src/screens
  src/components src/store` (excluding `.test.` files) — only
  `components/MfaEnrollmentBanner.tsx` (pre-existing US-5.1 dismiss-flag
  persistence, not token/secret-shaped) and one explanatory comment in
  `store/authStore.tsx`. No new US-5.2 file touches either storage API — the
  NFR's `secret`/`otpauth_uri`/`recovery_codes`/`current_password` values are
  held only in transient React state (RHF form state / component state in
  `SecurityScreen.tsx`, `RecoveryCodesDisplay.tsx`), confirmed also by the
  passing `*_never_reach_storage_console_or_third_party`-style test
  assertions (all pass except the two described below).
- `frontend/package.json` — confirmed still defines exactly `lint`,
  `format:check`, `type-check`, `test:coverage` (plus the pre-existing `dev`,
  `build`, `preview`, `test`, `format:write` — unrenamed, unremoved).

## Test defects found (not fixed — test-writer's files, per the harness brief)

Each reproduced independently (isolated `-t` runs) to separate "fails only in
this file's run order / this environment" from "my component is wrong."

1. **`components/RecoveryCodesDisplay.test.tsx` —
   `test_recovery_codes_display_copy_control_writes_codes_to_the_clipboard_api`.**
   Fails even run alone. Root cause: `@testing-library/user-event@14.5.2`'s
   `userEvent.setup()` unconditionally installs its own getter-only
   `navigator.clipboard` stub (`attachClipboardStubToView`,
   `node_modules/@testing-library/user-event/dist/cjs/utils/dataTransfer/Clipboard.js`),
   silently discarding the test's own `Object.assign(navigator, { clipboard:
   { writeText: vi.fn() } })` mock assigned just before `userEvent.setup()` is
   called. The component correctly calls `navigator.clipboard.writeText(...)`
   — it simply calls user-event's own stub, not the test's spy, so the spy
   assertion can never see the call regardless of implementation.
2. **`components/RecoveryCodesDisplay.test.tsx` —
   `test_recovery_codes_display_never_writes_codes_to_local_storage_session_storage_or_console`.**
   Same root cause, compounded: `userEvent`'s own registered `afterEach` only
   *resets* the stub's internal state, it does not restore the original
   `navigator.clipboard` descriptor (only a file-level `afterAll` does that).
   Once an earlier test in the same file calls `userEvent.setup()`, the
   getter-only property persists into this test, so its own
   `Object.assign(navigator, { clipboard: ... })` throws `TypeError: Cannot
   set property clipboard of #<Navigator> which has only a getter` before any
   component code runs.
3. **`components/MfaEnrollmentBanner.test.tsx` —
   `test_mfa_enrollment_banner_link_targets_settings_security`.** Passes in
   isolation; fails only when run after
   `test_mfa_enrollment_banner_dismiss_control_hides_the_banner_and_persists_via_session_storage`
   in the same file. That test sets
   `sessionStorage["mfaEnrollmentBannerDismissed"] = "true"` and — unlike this
   new test — never calls `sessionStorage.clear()`; the leaked value makes
   `MfaEnrollmentBanner`'s own (pre-existing, unmodified) `readDismissed()`
   return `true` on the next test's mount, so the banner (and its new link)
   never renders. Missing Arrange step in the new test, not a component defect.
4. **`screens/DeactivateAccountScreen.test.tsx` —
   `test_deactivate_account_screen_confirmation_step_names_the_consequence_before_final_submit`.**
   Structurally unsatisfiable by any implementation: the assertion is
   `expect(screen.getByText(/deactivat/i)).toBeInTheDocument()`, which
   requires **exactly one** match. `test/test-utils.tsx`'s
   `renderWithProviders` always renders a sibling
   `data-testid="route-location"` probe containing the current route's
   pathname — here literally `/settings/deactivate`, which itself matches
   `/deactivat/i` — and the very next line in the same test requires the
   `"Yes, deactivate my account"` button (whose own text also matches
   `/deactivat/i`) to already be present. Those two matches are unavoidable
   under the test's own two hard constraints (the route path and the
   mandatory button name, both used identically by other passing tests in
   this file and `SecurityScreen.test.tsx`'s disable flow), so a third
   (fourth, counting a natural `<h1>`) match from any confirmation copy always
   makes the query ambiguous. Verified by removing the `<h1>` wording and
   rephrasing the consequence paragraph in a scratch edit — still 2+ matches
   (button + route probe) — before reverting to the current, more readable
   copy.

None of the four affects component behavior verified elsewhere: `QrCode`'s
own 3 tests pass; `RecoveryCodesDisplay`'s other 2 tests (renders every code,
continue-gated-on-checkbox) pass; `MfaEnrollmentBanner`'s other 3 tests pass;
`DeactivateAccountScreen`'s other 5 tests pass, including the full-route-tree
success path asserting the confirmation message actually renders on `/login`.

## Blocking issues (attempt 1 — resolved in attempt 2)

1. **`test:coverage` unverifiable until the four test-file defects above are
   fixed** — not a source defect; loop back to `TEST_WRITING`
   (`changes_required_tests`, per `stage-map.yaml` `IMPLEMENTATION.loop_back`
   — this key exists in the canonical stage map though it is not repeated in
   `frontend-builder`'s own SKILL.md loop-back table).
   **Resolved:** test-writer fixed all four defects (test-generation-report
   v2); the full suite is green and `test:coverage` now runs to completion.

## Attempt 2 (2026-09-08) — closing the function-coverage gap

### Files created

- `frontend/src/store/queryClient.test.ts` — new unit test for the shared
  `store/queryClient.ts` singleton (2 tests): asserts
  `getDefaultOptions().queries.retry === 1` and
  `getDefaultOptions().mutations.retry === 0`, and that the singleton starts
  with an empty `getQueryCache()`. This is the only file created or modified
  this pass; no T1-T12 source file changed.

### Gate scripts run this pass

- `npm run test:coverage` — **before fix**: reproduced the reported gap
  exactly — exit 1, `ERROR: Coverage for functions (84.91%) does not meet
  global threshold (85%)` (functions 152/179; statements 96.55%; branches
  94.44%; lines 96.55%; `store/queryClient.ts` at 0% funcs/stmts/branches/lines,
  lines 1-12 uncovered). **After fix**: exit 0, 44 files / 192 tests passing,
  functions 85.39% (152/178), statements 96.71%, branches 94.57%, lines
  96.71%. No `ERROR` line; coverage summary printed cleanly.
- `npm run lint` — exit 0, `eslint . --max-warnings=0`, 0 findings.
- `npm run type-check` — exit 0, `tsc -b --noEmit`, 0 errors.
- `npm run format:check` — exit 0, `prettier --check .`,
  "All matched files use Prettier code style!".

### Self-check (SKILL.md step 8) — re-run

- `grep -rn "fetch(\|axios" src/screens/*.tsx src/components/*.tsx` (excluding
  `.test.` files) — zero real matches (`SessionsScreen.tsx`'s `.refetch()`
  remains the known substring false positive from attempt 1).
- `grep -rln "from \"react\"\|@tanstack/react-query" src/api/*.ts` (excluding
  `.test.` files) — zero matches.
- `grep -n "localStorage\|sessionStorage" src/store/queryClient.ts
  src/store/queryClient.test.ts` — zero matches.
- `frontend/package.json` — still defines exactly `lint`, `format:check`,
  `type-check`, `test:coverage` (unrenamed, unremoved); untouched this pass.
- `git status --porcelain frontend/` — every changed/added path is under
  `frontend/`; the only addition beyond attempt 1's own diff is
  `frontend/src/store/queryClient.test.ts`.

### Blocking issues (attempt 2)

None.

## Non-blocking findings

- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical) in
  dev-dependency transitive packages — not triaged this pass (same finding
  US-5.1's pipeline status recorded).
- OD-3, OD-5, OD-6, OD-7 remain `OPEN` per `docs/decisions/US-5.2-open-decisions.md`
  v2; each was implemented per `implementation_plan`'s documented default
  (banner-link-only for OD-3; `SUPPORTED_LOCALES` constant for OD-6;
  `Intl.supportedValuesOf("timeZone")`-derived combobox for OD-7) — none
  resolved, only designed around, consistent with the approved plan.
- `ProfileScreen.tsx`'s "only the changed fields" diffing (FR-2) is
  implemented against a plain baseline ref compared field-by-field, not
  react-hook-form's `formState.dirtyFields` — the latter requires subscribing
  to `formState` during render to stay live, and reading it only inside the
  submit handler (as first attempted) silently returned an empty object,
  sending the full form on every save. Caught by
  `test_profile_screen_submits_only_changed_fields_on_save` before this was
  shipped; noted here since it is a real react-hook-form gotcha a reviewer
  should be aware of if this pattern is copied elsewhere.
