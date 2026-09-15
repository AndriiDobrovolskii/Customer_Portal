---
artifact_type: impact_analysis
story: US-5.6
version: 1
status: DRAFT
created_at: "2026-09-15T10:00:00Z"
updated_at: "2026-09-15T10:00:00Z"
produced_by: impact-analyzer
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
supersedes: null
---

# Impact Analysis: Global Navigation (Frontend)

**Story ID:** US-5.6
**Track:** frontend (per `docs/stories/US-5.6-global-navigation.md` front matter, line 7)

## Precondition Check

- Specification v2: `APPROVED`. Specification review v1: `APPROVED`, verdict
  `PASS` (all six ACs Covered, no Contradiction, no Scope Creep; one Medium and
  one Low non-blocking finding — see below).
- `API_DESIGN`/`DB_DESIGN`: both recorded verdict `NOT_APPLICABLE`
  (`docs/workflow/history.jsonl`, `openapi-designer` and `db-designer`,
  2026-09-15) — no `api_design`/`openapi`/`database_design`/`entity_model`
  artifact exists or is expected, consistent with the approved specification's
  own "API / Persistence Impact" section ("no public API behavior... and no
  persistence behavior"). Design review v1 independently confirms this
  (`docs/reviews/designs/US-5.6-design-review.md`, verdict `NOT_APPLICABLE`,
  matching `stage-map.yaml`'s `DESIGN_REVIEW.optional_when` condition).
- Open decisions v2 (`docs/decisions/US-5.6-open-decisions.md`): OD-1 through
  OD-4 are all `RESOLVED` (human decision, 2026-09-15, `HUMAN_SPEC_APPROVAL`).
  Verified directly: `/tickets` as Home target with the staff-only-empty-list
  behavior recorded (OD-1); Home exempt from active-state (OD-2); flat-list
  nav, no grouping (OD-3); parent nav entries stay active on nested child
  routes via prefix matching (OD-4). All four resolutions are frontend UX
  choices confined to `AppShell.tsx` — none proposes a new endpoint,
  request/response field, or persistence change. No unresolved blocking Open
  Decision remains.
- `docs/workflow/active-story.yaml` (`active_story: US-5.6`) and
  `docs/workflow/workflow-state.yaml` (`story: US-5.6`,
  `current_stage: IMPACT_ANALYSIS`, `blocking_issues: []`) agree on the active
  story and stage — read directly.
- **Carried-forward bookkeeping note (non-blocking):** `specification_review`
  v1's own front matter records consuming `specification` at version 1 and
  `open_decisions` at version 1; both are now version 2. This is the same
  finding `workflow-state.yaml` carries forward as flagged "for
  DESIGN_REVIEW/IMPACT_ANALYSIS visibility." Judged non-blocking here: (a)
  this stage's own precondition is that the artifacts *it* consumes are
  current and non-superseded on disk — `specification_review` v1 carries
  `status: APPROVED` and no v2 exists, so it is the current version; (b) the
  v1→v2 delta on the specification is exactly the four Open Decision
  resolutions spec_review v1 itself required to be "recorded alongside the
  resolution" and "written back into the spec's FR text" — both of
  spec_review v1's own non-blocking findings (the OD-1 staff-only-empty-list
  omission, Medium; the keyboard-nav enforcement ambiguity, Low) are in fact
  closed by v2's text (FR-4's Boundary Condition; the Verification table's new
  `a11y-keyboard` row) — so spec_review v1's `PASS` verdict already
  contemplates and endorses this exact delta, not a different, un-reviewed
  scope change; (c) `HUMAN_SPEC_APPROVAL` explicitly verified "specification
  v2, specification_review v1, neither SUPERSEDED/ARCHIVED" before approving,
  and `IMPACT_ANALYSIS` has no `loop_back_stage` key that targets
  `SPEC_REVIEW` — only `SPECIFICATION`, `API_DESIGN`, `DB_DESIGN` — so a
  `BLOCKED` verdict here would stall the story on a re-review no stage in this
  pipeline is wired to trigger, over a mismatch a human gate already priced
  in. Recorded as a non-blocking finding below, not held as `BLOCKED`.

No blocking condition found. Proceeding with `PASS`.

## 1. Affected Files / Modules / Layers

Layer names below are `AGENTS.md` §3 Frontend subsection's table:
`screens/`, `components/` → `hooks/` → `store/` (read-only) / `api/`, plus
`routes/` (guards + layout). `AppShell.tsx` lives in `frontend/src/layouts/`;
`AppShell.test.tsx`'s own header comment records that a prior plan review
(`docs/reviews/plans/US-5.1-plan-review.md`) flagged which §3 row this file
categorizes under as an open, non-blocking question — this survey does not
resolve that categorization, only lists the file.

### `layouts/` (routes/guards + layout row)

| File | Change | Reason |
|---|---|---|
| `frontend/src/layouts/AppShell.tsx` | Modify | **FR-2:** add four new nav entries with no gating — Profile (`/settings/profile`), Security (`/settings/security`), Sessions (`/sessions`), Deactivate Account (`/settings/deactivate`). Confirmed ungated: `AppRoutes.tsx` lines 91-94 register all four inside the `ProtectedRoute`/`AppShell` group with no scope check — only auth, the same as `Tickets`. No new scope constant is introduced in `AppShell.tsx` for these four (contrast with the three existing scope-gated entries: `canReadUsers`, `canReadAudit`, `canReadAgentQueue`, all unchanged). **FR-4:** add a "Home"/logo control that always links to `/tickets`, implemented as a plain `Link` (or non-`NavLink` element) per OD-2's resolution — it must NOT be one of the elements swapped to `NavLink`, since Home and the existing "Tickets" entry share the identical `/tickets` target and only "Tickets" may show the active marker. **FR-5:** swap `Link` → `NavLink` on every entry except Home (Tickets, Sessions, Profile, Security, Deactivate Account, and — scope-gated as today — Agent Queue, Users, Audit Log), using `NavLink`'s default (no `end` prop) so parent entries with nested child/detail routes (Tickets → `/tickets/new`, `/tickets/:id`; Users → `/admin/users/new`, `/admin/users/:id`; Agent Queue → `/agent/tickets/:id`) stay active via prefix matching per OD-4's resolution. This keeps `AppShell.tsx` in the store-read-only lane its own header comment already claims (`useAuthStore()` read directly, no `hooks/` import) — no new layering exception is opened. |

### `routes/` (guards + layout row)

| File | Change | Reason |
|---|---|---|
| `frontend/src/routes/AppRoutes.tsx` | **No change** | Every nav target this Story adds (`/settings/profile`, `/settings/security`, `/sessions`, `/settings/deactivate`) and every target the "Home" control uses (`/tickets`) is already a registered route inside the same `ProtectedRoute`/`AppShell` group — confirmed by direct re-read, lines 87-110. FR-6/GN-AC6 ("no dead links") is a verification requirement, not a route-table change: the story's own Out of Scope line ("Restructuring `AppRoutes.tsx`'s existing route groups or guards") and the specification's "API / Persistence Impact" section both confirm no route change is in scope. **FR-1/GN-AC1** ("the shared nav is visible, unchanged across route transitions, no full page reload") is likewise satisfied by existing structure with no production change here: lines 77-111 already nest every authenticated route inside one `<ProtectedRoute><AppShell /></ProtectedRoute>` group, and `AppShell.tsx` line 52 already renders the routed screen via `<Outlet />` inside that single persistent shell — so a route transition inside this group re-renders only the `<Outlet />` content, not the surrounding `<nav>`. FR-1 is verification-only for this Story (§4's `AppRoutes.test.tsx` row), not a file to modify. Listed here to record that it was checked, not assumed unaffected. |

## 1a. Checked — Not Affected (reference only)

- `frontend/src/components/LogoutControls.tsx`, `frontend/src/components/MfaEnrollmentBanner.tsx` — no functional requirement touches either; the NFR line ("No regression to existing nav entries' behavior, scope gating, or `LogoutControls`/`MfaEnrollmentBanner` placement") is a constraint on how `AppShell.tsx` is edited, not a reason to modify these files themselves. Confirmed unchanged by direct re-read (lines 42-51 of `AppShell.tsx` place `<LogoutControls />` in `<header>` and `<MfaEnrollmentBanner>` immediately below it — this Story's nav edits stay inside `<nav>`, not this surrounding structure).
- `frontend/src/store/authStore.tsx`, `frontend/src/store/decodeTokenScopes.ts` — `scopes` is already exposed by `useAuthStore()` and already read directly in `AppShell.tsx` for the three existing gated entries (confirmed lines 32-38). This Story's four new entries are ungated (no scope check at all, per the routes' own lack of a scope requirement), so no new claim, decoder change, or store shape change is needed.
- `frontend/src/hooks/*`, `frontend/src/api/*` — no hook or API-client file is read or imported by this Story's changes; `AppShell.tsx` continues to import only `react-router-dom`, `components/LogoutControls`, `components/MfaEnrollmentBanner`, and `store/authStore` (confirmed unchanged import list except the `Link`→`NavLink` swap).
- `frontend/src/test/test-utils.tsx` — `RenderWithProvidersOptions.scopes` already exists (added for US-5.4) and already seeds the three existing gated entries' tests; this Story's four new ungated entries need no new seed option (unlike US-5.4's own file, which needed a `scopes` addition at the time).
- Any backend file under `app/` — confirmed `NOT_APPLICABLE` per the approved specification (v2), design review (v1, `NOT_APPLICABLE`), and both upstream `API_DESIGN`/`DB_DESIGN` stage results; this Story calls no endpoint it doesn't already call today (it adds no new `fetch`/`api/` call of any kind).

## 2. Cross-Module Ripple

None. This Story touches exactly one production file (`AppShell.tsx`), which
does not call another module's service, hook, or API function — it renders
`<Link>`/`<NavLink>` elements pointing at routes other modules' screens
already own, the same reach `AppShell.tsx` already has today for `Tickets`/
`Agent Queue`/`Users`/`Audit Log`. No new cross-module dependency direction
(`hooks/`→`hooks/`, `screens/`→`hooks/`, or any other) is introduced, and
`AGENTS.md` §3's "cross-module calls go service→service" discipline is a
backend concept this Story's all-frontend, no-backend-touch scope does not
implicate.

## 3. Migration/Schema Impact

**None.** This Story makes no backend, API, or database change — confirmed by
the approved specification v2 ("This Story explicitly changes no public API
behavior... and no persistence behavior"), by `API_DESIGN`/`DB_DESIGN` both
recording `NOT_APPLICABLE`, and by design review v1 (`NOT_APPLICABLE`,
corroborating both). No Alembic migration, no `models.py`/`repository.py`/
`schemas.py`/`router.py` change, no new table/column/index/endpoint. Stated
explicitly per this skill's own workflow requirement, not omitted.

## 4. Test-Surface Impact

### Existing test files that must change

| File | Reason |
|---|---|
| `frontend/src/layouts/AppShell.test.tsx` | **Modify (existing behavior shifts + new coverage in one file).** (a) FR-2: add cases asserting the four new entries (Profile, Security, Sessions, Deactivate Account) render unconditionally, including under the existing zero-scope case — `test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` (line 125) and its sibling zero-scope agent-queue test today assert only *absence* of the gated entries; per GN-AC2's table-driven scope-combination requirement, these need extending (or a new zero-scope case needs adding) to also assert *presence* of the five ungated entries (Tickets plus the four new ones) at zero scope. (b) FR-4: a new test clicking the Home control from a non-`/tickets` route (e.g. `/settings/profile`) and asserting navigation to `/tickets` (GN-AC4's own stated mechanism). (c) FR-5: new tests asserting (i) the current route's `NavLink` entry carries a distinguishing, programmatically-determinable marker (e.g. `aria-current="page"`, `NavLink`'s own default) while a different entry does not; (ii) Home never carries that marker, even while on `/tickets` (OD-2); (iii) a parent entry (e.g. Tickets) stays marked active while on one of its nested child/detail routes, e.g. `/tickets/42` (OD-4). Existing entries' href-only assertions (e.g. line 82: `getByRole("link", {name: /tickets/i})...toHaveAttribute("href","/tickets")`) keep passing under `NavLink` (renders as `<a>`, same accessible `link` role) — no rewrite needed there, but assertions distinguishing "Home" from "Tickets" must key on accessible name (they render different link text but share the identical `href="/tickets"`, so an `href`-only query would be ambiguous between the two). (d) FR-6/GN-AC6: a new test cross-checking every nav `to=`/`href` target against the set of paths `AppRoutes.tsx` registers — today there is no shared constants module either file imports (both `AppShell.tsx`'s `to=` values and `AppRoutes.tsx`'s `path=` values are separate inline string literals), so this test either hardcodes the expected route set or `planner`/`implementation-planner` decides whether a shared route-path source (e.g. a new `routePaths.ts`) is worth introducing — this survey does not decide that; flagged as the one place this Story *might* add a new file (see Notes for Downstream Stages). (e) a11y: this file has no `axe`/`toHaveNoViolations` usage today (confirmed by repo-wide search — the pattern exists in 21 `screens/*.test.tsx` files plus `test/vitest-axe.d.ts`/`test/setup.ts`, but not here), so the Verification table's `a11y` row (automated axe check on the nav in its authenticated state) is net-new capability added to an existing file, not a tweak to an existing check. |
| `frontend/src/routes/AppRoutes.test.tsx` | **Modify (new coverage, no route-table assertions change).** GN-AC1/GN-AC3 need an integration test proving the shared nav persists, visually unchanged, across a real client-side route transition with no full page reload, and that clicking a nav entry updates both the rendered screen and the browser URL. Today this file renders `<AppRoutes />` and asserts the *landing* route per test case (via `renderWithProviders`'s `route` option) but no existing test clicks a rendered nav link to move between two protected routes — that click-through assertion is naturally added here (this file already owns full-tree rendering), not in `AppShell.test.tsx`, which renders `AppShell` in isolation without the nested `<Routes>` a real transition needs. |

### New test files

None required. Every acceptance criterion (GN-AC1 through GN-AC6, plus the
a11y and a11y-keyboard Verification rows) is satisfiable as new/modified test
cases inside the two existing files above — this Story introduces no new
screen, hook, or API function that would otherwise need its own net-new test
file under `AGENTS.md` §5's "a new `screens/LoginScreen.tsx` requires
`LoginScreen.test.tsx`" convention.

## Non-Blocking Findings

- **Bookkeeping mismatch, not a content defect (see Precondition Check
  above).** `specification_review` v1's front matter records consuming
  `specification`/`open_decisions` at version 1; both are now version 2. The
  v2 delta is precisely the write-back spec_review v1's own findings
  demanded, and `HUMAN_SPEC_APPROVAL` explicitly verified this exact artifact
  pairing before approving. `IMPACT_ANALYSIS` has no `loop_back_stage` key
  targeting `SPEC_REVIEW`, so this is recorded for downstream visibility, not
  held as `BLOCKED`.
- **Route-path duplication is pre-existing, not introduced by this Story.**
  `AppShell.tsx`'s nav `to=` values and `AppRoutes.tsx`'s `path=` values are
  separate inline string literals with no shared constants module today. This
  Story's own FR-6/GN-AC6 ("no dead links") is the first requirement to test
  the two against each other, which may surface this as worth extracting —
  left to `planner`/`implementation-planner` to decide (§4 above), not
  resolved here.
- **Both of `specification_review` v1's own non-blocking findings are closed
  by specification v2**, for downstream stages' awareness: the Medium
  (staff-only-empty-list omission) is now FR-4's Boundary Condition; the Low
  (keyboard-nav enforcement ambiguity) is now covered by the Verification
  table's added `a11y-keyboard` row (manual/integration test asserting
  Tab/Shift-Tab reaches every visible nav entry in order and Enter activates
  the link). Neither should be treated as still-open by `planner`.

## Notes for Downstream Stages

- Whether a shared route-path source module is introduced to serve both
  `AppShell.tsx`'s `to=` values and `AppRoutes.test.tsx`'s/`AppShell.test.tsx`'s
  no-dead-links cross-check (vs. the test simply hardcoding the expected
  route set) is an architectural choice for `planner`, not decided here — the
  only place this Story could plausibly add a new file.
  Home's exact markup (a `Link`/`<a>` vs. a `<button onClick={navigate}>`) is
  likewise left to `planner`/`frontend-builder`; this survey states only the
  constraint OD-2 imposes (must not participate in `NavLink`'s active-state
  matching).
- Test assertions distinguishing "Home" from "Tickets" must key on accessible
  name/role, not `href`, since both share the identical `/tickets` target —
  a structural fact for `test-writer` to account for, not an ordering this
  survey prescribes.
