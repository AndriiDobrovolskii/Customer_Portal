---
artifact_type: open_decisions
story: US-5.6
version: 2
status: DRAFT
created_at: "2026-09-15T07:35:19Z"
updated_at: "2026-09-15T08:00:00Z"
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

# US-5.6 — Open Decisions

**Story:** `docs/stories/US-5.6-global-navigation.md` — Global Navigation (Frontend)
**Stage:** CLARIFICATION
**Status of this log:** First clarification pass for US-5.6 — no prior `US-5.6-open-decisions.md` existed to reconcile against.

Each entry: the question, why it can't be reliably inferred from `docs/product/*`, the story itself, or the current frontend/backend source, and the concrete impact of leaving it unresolved.

---

## OD-1 (High) — "Home" control target: `/tickets`, no dedicated dashboard screen (story's own Assumption #2 / Open Question #1)

**Question:** Should the nav's "Home"/logo control link to `/tickets` (matching what `"/"` already redirects to), or does "single navigation menu / main dashboard" (the User Story's own wording) require a distinct landing screen that isn't the customer ticket list?

**Why it can't be inferred:** The story's own author already flags this as unresolved — Assumption #2 states the default and explicitly labels it "**Open Decision — confirm before IMPLEMENTATION**," and Open Question #1 repeats that it "is the one choice that changes this Story's size." `docs/product/product-vision.md` and `personas.md` describe no dashboard/landing concept at all, so there is no product source to infer an answer from independently of the story's own flag. Verified directly against the current implementation: `frontend/src/routes/AppRoutes.tsx` line 87 already redirects `"/"` to `/tickets` for every authenticated user (US-5.3 Change 11), and `frontend/src/modules/support` (`GET /v1/support/tickets`, `app/modules/support/router.py:60-95`) confirms the route no longer 403s a caller lacking `tickets:read`/`tickets:write` — a caller with neither (e.g. a pure `admin` or `auditor` account holding only `users:read`/`audit:read`/`roles:write`) simply receives an **empty** customer-branch ticket list, not an error. So reusing `/tickets` as "Home" is not technically broken for a staff-only account, but the User Story's persona is "a portal user" generally (not "a Customer"), and the story's own Current State section calls out the Home control's purpose as letting a user return to a start page "from deep inside e.g. Admin or Agent screens" — for those personas, "Home" would land them on a list that is always empty and gives no indication that this is expected/normal versus a bug.

**Impact if unresolved:** Determines whether this Story stays a nav-only fix (as scoped) or grows to include a new landing screen (explicitly Out of Scope today, per the story's own text) — a scope-changing decision a spec-writer must not make unilaterally. Even if `/tickets` is confirmed as final, the empty-list-for-staff-only-users behavior surfaced above should be recorded alongside the resolution so the spec doesn't silently omit it.

**Source:** carried forward from the story's own Assumption #2 / Open Question #1; not yet resolved.

**Resolution (2026-09-15, HUMAN_SPEC_APPROVAL, sbruhov@gmail.com):** `/tickets` confirmed as the "Home" target; no dedicated dashboard screen. The staff-only-empty-list behavior is recorded alongside the resolution as an explicit Boundary Condition on `US-5.6-spec.md` FR-4.

---

## OD-2 (Medium) — Does "Home" itself ever carry active-state styling, given "Home" and "Tickets" both target the identical route

**Question:** Assumption #2 makes the Home/logo control link to `/tickets` — the same destination the existing "Tickets" nav entry already links to. Assumption #4 says the active-state mechanism is React Router's `NavLink` (`isActive`-driven class), and GN-AC5 requires "that entry is visually distinguished... from the others" (singular). While the user is on `/tickets`, should **only** "Tickets" show the active marker (with "Home" implemented as a plain, non-`NavLink` logo/brand element exempt from the active-state mechanism), or would a literal `NavLink` on both controls make **both** "Home" and "Tickets" show active simultaneously — contradicting GN-AC5's "distinguished from the others"?

**Why it can't be inferred:** Neither the Assumptions & Defaults table nor any Acceptance Criterion states whether "Home" participates in the active-state mechanism at all — Assumption #4 describes the mechanism generically ("Swap `Link` for React Router's own `NavLink`... across the nav") without saying whether the Home control counts as one of the nav's `Link`s being swapped, or is a separate, exempt element (e.g. a static logo). `docs/product/business-rules.md` and `business-glossary.md` say nothing about navigation UI patterns. This is a genuine conflict between two of the story's own defaults (Assumption #2's shared target, Assumption #4's blanket `NavLink` swap), not something a spec-writer can resolve by picking either default alone.

**Impact if unresolved:** GN-AC5's enforcement test ("Test asserting the current route's nav entry carries the active marker and a different one does not") behaves differently depending on the answer — implemented one way, the test as literally described would need to additionally assert "Home" does *not* carry the marker on `/tickets`; implemented the other way, "Home" would need its own active-state assertion. Left to an implementer's guess, GN-AC5 is at real risk of being interpreted two different, mutually exclusive ways.

**Source:** new finding, this pass — cross-reads Assumption #2, Assumption #4, and GN-AC5.

**Resolution (2026-09-15, HUMAN_SPEC_APPROVAL, sbruhov@gmail.com):** "Home" is exempt from the active-state mechanism and never shows active, even on `/tickets` — only "Tickets" carries the marker there. Recorded as an explicit Home Exception on `US-5.6-spec.md` FR-5.

---

## OD-3 (Low) — Nav entry grouping/sectioning vs. a flat list (story's own Open Question #2)

**Question:** Now that the full link set is 8 entries long (Tickets, Sessions, Profile, Security, Deactivate Account, and — scope-gated — Agent Queue, Users, Audit Log), should the admin/agent-only entries be visually grouped under a section (e.g. "Admin"/"Agent"), or remain a flat list matching today's convention?

**Why it can't be inferred:** The story's own Open Question #2 raises this and explicitly defers it: "Left to IMPLEMENTATION unless the requester has a preference." No product source (`business-rules.md`, `business-glossary.md`, `personas.md`) describes a navigation-grouping convention, and no prior frontend Story (US-5.1 through US-5.5) introduced a nav section/grouping precedent to reuse — `frontend/src/layouts/AppShell.tsx` today renders every entry as a sibling `<Link>` inside one `<nav>`, with no wrapping section element.

**Impact if unresolved:** Low — none of GN-AC1 through GN-AC6 requires or forbids grouping, so a flat list (matching today's convention, per the story's own suggested default) is a safe, non-blocking default that satisfies every stated Acceptance Criterion. Recorded so this default isn't silently treated as final if the requester does have a preference.

**Source:** carried forward from the story's own Open Question #2; not yet resolved.

**Resolution (2026-09-15, HUMAN_SPEC_APPROVAL, sbruhov@gmail.com):** Flat list, matching today's convention — no grouped/sectioned admin/agent entries. Recorded on `US-5.6-spec.md` FR-2.

---

## OD-4 (Low) — Does a parent nav entry show "active" while the user is on one of its child/detail routes?

**Question:** `AppRoutes.tsx` nests several routes under an entry the nav will link to only at its parent path — e.g. `/tickets/new` and `/tickets/:id` under "Tickets" (`/tickets`); `/admin/users/new` and `/admin/users/:id` under "Users" (`/admin/users`); `/agent/tickets/:id` under "Agent Queue" (`/agent/tickets`). Should the parent nav entry (e.g. "Tickets") show the active marker while the user is on one of these child routes (e.g. viewing `/tickets/42`), or only when the URL matches the nav entry's `to=` exactly?

**Why it can't be inferred:** Assumption #4 specifies the mechanism (`NavLink`'s built-in `isActive`) but not its matching mode — React Router v6's `NavLink` (`frontend/package.json`: `react-router-dom ^6.26.2`) defaults to prefix matching (active on any path starting with `to=`) unless the `end` prop is passed, which would restrict it to an exact match. GN-AC5 only says the distinction "updates correctly as the user navigates further," which is satisfied either way and doesn't disambiguate this specific case.

**Impact if unresolved:** Low — React Router's un-flagged default (prefix matching, parent stays active on a child route) is a reasonable, commonly-expected behavior and satisfies every stated AC either way, so it's a safe non-blocking default. Recorded so the choice is deliberate (via `end` prop usage or its omission) rather than an accidental side effect of whichever way an implementer happens to write the `NavLink` calls.

**Source:** new finding, this pass — cross-reads Assumption #4 against `AppRoutes.tsx`'s nested route structure and React Router v6's `NavLink` default.

**Resolution (2026-09-15, HUMAN_SPEC_APPROVAL, sbruhov@gmail.com):** Parent nav entries stay active on nested child/detail routes via prefix matching (React Router v6 `NavLink` default, no `end` prop). Recorded on `US-5.6-spec.md` FR-5.

---

## Summary

| # | Severity | Topic | Source of ambiguity | Resolution |
|---|---|---|---|---|
| OD-1 | High | "Home" target = `/tickets`, no dedicated dashboard | Story's own Assumption #2 / Open Question #1 (explicitly pre-IMPLEMENTATION-blocking); enriched with verified staff-only-empty-list behavior (`app/modules/support/router.py:60-95`) | RESOLVED 2026-09-15 — `/tickets` confirmed; staff-only-empty-list recorded as FR-4 Boundary Condition |
| OD-2 | Medium | Whether "Home" itself ever carries active-state styling, given it shares a target with "Tickets" | Assumption #2 vs. Assumption #4 vs. GN-AC5 | RESOLVED 2026-09-15 — "Home" exempt, FR-5 Home Exception |
| OD-3 | Low | Nav entry grouping/sectioning vs. flat list | Story's own Open Question #2 | RESOLVED 2026-09-15 — flat list, FR-2 |
| OD-4 | Low | Parent nav entry active-state on nested child/detail routes | Assumption #4 vs. React Router v6 `NavLink` default prefix matching | RESOLVED 2026-09-15 — prefix matching, FR-5 Nested Routes |

All four items above were resolved at `HUMAN_SPEC_APPROVAL` on 2026-09-15 by sbruhov@gmail.com, and each resolution was written back into `docs/specifications/US-5.6-spec.md` (v2) FR text — not left only in this table, per the precedent noted in `docs/reviews/specifications/US-5.6-spec-review.md`.
