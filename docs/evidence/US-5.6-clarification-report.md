---
artifact_type: clarification_report
story: US-5.6
version: 1
status: DRAFT
created_at: "2026-09-15T07:35:19Z"
updated_at: "2026-09-15T07:35:19Z"
produced_by: us-clarifier
inputs:
  - path: docs/product/product-vision.md
    version: null
  - path: docs/product/personas.md
    version: null
  - path: docs/product/business-rules.md
    version: null
  - path: docs/product/business-glossary.md
    version: null
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: 1
supersedes: null
---

# US-5.6 — Clarification Report

**Story:** `docs/stories/US-5.6-global-navigation.md` — Global Navigation (Frontend)
**Stage:** CLARIFICATION
**Active-story check:** Confirmed. `docs/workflow/active-story.yaml` names `US-5.6` / `docs/stories/US-5.6-global-navigation.md` as the active Story (`status: IN_PROGRESS`), matching the requested target. `docs/workflow/workflow-state.yaml` independently confirms `story: US-5.6` at `current_stage: CLARIFICATION`/`status: IN_PROGRESS` — the two agree. No mismatch.
**Prior Open Decisions log:** None existed for US-5.6 before this run.
**Front matter:** `track: frontend` is explicitly set — no ambiguity for the harness's IMPLEMENTATION dispatch.

## Scope, Actor, and Business Value

**Actor:** "a portal user" generically — the User Story deliberately does not name a single persona, since this Story's purpose is orienting *every* authenticated persona (Customer, Administrator, Support Agent, Auditor — `docs/product/personas.md`) inside whichever screens their role already reaches.

**Trigger/business value:** stated directly in the User Story and in "Current State" — `AppShell.tsx` already hosts one shared nav above every authenticated route, but three concrete gaps exist today (verified directly against `frontend/src/layouts/AppShell.tsx` and `frontend/src/routes/AppRoutes.tsx`, both read in full this pass):
1. The nav lists `Tickets` plus scope-gated `Agent Queue`/`Users`/`Audit Log` only — confirmed accurate. US-5.2's four self-service screens (`/settings/profile`, `/settings/security`, `/settings/deactivate`, `/sessions`) are registered routes with no nav entry at all.
2. Every link is a plain `Link`, not `NavLink` — confirmed; no active-state class exists anywhere in `AppShell.tsx`.
3. `"/"` redirects to `/tickets` (`AppRoutes.tsx` line 87) with no clickable "Home"/logo control anywhere in the nav — confirmed.

This closes a real completeness/UX gap in already-shipped functionality; it introduces no new screen, endpoint, or business capability. Matches the product vision's "user self-service" goal indirectly (makes existing self-service screens reachable) and Product Goal 5 ("Administrative functionality," by making the admin/agent screens reachable too).

**In scope / Out of scope:** clearly and consistently stated — extend the existing shell's nav only; no new routing library, no new dashboard screen (pending OD-1), no `AppRoutes.tsx` restructuring, no role-based personalization beyond what already exists. The story is explicit and largely unambiguous about this boundary.

## Dependency Check

- **US-5.1, US-5.2, US-5.3, US-5.4, US-5.5** are all `ARCHIVED` (`docs/catalog/stories.yaml`) — every screen this Story adds a nav entry for already exists and is routed. Verified directly: `frontend/src/routes/AppRoutes.tsx` registers `/tickets`, `/tickets/new`, `/tickets/:id`, `/sessions`, `/settings/profile`, `/settings/security`, `/settings/deactivate`, `/admin/users` (+ `new`/`:id`), `/admin/audit-logs`, `/agent/tickets` (+ `:id`) — every path GN-AC2/GN-AC6 reference exists.
- US-5.1's own open-decisions log still carries nine unresolved items (`docs/catalog/stories.yaml` note) — none of them concern navigation/nav-entry coverage, consistent with the precedent already set when US-5.3/US-5.4/US-5.5 each proceeded past this same fact.
- No backend Story is a dependency; this Story changes no API/DB (confirmed — the story states so and nothing in `docs/product/business-rules.md` contradicts it).

## What's Clear (verified directly against source, not just the story's own claims)

- **AppShell.tsx / AppRoutes.tsx current state** — the three gaps described in "Current State" are all confirmed accurate against the live files (see above); nothing overstated or stale.
- **Assumption #3 (link set)** — every route named in GN-AC2 is confirmed registered in `AppRoutes.tsx`; no invented screen.
- **New nav entries carry no scope gating** — `ProfileScreen.tsx`, `SecurityScreen.tsx`, `SessionsScreen.tsx`, `DeactivateAccountScreen.tsx` and their routes carry no `scopes.includes(...)` check anywhere (confirmed via grep across `frontend/src`) — so per Assumption #3's own rule ("gated by the same scope check... the route/screen itself already enforces"), these four new entries are visible to every authenticated user regardless of role, which is consistent with GN-AC2's table-driven test including a "zero-scope" row. This is inferable from the current code and not logged as an Open Decision.
- **Assumption #5 / NFR (cosmetic-only gating)** — matches the codebase's established convention exactly: `AppShell.tsx`'s existing admin/agent gating (`scopes.includes("users:read")` etc.) already reads `useAuthStore().scopes` directly with no enforcement claim, and BR-010/the Permission Scope glossary entry confirm server-side scope checks are the actual boundary. No contradiction.
- **Screen enumeration in GN-AC2 is exhaustive by the story's own text** — it explicitly lists exactly 8 screens (Tickets, Sessions, Profile, Security, Deactivate Account, Agent Queue, Users, Audit Log) and does not include sub-routes (`/tickets/new`, `/tickets/:id`, `/admin/users/new`, `/admin/users/:id`, `/agent/tickets/:id`). This is a resolved-by-citation reading, not an inference: those sub-routes are reached from within their parent list screens, not via top-level nav entries.
- **Accessibility mechanism** — React Router's `NavLink` sets `aria-current="page"` on the active link automatically, satisfying the NFR's "the active entry is programmatically determinable (not colour alone)" without any extra work. The a11y tooling the Enforcement Matrix's gate row requires already exists in this codebase (`frontend/src/test/vitest-axe.d.ts`, `frontend/src/test/setup.ts`, and is already used across most existing `*.test.tsx` screen tests) — the gate is achievable with no new dependency.
- **Acceptance criteria are testable** — GN-AC1 through GN-AC6 are all written as concrete, checkable Gherkin with no "the system should handle this appropriately"-style vague language, and the Enforcement Matrix already maps each to a specific test mechanism.

## What's Ambiguous or Contradicted (logged as Open Decisions)

Four items are recorded in `docs/decisions/US-5.6-open-decisions.md`:

1. **OD-1 (High, the story's own Assumption #2 / Open Question #1, formalized and enriched):** "Home" target = `/tickets`, no new dashboard screen — the story's own author already flags this as blocking before IMPLEMENTATION. This pass adds verified evidence that a staff-only account (holding neither `tickets:read` nor `tickets:write` — e.g. a pure `admin`/`auditor`) would land on an always-empty ticket list rather than an error (`app/modules/support/router.py:60-95` confirms `reject_agent_queue_access` was retired and the customer branch never 403s), which should inform the resolution rather than being silently assumed acceptable.
2. **OD-2 (Medium, new):** Assumption #2 (Home targets the same route as "Tickets") conflicts in effect with Assumption #4 (blanket `NavLink` swap) against GN-AC5's "distinguished from the others" (singular) — whether "Home" itself ever carries active-state styling is unstated and the two defaults, taken literally together, produce two simultaneously-active entries on `/tickets`.
3. **OD-3 (Low, the story's own Open Question #2, formalized):** nav entry grouping/sectioning vs. flat list — explicitly deferred by the story's own author to IMPLEMENTATION; recorded so the flat-list default isn't silently treated as final if the requester does have a preference.
4. **OD-4 (Low, new):** whether a parent nav entry (e.g. "Tickets," "Users," "Agent Queue") shows active state while the user is on one of its nested child/detail routes — React Router v6's `NavLink` default (prefix match) already gives a safe, non-blocking default, but the choice should be deliberate rather than an accidental side effect of how `NavLink`/`end` is used.

No ambiguity was silently dropped or silently answered; every gap found is either resolved above by a cited source or logged as one of the four Open Decisions.

## Readiness Verdict

**PASS — Ready for Specification**, with Open Decisions carried forward per `docs/workflow/artifact-lifecycle.md` (they are resolved at `HUMAN_SPEC_APPROVAL`, not here). Scope, actor, and business value are understood and restated above; the story's own "Current State" claims were independently verified against the live `AppShell.tsx`/`AppRoutes.tsx` and found accurate; every remaining ambiguity is either resolved by a cited source in this report or logged as an Open Decision in `docs/decisions/US-5.6-open-decisions.md`.

Per this skill's own contract, Open Decisions may remain `OPEN` at this stage — none of the four rises to `BLOCKED` (the story is intelligible, and `active-story.yaml`/`workflow-state.yaml` agree). All four are therefore carried as non-blocking findings in this stage's Result Envelope, in addition to being logged, so they travel with the transition rather than depending on someone opening this report — **OD-1** most prominently, since the story's own text already names it as the one choice that changes this Story's size (a nav-only fix vs. a new landing screen) and asks that it be confirmed no later than `SPECIFICATION`/`HUMAN_SPEC_APPROVAL`. OD-2 through OD-4 each have a safe, literal-AC-satisfying default already identified, so `SPECIFICATION` can proceed while all four remain open, provided the spec records them as Open Decisions rather than silently picking one default as final.

## Non-Blocking Findings

1. **OD-1** — "Home" target = `/tickets`, no dedicated dashboard screen: the story's own author already flags this as the one choice that changes this Story's size; must be confirmed no later than `SPECIFICATION`/`HUMAN_SPEC_APPROVAL`. See `docs/decisions/US-5.6-open-decisions.md` OD-1.
2. **OD-2** — whether "Home" itself ever carries active-state styling, given it shares a target with "Tickets." See OD-2.
3. **OD-3** — nav entry grouping/sectioning vs. flat list (the story's own Open Question #2). See OD-3.
4. **OD-4** — parent nav entry active-state on nested child/detail routes. See OD-4.
5. `docs/stories/README.md`'s backlog table has not been updated past US-5.5 ("Story drafted" status for US-5.2 through US-5.5, though all four are `ARCHIVED` per `docs/catalog/stories.yaml`) and has no row for US-5.6 yet. Does not affect this Story's readiness — `docs/catalog/stories.yaml` is the authoritative status source — but worth a maintainer's attention independent of this Story.
