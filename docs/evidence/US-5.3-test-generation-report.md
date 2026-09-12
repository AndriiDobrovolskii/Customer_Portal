---
artifact_type: test_generation_report
story: US-5.3
version: 3
status: DRAFT
created_at: "2026-09-09T09:30:00Z"
updated_at: "2026-09-12T00:35:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.3-plan-review.md
    version: 2
supersedes: null
---

> **Continuation note.** A previous partial run of this stage produced
> `docs/tests/US-5.3-test-strategy.md` (v1, DRAFT) and five hook test files
> (`useTickets.test.ts`, `useTicketDetail.test.ts`, `useCreateTicket.test.ts`,
> `useReplyToTicket.test.ts`, `useCloseTicket.test.ts`). All five were read and
> found correct and complete against `implementation_plan` v2 — MSW at the
> network boundary, no `vi.mock()`, AAA structure, `test_` naming — and were
> kept as-written except one additive gap fix (below). This report covers the
> remainder of the pass: everything else this stage's Output Artifacts
> required that did not already exist.

# Test Generation Report: Support Tickets — Frontend (US-5.3)

## What was generated

**5 new test source files**, **9 additive edits** to existing/pre-existing
test files, for **94 test-function references** cited in
`docs/tests/US-5.3-ac-test-matrix.md` (all 94 independently re-grepped against
the files as written — 0 missing, see Self-check below). No `frontend/src/`
non-test source file was created or modified — this stage owns tests only;
every symbol these tests import (`api/supportApi.ts`, the six new `hooks/`,
the three new `screens/`, `ApiError.retryAfterSeconds`/`httpPost`'s
`idempotencyKey` option, `getRetryAfterSeconds`) does not exist yet
(`IMPLEMENTATION`'s Tasks T1–T19 have not run) — the intended TDD-red state.

### New files

| File | Runtime test cases | Level |
|---|---|---|
| `frontend/src/hooks/useReopenTicket.test.ts` | 3 | Unit (`hooks/`) |
| `frontend/src/hooks/useRetryAfterCountdown.test.ts` | 5 | Unit (`hooks/`) |
| `frontend/src/screens/TicketListScreen.test.tsx` | 15 (10 single + 1 `it.each` over 5 statuses) | Integration (`screens/`) |
| `frontend/src/screens/NewTicketScreen.test.tsx` | 11 | Integration (`screens/`) |
| `frontend/src/screens/TicketDetailScreen.test.tsx` | 31 (17 single + 3 `it.each` blocks: 5 + 4 + 5 cases) | Unit (`offeredActionsForStatus`, 8 cases) + Integration (23 cases) |

### Additive edits

| File | Change | New cases |
|---|---|---|
| `frontend/src/hooks/useTickets.test.ts` | Added the missing "status change resets pagination" case (see "Gap fixed" below); 4 pre-existing cases kept unmodified | +1 (5 total) |
| `frontend/src/api/httpClient.test.ts` | Added `httpPost` `idempotencyKey` option coverage (Change 1) and `ApiError.retryAfterSeconds` 429-threading coverage (Change 2, OD-1); 5 pre-existing `httpPatch` cases kept unmodified | +7 (12 total) |
| `frontend/src/components/apiErrorHelpers.test.ts` | Added `getRetryAfterSeconds` coverage; 10 pre-existing cases kept unmodified | +3 (13 total) |
| `frontend/src/routes/AppRoutes.test.tsx` | Added 7 new `/tickets`-family route-table cases; renamed and retargeted 3 existing cases from `/` to `/tickets` (see "Renames" below); 8 unaffected pre-existing cases kept unmodified | +7 (18 total) |
| `frontend/src/routes/GuestOnlyRoute.test.tsx` | Renamed and retargeted 1 existing case from `/` to `/tickets`; 1 unaffected case kept unmodified | +0 (2 total) |
| `frontend/src/screens/LoginScreen.test.tsx` | Renamed and retargeted 1 existing case from `/` to `/tickets`; 6 unaffected cases kept unmodified | +0 (7 total) |
| `frontend/src/screens/MfaVerifyScreen.test.tsx` | Renamed and retargeted 2 existing cases from `/` to `/tickets`; 4 unaffected cases kept unmodified | +0 (6 total) |
| `frontend/src/layouts/AppShell.test.tsx` | Added a `/tickets` nav-link case and two `MfaEnrollmentBanner`-from-`AppShell` cases (its relocated render site, implementation_plan v2 Change 7); 2 pre-existing logout cases kept unmodified | +3 (5 total) |

### Not modified (deliberate)

- `frontend/src/components/MfaEnrollmentBanner.tsx`/`.test.tsx` — the
  component itself does not change under implementation_plan v2 Change 7
  (only its *caller* moves, from `PlaceholderHomeScreen.tsx` to
  `AppShell.tsx`). Its own three pre-existing bare-`render()` tests keep
  asserting the component in isolation and need no edit; the caller-relocation
  is proven instead by the two new `AppShell.test.tsx` cases above.
- `frontend/src/screens/PlaceholderHomeScreen.tsx`/`.test.tsx` — deletion is
  `task_breakdown` v2 Task T17's own deliverable (`frontend-builder`), tied to
  the implementation change itself, not a test-authoring decision. Deleting
  this test file now, before the implementation exists, is out of this
  stage's scope.
- `frontend/src/test/mswHandlers.ts`/`mswServer.ts`/`test-utils.tsx` — Task
  T5's own deliverable (baseline handlers) and `implementation_plan` v2 Risk
  2's explicit "no `test-utils.tsx` signature change" constraint,
  respectively. Every new/edited file above defines its own
  `server.use(...)` overrides; `TicketDetailScreen.test.tsx` wraps `ui` in its
  own local `<Routes><Route path="/tickets/:id" element={ui} /></Routes>`.

## Gap fixed in the pre-existing `useTickets.test.ts`

The file from the previous partial run proved the status filter is sent as a
query parameter but never proved TK-AC2's own second clause — "the cursor is
reset" — end to end (its own comment hand-waved this: "a distinct `status`
value is a distinct queryKey"). Added
`test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page`:
mounts unfiltered, pages forward to a second page via `fetchNextPage()`, then
flips `status` via `rerender()` and asserts `data.pages` is back to length 1
with `cursor: null` on the wire — the actual reset TK-AC2 requires, not just a
fresh-mount inference from the queryKey design.

## Self-check performed (skill Completion Criteria)

- `grep -rn "vi.mock(" frontend/src`: **0 hits**, anywhere in the tree
  (including this Story's 5 new/9 edited files and every pre-existing US-5.1/
  US-5.2 file).
- Every `it()`/`it.each()` title across **all 54** `.test.ts(x)` files in
  `frontend/src` (**280 titles total**, not only this Story's) matches
  `^test_[a-z0-9_%]+$` (`%s` only inside an `it.each` template) — checked
  programmatically, **0 pattern violations, 0 duplicate names within any
  file**.
- Every test-function reference in `docs/tests/US-5.3-ac-test-matrix.md`
  (**94 references**) was independently re-grepped against the file it
  claims, as a literal quoted `it("...")` title — **0 missing**.
- `crypto.randomUUID()` (the mechanism `useCreateTicket.test.ts`'s three
  key-lifecycle cases and `useCreateTicket.ts`'s own implementation depend
  on, per implementation_plan v2 Change 8) was verified to work under this
  project's actual test runtime (jsdom 25 + Vitest 2.1, via a throwaway probe
  test run and discarded) — no polyfill needed, no gap to report here.
- `docs/workflow/history.jsonl`'s `2026-09-08T21:00:00Z` `HUMAN_REJECTED`
  entry was read directly and its `comment` field's six OD resolutions
  (OD-1 High, OD-2 Medium, OD-3 Medium, OD-4 Low, OD-5 Low, OD-6 Medium)
  confirmed to match `implementation_plan` v2's own restatement of them
  word-for-word — the provenance this report's and the strategy doc's
  "OD-1..6 are firm architecture" conclusion rests on.

## Known RED-state failures (expected, not defects)

Every file listed above fails at **module-resolution time** today — none of
`api/supportApi.ts`, the six new `hooks/` files, the three new `screens/`
files, `httpPost`'s `idempotencyKey` option, `ApiError.retryAfterSeconds`, or
`apiErrorHelpers.ts`'s `getRetryAfterSeconds` export exist yet
(`IMPLEMENTATION` Tasks T1–T19 have not run). This is the intended TDD-red
state, consistent with `docs/tests/US-5.1-test-strategy.md`'s and
`docs/tests/US-5.2-test-strategy.md`'s own precedent. No test suite run and no
coverage number are reported by this pass — both require the implementation
to exist first (`test:coverage` is CI-only per `AGENTS.md` §5/§6's Frontend
subsection); enforced at `QUALITY_GATE`/Task T20 per `task_breakdown` v2.

## Renames (not deleted US-5.1 coverage)

FR-15 moves the authenticated home/post-login-redirect target from
`PlaceholderHomeScreen.tsx`'s `"/"` to `/tickets`. Four pre-existing test
cases had their **assertion target** changed from `/` to `/tickets` and were
renamed to match (function name and behavior both updated together, not
silently retargeted under an unchanged name):

- `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_login_is_redirected_to_placeholder_home` → `..._to_tickets`
- `routes/AppRoutes.test.tsx::test_app_routes_authenticated_user_visiting_register_is_redirected_to_placeholder_home` → `..._to_tickets`
- `routes/AppRoutes.test.tsx::test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home` → `..._to_tickets` (this case also gained a `GET /support/tickets` MSW handler, since `/tickets` now renders `TicketListScreen`, which fetches on mount)
- `routes/GuestOnlyRoute.test.tsx::test_guest_only_route_authenticated_user_is_redirected_to_placeholder_home` → `..._to_tickets`
- `screens/LoginScreen.test.tsx::test_login_screen_valid_credentials_without_mfa_stores_token_in_memory_and_redirects_to_home` → `..._redirects_to_tickets`
- `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_totp_code_completes_login_same_as_login_without_mfa` → `..._and_lands_on_tickets`
- `screens/MfaVerifyScreen.test.tsx::test_mfa_verify_screen_valid_recovery_code_completes_login_same_as_login_without_mfa` → `..._and_lands_on_tickets`

No AC coverage, assertion count, or behavior beyond the redirect target itself
changed in any of these — read as renames, not as removed US-5.1/US-5.2
coverage.

## Methodology notes worth a reviewer's attention

- **Fake timers confined to `useRetryAfterCountdown.test.ts`.** Per
  `docs/tests/US-5.3-test-strategy.md`'s async-assertion rule
  (`waitFor`/`findBy*`, never a fixed timer), `vi.useFakeTimers()` is used
  only in this one unit test file, advanced synchronously inside `act()`.
  The two screen-level 429 tests (`NewTicketScreen.test.tsx`,
  `TicketDetailScreen.test.tsx`) assert only the `t=0` state (message present,
  submit disabled, exactly one request fired) and leave the
  tick-to-zero/`isBlocked`-flips/interval-cleared-on-unmount proof entirely to
  the hook's own unit test — mixing fake timers with `userEvent`/`waitFor` at
  the screen level is unreliable and was deliberately avoided.
- **Route-ranking (Risk 9) asserted by rendered content, not by pathname.**
  `toHaveTextContent("/tickets")` is a substring match that `/tickets/new`
  would also satisfy, so
  `test_app_routes_tickets_new_renders_new_ticket_screen_not_ticket_detail_screen`
  asserts `NewTicketScreen`'s Subject field is present instead — the
  discriminating check Risk 9 actually needs.
- **`offeredActionsForStatus` export requirement recorded as a
  collaborator-shape decision**, not assumed silently: added as item 10 to
  `docs/tests/US-5.3-test-strategy.md`'s existing list. `implementation_plan`
  v2 places this pure function inside `TicketDetailScreen.tsx` itself; this
  pass's unit-level table-driven test (TK-AC9) requires it to be a named
  export from that same module, or the import fails at module-resolution
  time regardless of implementation correctness.
- **The three renamed-and-retargeted `AppRoutes.test.tsx`/`GuestOnlyRoute.test.tsx`/
  `LoginScreen.test.tsx`/`MfaVerifyScreen.test.tsx` cases are the only tests
  that can actually prove Task T19** (per `implementation_plan` v2 Change 11:
  `/` becomes `<Navigate to="/tickets" replace>`). An `AppRoutes.test.tsx`-only
  assertion of `/tickets` would pass even if `MfaVerifyScreen.tsx`'s
  `navigate("/")` or `LoginScreen.tsx`'s `?? "/"` default were never updated,
  because the `/`→`/tickets` redirect launders the result. These four files'
  standalone-render tests (no enclosing `/`→`/tickets` route) are the
  discriminating coverage; the `AppRoutes.test.tsx`-level assertions
  supplement rather than replace them.

## Coverage floor

Not measured by this pass — no implementation exists yet for the new/edited
test files to run against (RED state, above). Enforced at
`QUALITY_GATE`/Task T20 per `task_breakdown` v2, with no exclusion carved out
for `offeredActionsForStatus`'s unrecognized-status branch, the 429-only
`Retry-After` gate in `parseResponse`, or `useCreateTicket.ts`'s key-rotation
branch (all three are explicitly named, covered branches in this pass's own
suite, not gaps left for that gate to discover).

## Gaps Not Covered

None. Every TK-AC (TK-AC1 through TK-AC14) has at least one test asserting
its stated behavior — see `docs/tests/US-5.3-ac-test-matrix.md`'s "Gaps Not
Covered" section, which is empty for the same reason. Unlike US-5.2 (PS-AC1
untestable pending a missing backend endpoint), every endpoint this Story's
spec names already ships (US-4.1/US-4.2/US-4.3/US-4.4), so no AC is deferred.

## Attempt 2 (TEST_WRITING loop-back via `changes_required_tests`)

`IMPLEMENTATION`'s `frontend-builder` sub-step built the full implementation
against this stage's v1 test suite (289/291 passing) and, through isolated
reproduction, confirmed exactly three test-file defects (no implementation
defect in any of the three). This attempt fixes only those three; no test was
rewritten beyond what each fix required, no assertion was weakened, and no
`frontend/src` implementation file was touched (out of this stage's remit —
`frontend-builder` owns implementation code). `docs/tests/US-5.3-test-strategy.md`
and `docs/tests/US-5.3-ac-test-matrix.md` are unaffected in content (AC
coverage, unit/integration split, and test-function names named in the
matrix are all unchanged) and remain at v1.

1. **`frontend/src/hooks/useRetryAfterCountdown.test.ts`** —
   `test_use_retry_after_countdown_clears_its_interval_on_unmount` spied on
   `globalThis.clearInterval` via `vi.spyOn` and never restored it, leaking an
   undefined `clearInterval` into the next test in file order under vitest's
   fake-timer install/uninstall cycle
   (`test_use_retry_after_countdown_reinitializes_when_a_new_retry_after_seconds_value_arrives`
   failed with `ReferenceError: clearInterval is not defined` on unmount).
   Fix: added `clearIntervalSpy.mockRestore();` immediately after the
   existing assertion, in the same test.

2. **`frontend/src/screens/NewTicketScreen.test.tsx`** —
   `test_new_ticket_screen_blocks_submission_on_over_length_subject_body_category_without_calling_api`
   used `user.type()` to enter 151/5001/51-character strings; `user.type()`
   dispatches one synthetic keystroke per character and does not complete for
   a 5001-character string even at a 60s timeout (a documented
   `@testing-library/user-event` characteristic, unrelated to the component).
   Fix: replaced the three over-length `user.type()` calls with
   `fireEvent.change(el, { target: { value: <string> } })`, keeping the same
   subject/body/category lengths and the same assertions (a field-level alert
   renders, `apiCalled` stays `false`).

3. **`frontend/src/hooks/useTickets.test.ts`** —
   `test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page`
   declared `let status: string | undefined` and reassigned it later in the
   same test body; ESLint's `prefer-const` flagged the binding as a false
   positive (confirmed via an isolated repro of an unrelated closure of the
   same shape) — `prefer-const`'s own autofix (`let`→`const`) would throw
   `TypeError: Assignment to constant variable` at runtime, so the pattern
   needed reworking rather than autofixing. Fix: replaced the `let` binding
   with a `const statusRef: { current: string | undefined }` object, mutating
   `statusRef.current` instead of reassigning a variable — identical
   behavior (the hook still reads a fresh `status` value on each render via
   the closure, the test still asserts the same reset-to-one-page-with-null-cursor
   outcome), no ESLint suppression added.

### Verification (attempt 2, real command output)

- `npx vitest run` (full suite): **53 files / 291 tests passed** (up from
  289/291 at the end of `IMPLEMENTATION`'s frontend-builder sub-step; the two
  previously-failing/hanging tests named above now pass, plus the
  `useTickets.test.ts` case that previously failed `lint`).
- `npm run lint --max-warnings=0`: **0 errors** on all three touched files
  and on the full `frontend/src` tree except one **pre-existing** warning in
  `frontend/src/screens/TicketDetailScreen.tsx:44` (`react-refresh/only-export-components`,
  the mandated `offeredActionsForStatus` dual export required by TK-AC9) —
  not introduced by this attempt, not in a file this attempt touched; see
  this Result Envelope's `non_blocking_findings`.
- `npm run type-check` (`tsc -b --noEmit`): clean, no output.
- `npm run format:check` (`prettier --check .`): the three touched files are
  clean; 7 unrelated pre-existing files elsewhere in the tree (not touched by
  this attempt) were separately flagged and are out of this fix's scope.

## Attempt 3 (TEST_WRITING loop-back via `changes_required_tests`, after the
TicketDetailScreen.tsx eslintrc human sign-off)

`IMPLEMENTATION`'s `frontend-builder` sub-step re-verified the full DoD chain
against the current tree (attempt 3, after the human-approved
`frontend/.eslintrc.cjs` override made `lint` clean) and found one new
test-file defect, confirmed by two full-suite reproductions: a timing flake,
not present at the previous close-out run. No `frontend/src` implementation
file was touched by this fix (out of this stage's remit).
`docs/tests/US-5.3-test-strategy.md` and `docs/tests/US-5.3-ac-test-matrix.md`
are unaffected in content and remain at v1.

1. **`frontend/src/screens/ProfileScreen.test.tsx`** (US-5.2 file, fixed here
   because it is the loop-back's named defect) —
   `test_profile_screen_422_validation_error_maps_errors_array_onto_matching_fields`
   used `user.type()` to enter a 200-character display name; under
   full-suite load this reliably exceeded the 5000ms default test timeout
   (reproduced twice) while passing standalone in 3.2s — the same
   `@testing-library/user-event` long-string characteristic already fixed in
   `NewTicketScreen.test.tsx` (attempt 1/2 above), missed in this file. Fix:
   replaced the `user.type()` call with
   `fireEvent.change(el, { target: { value: "x".repeat(200) } })`, keeping
   the same input length and the same assertion (the field-level validation
   message renders).

### Verification (attempt 3, real command output)

- `npx vitest run` / `npm run test:coverage` (full suite, run twice): **53
  files / 291 tests passed** both times (up from 290/291 at the start of this
  attempt); coverage 97.47%/95.29%/87.39%/97.47% (statements/branches/
  functions/lines) vs. the 85% floor.
- `npm run lint --max-warnings=0`: **0 errors, 0 warnings**, full tree
  (confirms the TicketDetailScreen.tsx eslintrc sign-off holds).
- `npm run type-check` (`tsc -b --noEmit`): clean, no output.
- `npm run format:check` (`prettier --check .`): clean, full tree.
