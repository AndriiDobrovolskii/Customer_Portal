---
artifact_type: test_generation_report
story: US-5.2
version: 2
status: ARCHIVED
created_at: "2026-09-08T10:00:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.2-plan-review.md
    version: 1
  - path: docs/catalog/US-5.2-pipeline-status.md
    version: 1
supersedes: null
---

> **Version 2 note:** TEST_WRITING attempt 2 (loop-back from
> IMPLEMENTATION's `changes_required_tests`, `frontend-builder` attempt 1).
> Fixed the four test-file defects `frontend-builder` isolated and
> reported — see "Attempt 2 delta" below for what changed and why. No AC
> coverage, test-function names, or behavioral assertions changed — only
> mocking/isolation/query mechanics in the four named tests.
> `docs/tests/US-5.2-test-strategy.md` and
> `docs/tests/US-5.2-ac-test-matrix.md` remain accurate as written and stay
> at version 1.

# Test Generation Report: Account & Profile Self-Service — Frontend (US-5.2)

## What was generated

**15 new test source files** and **4 additive edits** to existing test files,
plus one infrastructure edit, for a total of **114 `it()` cases** (101 newly
written, 13 pre-existing and unmodified in the 4 additive files). Verified by
direct grep (counts below); every test-function name this pass's
`docs/tests/US-5.2-ac-test-matrix.md` cites was independently confirmed to
exist verbatim in its named file (98 references checked, 0 missing).

### New files

| File | Cases | Layer |
|---|---|---|
| `frontend/src/api/httpClient.test.ts` | 5 | Unit (`api/`) |
| `frontend/src/components/apiErrorHelpers.test.ts` | 10 | Unit (`components/`) |
| `frontend/src/hooks/useProfileUpdate.test.ts` | 5 | Unit (`hooks/`) |
| `frontend/src/hooks/useConfirmEmailChange.test.ts` | 3 | Unit (`hooks/`) |
| `frontend/src/hooks/useVerifyEmail.test.ts` | 3 | Unit (`hooks/`) |
| `frontend/src/hooks/useResendVerificationEmail.test.ts` | 2 | Unit (`hooks/`) |
| `frontend/src/hooks/useMfaEnroll.test.ts` | 2 | Unit (`hooks/`) |
| `frontend/src/hooks/useMfaActivate.test.ts` | 2 | Unit (`hooks/`) |
| `frontend/src/hooks/useMfaDisable.test.ts` | 2 | Unit (`hooks/`) |
| `frontend/src/hooks/useAccountDeactivate.test.ts` | 2 | Unit (`hooks/`) |
| `frontend/src/components/RecoveryCodesDisplay.test.tsx` | 4 | Integration (`components/`) |
| `frontend/src/components/QrCode.test.tsx` | 3 | Integration (`components/`) |
| `frontend/src/screens/ProfileScreen.test.tsx` | 13 | Integration (`screens/`) |
| `frontend/src/screens/EmailVerificationScreen.test.tsx` | 9 | Integration (`screens/`) |
| `frontend/src/screens/ConfirmEmailChangeScreen.test.tsx` | 5 | Integration (`screens/`) |
| `frontend/src/screens/SecurityScreen.test.tsx` | 15 | Integration (`screens/`) |
| `frontend/src/screens/DeactivateAccountScreen.test.tsx` | 6 | Integration (`screens/`) |

### Additive edits (existing coverage kept, cases appended only)

| File | New cases | Existing cases kept |
|---|---|---|
| `frontend/src/hooks/useLogin.test.ts` | 1 (`test_use_login_success_without_mfa_sets_auth_store_mfa_enabled_false`) | 3 |
| `frontend/src/hooks/useMfaVerify.test.ts` | 1 (`test_use_mfa_verify_success_sets_auth_store_mfa_enabled_true`) | 3 |
| `frontend/src/components/MfaEnrollmentBanner.test.tsx` | 1 (`test_mfa_enrollment_banner_link_targets_settings_security`) | 3 |
| `frontend/src/routes/AppRoutes.test.tsx` | 7 (three `/settings/*` redirect cases, two `/verify-email` direction cases, two `/confirm-email-change` direction cases) | 4 |

### Test infrastructure

- `frontend/src/test/test-utils.tsx` — extended `RenderWithProvidersOptions`
  with `mfaEnabled?: boolean` and `buildAuthSeed` with `mfaEnabled:
  options.mfaEnabled ?? false`, so `AuthStateSeed.mfaEnabled` (a **required**
  field once Plan Change 6 lands) has a value on every existing call site,
  including the ones this pass did not otherwise touch. Without this edit,
  `T9`'s own verification command ("seeded via `test-utils`'s `AuthProvider`
  `initialState`") would be unwritable.
- `frontend/src/test/mswHandlers.ts` / `mswServer.ts` — **not** written by
  this pass (Task T1's own deliverable, per this project's US-5.1
  precedent). Every new test defines its own `server.use(...)` override(s).

## Self-check performed (skill Completion Criteria)

- `grep -rn "vi.mock("` across `frontend/src` returns one hit, a comment
  string inside `DeactivateAccountScreen.test.tsx`'s own header explaining
  *why* it avoids `vi.mock('react-router-dom')` — no actual call anywhere.
- Every `it()` title in all 21 touched/created files matches
  `^test_[a-z0-9_]+$` (`AGENTS.md` §4 naming convention) — checked
  programmatically, 0 violations, 0 duplicate names within any file.
- Every test-function reference in `docs/tests/US-5.2-ac-test-matrix.md`
  (98 references) was independently confirmed to exist verbatim (as a
  quoted `it("...")` title) in the file it claims — 0 missing.

## Known RED-state failures (expected, not defects)

Every file listed above fails at **module-resolution time** today — none of
`api/profileApi.ts`, `mfaApi.ts`, `accountApi.ts`, the eight new hooks, the
five new/modified screens, `RecoveryCodesDisplay.tsx`, `QrCode.tsx`, or the
`httpPatch`/`getErrorStatus`/`authStore.mfaEnabled` additions exist yet
(Tasks T1–T12 have not run). This is the intended TDD-red state, consistent
with `docs/tests/US-5.1-test-strategy.md`'s own precedent.

One import failure has a distinct cause worth calling out on its own:
`screens/SecurityScreen.test.tsx` and `components/QrCode.test.tsx` will also
fail once their sibling symbols exist, because `qrcode.react` is not yet in
`frontend/package.json` — that dependency is Task T5's own deliverable (its
`AGENTS.md` §7.8 sign-off is already recorded, per this dispatch's own input
note referencing `HUMAN_PLAN_APPROVAL`). This is not an oversight; it is
named here so it reads as expected, not as a missed dependency.

## Known gap: PS-AC1 has no test

PS-AC1 ("profile view") cannot be tested — no `GET /profile`/`GET /users/me`
endpoint exists on the backend (FR-1, story Dependencies & Blockers #1, the
story's own `[blocked]` Enforcement Matrix marker). This is the approved
spec's own deferral, not a defect this pass introduced, and it is not
silently dropped: `docs/tests/US-5.2-ac-test-matrix.md` carries an explicit
PS-AC1 row stating why no test exists, and
`screens/ProfileScreen.test.tsx::test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values`
pins the write-only interim (FR-2/Assumption #3) that FR-1's deferral
implies, as a positive assertion rather than leaving the gap wholly implicit.
Surfaced in this stage's Result Envelope as a `non_blocking_findings` entry.

## Collaborator-shape decisions this pass had to make (recorded in full in `docs/tests/US-5.2-test-strategy.md`)

No design doc (API/DB design are both `NOT_APPLICABLE`) fixes an internal
hook signature, a form's field labels, or a component's prop shape beyond
the implementation plan's prose. To write concrete, executable assertions,
this pass fixed the following — flagged here as findings for
`frontend-builder`/`reconciliation-reviewer` to check the shipped shape
against, not treated as resolved Open Decisions:

1. **`httpClient.ts`'s `httpDelete` gains an additive `body?: unknown` field
   on its existing options bag**, beyond Plan Architectural Change 1's
   literal "only `httpPatch` is new" wording — FR-6's `DELETE /auth/mfa`
   needs a request body (`current_password`, `code`) the current zero-body
   `httpDelete<T>(path, options)` cannot express, and the existing
   `revokeSession` call site stays valid unmodified. If `frontend-builder`
   chooses a different mechanism, `hooks/useMfaDisable.test.ts` is the file
   to reconcile.
2. **`useProfileUpdate.ts`'s exact return shape** (`{ mutateAsync, isPending,
   conflict, resetConflict }`, with `mutateAsync` unwrapping `httpPatch`'s
   `{data, status, headers}` envelope down to a bare `ProfileRead`) — see the
   test-strategy doc's full rationale.
3. **Field labels/button names** for `ProfileScreen`, `SecurityScreen`, and
   `DeactivateAccountScreen`'s forms (e.g., "Display name", "Start
   enrollment", "Yes, disable MFA", "Yes, deactivate my account") — no
   design doc fixes UI copy; this pass's regex matchers (`/save profile/i`,
   etc.) are loose enough to tolerate minor wording differences but do fix
   the *presence* and *accessible name pattern* of each control.
4. **`MfaEnrollmentBanner`'s new link is a plain `<a href>`, not
   `react-router-dom`'s `<Link>`** — keeps the three pre-existing
   bare-`render()` assertions (no `MemoryRouter`) passing unmodified, per
   Plan Risk 7's additive-only requirement.

## Caveats worth a reviewer's attention (non-blocking)

- **`SecurityScreen.test.tsx`'s `getByLabelText(/code/i)` assumes exactly one
  "Code"-labeled control is visible at a time.** This holds for every
  scenario this pass writes (the enroll form's TOTP-code field and the
  disable form's TOTP-code field are never both rendered together), but if
  `frontend-builder` ever labels a third control containing "code" (e.g. a
  "Recovery code" field) in the same rendered tree, these queries become
  ambiguous. The field-label assumption is exactly `"Code"`, not merely
  "contains code" — flagged so a resulting test failure reads as a naming
  collision to fix, not a test-writer defect.
- **`ProfileScreen.test.tsx::test_profile_screen_submits_only_changed_fields_on_save`
  proves "only the changed fields" only weakly.** Because PS-AC1/FR-1 is
  deferred (no `GET /profile`), the form always starts blank — there is no
  populated-baseline scenario available to construct a case where a
  naive "always send every field" implementation would leak an
  *unchanged-but-populated* field alongside the real edit. This test still
  catches sending empty-string values for untouched fields, but it cannot
  fully exercise the AC's "only changed fields" guarantee until FR-1's
  blocking gap is closed by a future backend Story. `reconciliation-reviewer`
  should not read this row as stronger evidence than it is.

## Coverage floor

Not measured by attempt 1 of this stage — `test:coverage` is CI-only
(`AGENTS.md` §5/§6's Frontend subsection) and there was no built scaffold yet
for the new files to run against. Enforced at `QUALITY_GATE`/Task T13.
Attempt 2 (below) did run it, once IMPLEMENTATION's code existed and the
four test defects blocking a green suite were fixed; see "Attempt 2 delta"
for the resulting numbers. `QUALITY_GATE`/Task T13 remains the stage that
owns the pass/fail gate decision on this number — this report only records
what attempt 2 observed.

## Attempt 2 delta (TEST_WRITING loop-back, `changes_required_tests`)

IMPLEMENTATION's `frontend-builder` (attempt 1) implemented T1-T12 against
this pass's version-1 test suite and reported 186/190 passing, isolating
four defects to the test files themselves (`docs/catalog/US-5.2-pipeline-status.md`
attempt 1, "Test defects found"). All four verified against current source
and fixed; no test-function name, AC mapping, or asserted behavior changed.

1. **`components/RecoveryCodesDisplay.test.tsx`** — the copy-control test
   and the never-writes-to-storage test both mocked
   `navigator.clipboard.writeText` via `Object.assign(navigator, {
   clipboard: { writeText: vi.fn() } })`. Verified against
   `node_modules/@testing-library/user-event/dist/cjs/setup/setup.js`:
   `userEvent.setup()` unconditionally calls
   `Clipboard.attachClipboardStubToView(view)`, installing a getter-only
   `navigator.clipboard` (`dist/cjs/utils/dataTransfer/Clipboard.js`). A
   plain object assignment either gets silently shadowed (first test, if
   `setup()` ran first) or throws `TypeError: Cannot set property clipboard
   ... which has only a getter` (second test, once an earlier test already
   installed the getter). Fix: call `userEvent.setup()` first, then
   `vi.spyOn(navigator.clipboard, "writeText")` on user-event's own stub
   object instead of replacing `navigator.clipboard`. Confirmed this
   exercises the real code path — `RecoveryCodesDisplay.tsx`'s `handleCopy`
   calls `navigator.clipboard.writeText(...)` directly.
2. **`components/MfaEnrollmentBanner.test.tsx`** — the new
   `test_mfa_enrollment_banner_link_targets_settings_security` test lacked a
   `sessionStorage.clear()` Arrange step and inherited
   `mfaEnrollmentBannerDismissed=true` from the preceding
   dismiss-persistence test in the same file, so the banner (and its link)
   never rendered. Fix: added a describe-level `beforeEach(() =>
   sessionStorage.clear())` (isolates every test in the file, not just the
   one that failed) and removed the now-redundant inline clear from the
   dismiss-persistence test.
3. **`screens/DeactivateAccountScreen.test.tsx`** —
   `test_deactivate_account_screen_confirmation_step_names_the_consequence_before_final_submit`
   asserted `screen.getByText(/deactivat/i)` needs exactly one match, but
   `test/test-utils.tsx`'s always-rendered `data-testid="route-location"`
   probe (text `/settings/deactivate`), the screen's own `<h1>Deactivate
   account</h1>`, and the same test's mandatory "Yes, deactivate my
   account" button assertion all match `/deactivat/i` too — structurally
   unsatisfiable regardless of implementation. Fix: narrowed the query to
   `/sign you out/i`, the shortest fragment of the confirmation-consequence
   paragraph that stays unique against all three colliding strings —
   preserves this report's own caveat #3 ("matchers loose enough to
   tolerate minor wording differences") rather than pinning a full
   sentence.
4. Read `docs/catalog/US-5.2-pipeline-status.md`'s "Test defects found"
   section directly (the authoritative, complete list) to confirm no
   additional defect existed beyond the three files above — it names
   exactly four failing assertions across these three files (two in
   `RecoveryCodesDisplay.test.tsx`), matching "4 of 190 tests fail"
   exactly.

**Verification run (this attempt):**

- `npm run test -- --run` (full suite): **43 test files passed, 190 tests
  passed**, 0 failed.
- The three fixed files run in isolation together (`RecoveryCodesDisplay.test.tsx`,
  `MfaEnrollmentBanner.test.tsx`, `DeactivateAccountScreen.test.tsx`): 14/14
  pass.
- `npm run test:coverage`: now produces a full coverage report (attempt 1
  could not — `@vitest/coverage-v8`'s `reportOnFailure: false` default
  suppressed all output while any test failed). Result: **Statements
  96.55% (4423/4581), Branches 94.43% (815/863), Functions 84.91%
  (152/179), Lines 96.55% (4423/4581)**. The script's own configured
  global threshold requires Functions ≥85%; it exits 1 with `ERROR:
  Coverage for functions (84.91%) does not meet global threshold (85%)`.
  Not fixed by this pass — closing it means adding coverage of
  *implementation* code (a source-code change, out of this stage's scope
  and this pass's narrow defect-fix brief), not a test defect. The single
  largest identifiable gap is `frontend/src/store/queryClient.ts` at 0%
  (lines 1-12) — never imported by any test because
  `test/test-utils.tsx` constructs its own local `QueryClient` rather than
  importing the app's. Flagged in this stage's Result Envelope as a
  `non_blocking_finding` for `QUALITY_GATE`/Task T13 to weigh, since a
  failure there looping back to `TEST_WRITING` would consume this story's
  third and final loop-back attempt.
