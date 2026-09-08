---
artifact_type: test_strategy
story: US-5.1
version: 1
status: ARCHIVED
created_at: "2026-09-07T20:00:00Z"
updated_at: "2026-09-07T20:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.1-plan-review.md
    version: 1
supersedes: null
---

# Test Strategy: Authentication & Session Management — Frontend (US-5.1)

## Scope: written one level before this project's usual "before `IMPLEMENTATION`" state

Every prior `TEST_WRITING` pass in this repository (`US-4.1`–`US-4.3`) wrote
tests against a codebase whose `tests/` tree, pytest configuration, and CI
wiring already existed — only the specific symbols under test (a new
`service.py` method, a new schema) were missing, and the tests were expected
to fail at **collection/import time**. This Story is the repository's first
ever frontend work: **no `frontend/` directory exists at all** — no
`package.json`, `vite.config.ts`, `tsconfig.json`, ESLint/Prettier config, or
test runner. `docs/plans/US-5.1-task-breakdown.md`'s Task T1 (scaffold) is
itself an `IMPLEMENTATION`-stage task that has not run.

Despite that, this pass writes **real test source files** — 26 files, 82
`it()` cases — against the collaborator shapes fixed below, not merely a
prose plan. The reasoning: this skill's own Result Envelope contract requires
`PASS` to mean "every acceptance criterion has at least one test that
asserts its stated behavior, and the matrix rows name test functions that
exist" — a matrix naming functions that were never written could not
honestly claim `PASS`, and none of this stage's loop-back keys
(`changes_required_tests` routes back to `TEST_WRITING` itself;
`invalid_specification`/`invalid_api_design`/`invalid_database_design` do not
apply — nothing upstream is invalid) represents "planning done, authoring
deferred." `IMPLEMENTATION.loop_back.changes_required_tests`
(`docs/workflow/stage-map.yaml`) only makes sense as a routing target if test
files already exist before `IMPLEMENTATION` runs, exactly as this pass does.

Every test file below is expected to fail at **module-resolution time** (no
`frontend/` scaffold to resolve `../test/test-utils`, `../store/authStore`,
etc. against, not merely a missing named export) until `IMPLEMENTATION`'s
Tasks T1–T16 land the scaffold and every symbol. This is the intended
TDD-red state, one layer further out than `US-4.3`'s import-time failures —
not a defect in this pass.

## Unit vs. Integration split (`AGENTS.md` §5's Frontend subsection)

- **Unit** (`frontend/src/api/*.test.ts`, `frontend/src/hooks/*.test.ts`
  except the one integration file below) — a pure function or a hook in
  isolation via Vitest, MSW as the network boundary (never a hand-mocked
  `fetch`). Covers: `refreshCoordinator.ts`'s single-flight promise-sharing
  logic in isolation from any component tree (3 cases); `errorNormalization.ts`'s
  branch coverage over RFC 7807 shapes and Register's two non-conforming
  shapes (OD-4, 5 cases); each of the nine screen-facing hooks' own
  success/error mapping and (for session-mutating hooks) that the store is
  updated only in `onSuccess` (18 cases across 9 files).
- **Integration** (`frontend/src/{routes,layouts,components,screens}/*.test.tsx`,
  plus `frontend/src/hooks/refreshCoordinator.integration.test.tsx`) — React
  Testing Library renders the real component tree, MSW intercepts at the
  network boundary with handlers shaped like the real backend responses
  (status, body, and error envelope — including Register's two non-RFC7807
  shapes). No `vi.mock()` of the unit under test anywhere in this pass
  (confirmed by a repo-wide grep after writing all 26 files — see the
  generation report).

## Test infrastructure: one file written by this pass, two left to Task T4

Task T4 (`frontend/src/test/mswServer.ts`, `mswHandlers.ts`, `test-utils.tsx`)
is named as `frontend-builder`'s own `IMPLEMENTATION`-stage deliverable in
`docs/plans/US-5.1-task-breakdown.md`. On reflection during this pass,
`test-utils.tsx` is treated differently from the other two: `mswServer.ts`/
`mswHandlers.ts` genuinely encode **backend response shapes** — builder
territory, since they must match what `IMPLEMENTATION` actually builds
against. `test-utils.tsx`, by contrast, is the **render harness this test
suite itself defines** — its `renderWithProviders`/`renderHookWithProviders`
signature and its `data-testid="route-location"`/`"route-location-state"`
markers are load-bearing for nearly every routing/session assertion in this
pass (~50 of 82 cases). `IMPLEMENTATION.inputs` (`stage-map.yaml`) includes
`test_strategy`/`ac_test_matrix` but not `test_generation_report`, and Task
T4's own verification command fixes only the MSW handler count — nothing
about `test-utils.tsx`'s shape. Recording the contract only in this
document's prose would leave it something `frontend-builder` is never told
to read; every one of this suite's routing assertions would then fail on a
missing test id the first time these tests actually run, routing back
through `changes_required_tests` for a defect this pass could have
prevented. This pass therefore writes `frontend/src/test/test-utils.tsx`
itself — a test-only file in this skill's own output tree, the same
category as the 26 test source files, not a production or builder-owned
deliverable. `mswServer.ts` and `mswHandlers.ts` remain Task T4's, unwritten
here; every test file in this pass imports them assuming the shapes fixed
below.

## Collaborator-shape assumptions (no design doc fixes these — recorded so `IMPLEMENTATION`/`reconciliation-reviewer` can check the shipped shape against what this suite assumes)

- **`frontend/src/test/test-utils.tsx`** — **written by this pass** (see
  above), not assumed. Exports `renderWithProviders(ui, options?: { route?:
  string; isAuthenticated?: boolean; user?: UserRead; mfaToken?: string;
  mfaEnrollmentDeadline?: string | null })` — wraps `QueryClientProvider` +
  `AuthProvider` (seeded via a new test-only `initialState` prop, see below)
  + `MemoryRouter` (`initialEntries: [options.route ?? "/"]`), and renders a
  `RouteLocationProbe` sibling (`useLocation()`) exposing
  `data-testid="route-location"` (pathname) and
  `data-testid="route-location-state"` (a redirect's `state.from.pathname`,
  or `""`). No enclosing `<Routes>` is required for this to work — a bare
  guard's `<Navigate>` only needs a Router context to act, and the probe
  re-renders on any navigation inside the same `MemoryRouter`, which is why
  `ProtectedRoute.test.tsx`/`GuestOnlyRoute.test.tsx` can render the guard
  directly as `renderWithProviders`'s `ui` without a route table. Also
  exports `renderHookWithProviders(hook, options)` — the same provider stack
  wrapped around `@testing-library/react`'s `renderHook`. Also re-exports
  `waitFor`.
- **`frontend/src/test/mswServer.ts`** exports `server` (MSW `setupServer`),
  with `beforeAll`/`afterEach`/`afterEach`/`afterAll` wiring already done in a
  global Vitest setup file (assumed, not itself under test here) — every test
  file calls `server.use(...)` to override the default handler for its own
  scenario, never `server.listen()`/`close()` directly.
- **`frontend/src/api/authApi.ts`** exports one function per backend
  operation, matching Task T2's file list: `register`, `login`, `verifyMfa`,
  `refresh`, `logout`, `logoutAll`, `listSessions`, `revokeSession`,
  `requestPasswordReset`, `confirmPasswordReset`. All ten resolve relative to
  `/api/v1/auth/...`, matching the spec's own API Contract table and OD-1's
  same-origin dev-proxy default (`implementation_plan` Architectural Change
  1's scaffold bullet 2) — every MSW handler in this suite is written against
  that path prefix.
- **`frontend/src/api/refreshCoordinator.ts`** exports `coordinateRefresh(refreshFn:
  () => Promise<RefreshResponse>): Promise<RefreshResponse>` — a module-level
  singleton promise; concurrent callers share it; it resolves/rejects once
  per "generation" and a later call after settlement starts a new one. A
  test-only `resetRefreshCoordinator()` export clears the singleton between
  tests (unit test file only).
- **`frontend/src/api/errorNormalization.ts`** exports `normalizeApiError(input:
  { status: number; contentType: string | null; body: unknown }):
  NormalizedApiError`, `NormalizedApiError = { status: number; message:
  string; fieldErrors?: Record<string, string> }`.
- **`frontend/src/store/authStore.tsx`** exports `AuthProvider` and
  `useAuthStore()` returning `{ accessToken: string | null; isAuthenticated:
  boolean; user: UserRead | null; mfaToken: string | null;
  mfaEnrollmentDeadline: string | null; setSession: (session: { accessToken:
  string; user: UserRead; mfaEnrollmentDeadline?: string | null }) => void;
  setMfaToken: (token: string | null) => void; clearSession: () => void }`.
  `mfaEnrollmentDeadline` is added to the store beyond the plan's own Client
  State Notes (which name only `accessToken`/`isAuthenticated`/current
  user/`mfaToken`) because `PlaceholderHomeScreen` must read
  `LoginResponse`/`MfaVerifyResponse`'s own `mfa_enrollment_deadline` field
  from *somewhere* to surface `MfaEnrollmentBanner` (story Assumption #6),
  and no other mechanism is named anywhere upstream — flagged here as this
  pass's own necessary addition, not a design-doc-fixed fact.
  `AuthProvider` also accepts a test-only `initialState?: AuthStateSeed`
  prop (`AuthStateSeed` = the same shape minus the action functions) so
  `test-utils.tsx` can seed a starting session without going through a real
  login call — a test-only seam, harmless in production where the prop is
  simply omitted. Never persists `accessToken`/`mfaToken` to
  `localStorage`/`sessionStorage` (spec NFR) — this suite's `LoginScreen`
  MFA test explicitly asserts both are absent from browser storage after an
  MFA-required response, not merely that the screen navigated correctly.
- **Hooks** (`useRegister`, `useLogin`, `useMfaVerify`, `useLogout`,
  `useLogoutAll`, `useSessions`, `useRevokeSession`,
  `useRequestPasswordReset`, `useConfirmPasswordReset`) each wrap the
  matching `authApi` function in a TanStack Query `useMutation`/`useQuery`,
  returning that hook's native result object (`mutateAsync`, `isPending`,
  `isSuccess`, `isError`, `data`, ...). Session-mutating hooks
  (`useLogin`/`useMfaVerify`/`useLogout`/`useLogoutAll`) call
  `authStore.setSession`/`clearSession` inside their own `onSuccess`, never
  requiring the calling screen to do so — matching Task T5's own
  verification command ("diff-read confirms session-mutating hooks update
  the store only in `onSuccess`, never inside a calling screen").
  `useRevokeSession` is assumed to invalidate the `useSessions` query cache
  key on success (not separately unit-tested here — the screen-level
  `SessionsScreen` integration test is what actually proves the row
  disappears from the rendered list, which is the AC's real requirement, not
  the query-cache mechanics).
- **`frontend/src/routes/ProtectedRoute.tsx`** reads `useAuthStore()`
  (read-only), renders its `children` when authenticated, and otherwise
  renders a redirect to `/login` carrying the current location so a
  successful login can return the visitor there.
- **`frontend/src/routes/GuestOnlyRoute.tsx`** is `ProtectedRoute`'s
  converse: redirects an authenticated visitor to `/` (the placeholder
  home), renders `children` otherwise.
- **`frontend/src/routes/AppRoutes.tsx`** wires all seven screens plus both
  guards into one real route table (`react-router-dom` v6, pending Risk 1's
  dependency sign-off, per implementation-plan Architectural Change 5) —
  this suite's tests render `<AppRoutes />` directly inside a
  `MemoryRouter`-backed `renderWithProviders`, never a hand-rolled fake
  router.
- **`frontend/src/layouts/AppShell.tsx`** hosts the logout/logout-all
  buttons the story's FE-AC5 requires. **Layering categorization left open
  by this pass, per `plan_review`'s own Low finding**: whether `AppShell.tsx`
  should itself call `useLogout`/`useLogoutAll` (implying a `hooks/` import
  the `AGENTS.md` §3 `routes/ (guards + layout)` row does not explicitly
  authorize) or delegate to a `components/`-layer child that owns that
  import is an `IMPLEMENTATION`-time categorization decision, not a testable
  AC condition — this suite asserts only the observable behavior (the
  buttons call the right endpoint and produce the right client-side effect),
  which holds under either categorization.
- **Screens** (`RegisterScreen`, `LoginScreen`, `MfaVerifyScreen`,
  `ForgotPasswordScreen`, `ResetPasswordScreen`, `SessionsScreen`,
  `PlaceholderHomeScreen`) each render a labeled form (React Hook Form) with
  `<label htmlFor>` associations (so `getByLabelText` resolves), a submit
  button whose accessible name is asserted directly (`/register/i`,
  `/^log in$/i`, `/verify/i`, `/send reset link/i`, `/reset password/i`), and
  render `ErrorState`/`FieldError` on failure per FE-AC9/FE-AC11.
  `SessionsScreen` renders each session as a `role="listitem"` row exposing
  a `Revoke <device label>` accessible button name.
- **`frontend/src/components/ErrorState.tsx`** accepts `{ kind: "network" |
  "server"; onRetry: () => void }` and renders a generic message plus a
  `Retry` button invoking `onRetry`.
- **`frontend/src/components/FieldError.tsx`** accepts `{ fieldErrors?:
  Record<string, string>; field: string }` and renders that field's mapped
  message, or nothing.
- **`frontend/src/components/MfaEnrollmentBanner.tsx`** accepts `{ deadline:
  string | null }`, renders a `role="status"` element naming the deadline
  when present, persists dismissal to `sessionStorage` under the key
  `mfaEnrollmentBannerDismissed` (OD-7's copy/tone remain genuinely open;
  this suite asserts only the structural default the implementation plan
  fixes, not OD-7's still-open exact wording).

## Open-Decision defaults this pass had to pick to write concrete assertions

Per `AGENTS.md` §1/this skill's own Constraints, `test-writer` does not
resolve Open Decisions — but a test assertion is necessarily concrete, so
where a screen's exact behavior is OD-gated, this pass records the specific
default it tested against (distinct from the implementation-plan's own
documented defaults, which this pass otherwise follows verbatim):

- **OD-6 (current-session revoke affordance)** — `implementation_plan`
  fixed `SessionsScreen`'s row component to take an `isCurrent` prop "making
  either OD-6 answer a prop/branch change, not a re-architecture," but did
  not itself pick disable-vs-let-it-409. This pass tests the **disable**
  default (`test_sessions_screen_current_session_row_revoke_control_is_disabled_per_od_6_default`)
  as the more defensible UX default absent a resolution, and separately
  proves the hook-level 409 path still exists
  (`useRevokeSession.test.ts::test_use_revoke_session_current_session_surfaces_normalized_409_current_session_error`)
  so the "let it 409" alternative remains provably wired even if OD-6
  resolves the other way and only the screen's disable-branch needs
  removing.
- **OD-7 (banner copy/dismissal)** — tested structurally only (renders when
  present, dismissible, persists via `sessionStorage`), never against
  specific copy text.
- **OD-8 (placeholder home content)** — tested structurally only (renders a
  heading for an authenticated user; surfaces the banner when the deadline
  is present).
- **OD-5 (validation rule set)** — tested against `implementation_plan`
  Architectural Change 7's own literal constants (Register: 8-char
  composition rule; Reset-Password: 12-char minimum), **plus** two tests
  proving the two genuinely server-only sub-rules (breach-check,
  differs-from-current) are deliberately **not** simulated client-side.
- **OD-1 (CORS)** — all MSW handlers and `authApi` assumptions use the
  same-origin `/api/v1/auth/...` path convention (implementation_plan's
  documented default); no test exercises a cross-origin/CORS-header
  scenario, since that is a browser/network-layer concern MSW does not
  model at all.
- **OD-2/OD-3** — the single-flight coordinator design (FE-AC4) is tested as
  fixed regardless of how these resolve (implementation_plan Architectural
  Change 3); no proactive/timer-based refresh test exists, matching Risk 4's
  explicit "not built" scope.

## Answering `plan_review`'s two Low, non-blocking findings

1. **`AppShell.tsx`'s `hooks/` import categorization** — not resolved by this
   pass (an `IMPLEMENTATION`-time architectural call, not a test-writer
   decision); the test suite asserts only observable behavior, which holds
   under either categorization. Recorded above, not silently dropped.
2. **The implied full FR-2/FR-3 flow tests** — **closed, not left open**.
   `routes/AppRoutes.test.tsx::test_app_routes_unauthenticated_navigation_to_protected_route_redirects_to_login_and_back_after_successful_login`
   already is a continuous FR-2 flow (unauthenticated → redirected to
   `/login` → real credential submission → lands back on the real
   originally-requested route, through the actual route tree). No
   equivalent continuous FR-3 test existed anywhere in the per-screen
   suite, so this pass added one:
   `routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home`
   (credentials submit → MFA-required → navigate to verify → valid TOTP
   code → lands on placeholder home) — the continuous MFA-challenge flow
   impact-analysis flagged as implied but unnamed.

## a11y bar

The Enforcement Matrix's "automated accessibility check (e.g. axe)" `[gate]`
row names a library (`vitest-axe` or equivalent) that
`implementation_plan` Risk 1 / Architectural Change 9 correctly flags as a
new dependency pending `AGENTS.md` §7.8 sign-off — not yet approved. This
pass does not write an assertion against an unapproved import. It does write
the dependency-free floor that is testable today:
`screens/RegisterScreen.test.tsx::test_register_screen_supports_full_keyboard_navigation_across_its_fields_and_submit_control`
(tab order reaches every field and the submit control, via
`@testing-library/user-event`'s `tab()` + `toHaveFocus()`). The automated,
axe-based check itself remains an open gap until the dependency is
approved — recorded in the generation report, not silently substituted.

## Coverage floor

85% minimum via `test:coverage`, `AGENTS.md` §5/§6's Frontend subsection —
enforced by `gate-enforcer` at `QUALITY_GATE`, not measured by this stage
(there is no scaffold to run `vitest --coverage` against yet).
