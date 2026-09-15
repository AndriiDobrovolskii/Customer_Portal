---
artifact_type: reconciliation
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T10:51:51Z"
updated_at: "2026-09-15T16:00:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.6-spec-review.md
    version: 1
  - path: docs/reviews/designs/US-5.6-design-review.md
    version: 1
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.6-plan-review.md
    version: 1
  - path: docs/tests/US-5.6-test-strategy.md
    version: 1
  - path: docs/tests/US-5.6-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.6-test-generation-report.md
    version: 1
  - path: docs/evidence/US-5.6-implementation-report.md
    version: 1
  - path: docs/verification/US-5.6-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.6-security-review.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 2
supersedes: null
---

# Reconciliation Review: Global Navigation (Frontend) — US-5.6

**Story ID:** US-5.6
**Reviewed:** 2026-09-15
**Overall Verdict:** PASS

**Note on verdict vocabulary.** `assets/template.md`'s placeholder (`{{Pass | Pass with Issues |
Fail}}`) uses the retired enum. Per `AGENTS.md` §8 (canonical sources win on conflict) and
`docs/workflow/artifact-lifecycle.md` §2 ("`Pass`... MUST NOT appear in any skill or new artifact"),
matching this skill's own Harness Contract and the sibling `implementation_verification` v1/
`security_review` v1 reports for this Story, this report uses `PASS` / `CHANGES_REQUIRED` /
`BLOCKED` throughout, not the template's stale wording.

## Preconditions

`implementation-verifier` (`docs/verification/US-5.6-implementation-verification.md` v1) recorded
**PASS**, and `gate-enforcer` (`docs/evidence/US-5.6-quality-gate-report.md` v1) recorded **PASS**
(`npm run lint`/`format:check`/`type-check` clean, `npm run test:coverage` 503/503 tests across
74/74 files, all four coverage metrics above the 85% floor). Both preconditions satisfied.
`security-reviewer` (`docs/reviews/security/US-5.6-security-review.md` v1) also recorded **PASS**,
read for context though not a formal precondition of this stage. `docs/workflow/stage-map.yaml`'s
own `RECONCILIATION` entry (lines 327-336) was read this session and confirms `next: HUMAN_PR_APPROVAL`
and the six valid `loop_back` keys — matching this report's Result Envelope. Every consumed artifact's
front-matter `version`/`status` was read directly off disk this session and matches this report's
own `inputs:` above; none is `SUPERSEDED` or `ARCHIVED`. `docs/decisions/US-5.6-open-decisions.md`
v2 confirms OD-1 through OD-4 all `RESOLVED` at `HUMAN_SPEC_APPROVAL` on 2026-09-15 — no unresolved
blocking Open Decision. `api_design`/`openapi`/`database_design`/`entity_model` are correctly
`NOT_APPLICABLE` (`design_review` v1's own Overall Verdict is `NOT_APPLICABLE`) — this Story
changes no backend/API/DB surface, confirmed by `implementation_report` v1's file-set claim
(exactly three frontend files touched: `AppShell.tsx`, `AppShell.test.tsx`, `AppRoutes.test.tsx`).

## Method

Per this skill's required reading order: `docs/specifications/US-5.6-spec.md` v2 (GN-AC1 through
GN-AC6's FR text and the Verification table's `a11y`/`a11y-keyboard` rows), then
`docs/tests/US-5.6-ac-test-matrix.md` v1, then both named test files in full —
`frontend/src/layouts/AppShell.test.tsx` (409 lines, 19 `it` blocks) and
`frontend/src/routes/AppRoutes.test.tsx` (519 lines, 31 `it` blocks) — read directly, not taken on
any prior stage's summary, then `docs/plans/US-5.6-implementation-plan.md` v1. The current
`frontend/src/layouts/AppShell.tsx` production file was also read in full and compared line-by-line
against the plan's Architectural Changes 1-3.

`frontend/src/routes/AppRoutes.tsx` was also read in full this session (not taken from
`implementation_verification` v1's line-number citation on trust) to independently confirm GN-AC2's
converse direction — that the nav's 8 entries are not just individually valid but *complete* against
the actual authenticated top-level screen set. Confirmed: inside the `ProtectedRoute`/`AppShell`
group (`AppRoutes.tsx:77-111`), the top-level (non-child/detail) routes are exactly `/tickets`
(`:88`), `/sessions` (`:91`), `/settings/profile` (`:92`), `/settings/security` (`:93`),
`/settings/deactivate` (`:94`), `/admin/users` (`:101`), `/admin/audit-logs` (`:104`), and
`/agent/tickets` (`:109`) — precisely the 8 unique `href`s the nav renders (Home dedupes with
Tickets). The child/detail routes `/tickets/new`, `/tickets/:id`, `/admin/users/new`,
`/admin/users/:id`, `/agent/tickets/:id` correctly have no nav entry (reached via in-screen
navigation, not the global nav), and `/verify-email`/`/confirm-email-change` sit outside the
`ProtectedRoute`/`AppShell` group entirely, so they are correctly excluded from "every existing
frontend screen" in GN-AC2's sense. No 9th authenticated top-level screen exists with a missing nav
entry — GN-AC2's completeness clause holds against the primary source, not merely against the AC
text's own enumeration.

**This stage's two explicit remit items were independently investigated, not re-litigated as already
closed:**

1. **OD-3's flat-list negative-structure gap** — assessed below under "OD-3 Assessment."
2. **The a11y-keyboard test's Enter-on-anchor step** — re-run directly in this session (not taken on
   `implementation_report`/`quality_gate_report`'s word). Result:
   `npx vitest run src/layouts/AppShell.test.tsx -t
   "test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry"`
   executed the full test, including its final Shift-Tab-to-Users → `{Enter}` → assert
   `route-location` reads `/admin/users` sequence, and it **passed** (1 passed, 596ms). The full
   files were also re-run together (`AppShell.test.tsx` + `AppRoutes.test.tsx`): 50/50 passed
   (19 + 31), matching `implementation_report` v1's and `quality_gate_report` v1's claimed counts
   exactly. The step that `test-writer`'s own report flagged as having "no in-repo precedent and
   hasn't executed yet" now demonstrably executes and passes against the real, current
   `user-event@14.5.2` + `react-router-dom@^6.26.2` stack, not merely against a claim that it does.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| GN-AC1 | "Given a signed-in user on any route inside the ProtectedRoute/AppShell group / Then the shared nav is visible, unchanged across route transitions (no full page reload)" | Yes | `test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` (`AppRoutes.test.tsx:498`) | Yes | Yes | Asserts the pre-click "Tickets" nav link DOM node is referentially identical (`toBe`) to the post-click one — direct proof of no remount, not just a URL-string check. |
| GN-AC2 | "Given a signed-in user viewing the nav / Then every existing frontend screen (Tickets, Sessions, Profile, Security, Deactivate Account, and — scope-gated as today — Agent Queue, Users, Audit Log) has a corresponding nav entry / And a user without a gating scope does not see that entry" | Yes | `test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href` (`:213`); extended `test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` (`:127`) and `test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope` (`:163`); pre-existing `test_app_shell_renders_the_users_and_audit_log_nav_entries_when_scopes_include_users_read_and_audit_read` (`:114`), `test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read` (`:151`) | Yes | Yes | Positive coverage for all 8 entries by role+name+href, at both a representative granted-scope combination and at zero scope (five ungated entries present); negative coverage for each gated entry (`queryByRole(...).not.toBeInTheDocument()`) at zero scope. Both clauses of the AC directly asserted. |
| GN-AC3 | "Given a signed-in user on any page / When they click a nav entry / Then the target screen renders via client-side routing (no full page reload) / And the browser URL updates to match" | Yes | `test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` (`AppRoutes.test.tsx:498`) | Yes | Yes | Clicks the "Sessions" nav link, asserts `route-location` testid updates to `/sessions` (URL-match clause) and the nav is not remounted (client-side-routing clause), via the same DOM-node-identity assertion as GN-AC1. |
| GN-AC4 | "Given a signed-in user on any page / Then a \"Home\" control (or clickable logo) is present in the nav / When clicked, it navigates to /tickets" | Yes | `test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route` (`:234`) | Yes | Yes | Starts on `/settings/profile` (a non-`/tickets` page, deep in account self-service), clicks "Home," asserts `route-location` reads `/tickets`. |
| GN-AC5 | "Given a signed-in user has navigated to a page via a nav entry / Then that entry is visually distinguished (e.g. a distinct class/style) from the others / And the distinction updates correctly as the user navigates further" | Yes | `test_app_shell_current_route_nav_entry_carries_aria_current_while_a_different_entry_does_not` (`:247`), `test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets` (`:258`, OD-2), `test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route` (`:270`, OD-4), `test_app_shell_active_nav_entry_updates_after_navigating_to_a_different_entry` (`:280`) | Yes | Yes | `aria-current="page"` (a programmatically-determinable marker, not colour alone, satisfying the NFR) asserted present on the active entry and absent on an inactive one; Home's exemption and nested-route prefix-matching directly asserted; a second assertion after a click proves the marker moves, not just a one-shot render. |
| GN-AC6 | "Given every nav entry rendered under any combination of scopes / Then each entry's target resolves to a registered route in AppRoutes.tsx / And none renders a blank screen or a 404" | Yes | `test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope` (`:295`) | Yes | Yes | Renders `AppShell` fully scoped (all three gates open, exercising every entry per the AC's "any combination of scopes"), collects all 8 unique `href`s, renders `AppRoutes` at each, and asserts both a real-content signal (`route-location` text) and the `navigation` landmark (unique to `AppShell`, ruling out a blank/404/login-redirect render) — a genuinely behavioral cross-check against the actual route table, not a parallel hardcoded list. |
| a11y (Verification table) | "Automated a11y check (e.g. axe) on the nav in its authenticated state" | Yes | `test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped` (`:349`) | Yes | Yes | Runs `axe()` against the fully-scoped, authenticated `AppShell` render; asserts `toHaveNoViolations()`. |
| a11y-keyboard (Verification table) | "Manual or integration test asserting that Tab/Shift-Tab focus reaches every visible nav entry in order, and Enter activates the link" | Yes | `test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry` (`:366`) | Yes | Yes | Forward Tab through all 9 entries (Home → Tickets → Sessions → Profile → Security → Deactivate Account → Agent Queue → Users → Audit Log) in document order, each asserted with `toHaveFocus()`; one Shift-Tab back to Users; `{Enter}` activates the focused link, asserted by `route-location` reading `/admin/users`. **Independently re-run in this session — the final Enter-on-anchor step (the one part flagged by `test-writer` as unexecuted pre-implementation) executes and passes**, not merely claimed to. |

## OD-3 Assessment (this stage's explicit remit — not re-litigated as already closed)

**Question:** does the existing role/name-query coverage adequately prove FR-2/OD-3's flat-list
requirement ("without nested dropdowns or explicitly grouped sections"), or is the absent negative-
structure assertion an AC-adequacy gap?

**Finding: adequate for AC compliance, but the coverage gap for the FR-2 *flat-list* clause
specifically is real and worth naming — non-blocking.**

- GN-AC2's own verbatim text (the only AC FR-2 traces to) says nothing about layout structure — it
  requires "a corresponding nav entry" per screen and correct scope-gating, both of which are fully
  and directly asserted (see the GN-AC2 row above). The flat-list/no-grouping requirement is an
  FR-2 elaboration derived from OD-3's resolution, not a clause of GN-AC2's own Gherkin text. So
  GN-AC2 itself is fully proven regardless of this gap, and the absence of a negative-structure
  assertion does not leave any AC unproven — it does not force a Fail.
- That said, the role/name-query coverage (`getByRole("link", { name: ... })`) genuinely does
  **not** prove flat-list-ness: React Testing Library's role queries locate an element by its
  accessible role and name regardless of DOM ancestry — a `<section aria-label="Admin"><NavLink>
  Users</NavLink></section>` or a `<div role="menu">` wrapper around the same links would still
  satisfy every existing assertion in this suite. So if a future change (in this Story or a later
  one) silently reintroduced grouping or nested-dropdown markup, this test suite would not catch
  it — the current `AppShell.tsx` (re-read this session, lines 41-58) is in fact a flat list of
  sibling elements today, matching OD-3's resolution, but that specific structural property is
  asserted only by visual inspection of the source, not by an automated test.
- **Verdict on this remit item:** not an AC-adequacy gap (GN-AC2 is fully covered as literally
  written), but a genuine, non-blocking test-coverage gap against FR-2's fuller stated text. Carried
  forward as a non-blocking finding below rather than a loop-back-forcing one, consistent with how
  `implementation_verification` v1 and the `ac_test_matrix` itself already framed it — this stage's
  independent assessment concurs with, rather than simply repeats, that framing.

## Spec Drift Check

Compared the current `frontend/src/layouts/AppShell.tsx` against spec v2's FR-1 through FR-6 and the
implementation plan's Architectural Changes 1-5 directly, line by line:

- Home is a plain `Link` (`AppShell.tsx:49`), never `NavLink` — matches FR-4/OD-2 exactly.
- All other entries (`Tickets`, `Sessions`, `Profile`, `Security`, `Deactivate Account`, and the
  three scope-gated entries) are `NavLink` with no `end` prop — matches FR-5/OD-4's prefix-matching
  resolution exactly.
- The four new entries are added as plain flat siblings, no wrapping section — matches FR-2/OD-3
  (see OD-3 Assessment above for the coverage caveat, not a drift finding).
- No new scope constant, no change to `canReadUsers`/`canReadAudit`/`canReadAgentQueue`, no change
  to `AppRoutes.tsx` (confirmed empty `git diff --stat` for that file), no new screen, hook, or API
  call introduced — matches the spec's "API / Persistence Impact" statement of zero backend/API/DB
  change and the plan's "Files To Create: None."
- No field renamed, no validation rule loosened or tightened, no error code changed from what the
  spec states (this Story states no validation/error-handling requirement beyond GN-AC6's dead-link
  clause, itself fully covered).

**No drift found.** The shipped implementation matches the approved spec (v2) and implementation
plan (v1) exactly.

## Non-Blocking Findings (carried forward, do not affect the verdict)

- **OD-3's flat-list requirement (FR-2) has no dedicated negative-structure test assertion.** See
  "OD-3 Assessment" above — GN-AC2 itself is fully proven; this is a coverage gap against the fuller
  FR-2 text, not an AC gap. Recommended (not required) for `test-writer` to close with a query such
  as asserting the nav's entries share a common parent with no intervening `<section>`/`role="menu"`
  wrapper, should a future Story touch this file again.
- **Pre-existing route-path duplication** between `AppShell.tsx`'s `to=` literals and
  `AppRoutes.tsx`'s `path=` literals (not introduced by this Story; `planner` explicitly considered
  and rejected extracting a shared constants module — Architectural Change 4). GN-AC6's behavioral
  cross-check test is the mitigation in place today. Carried forward unchanged from
  `implementation_verification` v1.

## Verdict Rationale

Every one of GN-AC1 through GN-AC6, plus both Verification-table rows (`a11y`, `a11y-keyboard`),
has a matrix row, a named test function that was opened and confirmed to exist at the cited
location, and assertions read in full and confirmed to match the AC's actual stated behavior — not
merely proximity to it. The a11y-keyboard test's previously-unexecuted final Enter-on-anchor step
was independently re-run in this session and confirmed passing against the current implementation,
closing the one open empirical question this stage was specifically asked to verify. No spec drift
was found comparing the shipped `AppShell.tsx` against spec v2 and implementation plan v1. The one
carried-forward OD-3 finding is a non-blocking test-coverage gap against FR-2's fuller text, not an
AC-adequacy gap against GN-AC2 as literally written, so it does not force a Fail. Verdict: **PASS**.
