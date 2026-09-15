---
artifact_type: open_decisions
story: US-5.5
version: 2
status: ARCHIVED
created_at: "2026-09-13T20:00:00Z"
updated_at: "2026-09-14T02:30:00Z"
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
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: 1
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 1
supersedes: docs/decisions/US-5.5-open-decisions.md (v1)
---

# Open Decisions: US-5.5 — Agent Console (Frontend)

This is a re-run of `CLARIFICATION` for US-5.5, ordered by `story-orchestrator`'s
`HUMAN_REDIRECTED` routing from `PLAN_REVIEW` back to `CLARIFICATION`
(`docs/workflow/history.jsonl` at `2026-09-14T02:20:00Z`). `PLAN_REVIEW`
returned `BLOCKED` because the five Open Decisions below were still `OPEN` in
the `APPROVED` v1 specification (`docs/reviews/plans/US-5.5-plan-review.md`),
the same root cause already seen once on the sibling story US-5.4: the
`HUMAN_SPEC_APPROVAL` gate approved the v1 specification without carrying a
resolution for any of OD-1 through OD-5. A human stakeholder
(`sbruhov@gmail.com`) supplied an explicit resolution for each of the five
items in this same session, today (2026-09-14). This revision records those
human-supplied resolutions; it does not invent, infer, or guess any of them.

All five items carried in `docs/decisions/US-5.5-open-decisions.md` (version 1,
`status: DRAFT`, all `OPEN`) are resolved below. Re-reading the story,
`docs/product/*`, and `docs/workflow/active-story.yaml` for this pass
surfaced no further genuinely new Open Decision beyond the normal
responsibilities checklist — see "Re-check of the normal Open-Decision
triggers" at the end of this file.

---

## OD-1 — Assignee identity: `assignee_id` is a raw UUID with no backend-provided display name — RESOLVED

**Question:** How should the queue's "assignee" column (AG-AC1) and the
agent ticket-detail screen render an assigned agent's identity, given
`assignee_id` is a bare UUID?

**Why it couldn't be inferred:** `AgentTicketRead` and `AgentTicketStateRead`
(`app/modules/support/schemas.py`) both carry `assignee_id: uuid.UUID | None`
only — no display-name field exists, and resolving one would require
`GET /admin/users/{id}` (`users:read`), a scope a `support_agent` is not
guaranteed to hold. US-4.4's own spec explicitly declined to add a
display-name field and punted the question to this Story.

**Resolution:** Accept the plan's interim default — shortened/truncated UUID
display (no backend-provided display name available).

**Rationale:** No name-resolution endpoint is reachable by every agent
holding only `tickets:write`/`tickets:read`; adding an opportunistic call
that succeeds only for a caller who also happens to hold `users:read` would
produce an inconsistent UI depending on the viewer's own permission set.
Consistent with this Story's own "no backend changes" constraint
(Assumption #7).

**Source:** human decision, 2026-09-14.

---

## OD-2 — No agent-directory mechanism for "assign to another agent" or the queue's "a specific agent" filter — RESOLVED

**Question:** How does the UI let an agent pick *which* other agent to
assign a ticket to, and how does the queue's `assignee_id` filter offer "a
specific agent" as In Scope promises?

**Why it couldn't be inferred:** No endpoint in this Story's API Contract
table (or any dependency) enumerates agent accounts for a caller holding
only `tickets:write`. `GET /admin/users` requires `users:read`, a separate
scope this Story never asserts a `support_agent` holds.

**Resolution:** Accept the plan's interim default — raw-UUID text input for
the assign-target and the queue's "a specific agent" filter (no
agent-directory endpoint exists).

**Rationale:** Keeps AG-AC1/AG-AC2 implementable as literally written
without inventing a directory-lookup dependency that does not exist yet;
defers a proper agent-directory picker to a follow-up story once an
accessible enumeration endpoint is available.

**Source:** human decision, 2026-09-14.

---

## OD-3 — Detail-screen "assign" affordance has no `assignee_id` to read: `TicketDetailRead` was deliberately not extended — RESOLVED

**Question:** AG-AC6 offers "assign" as a detail-screen action at every
non-closed status, and AG-AC3 says the detail screen renders "the ticket
header." Since `TicketDetailRead` carries no assignee field at all, what
does the detail screen display as the "current assignee," and where does
that value come from?

**Why it couldn't be inferred:** `TicketDetailRead`
(`app/modules/support/schemas.py`) has no `assignee_id` field — US-4.4's own
OD-2 was explicitly `APPROVED` as "Do not extend `GET /v1/support/tickets/{id}`
with `assignee_id`" (`docs/decisions/US-4.4-open-decisions.md` OD-2). This
Story's own API Contract table reflects that split (the queue row says
"agent shape, incl. `assignee_id`"; the `GET /{id}` row does not), yet AG-AC6
still offers "assign" as a detail-screen action.

**Resolution:** Accept the plan's interim default — navigation-state
handoff of the assignee from the queue row into the detail screen.

**Rationale:** Passes the queue row's `assignee_id` into the detail screen's
local state at navigation time, updated from `AgentTicketStateRead`'s
response after any assign/unassign call made from that screen; treated as
stale/unknown if the screen is opened by direct URL rather than from the
queue. Requires no workaround endpoint and no narrowing of AG-AC6.

**Source:** human decision, 2026-09-14.

---

## OD-4 — Should the agent console and the customer ticket UI share one app shell for a dual-role user? (Story's own Open Question #2) — RESOLVED

**Question:** Should `/agent/*` and `/tickets` be reachable from one shared
authenticated app shell for a user who holds both a customer identity and
agent scopes, or should `/agent/*` be a wholly separate entry point?

**Why it couldn't be inferred:** This is the story's own Open Question #2,
explicitly left unresolved by its author. `docs/specifications/US-5.4-spec.md`
FR-9 establishes scope-derived nav-entry visibility as the codebase's
existing pattern, but does not establish the specific outcome for a caller
who would see both `/tickets` and `/agent/*` entries simultaneously.

**Resolution:** Accept the plan's interim default — one shared AppShell with
a nav link, no separate entry point.

**Rationale:** Extends the existing scope-derived nav pattern (US-5.4 FR-9):
an `/agent/*` top-level nav entry gated on `tickets:read`, alongside the
existing `/tickets` entry, within the same shared authenticated shell — no
separate entry point, no role switcher.

**Source:** human decision, 2026-09-14.

---

## OD-5 — Close/reopen UI interaction shape: confirmation and the optional `reason` field — RESOLVED

**Question:** What does the actual close/reopen interaction look like —
does it collect the API's optional `reason` field, and/or require a
confirmation step — given no Acceptance Criterion in this Story describes
it (unlike Resolve, which AG-AC5 specifies down to the empty-note
client-side block)?

**Why it couldn't be inferred:** AG-AC6 lists "close"/"reopen" only as
status-gated affordances, not as described interactions. A precedent
exists from the customer-facing UI (`docs/specifications/US-5.3-spec.md`
FR-7/FR-8) but is suggestive, not binding, for the agent side.

**Resolution:** Accept the plan's interim default — a single action button,
no reason field, no confirmation modal (mirrors US-5.3 FR-7/FR-8).

**Rationale:** Mirrors US-5.3 FR-7/FR-8 exactly, keeping the interaction
pattern consistent across the two Stories' otherwise-shared thread/detail
components.

**Source:** human decision, 2026-09-14.

---

## Re-check of the normal Open-Decision triggers (this pass)

Re-reading `docs/product/product-vision.md`, `personas.md`,
`business-rules.md`, `business-glossary.md`, and
`docs/stories/US-5.5-agent-console-ui.md` against this skill's own
Responsibilities list (business intent, acceptance criteria, security
expectations, validation expectations, dependencies, assumptions) surfaced
no additional item that cannot be reliably inferred from those sources or
the story itself. The version-1 "Carried forward / resolved by citation"
items (the story's own Open Question #3 resolved by citation to US-4.4 OD-1;
AG-AC8's `Retry-After` mechanism confirmed already built in
`frontend/src/api/httpClient.ts`; the `track: frontend` front-matter check;
the US-4.4 hard-blocker discharge; and the hand-built-components precedent
inherited from US-5.3 OD-5) remain resolved by citation and are not reopened
here — nothing in the human's five resolutions or in this re-read touches
any of them.

**No new Open Decisions are recorded in this revision.**

---

## Summary

| # | Severity | Topic | Resolution |
|---|---|---|---|
| OD-1 | High | Assignee UUID has no display name | Shortened/truncated UUID display |
| OD-2 | High | No agent-directory mechanism for "assign to another agent" / "specific agent" filter | Raw-UUID text input, no directory picker |
| OD-3 | Medium | Detail-screen "assign" affordance vs. `TicketDetailRead` carrying no `assignee_id` | Navigation-state handoff from queue row |
| OD-4 | Medium | Shared app shell / nav for dual-role users | One shared AppShell with a nav link |
| OD-5 | Low | Close/reopen interaction shape (reason field, confirmation) | Single action button, no reason field, no confirmation modal |

All five resolved this pass (source: human decision, 2026-09-14). None were
guessed or inferred by this skill.
