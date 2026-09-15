---
artifact_type: task_breakdown
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T12:00:00Z"
updated_at: "2026-09-15T14:15:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 2
supersedes: null
---

# Task Breakdown — US-5.6 (Global Navigation, Frontend)

**Track:** `frontend` (`docs/stories/US-5.6-global-navigation.md` front matter, line 7).
Per `docs/workflow/stage-map.yaml`'s `IMPLEMENTATION` stage (`skills_by_track.frontend`),
this track dispatches exactly one execution skill, `frontend-builder` — there is no
per-layer split for this track. `API_DESIGN`/`DB_DESIGN` both recorded `NOT_APPLICABLE`
(impact analysis v1, Precondition Check): no `docs/designs/api/US-5.6-*` or
`docs/designs/database/US-5.6-*` artifact exists to attribute any task to.

**Scaffold check:** `frontend/` already exists (shipped by US-5.1 onward) — the frontend
ordering rule's "scaffold before everything" step is already satisfied.

**Scope is unusually small and confined to one layer.** The implementation plan's Files
To Create is `None`; Files To Modify is exactly three files, all inside the same
AGENTS.md §3 Frontend row. No `api/`, `store/`, or `hooks/` task exists in this sequence —
the plan and impact analysis both confirm none of those layers changes (Architectural
Changes 1-3; "Checked — Not Affected" §1a), so the ordering rule's "`api/`/`store/` before
`hooks/`, `hooks/` before `routes/`/`screens/`" is vacuous here; only the
production-before-its-test-coverage floor is live.

**Layer attribution note.** `frontend/src/layouts/AppShell.tsx` has no dedicated row in
AGENTS.md §3's Frontend layer table; it is attributed to the `routes/ (guards + layout)`
row, per that row's own "guards + layout" label and the impact analysis's own heading
(`### layouts/ (routes/guards + layout row)`) — the same attribution
`docs/plans/US-5.4-task-breakdown.md` and `docs/plans/US-5.5-task-breakdown.md` used for
this same file. This survey's own note that a prior plan review flagged this file's exact
§3 categorization as an open, non-blocking question is carried forward, not re-litigated
here; it does not change which single row this Story's only production file belongs to.

**No route-table production change.** `frontend/src/routes/AppRoutes.tsx` itself is
unmodified (impact analysis §1, "No change"; implementation plan, Files To Modify note) —
only its paired test file gains new coverage. Following
`docs/plans/US-5.5-task-breakdown.md`'s T9/T10 precedent ("fixture/test-only, no
production change"), this is sequenced as its own task rather than folded into the
`AppShell.tsx` task, since it touches a different file with no code-level import between
the two.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | `routes/` (guards + layout) | — | `frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx` | `npx vitest run src/layouts/AppShell.test.tsx --coverage` covering: the two existing zero-scope cases extended (not replaced) to also assert presence of the five ungated entries — Tickets, Sessions, Profile, Security, Deactivate Account (FR-2/GN-AC2, Risk 2); the four new entries' accessible name + `href` under a representative granted-scope combination; Home clicked from a non-`/tickets` route (e.g. `/settings/profile`) navigates to `/tickets` (FR-4/GN-AC4); the current route's `NavLink` entry carries `aria-current="page"` while a different entry does not, Home never carries it even on `/tickets` (only "Tickets" does there, keyed on accessible name since both share `href="/tickets"`) (FR-5/GN-AC5, OD-2, Risk 1); a parent entry (e.g. Tickets) stays active on a nested route such as `/tickets/42` (OD-4); the GN-AC6 behavioral cross-check — render with every scope granted, collect every nav `href`, render `AppRoutes` at each, assert a real screen appears (not blank/404/login-redirect) (Risk 5); a net-new `axe`/`toHaveNoViolations` case on the nav in its authenticated state (Risk 3); an a11y-keyboard case (Tab/Shift-Tab reaches every visible entry in document order, Enter activates the focused link). Additionally: `npm run type-check` clean on `AppShell.tsx`; `grep -RniE "from ['\"](\.\./)*api/|from ['\"](\.\./)*hooks/" frontend/src/layouts/AppShell.tsx` returns nothing (no new `api/`/`hooks/` import — file stays store-read-only); diff review confirms Home renders as a plain `Link` (not `NavLink`, not a `<button>`) while every other entry (Tickets, Sessions, Profile, Security, Deactivate Account, and the three existing scope-gated entries) renders as `NavLink` with no `end` prop. |
| T2 | frontend-builder | `routes/` (guards + layout, fixture/test-only — no production change) | T1 (floor dependency: exercises the nav `AppShell.tsx` renders; no `frontend/src/routes/AppRoutes.tsx` code import requires it, since that file itself is unmodified) | `frontend/src/routes/AppRoutes.test.tsx` | `npx vitest run src/routes/AppRoutes.test.tsx --coverage` covering GN-AC1/GN-AC3: starting on one protected route, clicking a rendered nav entry lands on the target screen's content, and the nav's own stable content (e.g. the "Tickets" link) is still present and unchanged immediately after — evidencing the shared `AppShell`/`<nav>` was not remounted, only the routed `<Outlet />` content changed; no existing case in this file is rewritten. `git diff --stat -- frontend/src/routes/AppRoutes.tsx` empty (confirms no production change to this file, per the implementation plan). |
| T3 | gate-enforcer | — | T1, T2 | — | `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage` (AGENTS.md §2 Frontend subsection's four load-bearing scripts) all green from `frontend/`; diff review against AGENTS.md §3's Frontend layer table (no `lint-imports` equivalent exists for this stack) confirms `AppShell.tsx`'s import list is unchanged apart from `react-router-dom`'s `Link`/`NavLink` names — no new `api/` or `hooks/` import; coverage stays at the existing 85% floor with no touched module regressing. |

**Parallel-eligible batches:** none — this sequence has no independent branches. T1 is the
sole production task and the only real dependency; T2 depends on T1 as a floor (same nav
element, different test file); T3 is the sequence's sole terminal task.

## Resolved Decisions Consumed by This Sequence

`docs/decisions/US-5.6-open-decisions.md` (v2) records OD-1 through OD-4 as `RESOLVED` by
explicit human decision (2026-09-15), folded into
`docs/specifications/US-5.6-spec.md` v2's FR-2, FR-4, and FR-5 as stated requirement
text. This stage resolves no Open Decision itself
(`implementation-planner`'s own Prohibited: "do not resolve Open Decisions"); T1 implements
each resolution already settled upstream, cited by FR number:

- **OD-1** (Home target = `/tickets`, no new dashboard screen, staff-only-empty-list
  Boundary Condition) — FR-4; implemented in T1 (Home `Link` markup), asserted by T1's
  Home-click test.
- **OD-2** (Home exempt from active-state, even on `/tickets`) — FR-5's Home Exception;
  implemented in T1 (plain `Link`, not `NavLink`), asserted by T1's `aria-current` test.
- **OD-3** (flat list, no grouping/sectioning) — FR-2; implemented in T1 (new entries added
  as plain siblings in source order, no new section wrapper).
- **OD-4** (parent nav entries stay active on nested child/detail routes via prefix
  matching) — FR-5's Nested Routes; implemented in T1 (`NavLink` with no `end` prop),
  asserted by T1's nested-route test.

**Implementation Plan Risk citations, checked against the plan's own numbering:**

- **Risk 1** (Home/Tickets active-state ambiguity — a copy-paste `Link`→`NavLink`
  conversion across every entry would make Home a `NavLink` too) is enforced as an
  explicit diff-review check on T1 (Home stays a plain `Link`) in addition to the direct
  test assertion T1's Verification Command states.
- **Risk 2** (extending, not rewriting, the existing zero-scope tests) is stated
  explicitly in T1's Verification Command ("extended (not replaced)") so this isn't
  executed as delete-and-rewrite under AGENTS.md §7.7.
- **Risk 3** (`axe`/`toHaveNoViolations` is net-new wiring in `AppShell.test.tsx`
  specifically, though the pattern exists repo-wide) is folded into T1 as its own listed
  case, not assumed to already exist.
- **Risk 4** (`NavLink`'s default `aria-current="page"` must not collide with an existing
  custom attribute) required no new task — the plan's own direct re-read confirmed no
  conflict exists; recorded here as checked, not re-verified by this stage.
- **Risk 5** (the GN-AC6 behavioral cross-check must render with every scope granted, not
  the default/no-scope render, or it silently never visits the gated entries) is folded
  into T1's Verification Command explicitly.

## Files Not Touched (confirmed, not re-derived)

No task in this sequence touches `frontend/src/routes/AppRoutes.tsx` (production),
`frontend/src/store/authStore.tsx`/`decodeTokenScopes.ts`,
`frontend/src/components/LogoutControls.tsx`/`MfaEnrollmentBanner.tsx`, any
`frontend/src/hooks/*`/`frontend/src/api/*` file, `frontend/src/test/test-utils.tsx`, or
any `app/` backend file — all confirmed unaffected by the impact analysis and the
implementation plan; no new file is created. This sequence traces every task to a file the
plan or impact analysis already named — no scope is invented here.
