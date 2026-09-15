---
artifact_type: test_strategy
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
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.6-plan-review.md
    version: 1
supersedes: null
---

# Test Strategy: Global Navigation (US-5.6)

**Track:** frontend. `API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` for this Story (spec v2's
own "API / Persistence Impact": no public API or persistence change), so per this skill's
frontend-track instructions the reference contract is the specification's own Verification
table (spec v2, "Verification" section) plus the implementation plan/task breakdown, not a
separate `openapi.yaml`/`entity-model.md`.

## Scope

This Story adds no screen, hook, or API-client function (implementation plan's Files To
Create: `None`). All new behavior lives in one file, `frontend/src/layouts/AppShell.tsx`
(four new ungated nav entries, a "Home" control, `Link` → `NavLink` swap for active-state
indication), verified — not implemented — by proving nav targets resolve against the
existing, unmodified route table in `frontend/src/routes/AppRoutes.tsx`. Per `AGENTS.md`
§5's Frontend subsection, this Story therefore needs **no new unit-test file**: there is no
pure function or hook in isolation to test. All coverage is integration-level, exercising
the real component tree via React Testing Library, consistent with both files already being
integration-style suites before this Story.

## Unit vs. Integration Split

| Level | File | Why |
|---|---|---|
| Integration | `frontend/src/layouts/AppShell.test.tsx` | Renders `AppShell` directly via `renderWithProviders` (real `MemoryRouter`, real `AuthProvider`/`QueryClientProvider`). Every FR (FR-2 through FR-6) is observable only through the rendered nav's DOM (accessible name, `href`, `aria-current`), not through a pure function — there is no business-logic branch to isolate as a unit test. |
| Integration | `frontend/src/routes/AppRoutes.test.tsx` | Renders the full route tree so a real client-side transition (nav click → `<Outlet />` content swap, nav itself unremounted) can be proven — `AppShell.test.tsx` renders `AppShell` in isolation with no nested `<Routes>`, so it cannot exercise an actual screen-to-screen transition (GN-AC1/GN-AC3 specifically). |

No new unit-test file is introduced, matching the impact analysis's Test-Surface Impact
section ("New test files: None required") and the implementation plan's Testing Strategy
closing bullet.

## Fakes / MSW Handlers Needed

No new MSW handler was required. `frontend/src/test/mswHandlers.ts`'s existing baseline
already covers every on-mount fetch the GN-AC6 cross-check and the new nav-click test
trigger: `GET /support/tickets` (shared by `TicketListScreen`/`AgentTicketQueueScreen`),
`GET /auth/sessions`, `GET /admin/users`, `GET /admin/audit-logs`. `ProfileScreen`,
`SecurityScreen`, and `DeactivateAccountScreen` issue no GET on mount at all (independently
re-confirmed: no on-mount `useQuery` fires when those screens render in the GN-AC6
cross-check or the Tab-order test). This matches `docs/reviews/plans/US-5.6-plan-review.md`'s
Risk-Realism finding that the plan's own Testing Strategy prose understates this ("MSW where
a click triggers a network call" undersells the GN-AC6 cross-check's eight mount-triggered
fetches) while the underlying handler baseline already covers it — no gap acted on here.

`frontend/src/test/test-utils.tsx`'s `RenderWithProvidersOptions.scopes` (added for US-5.4)
seeds every scope combination this Story's tests need; no new seed option was added.

## Statement-Count Ceiling

Not applicable. `AGENTS.md` §5's statement-count-ceiling guidance targets backend
list/nested-data endpoints guarding against a lazy-loading regression; this Story makes no
backend change and adds no list endpoint.

## Test Cases Per Level

### `frontend/src/layouts/AppShell.test.tsx` (integration)

- Two existing zero-scope cases (`test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope`,
  `test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope`)
  **extended in place**, not rewritten, with new positive assertions for the five ungated
  entries (Tickets, Sessions, Profile, Security, Deactivate Account) at zero scope
  (GN-AC2; Implementation Plan Risk 2 — extend, don't replace, a passing test).
- New `describe("AppShell global navigation (US-5.6)")` block, eight new cases: the four
  new entries' accessible name + `href` under a representative granted-scope combination
  (GN-AC2); Home clicked from a non-`/tickets` route lands on `/tickets` (GN-AC4/OD-1);
  the current route's entry carries `aria-current="page"` while a different entry does not
  (GN-AC5); Home never carries `aria-current`, even on `/tickets`, keyed on accessible name
  since both share `href="/tickets"` (GN-AC5's Home Exception/OD-2); a parent entry (Tickets)
  stays active on a nested route `/tickets/42` (OD-4); the active marker updates after a
  further navigation, not just a one-shot render (GN-AC5's "updates correctly... as the user
  continues to navigate"); the GN-AC6 behavioral cross-check (render with every scope
  granted, collect all nav `href`s into a `Set` — asserted to be exactly eight unique
  targets given Home/Tickets share one — then render `AppRoutes` at each and assert a real,
  non-login screen renders); an automated axe check on the nav in its fully scoped state
  (a11y row); and a combined Tab/Shift-Tab-order-plus-Enter-activation case (a11y-keyboard
  row).

### `frontend/src/routes/AppRoutes.test.tsx` (integration)

- One new case: starting on `/tickets`, click the "Sessions" nav entry; assert the URL
  updates to `/sessions` (client-side routing, GN-AC3) and that the "Tickets" nav link is
  the *same* DOM node captured before the click (`toBe`, reference equality) — proving the
  shared `AppShell`/`<nav>` was not remounted, only the routed `<Outlet />` content changed
  (GN-AC1). No `window.location` navigation exists to assert against in jsdom/RTL; this is
  the strongest available proxy for "no full page reload" in this rendering model, matching
  the implementation plan's own stated rationale.

## Determinism / AAA

Every new and extended test follows `# Arrange` / `# Act` / `# Assert` comments. Async
assertions use `findBy*`/`waitFor`, never a fixed `setTimeout`. The GN-AC6 cross-check's
`for...of` loop over a `Set` of hrefs collected at runtime is the one place this Story
deviates from "no loop in a test body" — this is a direct implementation of Architectural
Change 5's own prescribed mechanism (collect real hrefs from the rendered DOM, then assert
each resolves), not a substitute for `parametrize`; a hardcoded, hand-authored list was
explicitly rejected by the plan (Architectural Change 4/5) as a third, independently-drifting
copy of the same route literals. The loop's single logical assertion target is "every
collected nav href resolves to a live, non-login screen" — verified directly against this
Story's own two authors (`AppShell.test.tsx` collects, `AppRoutes.tsx` supplies the route
table under test), with no hardcoded parallel literal list. That target is made true, not just
asserted, by pairing two checks inside the loop: the `route-location` text match (proves the
URL landed on the intended path) and a `screen.getByRole("navigation")` presence check (proves
`AppShell.tsx`'s `<nav>` — unique to that file in this codebase — actually rendered, which is
only possible if the route matched inside the `ProtectedRoute`/`AppShell` group). Either check
alone is insufficient: `route-location` alone would also pass for a blank/unmatched render
(it echoes `MemoryRouter`'s `initialEntries` regardless of whether anything matched), and
`navigation` alone would not prove the URL is what was intended. Together they rule out both
of GN-AC6's named failure modes — a blank screen and a login-redirect artifact — not just one.

## Verified Execution (RED state, pre-`IMPLEMENTATION`)

`npx tsc --noEmit -p tsconfig.app.json` — clean, no type errors.
`npx eslint src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx` — clean.
`npx prettier --check src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx` — clean.
`npx vitest run src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx` — 50 tests run,
39 passed, 11 failed. All 11 failures are the new/extended US-5.6 cases listed above (2
extended zero-scope cases, 8 of the 9 new `AppShell.test.tsx` cases, 1 new `AppRoutes.test.tsx`
case), failing because `frontend/src/layouts/AppShell.tsx` has not yet been changed by
`IMPLEMENTATION` (still only renders a plain `Link`-based Tickets/Agent Queue/Users/Audit Log
nav, no Home, no `NavLink`, no account self-service entries) — the expected TDD-red state this
harness's own precedent (`frontend/src/test/test-utils.tsx`'s header comment, written by
`test-writer` for US-5.1 ahead of its own implementation) establishes for `TEST_WRITING`
output. No test was weakened, skipped, or `xfail`-marked to hide this; the red state is the
evidence that these tests actually exercise the not-yet-built behavior rather than passing
vacuously. The one new `AppShell.test.tsx` case that already passes today is the axe check
(`test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped`) — the
current minimal nav has no accessibility violation of its own, so this is a legitimately
passing floor, not a vacuous one; it will continue to assert the same thing once the nav
grows.

**GN-AC6 cross-check test, verified directly, not just asserted.** The behavioral cross-check
(`test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope`) was
specifically re-run in isolation (`npx vitest run ... -t
test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope`) to
confirm its `for...of` loop body actually executes today — over the 4 real hrefs
`AppShell.tsx` currently renders (`/tickets`, `/agent/tickets`, `/admin/users`,
`/admin/audit-logs`) — and that every per-href assertion inside the loop (the `route-location`
match, and the `navigation`-landmark presence proving the shell rendered rather than a blank
body or a login-redirect) passes today. The test's sole failure is
`expected 4 to be 8` on the trailing `expect(hrefs.size).toBe(8)`, deliberately placed after
the loop so this is verifiable pre-`IMPLEMENTATION` rather than asserted on faith. This closes
a defect an earlier draft of this test had: asserting `hrefs.size` *before* the loop meant the
loop body had never executed against real DOM output, and the per-href assertion
(`toHaveTextContent(href)` alone, without the `navigation`-landmark check) would have passed
identically for a genuinely blank render, since `route-location` echoes `MemoryRouter`'s
`initialEntries` regardless of whether anything matched. Both issues are fixed in the version
committed here.
