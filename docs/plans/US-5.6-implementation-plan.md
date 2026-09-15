---
artifact_type: implementation_plan
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T11:00:00Z"
updated_at: "2026-09-15T14:15:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.6-spec-review.md
    version: 1
  - path: docs/reviews/designs/US-5.6-design-review.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 2
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
supersedes: null
---

# Implementation Plan: Global Navigation (Frontend)

**Story ID:** US-5.6
**Track:** frontend (`docs/stories/US-5.6-global-navigation.md` front matter, line 7)

## Goal

Complete the nav already hosted by `AppShell.tsx` so every existing
authenticated screen is reachable and orientable, without adding any new
screen, route, or backend behavior (spec v2's "API / Persistence Impact":
"no public API behavior... and no persistence behavior"; design review v1:
`NOT_APPLICABLE`, corroborating). Concretely: add four ungated nav entries
for the account self-service screens (FR-2 — Profile, Security, Sessions,
Deactivate Account), add a "Home" control that always targets `/tickets`
(FR-4, resolving OD-1), swap the nav's `Link` elements for `NavLink` so the
current section is visually and programmatically distinguished (FR-5), with
"Home" itself exempt from that mechanism (OD-2) and parent entries staying
active on nested child/detail routes via `NavLink`'s default prefix matching
(OD-4), and verify — not restructure — that every nav target resolves to a
registered route (FR-6). This plan builds directly on
`impact-analyzer`'s survey (`docs/impact-analysis/US-5.6-impact-analysis.md`
v1) rather than re-deriving the affected-file list, and makes the two
concrete implementation calls the survey explicitly leaves open (Home's
markup, and whether a shared route-path constants module is worth
introducing) below.

## Architectural Changes

1. **Four new ungated nav entries, `AppShell.tsx` only (FR-2).** Add
   `<NavLink to="/settings/profile">Profile</NavLink>`,
   `<NavLink to="/settings/security">Security</NavLink>`,
   `<NavLink to="/sessions">Sessions</NavLink>`,
   `<NavLink to="/settings/deactivate">Deactivate Account</NavLink>` inside
   the existing `<nav>`, unconditionally (no scope check) — confirmed by the
   impact analysis and independently re-verified against
   `frontend/src/routes/AppRoutes.tsx` lines 91-94: all four are registered
   inside the `ProtectedRoute`/`AppShell` group with only auth gating, the
   same as the existing `Tickets` entry. No new scope constant is
   introduced for these four; the three existing gated entries
   (`canReadUsers`, `canReadAudit`, `canReadAgentQueue`) are unchanged. Flat
   list, no grouping/sectioning (OD-3/FR-2) — new entries are added as
   plain siblings in source order (Tickets, Sessions, Profile, Security,
   Deactivate Account, then the existing scope-gated block), not wrapped in
   a new section element.

2. **"Home" control, plain `Link`, not `NavLink` and not a `<button>`
   (FR-4, OD-1, OD-2).** Add `<Link to="/tickets" aria-label="Home">Home</Link>`
   (or an equivalent visible-text/logo element carrying an explicit
   accessible name) as the nav's first child, before `Tickets`. Decision:
   a plain anchor-rendering `Link`, not a `<button onClick={navigate}>`.
   Rationale: the Verification table's `a11y-keyboard` row requires Tab
   reach and Enter activation on every visible nav entry — an anchor gets
   both natively and matches every other nav entry's element type, whereas
   a `<button>` also activates on Space and would make this one entry
   behave differently under that same test for no requirement-driven
   reason. It must not be `NavLink`: Home and the existing `Tickets` entry
   share the identical `/tickets` target, and OD-2's resolution requires
   only `Tickets` to ever carry the active marker there — using `NavLink`
   for Home would make both entries active simultaneously on `/tickets`,
   contradicting FR-5's Home Exception. Home needs an explicit accessible
   name distinct from "Tickets" (visible text "Home", or `aria-label` if a
   future logo image replaces the text) precisely because both elements
   render `href="/tickets"` — an `href`-only query cannot distinguish them,
   so tests and the axe check both need a named, distinguishable element.

3. **`Link` → `NavLink` on every existing gated/ungated entry except Home
   (FR-5, OD-4).** `Tickets`, `Sessions`, `Profile`, `Security`,
   `Deactivate Account`, and — scope-gated as today — `Agent Queue`,
   `Users`, `Audit Log` all become `NavLink`, using `NavLink`'s default (no
   `end` prop), so a parent entry with nested child/detail routes (Tickets
   → `/tickets/new`, `/tickets/:id`; Users → `/admin/users/new`,
   `/admin/users/:id`; Agent Queue → `/agent/tickets/:id`) stays active via
   prefix matching, per OD-4's resolution. `NavLink`'s own default marker
   (`aria-current="page"` on the active `<a>`, applied automatically — no
   custom `className` function needed) satisfies FR-5's "programmatically
   determinable... not colour alone" NFR directly; this plan does not add a
   hand-rolled `isActive`-driven class on top of it, since the NFR is
   satisfied by the attribute alone and adding a redundant class would be
   an unrequested embellishment.

   **Prefix-matching collision check (verified, not assumed):** with no
   `end` prop, a `NavLink` is active on any path starting with its `to=`.
   Checked every nav `to=` value against every other for a prefix
   relationship: `/tickets`, `/sessions`, `/settings/profile`,
   `/settings/security`, `/settings/deactivate`, `/agent/tickets`,
   `/admin/users`, `/admin/audit-logs`. None is a path-segment prefix of
   another — in particular, the three `/settings/*` entries are siblings
   with no `/settings`-only parent nav entry that could light up alongside
   them. FR-5 and GN-AC5's "distinguished from the others" therefore holds:
   no two non-Home entries can be simultaneously active under prefix
   matching for any route this Story's nav renders.

4. **No shared route-path constants module — rejected, not deferred.** The
   impact analysis's Notes for Downstream Stages flags this as the one
   place this Story could plausibly add a new file, and leaves the call to
   this plan. **Decision: do not introduce one.** Reasons: (a) the survey's
   own affected-file table records `frontend/src/routes/AppRoutes.tsx` as
   "No change" — every target this Story's nav needs is already registered
   there, and rewriting its `path=` literals to import shared constants
   would touch a file this Story has no FR-driven reason to modify,
   tripping `AGENTS.md` §7.8's "no opportunistic refactor of untouched
   code"; (b) this skill's own Planning Rules require every planned file
   change to trace to a specific spec/design requirement — FR-6/GN-AC6
   requires *verification* that nav targets resolve to registered routes,
   not a change to how those routes are declared; a passing behavioral test
   (Architectural Change 5, Testing Strategy) satisfies FR-6 with zero
   production change; (c) `US-5.5`'s own implementation plan (Architectural
   Change 6) sets direct in-repo precedent for rejecting a similar
   extraction for the same reason (survey lists the file as unaffected;
   extracting anyway would violate that boundary). The pre-existing
   duplication the impact analysis flagged is real but is a candidate for a
   future story once a second Story's need for it appears, not this one's.

5. **FR-6/GN-AC6 verification strategy: behavioral cross-check, not a
   hardcoded parallel list.** The impact analysis's own fallback ("the test
   simply hardcodes the expected route set") is rejected as the
   implementation, not just the constants module: a hardcoded list in the
   test file would be a *third* copy of the same literals, drifts exactly
   like the two it's supposed to catch drifting, and doesn't actually prove
   the target renders anything. Instead (see Testing Strategy): the new
   `AppShell.test.tsx` case renders `AppShell`, collects every nav entry's
   `href` from the rendered DOM across a scope superset (all gates
   granted), then for each collected `href` renders `AppRoutes` at that
   path via `renderWithProviders`'s existing `route` option and asserts a
   real screen renders (not a blank body, not a 404/redirect-to-login
   artifact under an authenticated, fully-scoped render). This proves both
   clauses of GN-AC6 — "resolves to a registered route" and "none renders a
   blank screen or a 404" — directly against `AppRoutes.tsx`'s actual route
   table, with no new production file and no parallel literal list.

## Files To Create

None. Every requirement is satisfied by modifying the two files below;
this Story introduces no new screen, hook, API function, or route (spec's
own Out of Scope: "Any new screen or backend endpoint"; "Restructuring
`AppRoutes.tsx`'s existing route groups or guards").

## Files To Modify

| File | Change |
|---|---|
| `frontend/src/layouts/AppShell.tsx` | Add the Home `Link` (Architectural Change 2) as the nav's first child. Add four new ungated `NavLink` entries — Profile, Security, Sessions, Deactivate Account (Change 1). Convert every existing `Link` (Tickets, and the three scope-gated entries) to `NavLink`, no `end` prop (Change 3). No change to `useAuthStore()` usage, `canReadUsers`/`canReadAudit`/`canReadAgentQueue` derivation, or the `LogoutControls`/`MfaEnrollmentBanner` render sites — this file stays in the store-read-only lane its own header comment already claims (no new `hooks/`/`api/` import). |
| `frontend/src/layouts/AppShell.test.tsx` | (a) Extend the existing zero-scope case(s) (`test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` and the agent-queue sibling) to also assert *presence* of the five ungated entries (Tickets plus the four new ones) at zero scope — extending the existing assertions, not replacing or weakening them, per GN-AC2's scope-combination table and `AGENTS.md` §7's prohibition on weakening a passing test. (b) New case(s) asserting the four new entries render by accessible name and `href` under a representative scope combination. (c) New case clicking Home from a non-`/tickets` route (e.g. `/settings/profile`) and asserting navigation lands on `/tickets` (FR-4/GN-AC4). (d) New cases asserting: the current route's `NavLink` entry carries `aria-current="page"` while a different entry does not (FR-5/GN-AC5); Home never carries `aria-current`, even while on `/tickets`, and only "Tickets" does there (OD-2); a parent entry (e.g. Tickets) stays marked active on a nested route, e.g. `/tickets/42` (OD-4). Assertions distinguishing "Home" from "Tickets" key on accessible name/role, not `href` alone, since both share `href="/tickets"`. Existing href-only assertions on unaffected entries are unchanged — `NavLink` renders as an `<a>` with the same accessible `link` role, so no existing passing assertion needs rewriting. (e) New case implementing Architectural Change 5's behavioral GN-AC6 cross-check: render `AppShell` with every gate granted, collect every nav `href`, then render `AppRoutes` at each collected path (authenticated, same full scope set) and assert a real screen renders, not a blank body or a login/404 redirect artifact. (f) New `axe`/`toHaveNoViolations` case on the nav in its authenticated state (net-new capability in this file — the pattern exists in 21 `screens/*.test.tsx` files plus `test/vitest-axe.d.ts`/`test/setup.ts`, per the impact analysis, but not here today). (g) a11y-keyboard case: Tab/Shift-Tab reaches every visible nav entry in order and Enter activates the focused link (Spec Verification's `a11y-keyboard` row). |
| `frontend/src/routes/AppRoutes.test.tsx` | New integration case(s) proving GN-AC1/GN-AC3: render `AppRoutes` in a `MemoryRouter` (via `renderWithProviders`, already this file's pattern), click a rendered nav entry, and assert (i) the target screen's content renders, (ii) the nav itself (a stable element/text, e.g. the "Tickets" link) is still present and unchanged immediately after the click — proving the surrounding `AppShell`/`<nav>` was not remounted, only the routed `<Outlet />` content changed, (iii) no full-page-reload side effect is observable in this rendering model (there is no `window.location` navigation to assert against in jsdom/RTL — client-side routing is proven by the URL/content updating via React Router state, which is what (i)/(ii) already assert). No existing test case's assertions change; this file's existing per-route/per-scope tests are unaffected since no route table changes. |

No `AGENTS.md` §7.9-protected file (`pyproject.toml`, `migrations/env.py`,
`.pre-commit-config.yaml`) is touched by this plan. No change to
`frontend/src/routes/AppRoutes.tsx` (confirmed by the impact analysis and
independently re-verified against the file's current content: every target
this Story's nav needs — `/settings/profile`, `/settings/security`,
`/sessions`, `/settings/deactivate`, `/tickets` — is already registered
inside the `ProtectedRoute`/`AppShell` group). No change to
`frontend/src/store/authStore.tsx`/`decodeTokenScopes.ts`,
`frontend/src/components/LogoutControls.tsx`/`MfaEnrollmentBanner.tsx`, any
`frontend/src/hooks/*`/`frontend/src/api/*` file, or
`frontend/src/test/test-utils.tsx` (`scopes` seeding already exists, added
for US-5.4) — all confirmed unaffected by the impact analysis and
independently re-checked here.

## Risks

1. **Home/Tickets active-state ambiguity is a real implementation trap, not
   just a spec nuance.** Both elements target `/tickets`; a developer
   copy-pasting the `Link`→`NavLink` conversion across every nav entry
   without reading OD-2's resolution would make Home a `NavLink` too,
   producing two simultaneously "active" elements on `/tickets` and
   silently violating FR-5's Home Exception. Mitigation: Architectural
   Change 2 states explicitly that Home stays a plain `Link`, and the new
   AppShell test (Files To Modify, item d) asserts this directly (Home
   never carries `aria-current`, even on `/tickets`), not just indirectly
   through a passing a11y scan.
2. **Extending, not rewriting, the existing zero-scope tests.** GN-AC2's
   scope-combination coverage requires the existing
   `test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope`
   case (and its agent-queue sibling) to gain new positive assertions
   (presence of the five ungated entries) alongside their existing negative
   ones (absence of the gated entries). Flagged explicitly as "extend,
   in-place" so this isn't executed as delete-and-rewrite, which would
   read as weakening/removing a passing test under `AGENTS.md` §7.7.
3. **`axe`/`toHaveNoViolations` is net-new wiring in this specific file.**
   The harness (`test/vitest-axe.d.ts`, `test/setup.ts`) already supports it
   repo-wide, but `AppShell.test.tsx` has never invoked it before this
   Story — the first a11y test added here is where any import/setup gap
   would surface, not a place where the pattern is merely being repeated.
4. **`NavLink`'s default `aria-current="page"` must not collide with an
   existing custom attribute.** Confirmed by direct re-read of the current
   `AppShell.tsx`: no nav element sets `aria-current` today, so adopting
   `NavLink`'s default introduces no conflict — recorded as checked, not
   assumed.
5. **The behavioral GN-AC6 cross-check (Architectural Change 5) must render
   with every scope granted, not the default/no-scope render.** Under a
   no-scope render, `AppShell` would only emit the five ungated hrefs, and
   the check would silently never visit `/admin/users`, `/admin/audit-logs`,
   or `/agent/tickets` — passing without actually covering GN-AC6's "under
   any combination of scopes" clause for the gated entries. Mitigation:
   the test explicitly renders with `scopes: ["users:read", "audit:read",
   "tickets:read"]` (all three gates open) before collecting hrefs, so all
   eight targets are exercised in one pass.

## Validation Strategy

`npm run lint`, `npm run format:check`, `npm run type-check`, and
`npm run test:coverage` (`AGENTS.md` §2 Frontend subsection — these exact
script names) must all stay green. No `lint-imports` equivalent exists for
the frontend layer table; `AGENTS.md` §3's Frontend layer constraints are
checked by reading the diff: `AppShell.tsx` continues to import only
`react-router-dom`, `components/LogoutControls`, `components/MfaEnrollmentBanner`,
and `store/authStore` (`useAuthStore()`, read-only) — no new `api/` or
`hooks/` import is introduced by this Story, so the `screens/`,
`components/` → `hooks/` → `store/`/`api/` layer table is unaffected. `type-check`
additionally re-confirms `NavLink`'s props (`to`, no `end`) type-check
identically to `Link`'s, since only the element name changes, not the
`to=` value's type. Coverage stays at the existing 85% floor
(`vitest --coverage`); no touched module may lose coverage. No
`AGENTS.md` §7.9-protected file is touched. No Open Decision remains open —
all four (OD-1 through OD-4) are `RESOLVED` and incorporated into spec v2's
FR text (`docs/decisions/US-5.6-open-decisions.md` v2).

## Testing Strategy

Per `AGENTS.md` §5 Frontend subsection's unit/integration split — this
Story adds no hook or API function, so there is no new unit-test file; all
coverage is integration-level, exercising the real component tree via React
Testing Library, consistent with both existing files already being
integration-style suites:

- **`frontend/src/layouts/AppShell.test.tsx`** (integration, renders
  `AppShell` directly with `renderWithProviders`, MSW where a click
  triggers a network call): the two zero-scope cases extended for
  presence of the five ungated entries (Risk 2); new cases for the four new
  entries' accessible name + `href` under a representative scope; the Home
  click-through-to-`/tickets` case (FR-4/GN-AC4); the active-state cases —
  current entry carries `aria-current="page"`, a different entry does not,
  Home never does even on `/tickets` (FR-5/GN-AC5, OD-2), a parent entry
  stays active on a nested child route such as `/tickets/42` (OD-4); the
  behavioral GN-AC6 cross-check described in Architectural Change 5 (render
  with every scope granted, collect every nav `href`, render `AppRoutes` at
  each, assert a real screen — not blank/404/login-redirect — appears); an
  automated a11y check (`axe`/`toHaveNoViolations`) on the nav in its fully
  authenticated, fully scoped state; and an a11y-keyboard case (Tab/Shift-Tab
  reaches every visible nav entry in document order, Enter activates the
  focused link).
- **`frontend/src/routes/AppRoutes.test.tsx`** (integration, already
  renders the full route tree): a new case proving GN-AC1/GN-AC3 —
  starting on one protected route, clicking a nav entry lands on the target
  screen's content, and the nav's own stable content (e.g. the "Tickets"
  link) is still present and unchanged right after, evidencing the shared
  `AppShell`/`<nav>` was not remounted by the transition. No existing case
  in this file changes; no new route-table assertions are added since the
  route table itself is unmodified.
- No new unit-test file, no new screen/hook/API test — this Story's entire
  test surface is the two files above, matching the impact analysis's
  Test-Surface Impact section exactly ("New test files: None required").

## Dependency on Prior Stories

- **US-5.1** — auth store (`scopes`), `ProtectedRoute`. Reused unmodified.
- **US-5.2** — the four account self-service screens
  (`ProfileScreen`, `SecurityScreen`, `SessionsScreen`,
  `DeactivateAccountScreen`) and their already-registered routes. This
  Story links to them; it does not modify them.
- **US-5.3** — `/tickets` as the authenticated landing target (Change 11)
  and the existing `Tickets` nav entry this Story converts to `NavLink`.
- **US-5.4, US-5.5** — the existing scope-gated nav-entry pattern
  (`canReadUsers`/`canReadAudit`/`canReadAgentQueue`) this Story leaves
  unchanged except for the `Link`→`NavLink` element swap.

## Open Decisions Status

All four items in `docs/decisions/US-5.6-open-decisions.md` (v2) — OD-1
("Home" target = `/tickets`, no dashboard), OD-2 (Home exempt from
active-state), OD-3 (flat list, no grouping), OD-4 (prefix-matching
active-state on nested routes) — are `RESOLVED` by explicit human decision
(2026-09-15) and incorporated as requirement text in
`docs/specifications/US-5.6-spec.md` v2's FR-2, FR-4, and FR-5. None is a
dependency this plan is waiting on; this plan implements each resolution as
stated spec behavior (Architectural Changes 1-3 above), not as an interim
default. This plan resolves no Open Decision itself — it consumes
resolutions already recorded upstream.

## Non-Blocking Findings Carried Forward

- **Bookkeeping mismatch (from impact analysis, unresolved by design,
  non-blocking):** `specification_review` (v1, front matter) records
  consuming `specification`/`open_decisions` at version 1; both are now
  version 2. The v2 delta is exactly the write-back `specification_review`
  v1 itself required, and `HUMAN_SPEC_APPROVAL` verified this exact
  artifact pairing before approving. Carried forward for downstream-stage
  visibility, not re-litigated or held blocking here — this plan's own
  precondition is that every artifact *it* consumes is current and
  non-superseded on disk, which holds (all listed in front matter `inputs`
  above are the current, non-superseded versions).
