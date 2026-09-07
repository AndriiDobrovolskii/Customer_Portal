---
artifact_type: test_generation_report
story: US-5.1
version: 1
status: DRAFT
created_at: "2026-09-07T20:00:00Z"
updated_at: "2026-09-07T20:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/tests/US-5.1-test-strategy.md
    version: 1
  - path: docs/tests/US-5.1-ac-test-matrix.md
    version: 1
supersedes: null
---

# Test Generation Report: Authentication & Session Management — Frontend (US-5.1)

## Why this pass ran (TEST_WRITING, attempt 1)

`story-orchestrator` advanced from `HUMAN_PLAN_APPROVAL` (human approved
`implementation_plan` v1, `task_breakdown` v1, `plan_review` v1;
`docs/workflow/workflow-state.yaml` `updated_at: "2026-09-07T19:15:00Z"`) to
`TEST_WRITING`. `IMPLEMENTATION` (Task T1, the frontend scaffold) has not
run — confirmed by direct listing: no `frontend/` directory existed anywhere
in the repository before this pass (matching `impact_analysis`'s own
confirmed finding). This Story is the repository's first frontend work, so
this pass writes real test source files one level further out than every
prior `TEST_WRITING` pass in this project (`US-4.1`–`US-4.3`): those wrote
tests against a codebase whose test runner/config already existed and only
specific symbols were missing; here neither the symbols nor the scaffold
(`package.json`, `vite.config.ts`, `tsconfig.json`, ESLint/Prettier config,
Vitest) exist. See `docs/tests/US-5.1-test-strategy.md`'s "Scope" section for
the full reasoning on why this pass still writes real test files rather than
planning prose only.

## Files created this pass

**26 test source files, 82 `it()` cases**, under `frontend/src/`:

| Layer | Files | Cases |
|---|---|---|
| `api/` (unit) | `refreshCoordinator.test.ts` (3), `errorNormalization.test.ts` (5) | 8 |
| `hooks/` (unit) | `useRegister.test.ts` (2), `useLogin.test.ts` (3), `useMfaVerify.test.ts` (3), `useLogout.test.ts` (1), `useLogoutAll.test.ts` (1), `useSessions.test.ts` (1), `useRevokeSession.test.ts` (2), `useRequestPasswordReset.test.ts` (1), `useConfirmPasswordReset.test.ts` (2) | 16 |
| `hooks/` (integration, Task T6) | `refreshCoordinator.integration.test.tsx` (2) | 2 |
| `routes/` (integration) | `ProtectedRoute.test.tsx` (3), `GuestOnlyRoute.test.tsx` (2), `AppRoutes.test.tsx` (4) | 9 |
| `layouts/` (integration) | `AppShell.test.tsx` (2) | 2 |
| `components/` (integration) | `ErrorState.test.tsx` (3), `FieldError.test.tsx` (2), `MfaEnrollmentBanner.test.tsx` (3) | 8 |
| `screens/` (integration) | `RegisterScreen.test.tsx` (9), `LoginScreen.test.tsx` (6), `MfaVerifyScreen.test.tsx` (5), `ForgotPasswordScreen.test.tsx` (3), `ResetPasswordScreen.test.tsx` (6), `SessionsScreen.test.tsx` (5), `PlaceholderHomeScreen.test.tsx` (3) | 37 |

Plus one test-harness file this pass writes as its own render-contract
specification (see "Self-review fixes" #5 below):
`frontend/src/test/test-utils.tsx`.

Plus this stage's own three artifacts:
`docs/tests/US-5.1-test-strategy.md`, `docs/tests/US-5.1-ac-test-matrix.md`,
this file — new, v1.

**No production code or scaffold file was created**, and two of Task T4's
three test-infrastructure files remain unwritten (see below). Specifically
NOT written by this pass (per this skill's own Constraints):

- `frontend/package.json`, `vite.config.ts`, `tsconfig*.json`, ESLint/Prettier
  config, `index.html`, `src/main.tsx`, `src/App.tsx` (Task T1,
  `frontend-builder`'s own deliverable).
- `frontend/src/test/mswServer.ts`, `mswHandlers.ts` (Task T4,
  `frontend-builder`'s own deliverable — these encode backend response
  shapes, builder territory). `test-utils.tsx`, Task T4's third named file,
  **was** written by this pass instead — see "Self-review fixes" #5.
- Every production symbol the test files import: `authApi.ts`, `types.ts`,
  `errorNormalization.ts`, `refreshCoordinator.ts`, `authStore.tsx`,
  `queryClient.ts`, all nine hooks, `ProtectedRoute.tsx`, `GuestOnlyRoute.tsx`,
  `AppRoutes.tsx`, `AuthLayout.tsx`, `AppShell.tsx`, all seven screens,
  `ErrorState.tsx`, `FieldError.tsx`, `MfaEnrollmentBanner.tsx`.

## Verified this pass (pre-scaffold — no `npm install`, `tsc`, `eslint`, or `vitest` can run yet)

There is no `frontend/package.json` and therefore no installed toolchain —
`npm run lint`, `npm run type-check`, and `npx vitest run` cannot be invoked
against these files at all yet, unlike `US-4.3`'s pre-`IMPLEMENTATION` pass
(which could at least run `ruff`/`mypy`/`pytest --collect-only` against an
existing Python toolchain and got real, if red, output). Reporting a
fabricated "ran and failed as expected" transcript here would violate
`AGENTS.md` §7.9 ("reporting a check as passing \[or having run\] without
running it is the most serious violation"); none is reported.

What **was** checked, mechanically, against the working tree:

```
grep -r "vi\.mock(" frontend/src
  → no matches (confirmed after fixing 3 explanatory-comment false
    triggers found and corrected during this pass's own self-review — see
    below). No test file calls Vitest's component-mocking API on the
    component/hook/store under test, satisfying both AGENTS.md §5's
    "no mocking the unit under test" rule and
    .pre-commit-config.yaml's frontend-vi-mock-in-integration-tests hook
    (confirmed by direct read: scoped to
    ^frontend/src/screens/.*\.test\.tsx$, pygrep entry '\bvi\.mock\(').

grep -ohE 'test_[a-z0-9_]+' docs/tests/US-5.1-ac-test-matrix.md | sort -u
  → 83 unique tokens
grep -rohE 'it\("test_[a-z0-9_]+"' frontend/src --include=*.test.ts --include=*.test.tsx \
  | grep -oE 'test_[a-z0-9_]+' | sort -u
  → 82 unique tokens (every it() case's own name, exactly once each —
    no duplicate test names across files)
comm -23 named.txt defined.txt
  → test_matrix (a filename-fragment false positive from the matrix
    document's own filename in its text, matching the identical
    false-positive class US-4.3's report already documented — not a real
    function-name mismatch)
comm -13 named.txt defined.txt
  → (empty) — every defined test function is named somewhere in the matrix
```

Every `it("test_...")` case actually present in the 26 files written this
pass is named in `docs/tests/US-5.1-ac-test-matrix.md`, and every name the
matrix cites (aside from the filename-fragment false positive) resolves to a
real, existing test case. This is the strongest verification available
before a toolchain exists — it proves the matrix and the source agree with
each other, not that any test would pass or even parse correctly, which
requires `IMPLEMENTATION`'s Task T1 (scaffold) at minimum.

## What could not be verified this pass, and why

1. **No syntax/type check is possible.** These are `.ts`/`.tsx` files with no
   `tsconfig.json` to compile against and no installed TypeScript compiler.
   A typo, an unclosed JSX tag, or an import-path error would not be caught
   until `IMPLEMENTATION` Task T1 lands the scaffold and `npm run type-check`
   can run. This pass's own read-through of each file before writing the next
   is the only check applied.
2. **No test actually executed.** `npx vitest run` cannot run without
   `package.json`'s `vitest` dependency and `vite.config.ts`'s test
   configuration. Every test in this pass is, by construction, in the
   TDD-red state one level further out than `US-4.3`'s import-time failures —
   expected and self-resolving once `IMPLEMENTATION` lands the missing
   scaffold and symbols (Tasks T1–T16, in the dependency order
   `docs/plans/US-5.1-task-breakdown.md` already fixes).
3. **MSW v2 API surface assumed, not confirmed against an installed
   version.** `http.get/post/delete` + `HttpResponse.json(...)`/`HttpResponse.error()`
   syntax is fixed by Task T4's own verification command
   (`grep -c "http\.\(get\|post\|delete\)" frontend/src/test/mswHandlers.ts`
   already assumes this exact API), so this pass follows the same
   convention rather than inventing its own — but the actual installed MSW
   version is `frontend-builder`'s choice at Task T1, not confirmed here.
4. **The a11y bar's automated check is not implemented at all** (see below;
   intentional, not an oversight).
5. **Coverage** cannot be measured (`test:coverage` requires the full
   scaffold) — deferred to `gate-enforcer` at `QUALITY_GATE`, same as every
   prior story.

## Self-review fixes (before declaring PASS)

1. **Three files' own explanatory comments literally contained the string
   `vi.mock(`** (`screens/RegisterScreen.test.tsx`, `screens/LoginScreen.test.tsx`,
   `routes/AppRoutes.test.tsx`) — written to explain that the file does
   *not* call it. `.pre-commit-config.yaml`'s `frontend-vi-mock-in-integration-tests`
   hook is a pygrep rule (`'\bvi\.mock\('`) that does not distinguish
   comments from code, and its `files:` scope
   (`^frontend/src/screens/.*\.test\.tsx$`) would have matched two of these
   three at commit time — a self-inflicted gate failure the moment
   `IMPLEMENTATION` tries to commit this pass's own files. Fixed by
   rewording all three comments to describe the constraint without the
   literal substring (confirmed via `grep -r "vi\.mock(" frontend/src` → no
   matches, above).
2. **The implied full-flow tests `plan_review` flagged (Test-Strategy
   Realism, Low) were closed, not left as a documented gap.** Added
   `routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home`
   — the one continuous FR-3 flow (credentials → MFA-required → verify code
   → placeholder home) that did not previously exist anywhere in the
   per-screen suite; the equivalent continuous FR-2 flow already existed
   (`test_app_routes_unauthenticated_navigation_to_protected_route_redirects_to_login_and_back_after_successful_login`).
3. **The ac-test-matrix's first draft under-cited three real unit tests**
   (`useRegister.test.ts::test_use_register_duplicate_email_surfaces_normalized_409_error`,
   `useLogin.test.ts::test_use_login_invalid_credentials_surfaces_normalized_401_error_without_leaking_account_existence`,
   `useConfirmPasswordReset.test.ts::test_use_confirm_password_reset_invalid_token_surfaces_normalized_error`)
   and referred to `MfaEnrollmentBanner.test.tsx`/`PlaceholderHomeScreen.test.tsx`'s
   cases only as "(3 tests)" rather than by name. Corrected — every one of
   the 82 defined test names is now individually named in the matrix,
   confirmed by the `comm -13` re-check above returning empty.
4. **`frontend/src/test/test-utils.tsx` (one of Task T4's three named files)
   was written by this pass rather than left to `frontend-builder`.**
   Initially deferred, on the reasoning that Task T4 as a whole is
   test-infrastructure, not test source. On reflection: `test-utils.tsx`'s
   `renderWithProviders`/`renderHookWithProviders` signature and its
   `data-testid="route-location"`/`"route-location-state"` markers are
   load-bearing for roughly 50 of this pass's 82 test cases, and
   `IMPLEMENTATION.inputs` (`stage-map.yaml`) does not include
   `test_generation_report` — nothing tells `frontend-builder` to read this
   pass's own prose assumptions about that file's shape. Left unwritten, the
   first real test run would fail on a missing test id across half the
   suite, purely from an unstated contract, and loop back through
   `changes_required_tests` for a defect this pass could have prevented by
   simply writing the file. `mswServer.ts`/`mswHandlers.ts` remain
   `frontend-builder`'s: they encode backend response shapes, which is
   builder territory in a way a generic render harness is not.
5. **T6's file path was relocated, not inherited silently.**
   `docs/plans/US-5.1-task-breakdown.md`'s own Notes flagged
   `frontend/src/api/refreshCoordinator.integration.test.tsx` as "this
   breakdown's placement, not plan-fixed" and asked `test-writer` to
   confirm it. This pass places it at
   `frontend/src/hooks/refreshCoordinator.integration.test.tsx` instead:
   the test renders hooks via React Testing Library under a
   `QueryClientProvider`, and `AGENTS.md` §3's Frontend layer table forbids
   `api/` from importing React/TanStack Query at all — keeping a
   React-rendering test physically inside `api/` would misrepresent that
   boundary even though the test file itself sits outside `lint-imports`'s
   (nonexistent, for this stack) enforcement. `hooks/` is the layer the same
   table explicitly authorizes to import both `api/` and TanStack Query
   together, which is the actual boundary this test proves.

## Test-writer's own collaborator-shape assumptions

Recorded in full in `US-5.1-test-strategy.md`'s own section of the same
name; summarized here for the Result Envelope's `non_blocking_findings`. Most
consequential:

1. `test-utils.tsx` is assumed to export `renderWithProviders(ui, options)`
   and `renderHookWithProviders(hook)`, both wrapping
   `QueryClientProvider` + `AuthProvider` + `MemoryRouter`, and to render
   `data-testid="route-location"`/`"route-location-state"` markers this
   entire suite depends on for asserting routing outcomes without touching
   React Router internals directly. This is the single highest-leverage
   assumption in the whole pass — if `frontend-builder` shapes `test-utils.tsx`
   differently, most of the 26 files need a mechanical (not logical) update
   to their `renderWithProviders`/`renderHookWithProviders` call sites, not
   a rewrite of their assertions.
2. `authApi.ts`'s ten functions all resolve against `/api/v1/auth/...`
   (OD-1's same-origin default) — every MSW handler in this suite is written
   against that exact path prefix; a different base path or a
   cross-origin/CORS resolution of OD-1 would require every handler's path
   argument updated, not the test logic itself.
3. `useRevokeSession` is assumed to invalidate the sessions query cache on
   success; this pass does not unit-test that mechanic directly, only the
   screen-level observable effect (`SessionsScreen.test.tsx`) — matching
   this project's general preference for testing the effect a user/AC cares
   about over an internal cache-invalidation call.
4. `MfaEnrollmentBanner`'s dismissal persistence key
   (`mfaEnrollmentBannerDismissed`) and `ErrorState`'s `kind: "network" |
   "server"` prop shape are both this pass's own invented literal — no
   design doc fixes either; `reconciliation-reviewer` should confirm the
   shipped shape against this assumption, not silently trust it.

## OD-6 default recorded (not resolved) by this pass

`task_breakdown` T14 left `SessionsScreen`'s revoke-affordance behavior on
the current-session row as "per whichever OD-6 default is in force at build
time," without itself picking one. This pass had to test something concrete
and chose **disable the control on the current-session row**
(`test_sessions_screen_current_session_row_revoke_control_is_disabled_per_od_6_default`),
while separately keeping the hook-level 409-surfacing test
(`useRevokeSession.test.ts::test_use_revoke_session_current_session_surfaces_normalized_409_current_session_error`)
intact so the "let it 409" alternative remains provably wired if OD-6
resolves the other way. This is a testing default, not an OD-6 resolution —
flagged for `reconciliation-reviewer`/a human to confirm before this
screen's implementation is considered final.

## Gaps carried forward — not tested here, and why

1. **The a11y bar's automated axe-based check is not implemented.**
   `implementation_plan` Risk 1 / Architectural Change 9 correctly flags the
   library itself (`vitest-axe` or equivalent) as a new dependency requiring
   `AGENTS.md` §7.8 sign-off, not yet recorded as approved anywhere in this
   story's workflow history. This pass writes the one dependency-free floor
   that is testable today (keyboard/focus order on `RegisterScreen`) and
   explicitly does not fabricate an axe-shaped assertion against an
   unapproved import. The other six screens' equivalent keyboard/focus
   floor is not separately written — the mechanism is identical across
   screens (native semantic elements + `:focus-visible`, per Architectural
   Change 6) and one representative proof was judged sufficient pending the
   real automated check; a full per-screen axe pass is still owed once the
   dependency is approved.
2. **FE-AC11 (network/5xx) is not tested on every one of the seven
   screens.** `SessionsScreen`/`RegisterScreen`/`LoginScreen`/`MfaVerifyScreen`/
   `ForgotPasswordScreen`/`ResetPasswordScreen` each have at least one
   network-error case (six of seven), and `RegisterScreen`/`LoginScreen`/
   `SessionsScreen` additionally have a dedicated 5xx case; `PlaceholderHomeScreen`
   has none (it makes no request of its own in this Story's scope — it only
   renders the already-fetched session state). This is judged sufficient
   because FE-AC11's text is one general behavior ("any endpoint in this
   Story") proven by a representative sample plus the shared `ErrorState`
   component's own direct unit tests, not eleven independently-worded ACs —
   but this is a scope choice, not an oversight, and is named here rather
   than left implicit.
3. **OD-1 (CORS), OD-2/OD-3 (single-flight/proactive refresh), OD-5
   (validation rule set), OD-7 (banner copy), OD-8 (placeholder content) are
   all tested against this pass's or the implementation plan's own recorded
   default, not a resolved Open Decision.** Every default used is named
   explicitly in `US-5.1-test-strategy.md`'s "Open-Decision defaults" and
   "Collaborator-shape assumptions" sections — none is silently assumed.
4. **`AppShell.tsx`'s `hooks/`-import layering categorization**
   (`plan_review`'s Low finding) is not resolved by this pass — the test
   suite's assertions hold under either categorization, so this is
   correctly a test-writer non-issue, but it remains open for
   `IMPLEMENTATION`/`security-reviewer` to settle.
5. **`react-router-dom` and the a11y-check library are both still pending
   `AGENTS.md` §7.8 dependency sign-off**, per `implementation_plan` Risk 1 —
   this pass writes tests assuming `react-router-dom` v6 is approved (the
   plan's own named choice), consistent with how `task_breakdown` already
   gates Tasks T7/T16 on that same sign-off rather than blocking test
   authoring on it.

## Result

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-5.1
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-5.1-test-strategy.md
    - docs/tests/US-5.1-ac-test-matrix.md
    - docs/evidence/US-5.1-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "First-ever frontend TEST_WRITING pass in this repository: no frontend/ scaffold exists yet (IMPLEMENTATION Task T1 has not run), one level further out than US-4.3's precedent (missing symbols, not a missing toolchain). 26 real test files / 82 it() cases were written, plus frontend/src/test/test-utils.tsx (one of Task T4's three named files, written by this pass rather than left to frontend-builder - see below), against collaborator-shape assumptions recorded in full in US-5.1-test-strategy.md, expected to fail at module-resolution time until IMPLEMENTATION Tasks T1-T16 land the scaffold and every symbol - the intended TDD-red state, not a defect. No lint/type-check/test run could be executed (no installed toolchain); verification this pass is limited to a grep-based reconciliation between the ac-test-matrix and the actual it() names in the working tree, which found and closed three under-citation gaps and one filename-fragment false positive."
    - "Self-caught before declaring PASS: three files' own explanatory comments literally contained the substring 'vi.mock(' (intended to describe that the file does NOT call it), which would have tripped .pre-commit-config.yaml's frontend-vi-mock-in-integration-tests pygrep hook (comment-blind) for the two of the three under frontend/src/screens/. Reworded all three; confirmed zero matches for the literal pattern across frontend/src afterward."
    - "Closed plan_review's Test-Strategy Realism [Low] finding: added routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home as the one continuous FR-3 flow test that did not previously exist (the equivalent FR-2 flow test already existed). plan_review's other Low finding (AppShell.tsx's hooks/-import layering categorization) is answered as intentionally not resolved by this pass - the test suite's assertions hold under either categorization; left for IMPLEMENTATION/security-reviewer."
    - "Relocated task_breakdown's T6 file from its own flagged-as-unconfirmed placement (frontend/src/api/refreshCoordinator.integration.test.tsx) to frontend/src/hooks/refreshCoordinator.integration.test.tsx: AGENTS.md section 3's Frontend layer table forbids api/ from importing React/TanStack Query at all, and this test necessarily renders hooks via renderHook under a QueryClientProvider - hooks/ is the layer that table authorizes to import both api/ and TanStack Query together, the actual boundary this test proves."
    - "OD-6 (current-session revoke affordance) has no fixed default anywhere upstream (task_breakdown T14 explicitly left it to whichever default is in force at build time). This pass tested the disable-the-control default as the more defensible UX choice, while keeping the hook-level 409-surfacing test intact so the alternative (let it 409) remains provably wired if OD-6 resolves the other way. Flagged for reconciliation-reviewer/a human to confirm before SessionsScreen's implementation is considered final."
    - "a11y bar (Enforcement Matrix's own [gate] row): the automated axe-based check is NOT implemented - the library itself (vitest-axe or equivalent) is a new dependency pending AGENTS.md section 7.8 sign-off (implementation_plan Risk 1), not yet recorded as approved in this story's workflow history. Only a dependency-free keyboard/focus-order floor was written, on one representative screen (RegisterScreen), not all seven - the mechanism is identical across screens (native semantic elements + :focus-visible per Architectural Change 6). A full per-screen automated check remains owed once the dependency is approved."
    - "FE-AC11 (network/5xx) is tested on 6 of 7 screens (all but PlaceholderHomeScreen, which makes no request of its own) and 5xx specifically on 3 of 7 (RegisterScreen, LoginScreen, SessionsScreen) - judged sufficient because FE-AC11 is one general cross-cutting behavior proven by a representative sample plus ErrorState's own direct unit tests, not eleven independently-worded ACs. Named here as a scope choice, not hidden as an oversight."
    - "react-router-dom and the a11y-check library both remain pending AGENTS.md section 7.8 dependency sign-off (implementation_plan Risk 1, carried by task_breakdown against Tasks T7/T16). This pass's tests assume react-router-dom v6 is approved (the plan's own named choice) consistent with how task_breakdown already gates T7/T16 on the same sign-off without blocking test authoring on it."
    - "frontend/src/test/test-utils.tsx was written by this pass, not left to frontend-builder's Task T4 as originally planned: its renderWithProviders/renderHookWithProviders signature and route-location/route-location-state test-id markers are load-bearing for ~50 of 82 test cases, and IMPLEMENTATION.inputs (stage-map.yaml) does not include test_generation_report, so an unwritten contract would have failed at first real test run. mswServer.ts/mswHandlers.ts remain frontend-builder's (they encode backend response shapes). test-utils.tsx also fixes authStore.tsx's shape one field further than the plan's own Client State Notes: an mfaEnrollmentDeadline field (PlaceholderHomeScreen's MfaEnrollmentBanner needs it from somewhere and nothing upstream names a source) and a test-only AuthProvider initialState seeding prop - both this pass's own necessary additions, not design-doc-fixed facts. Every other collaborator shape this suite assumes (authApi.ts's /api/v1/auth/... path convention; each hook's onSuccess-updates-store contract; MfaEnrollmentBanner's dismissal-key/ErrorState's kind prop) is recorded in full in US-5.1-test-strategy.md's Collaborator-shape assumptions section - none is a design-doc-fixed fact. reconciliation-reviewer should confirm every shipped shape against these assumptions, not silently trust them, exactly as this project's US-4.3 precedent already established for the backend track."
```
