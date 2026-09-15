---
artifact_type: test_generation_report
story: US-5.6
version: 1
status: DRAFT
created_at: "2026-09-15T10:21:26Z"
updated_at: "2026-09-15T10:21:26Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.6-plan-review.md
    version: 1
supersedes: null
---

# Test Generation Report: Global Navigation (US-5.6)

## Files Touched

| File | Change |
|---|---|
| `frontend/src/layouts/AppShell.test.tsx` | Extended 2 existing zero-scope cases in place (added positive assertions for the five ungated entries; no existing assertion removed, weakened, or rewritten). Added 8 new cases in a new `describe("AppShell global navigation (US-5.6)")` block. Added imports: `axe` from `vitest-axe`, `AppRoutes` from `../routes/AppRoutes`. |
| `frontend/src/routes/AppRoutes.test.tsx` | Added 1 new case proving GN-AC1/GN-AC3 (nav persists, unremounted, across a client-side transition). No existing case modified. |

No production file was modified — `frontend/src/layouts/AppShell.tsx` and
`frontend/src/routes/AppRoutes.tsx` are untouched, per this skill's own constraint ("does not
write application code") and per the task breakdown's T1/T2 split, which attributes the
production change to `frontend-builder` at `IMPLEMENTATION`, not to this stage.

No new test file was created (matches impact analysis's Test-Surface Impact: "New test files:
None required"). No new MSW handler was added — `frontend/src/test/mswHandlers.ts`'s existing
baseline already covers every fetch this Story's new tests trigger (verified directly, see
Test Strategy's "Fakes / MSW Handlers Needed" section).

## Tests Added / Extended

11 test cases total: 2 extended, 9 new (8 in `AppShell.test.tsx`, 1 in `AppRoutes.test.tsx`).
Full list and per-AC mapping: `docs/tests/US-5.6-ac-test-matrix.md`.

## Verification Run

```
npx tsc --noEmit -p tsconfig.app.json
```
Clean — no type errors introduced.

```
npx eslint src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx
```
Clean — no findings.

```
npx prettier --check src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx
```
"All matched files use Prettier code style!"

```
npx vitest run src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx
```
Result: **2 test files, 50 tests total — 39 passed, 11 failed.**

All 11 failures are exactly the new/extended US-5.6 cases:

- `AppShell admin navigation (US-5.4) > test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` (extended)
- `AppShell admin navigation (US-5.4) > test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope` (extended)
- `AppShell global navigation (US-5.6) > test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href`
- `AppShell global navigation (US-5.6) > test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route`
- `AppShell global navigation (US-5.6) > test_app_shell_current_route_nav_entry_carries_aria_current_while_a_different_entry_does_not`
- `AppShell global navigation (US-5.6) > test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets`
- `AppShell global navigation (US-5.6) > test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route`
- `AppShell global navigation (US-5.6) > test_app_shell_active_nav_entry_updates_after_navigating_to_a_different_entry`
- `AppShell global navigation (US-5.6) > test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope`
- `AppShell global navigation (US-5.6) > test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry`
- `AppRoutes (FE-AC10) > test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav`

Each fails because `frontend/src/layouts/AppShell.tsx` has not yet been changed by
`IMPLEMENTATION` — it still renders only a plain-`Link` Tickets/Agent Queue/Users/Audit Log
nav with no Home control, no account self-service entries, and no `NavLink`/`aria-current`.
This is the expected **TDD-red state** for `TEST_WRITING` output on this track — the same
precedent `frontend/src/test/test-utils.tsx`'s own header comment records for US-5.1 ("Still
expected to fail at module-resolution time until IMPLEMENTATION lands..."). Stated plainly,
with a single consistent count: **12 cases were touched or added by this pass** (2 extended
zero-scope cases + 8 new `AppShell.test.tsx` cases + 1 new `AppRoutes.test.tsx` case + 1 new
`AppShell.test.tsx` axe case) — **11 of those 12 are red**, and **1 is green**. The one green
case is the axe check (`test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped`)
— a legitimate pass, not a vacuous one: the current minimal nav has no accessibility violation
of its own, and the same assertion will keep holding once the nav grows. The remaining **38
pre-existing, untouched tests** (50 total − 12 touched/added = 38) pass unchanged, confirming
no regression was introduced to either file's existing coverage. 38 + 11 + 1 = 50, matching
the run total above.

**GN-AC6 cross-check — verified to actually exercise its own mechanism, not just assert a
count.** An initial draft of `test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope`
asserted `hrefs.size === 8` *before* the `for...of` loop, which meant (a) the loop's own body
had zero execution evidence pre-`IMPLEMENTATION` (it would run for the first time only once
the count already matched, i.e. after `IMPLEMENTATION` — passing vacuously the very first time
it ever ran), and (b) the per-href assertion inside the loop was `route-location` text-content
alone, which is satisfied by `MemoryRouter`'s `initialEntries` regardless of whether anything
actually matched — so it would not have caught a genuinely blank render. Both were fixed
before this report was finalized: the count assertion now runs *after* the loop (verified by
isolated re-run: the loop executes today over the 4 real hrefs `AppShell.tsx` currently
renders, each passing its per-href assertions, and the test's sole failure is
`expected 4 to be 8`), and a `screen.getByRole("navigation")` presence check was added inside
the loop — `<nav>` is unique to `AppShell.tsx` in this codebase (direct search confirmed no
other screen/layout, including `AuthLayout.tsx`'s login render site, renders one), so its
presence can only follow from the route having matched and rendered inside the
`ProtectedRoute`/`AppShell` group, ruling out both a blank/404 render and a login-redirect
artifact — the two failure modes GN-AC6 itself names.

## Gaps / Items That Could Not Be Tested Yet

Every AC (GN-AC1–GN-AC6) and both non-numbered Verification rows (`a11y`, `a11y-keyboard`)
have a test function that asserts the AC's stated behavior directly (not merely its
existence) — see `docs/tests/US-5.6-ac-test-matrix.md`'s Coverage Confirmation. OD-3 (flat
list, no grouping) has no dedicated assertion of its own because it is a negative structural
property (absence of a wrapper element) rather than an independently observable behavior; it
is covered indirectly by every new-entry query resolving via `getByRole`/`name` directly
against the nav, with no assumption about a containing section — noted in the matrix rather
than left silent.

One item genuinely could not be verified pre-`IMPLEMENTATION`, recorded rather than silently
assumed: `test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry`'s
final step, `await user.keyboard("{Enter}")` activating a focused `<a>` link element, has no
prior precedent anywhere in this repository (confirmed by a repo-wide search for `{Enter}`/
`keyboard(` before writing this test) and, because the test already fails earlier at its
first `Tab`/`getByRole("link", { name: /^home$/i })` assertion (Home does not exist yet), the
`keyboard("{Enter}")` line has never actually executed in this codebase. `@testing-library/
user-event@14.5.2`'s documented behavior is that Enter on a focused native anchor dispatches a
click, which is what this assertion relies on — but this is an expectation about the library,
not evidence from a run in this repository. This should be re-verified once `IMPLEMENTATION`
lands the Home/`NavLink` changes and the test's earlier `Tab` assertions start passing, before
treating the full case as proven.

## Constraints Observed

- No `vi.mock()` on the unit under test (`AppShell`/`AppRoutes`) in either file — both use
  MSW (`server.use(...)` overrides plus the existing baseline handlers) at the network
  boundary only, consistent with `AGENTS.md` §5's Frontend subsection and this skill's own
  constraint.
- No test was weakened, skipped, or `xfail`-marked to force a green run — the 11 failures
  above are reported as-is, the expected and correct state for a `TEST_WRITING`-stage
  artifact produced ahead of `IMPLEMENTATION`.
- No AC was invented beyond the spec's stated six plus the two Verification-table rows; OD-3
  is recorded as indirectly, not directly, covered rather than asserted against a fabricated
  DOM structure.
