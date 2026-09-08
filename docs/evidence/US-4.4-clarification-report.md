---
artifact_type: clarification_report
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T00:00:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
supersedes: null
---

# Clarification Report: US-4.4 Agent Ticket Queue & Assignment

**Story:** `docs/stories/US-4.4-agent-ticket-queue-and-assignment.md`
**Open Decisions:** `docs/decisions/US-4.4-open-decisions.md` (v1, 4 items)

## Business Intent

As a support agent, I want to see the queue of tickets needing attention, take
ownership of one, and see what is assigned to me, so that work is discoverable
and divisible rather than something reachable only by being handed a ticket
id. This is the fourth slice of Epic 4 and the only Epic-5-driven backend
Story: it turns the `tickets:read` scope from reject-only (a deliberate US-4.1
scope cut, OD-4) into its intended agent-queue purpose, and adds the
`assignee_id` column US-4.3 TC-AC4's "previously assigned agent" language
presupposed but the schema never had. Actor, trigger, and business value are
explicitly stated — no inference needed.

## What's Clear

- The agent-branch replacement of `reject_agent_queue_access` on the existing
  `GET /v1/support/tickets`, rather than a new `/queue` path (Assumption #1),
  with its filters (`status`, `category`, `assignee_id` including `me`/
  `none`), default ordering (oldest `updated_at` first, Assumption #8), and
  closed-ticket exclusion by default (Assumption #9) are all fully specified
  with testable Given/When/Then criteria (AQ-AC1, AQ-AC2).
- The assignment model (single nullable `assignee_id`, not a join table —
  Assumption #3), the two new endpoints and their scope (`tickets:write` —
  Assumption #4), self-assign-or-assign-others (Assumption #5), and
  assignment's non-precondition relationship to resolve/reply (Assumption #6,
  consistent with already-shipped US-4.3 Assumption #3) are all explicit.
- Customer-branch non-regression (AQ-AC5, AQ-AC6) and the negative paths for
  missing scope, non-agent assignee, and closed-ticket assignment (AQ-AC7,
  AQ-AC8, AQ-AC9) are fully specified.
- Concurrency (AQ-AC10, conditional update scoped to expected `assignee_id`)
  follows the identical, already-shipped pattern US-4.3 FR-9 established for
  `/resolve` — no new mechanism needed.
- Audit events (`ticket_assigned`, `ticket_unassigned`, each recording
  `actor_id` and target `assignee_id`) and the additive-only migration
  (nullable column + two indexes, no expand→migrate→contract) are explicit
  and consistent with BR-014/BR-019's existing audit conventions.
- `admin` is a valid assignment target alongside `support_agent`: BR-010
  authorizes on permission scope (`tickets:write`), never role name, and both
  roles hold it per the existing permission-grant migration.

## What's Ambiguous

Four Open Decisions are logged in `docs/decisions/US-4.4-open-decisions.md`.

- **OD-1 (Critical):** The API Contract says assign/unassign return
  `TicketStateRead` "(agent shape)," and Assumption #7/the NFR section say
  `assignee_id` must never appear on a customer-facing response shape — but
  `TicketStateRead` is the same schema already returned by the already-shipped
  `/close` and `/reopen` endpoints, both of which a **customer** (the ticket's
  requester) can call. Extending the shared schema, as the API Contract's
  wording could be read to imply, would leak `assignee_id` into those two
  customer-reachable responses, violating this story's own data-minimization
  rule. The same tension applies to `GET /v1/support/tickets`'s shared
  `TicketRead` item shape. This is a conflict between two of the story's own
  sections, not a gap `story-spec-writer` should silently pick a side on.
- **OD-2 (Medium):** In Scope says "agent-facing read shapes" (plural) but the
  API Contract table only names the queue list and the two assign endpoints —
  leaving whether `GET /{id}` (`TicketDetailRead`) is also expected to gain
  `assignee_id` unstated.
- **OD-3 (Medium):** Unassign on a `closed` ticket is not addressed by any AC
  (only assign-on-closed is, AQ-AC9); symmetry vs. no-op-allowed is a real
  open choice.
- **OD-4 (Low):** Whether the "assignee must be an agent" check (AQ-AC8) also
  rejects a deactivated agent account, which AQ-AC8's own rationale
  ("cannot act on it") would support but its literal wording doesn't state.

Three of the story's own explicit Open Questions (#1, #3, #4) resolve by
direct citation to the story's own Out of Scope section and to already-shipped
US-4.3 behavior, and are not carried forward as Open Decisions — see the
"Carried forward, non-blocking" section of the Open Decisions log.

## Dependency Check

- **US-4.1** (create ticket, `ST-AC2`/OD-4): shipped, archived. Established
  that agent-queue visibility was deliberately deferred out of that story;
  this story is the deferred work. No conflict.
- **US-4.2** (ticket replies): shipped, archived. `resolve_actor_kind` and the
  `tickets:write` → `"agent"` derivation this story reuses for the assign
  endpoints already exists there (`app/modules/support/dependencies.py`); no
  new derivation mechanism needed.
- **US-4.3** (ticket resolution): shipped, archived, and directly load-bearing
  for OD-1 — `/close` and `/reopen`'s customer-reachability, and the
  `TicketStateRead` schema this story's API Contract names, are both US-4.3
  artifacts this story must not regress.
- `docs/stories/README.md` confirms this story "replaces
  `reject_agent_queue_access` ... and adds `tickets.assignee_id`... blocks
  US-5.5 and nothing else" — consistent with the above; no other story depends
  on this one's output besides US-5.5 (frontend, out of this workflow's
  backend track).

## Readiness Verdict

**Ready for Specification**, with 4 Open Decisions carried forward
(`docs/decisions/US-4.4-open-decisions.md`). OD-1 is Critical and should be
confirmed by a human before `story-spec-writer`/`openapi-designer` commit to
the assign/unassign and queue response schemas — proceeding on this skill's
recommended default (distinct `AgentTicketRead`/`AgentTicketStateRead`
schemas, `TicketRead`/`TicketStateRead` left untouched) is reasonable for
drafting purposes but should be confirmed at `HUMAN_SPEC_APPROVAL` given the
regression risk to already-shipped US-4.3 customer-facing responses if the
other reading is chosen instead.
