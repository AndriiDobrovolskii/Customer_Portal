---
artifact_type: pr_summary
story: US-5.6
version: 1
status: DRAFT
created_at: "2026-09-15T14:39:40Z"
updated_at: "2026-09-15T14:39:40Z"
produced_by: pr-preparer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/evidence/US-5.6-implementation-report.md
    version: 1
  - path: docs/verification/US-5.6-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.6-security-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-5.6-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-5.6-traceability.md
    version: 1
  - path: docs/evidence/US-5.6-quality-gate-report.md
    version: 1
supersedes: null
---

# PR Summary: US-5.6 — Global Navigation (Frontend)

## Gate Confirmation

All four required upstream gates were read directly from their own artifacts (not taken on a
verbal "it's all good") and each records verdict **PASS**, against the current, non-stale input
versions:

| Gate | Artifact | Version | Verdict |
|---|---|---|---|
| `gate-enforcer` (QUALITY_GATE, attempt 1) | `docs/evidence/US-5.6-quality-gate-report.md` | v1 | PASS |
| `implementation-verifier` | `docs/verification/US-5.6-implementation-verification.md` | v1 | PASS |
| `security-reviewer` | `docs/reviews/security/US-5.6-security-review.md` | v1 | PASS |
| `reconciliation-reviewer` | `docs/reviews/reconciliation/US-5.6-reconciliation.md` | v1 | PASS |

`docs/workflow/workflow-state.yaml` (`story: US-5.6`, `current_stage: PR_PREPARATION`,
`previous_stage: HUMAN_PR_APPROVAL`, `last_result.verdict: PASS` for `RECONCILIATION`) and
`docs/workflow/active-story.yaml` (`active_story: US-5.6`) agree on the active story.
`HUMAN_PR_APPROVAL` was recorded approved by `sbruhov@gmail.com` at `2026-09-15T16:00:00Z`
against exactly these four artifacts at these versions (`implementation_verification` v1,
`security_review` v1, `reconciliation` v1, `traceability` v1). Every front-matter
`version`/`status` named in this artifact's own `inputs:` block was read directly off disk in
this session, not carried from the resolved-path list handed to this stage: `story`
(`docs/stories/US-5.6-global-navigation.md`, no front-matter version field, `track: frontend`),
`specification` v2/APPROVED, `impact_analysis` v1/DRAFT, `implementation_plan` v1/APPROVED,
`implementation_report` v1/DRAFT, `implementation_verification` v1/APPROVED, `security_review`
v1/APPROVED, `reconciliation` v1/APPROVED, `traceability` v1/APPROVED — none is `SUPERSEDED` or
`ARCHIVED`. `docs/decisions/US-5.6-open-decisions.md` v2 (read directly this session) confirms
OD-1 through OD-4 all `RESOLVED` at `HUMAN_SPEC_APPROVAL` 2026-09-15; no unresolved blocking Open
Decision remains in any `APPROVED` input this stage depends on. Every downstream *review* stage
(`QUALITY_GATE`, `IMPLEMENTATION_VERIFICATION`, `SECURITY_REVIEW`, `RECONCILIATION`) passed on its
first attempt with no loop-back — the one rejection this delivery saw was earlier and upstream of
implementation: `HUMAN_PLAN_APPROVAL` was `REJECTED` 2026-09-15T13:30:00Z for a reason unrelated
to plan content (the human wanted to manually exercise US-1.1–US-4.4 first), routed back to
`ARCHITECTURE_PLANNING` (no plan/task-breakdown content was changed), then re-entered and
`APPROVED` 2026-09-15T14:15:00Z against the same v1 `implementation_plan`/`task_breakdown`. No
code-quality or review-driven loop-back occurred anywhere in this delivery.

**`stale_reconciliation` check (this stage's only loop-back trigger):** `git diff --stat --
frontend/` in this session shows the identical file set and line counts `security_review` v1
already recorded from its own re-run (`AppShell.tsx` +20/-5, `AppShell.test.tsx` +225,
`AppRoutes.test.tsx` +31 — 271 insertions/5 deletions total), and `git log --oneline -5` shows no
commit landed after `RECONCILIATION`'s `recorded_at: "2026-09-15T15:30:00Z"` in
`workflow-state.yaml`. The working tree has not moved since `reconciliation-reviewer` ran — its
verdict still describes exactly what would ship. `stale_reconciliation` does not apply.

## PR Title

```
feat: complete global navigation (US-5.6)
```

## Summary

Completes the shared navigation already hosted by `AppShell.tsx` for every existing
authenticated screen. No new screen, route, or backend/API/DB change is introduced
(`API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE`, per the story's own Out of Scope section) — this
Story only makes screens prior Stories already shipped reachable from the shared nav, and orients
the user inside them.

Delivers:
- **Full nav link coverage** — four new, ungated `NavLink` entries added as flat siblings for the
  account self-service screens that previously had no nav entry: Sessions (`/sessions`), Profile
  (`/settings/profile`), Security (`/settings/security`), Deactivate Account
  (`/settings/deactivate`). The three existing scope-gated entries (Agent Queue, Users, Audit
  Log) keep their current `canReadAgentQueue`/`canReadUsers`/`canReadAudit` gating, unchanged
  (FR-2, GN-AC2).
- **"Home" control** — a plain `Link` (never `NavLink`) targeting `/tickets`, present on every
  authenticated page, added as the nav's first child (FR-4, GN-AC4, resolves OD-1). Deliberately
  not a `NavLink`/`<button>` so it never competes with the "Tickets" entry for the active marker
  on `/tickets` (resolves OD-2).
- **Active-state indication** — every other nav entry (`Tickets` plus the three scope-gated
  entries, plus the four new ones) converted `Link` → `NavLink` with no `end` prop, so
  `NavLink`'s own `aria-current="page"` marks the current section programmatically (not colour
  alone) and a parent entry stays active on nested child/detail routes via prefix matching (FR-5,
  GN-AC5, resolves OD-4).
- **No dead nav links** — every nav target cross-checked, and proven by a behavioral test, to
  resolve to a route already registered in `AppRoutes.tsx` (FR-6, GN-AC6); `AppRoutes.tsx` itself
  is unmodified.
- **Persistent nav, client-side routing** — the shared nav remains mounted and visible across
  route transitions with no full page reload; clicking a nav entry updates the URL and renders
  the target via client-side routing (FR-1/FR-3, GN-AC1/GN-AC3).

Linked story: `docs/stories/US-5.6-global-navigation.md`
Linked spec: `docs/specifications/US-5.6-spec.md` (v2, APPROVED)
Linked plan: `docs/plans/US-5.6-implementation-plan.md` (v1, APPROVED)

Entire diff is confined to one production file, `frontend/src/layouts/AppShell.tsx` (+20/-5), plus
test-only additions to `frontend/src/layouts/AppShell.test.tsx` (+225) and
`frontend/src/routes/AppRoutes.test.tsx` (+31). No new dependency, no new configuration/setting,
and no existing exported function signature changed shape.

## Test Plan

Built from `docs/reconciliation/US-5.6-traceability.md` (v1) and
`docs/evidence/US-5.6-quality-gate-report.md` (v1). All 6 spec Acceptance Criteria (GN-AC1–GN-AC6)
plus both Verification-table rows (`a11y`, `a11y-keyboard`) have a matrix row, a test function
confirmed to exist verbatim in the working tree, and assertions confirmed by
`reconciliation-reviewer` — reading the actual test files, not their names — to match each AC's
stated behavior in Full.

- [x] GN-AC1 `[gate]` — the shared nav is visible and unchanged across route transitions, no full
      page reload. Proven by DOM-node-identity assertion, not just a URL-string check.
      (`AppRoutes.test.tsx::test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav`)
- [x] GN-AC2 `[gate]` — every existing frontend screen has a corresponding nav entry, and a user
      without a gating scope does not see it. Independently cross-checked: the nav's 8 unique
      targets match `AppRoutes.tsx`'s top-level authenticated route set exactly, no missing 9th
      screen. (`AppShell.test.tsx::test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href`
      plus extended zero-scope and pre-existing gated-entry cases)
- [x] GN-AC3 `[gate]` — clicking a nav entry renders the target via client-side routing and
      updates the URL. (same test as GN-AC1)
- [x] GN-AC4 — Home navigates to `/tickets` from a non-`/tickets` route.
      (`AppShell.test.tsx::test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route`)
- [x] GN-AC5 — the current entry carries `aria-current="page"`, a different entry does not, Home
      never carries it even on `/tickets`, a parent entry stays active on a nested detail route,
      and the marker moves after a further navigation. (four `AppShell.test.tsx` functions)
- [x] GN-AC6 `[gate]` — every nav target resolves to a registered route; none renders a blank
      screen or a 404. Proven by a behavioral cross-check (collects rendered `href`s, renders
      `AppRoutes` at each), not a parallel hardcoded list.
      (`AppShell.test.tsx::test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope`)
- [x] a11y `[gate]` — `axe()` on the fully-scoped, authenticated nav asserts zero violations.
- [x] a11y-keyboard `[gate]` — Tab/Shift-Tab reaches all 9 entries in document order; Enter
      activates the focused link. Independently re-run by `reconciliation-reviewer` in this
      session (the one step `test-writer` had flagged as unexecuted pre-implementation) and
      confirmed passing.
- [x] Full Definition-of-Done mechanical gate
      (`docs/evidence/US-5.6-quality-gate-report.md`, v1): `npm run lint` PASS (0 warnings),
      `npm run format:check` PASS, `npm run type-check` PASS, `npm run test:coverage` PASS —
      **74/74 test files, 503/503 tests**, coverage Statements 97.68%, Branches 94.55%, Functions
      86.47%, Lines 97.68% (all four clear the 85% floor); both touched files show
      100/100/100/100 in their own per-module rows.
- [x] Frontend runtime-rule substitutes independently re-verified three times this delivery (by
      `gate-enforcer`, `implementation-verifier`, and `security-reviewer`, each against the
      current working tree): no `fetch`/`axios`/`api/` import introduced, no
      `localStorage`/`sessionStorage` token handling, read-only `useAuthStore()` usage unchanged,
      zero banned idioms (`console.*`, `any`, `eslint-disable`), no `dangerouslySetInnerHTML`.

Coverage type split: integration only (React Testing Library + MSW where applicable), consistent
with this Story adding no new hook or API function — both existing test files
(`AppShell.test.tsx`, `AppRoutes.test.tsx`) are already integration-style suites; no new
unit-test file was required or added.

**Non-blocking, does not gate this PR** (carried through `IMPLEMENTATION_VERIFICATION`,
`SECURITY_REVIEW`, and `RECONCILIATION`, none escalated):
- OD-3's flat-list requirement (FR-2) has no dedicated *negative*-structure test assertion (e.g.
  "no containing `<section>`/`role=\"menu\"` wrapper") — covered only indirectly via role/name
  queries that assume a flat list. `reconciliation-reviewer` assessed this as adequate for GN-AC2
  as literally written (not an AC-adequacy gap), but a genuine coverage gap against FR-2's fuller
  text. Recommended, not required, for `test-writer` to close if `AppShell.test.tsx` is touched
  again.
- Pre-existing route-path duplication between `AppShell.tsx`'s `to=` literals and
  `AppRoutes.tsx`'s `path=` literals (not introduced by this Story). `planner` explicitly
  considered and rejected extracting a shared constants module (would have touched
  `AppRoutes.tsx`, which the impact analysis marked no-change). GN-AC6's behavioral cross-check
  test is the mitigation in place today.

## Risk / Rollback

Per `docs/plans/US-5.6-implementation-plan.md`'s Risks section:

- **No backend/API/DB surface is touched** — the entire diff is nav markup in one file plus
  test-only additions; `AppRoutes.tsx` itself is unmodified (confirmed by an empty
  `git diff --stat`). Rollback is a plain revert of the commit; no migration to reverse, no data
  to backfill.
- **No new dependency was added** — `frontend/package.json`/`package-lock.json` show no diff.
- **Home/Tickets active-state ambiguity was the plan's own named implementation trap** (both
  target `/tickets`): closed by keeping Home a plain `Link`, never `NavLink`, directly asserted by
  a dedicated test (`test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets`)
  rather than only an indirect a11y-scan check.
- **Prefix-matching collision was checked, not assumed**: the plan verified every nav `to=` value
  against every other for a path-segment-prefix relationship before adopting `NavLink`'s default
  (no `end` prop) — none collides, so no two non-Home entries can be simultaneously active under
  prefix matching for any route this Story's nav renders.
- **Client-decoded scopes remain cosmetic only, never an authorization boundary** — the four newly
  ungated entries are all account self-service screens the approved spec (FR-2) states verbatim
  should be ungated; the three routes that remain scope-gated are still conditionally rendered
  (not CSS-hidden), independently confirmed by `security-reviewer`. No nav change alters
  server-side authorization.

## `.env.example` Check

**Confirmed current — no change required.** This Story adds no new configuration, setting, or
dependency: `git diff --stat -- frontend/.env.example .env.example` returns empty, consistent
with the story's own Out of Scope section (no new screen or backend endpoint) and independently
confirmed by both `implementation-verifier` (§6.7 row, "N/A — no new setting") and
`security-reviewer`.

## Commit Hygiene Check (AGENTS.md §7.8)

**US-5.6's own file set is clean; one pre-existing branch-state concern is flagged, not silently
absorbed into this draft.**

- `git status --porcelain -- frontend/` shows exactly 3 modified tracked files —
  `frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx`,
  `frontend/src/routes/AppRoutes.test.tsx` — matching `implementation_report` v1's file-set claim
  exactly, and matching every Files-To-Modify row in `implementation_plan` v1. No file outside
  that set changed under `frontend/`; no drive-by refactor found within the touched file (the
  entire production diff is import + nav-markup changes, no unrelated logic altered).
- Every other modified/untracked path in the working tree
  (`docs/catalog/stories.yaml`, `docs/workflow/active-story.yaml`,
  `docs/workflow/history.jsonl`, `docs/workflow/workflow-state.yaml`, and the full
  `docs/{stories,specifications,reviews,decisions,evidence,impact-analysis,plans,tests,
  verification,reconciliation,catalog}/US-5.6-*` artifact set) is this delivery's own
  workflow/documentation output, owned by its producing skill per
  `docs/workflow/artifact-paths.yaml` — not unrelated scope.
- **Flagged, not resolved here:** the current branch, `feat/us-5.5-agent-console-ui`, is 5
  commits ahead of `main` (`2fbb560`, `5e28235`, `fd62fc1`, `a426a1e`, `8563ae6` — the merged
  US-5.5 feature commit plus US-5.4/US-5.5 archive and unrelated docs commits) and 4 ahead of its
  own origin remote; no dedicated `feat/us-5.6-*` branch has been created. This is a pre-existing
  branch-naming/history state carried from Story activation
  (`docs/workflow/workflow-state.yaml`'s own `note` field already records this as reported, not
  auto-resolved, per `start-flow.md` branch policy), not something this Story's implementation
  introduced, and none of those prior commits touch this Story's own file set. It means a plain
  `git push` from this branch today would carry US-5.5's already-committed history (not yet
  merged into `main` via PR) along with this Story's new commit(s). Recommend confirming with the
  user whether US-5.5 already has an open PR from this branch (in which case this Story's commit
  would simply extend that same PR) or whether a fresh `feat/us-5.6-global-navigation` branch off
  `main` should be cut before anything is pushed — this stage does not run `git` itself and takes
  no action on it.

---

**This is drafted content only.** Pushing the branch or opening the Pull Request requires an
explicit, separate human instruction to run `git push` / invoke `pr-creator` (`gh pr create` or
the `github` MCP server) — this skill does not push, open, or merge anything itself. Given the
branch-state flag above, that instruction should also settle how this Story's commit(s) relate to
the existing `feat/us-5.5-agent-console-ui` branch before anything is pushed.
