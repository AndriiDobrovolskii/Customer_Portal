---
artifact_type: pr_summary
story: US-5.6
version: 2
status: DRAFT
created_at: "2026-09-15T14:39:40Z"
updated_at: "2026-09-15T18:00:00Z"
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

**Regeneration note (attempt 2).** This is a re-run of `PR_PREPARATION`, not a first pass. `v1`
(`created_at: 2026-09-15T14:39:40Z`) was drafted against the working tree while it still sat
uncommitted on `feat/us-5.5-agent-console-ui`. Since then, per human decision at `PR_CREATION`
(2026-09-15T17:45:00Z), the branch-hygiene finding `v1` flagged (this branch carried US-5.5's
already-merged history) was resolved by cutting a fresh branch, `feat/us-5.6-global-navigation`,
directly off `origin/main` (which already has US-5.5 merged as `dc0b8a1` via PR #39) and committing
US-5.6's own changes there as a single commit, `99e5128`. `pr-creator`'s staleness check correctly
found `v1` stale (its `updated_at` predates `99e5128`'s commit timestamp,
`2026-09-15T14:46:51Z` — note this environment's clock reads earlier in the day than
`workflow-state.yaml`'s own recorded event times, the same discrepancy already recorded in prior
quality-gate reports) and looped back here (`stale_pr_summary`). Content below is re-verified
against the current tree/commit, not copied from `v1`. The prior branch-hygiene finding is
**RESOLVED**, not carried forward as open. This artifact's own `updated_at` below
(`2026-09-15T18:00:00Z`) is deliberately stamped in `workflow-state.yaml`'s recorded-event time
frame (the frame `pr-creator`'s staleness check compares against), not the environment's raw
system clock — that keeps the staleness comparison against `99e5128`'s `14:46:51Z` unambiguous in
either direction and avoids a second spurious `stale_pr_summary` loop.

## Gate Confirmation

All four required upstream gates were read directly from their own artifacts this session (not
taken on a verbal "it's all good"), and each still records verdict **PASS** at the same version as
`v1` consumed — none has been re-run or revised since:

| Gate | Artifact | Version | Verdict |
|---|---|---|---|
| `gate-enforcer` (QUALITY_GATE, attempt 1) | `docs/evidence/US-5.6-quality-gate-report.md` | v1 | PASS |
| `implementation-verifier` | `docs/verification/US-5.6-implementation-verification.md` | v1 | PASS |
| `security-reviewer` | `docs/reviews/security/US-5.6-security-review.md` | v1 | PASS |
| `reconciliation-reviewer` | `docs/reviews/reconciliation/US-5.6-reconciliation.md` | v1 | PASS |

`docs/workflow/workflow-state.yaml` (`story: US-5.6`, `current_stage: PR_PREPARATION`,
`previous_stage: PR_CREATION`, `attempt: 2`, `last_result.verdict: CHANGES_REQUIRED` for
`PR_CREATION`/`stale_pr_summary`) and `docs/workflow/active-story.yaml` (`active_story: US-5.6`)
agree on the active story. `HUMAN_PR_APPROVAL` remains recorded approved by `sbruhov@gmail.com` at
`2026-09-15T16:00:00Z` against exactly `implementation_verification` v1, `security_review` v1,
`reconciliation` v1, `traceability` v1 — none of those four has changed since that approval, so it
still covers what would ship. Every front-matter `version`/`status` named in this artifact's own
`inputs:` block was read directly off disk this session: `story`
(`docs/stories/US-5.6-global-navigation.md`, no front-matter version field, `track: frontend`),
`specification` v2/APPROVED, `impact_analysis` v1/DRAFT, `implementation_plan` v1/APPROVED,
`implementation_report` v1/DRAFT, `implementation_verification` v1/APPROVED, `security_review`
v1/APPROVED, `reconciliation` v1/APPROVED, `traceability` v1/APPROVED — none is `SUPERSEDED` or
`ARCHIVED`. `docs/decisions/US-5.6-open-decisions.md` v2 confirms OD-1 through OD-4 all `RESOLVED`
at `HUMAN_SPEC_APPROVAL` 2026-09-15; no unresolved blocking Open Decision remains in any `APPROVED`
input this stage depends on.

**`stale_reconciliation` check (this stage's only loop-back trigger):** re-run against the current
commit, not `v1`'s. `git show --stat 99e5128` (also `HEAD`) shows a single commit, authored
2026-09-15T17:46:51+03:00, containing exactly the story's known file set: the full
`docs/*US-5.6*` artifact set (including `docs/reviews/reconciliation/US-5.6-reconciliation.md`
itself), `docs/catalog/stories.yaml`, `docs/workflow/active-story.yaml`,
`docs/workflow/history.jsonl`, `docs/workflow/workflow-state.yaml`, and the three frontend files
(`frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx`,
`frontend/src/routes/AppRoutes.test.tsx`). `git diff origin/main..HEAD --stat` confirms the same
28-file set, 271 insertions/5 deletions across the frontend files unchanged from what
`security_review` v1 and `reconciliation` v1 already reviewed (`AppShell.tsx` +20/-5,
`AppShell.test.tsx` +225, `AppRoutes.test.tsx` +31) — the content those two reviews evaluated is
byte-for-byte what this commit ships; only its location (a new branch/commit) changed, not its
substance. `reconciliation-reviewer`'s verdict still describes exactly what would ship.
`stale_reconciliation` does not apply.

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

Ships as a single commit, `99e5128` ("feat: global navigation (US-5.6)"), on
`feat/us-5.6-global-navigation`, based directly on `origin/main`. Its production diff is confined
to one file, `frontend/src/layouts/AppShell.tsx` (+20/-5), plus test-only additions to
`frontend/src/layouts/AppShell.test.tsx` (+225) and `frontend/src/routes/AppRoutes.test.tsx`
(+31). No new dependency, no new configuration/setting, and no existing exported function
signature changed shape.

## Test Plan

Built from `docs/reconciliation/US-5.6-traceability.md` (v1) and
`docs/evidence/US-5.6-quality-gate-report.md` (v1). All 6 spec Acceptance Criteria (GN-AC1–GN-AC6)
plus both Verification-table rows (`a11y`, `a11y-keyboard`) have a matrix row, a test function
confirmed to exist verbatim in the working tree, and assertions confirmed by
`reconciliation-reviewer` — reading the actual test files, not their names — to match each AC's
stated behavior in full.

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
      activates the focused link. Independently re-run by `reconciliation-reviewer` in its own
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
      working tree that is now committed unchanged as `99e5128`): no `fetch`/`axios`/`api/`
      import introduced, no `localStorage`/`sessionStorage` token handling, read-only
      `useAuthStore()` usage unchanged, zero banned idioms (`console.*`, `any`, `eslint-disable`),
      no `dangerouslySetInnerHTML`.

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
  `git diff --stat` for that path within `git diff origin/main..HEAD`). Rollback is a plain revert
  of the single commit `99e5128`; no migration to reverse, no data to backfill.
- **No new dependency was added** — `git diff origin/main..HEAD --stat -- frontend/package.json
  frontend/package-lock.json` is empty.
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

**Re-confirmed current — no change required.** This Story adds no new configuration, setting, or
dependency: `git diff origin/main..HEAD --stat -- .env.example frontend/.env.example` returns
empty against the current commit `99e5128`, consistent with the story's own Out of Scope section
(no new screen or backend endpoint) and independently confirmed by both `implementation-verifier`
(§6.7 row, "N/A — no new setting") and `security-reviewer`.

## Commit Hygiene Check (AGENTS.md §7.8)

**Re-verified against the new single commit `99e5128` on `feat/us-5.6-global-navigation`; clean.**

- `git branch --show-current` confirms the active branch is `feat/us-5.6-global-navigation`.
  `git merge-base --is-ancestor origin/main HEAD` confirms `HEAD` is a clean descendant of
  `origin/main` (`dc0b8a1`) — a real, linear branch-off, not a stale/diverged base.
- `git log --oneline -3` shows exactly one story commit, `99e5128` ("feat: global navigation
  (US-5.6)"), directly on top of `dc0b8a1` (the already-merged US-5.5 PR #39). No stray WIP,
  fixup, or merge-conflict-resolution commit exists on this branch.
- `git diff origin/main..HEAD --stat` shows exactly 28 changed files: the three frontend files this
  Story's `implementation_plan`/`implementation_report` name
  (`frontend/src/layouts/AppShell.tsx`, `frontend/src/layouts/AppShell.test.tsx`,
  `frontend/src/routes/AppRoutes.test.tsx`), plus `docs/catalog/stories.yaml`,
  `docs/workflow/active-story.yaml`, `docs/workflow/history.jsonl`,
  `docs/workflow/workflow-state.yaml`, and the full `docs/{stories,specifications,reviews,
  decisions,evidence,impact-analysis,plans,tests,verification,reconciliation,catalog,pr}/US-5.6-*`
  artifact set — this delivery's own workflow/documentation output, owned by its producing skill
  per `docs/workflow/artifact-paths.yaml`, not unrelated scope. No file outside that set changed;
  `frontend/package.json`/`package-lock.json` untouched (independently confirms no new
  dependency); no drive-by refactor found within the touched production file (the entire diff is
  import + nav-markup changes, no unrelated logic altered).
- `git diff origin/main..HEAD | grep -nE "^<<<<<<<|^=======|^>>>>>>>"` returns no match — no
  leftover conflict marker from the stash-pop/manual-resolve step that produced this commit
  (`workflow-state.yaml`'s own note records four workflow-tracking files were hand-resolved during
  that merge; this grep confirms none of the four, nor any other changed file, still carries a
  marker).
- **Prior finding RESOLVED, not carried forward:** `v1` of this draft flagged that the working
  branch (`feat/us-5.5-agent-console-ui`) carried unmerged US-5.5 history alongside this Story's
  changes. Per human decision recorded in `workflow-state.yaml` (2026-09-15T17:45:00Z), a fresh
  branch, `feat/us-5.6-global-navigation`, was cut from `origin/main` (which already has US-5.5
  merged as `dc0b8a1`) and only US-5.6's own changes were carried over and committed as `99e5128`.
  The four loose commits that used to sit ahead of `main` on `feat/us-5.5-agent-console-ui` are not
  ancestors of this branch and are not part of what this PR would ship — confirmed by this
  session's own `git diff origin/main..HEAD --stat`, which shows only this Story's file set. This
  is resolved history, not an open concern for this draft.
- **Flagged, not blocking:** commit `99e5128` itself contains `pr_summary` **v1** (the version that
  was current when the commit was made); this **v2** revision is, as of this write, an uncommitted
  working-tree change layered on top. `pr-creator` reads the PR body from the file on disk at
  push time, so the body it uses will be this v2 content regardless — but the pushed commit's own
  history will carry v1 of this doc until a later commit (outside this stage's remit; this skill
  does not commit) updates it. Not a hygiene defect in `99e5128` itself, since v1 was in fact
  current when that commit was made.

---

**This is drafted content only.** Pushing the branch or opening the Pull Request requires an
explicit, separate human instruction to run `git push` / invoke `pr-creator` (`gh pr create` or
the `github` MCP server) — this skill does not push, open, or merge anything itself.
