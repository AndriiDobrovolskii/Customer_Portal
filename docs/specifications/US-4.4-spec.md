---
artifact_type: specification
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-07T10:00:00Z"
updated_at: "2026-09-07T16:00:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/evidence/US-4.4-clarification-report.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Specification: Agent Ticket Queue & Assignment

**Source:** docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
**Story ID:** US-4.4
**Generated:** 2026-09-07
**Status:** Draft

## Summary

This spec covers giving a support agent access to the ticket queue on the
existing `GET /v1/support/tickets` endpoint (replacing today's reject-only
agent branch), letting an agent take or release ownership of a ticket via two
new `assign`/`unassign` endpoints, and exposing `assignee_id` on agent-facing
responses only — without changing the already-shipped customer-facing
contract or the US-4.3 resolve/close/reopen state machine.

## Background

As a support agent, I want to see the queue of tickets needing attention,
take ownership of one, and see what is assigned to me, so that work is
discoverable and divisible rather than something I can only reach by being
handed a ticket id.

`tickets:read` is already granted to `support_agent` and `admin` but is
currently used only to reject agent callers from the queue endpoint
(`reject_agent_queue_access`, a deliberate US-4.1 scope cut). No
`assignee_id` column exists on `tickets` today. This story turns
`tickets:read` into the scope it was named for and adds the column US-4.3
TC-AC4's "the previously assigned agent" language presupposed but the schema
never had.

## Functional Requirements

### FR-1: Agent Views the Ticket Queue

Given an agent holding `tickets:read`, when `GET /v1/support/tickets` is
called, the system responds `200` with every ticket not in status
`"closed"`, regardless of requester, ordered oldest-`updated_at` first
(stable-tiebroken by `id`), and each item carries `assignee_id`. The
response is cursor-paginated with no total count.

**Derived from:** AQ-AC1; the agent-branch response item shape (which
carries `assignee_id`) follows OD-1's recommended default — see
[Response Schemas](#response-schemas) and [Open Questions](#open-questions).

### FR-2: Queue Filtering

Given an agent holding `tickets:read`, when `GET /v1/support/tickets` is
called with `status`, `category`, or `assignee_id` query parameters, the
system returns only matching tickets. `assignee_id=me` resolves to the
calling agent's own id. `assignee_id=none` returns only tickets with no
assignee. `status=closed` is the only way a closed ticket appears in the
response — the default, filterless queue excludes closed tickets.

**Derived from:** AQ-AC2.

### FR-3: Assign a Ticket

Given an agent holding `tickets:write` and a ticket with no assignee, when
`POST /v1/support/tickets/{id}/assign` is called with `{assignee_id}` naming
another agent, the system responds `200` with `assignee_id` set and writes a
`ticket_audit_log` entry (`event=ticket_assigned`, `actor=`the caller,
`target=`the ticket). Re-assigning an already-assigned ticket replaces the
assignee and writes the same audit event for the new value.

**Derived from:** AQ-AC3; response shape follows OD-1's recommended default
— see [Response Schemas](#response-schemas).

### FR-4: Unassign a Ticket

Given a ticket with an assignee, when `DELETE /v1/support/tickets/{id}/assign`
is called by a caller holding `tickets:write`, the system responds `200`
with `assignee_id` null and writes a `ticket_audit_log` entry
(`event=ticket_unassigned`).

Whether this success path applies when the ticket is `"closed"`, or whether
a closed ticket instead falls to FR-9's `409` (mirroring assign's
closed-ticket restriction, for symmetry), is OD-3 — not resolved by any
Acceptance Criterion. Per OD-3's recommended default, not yet
human-confirmed: a closed ticket also returns `409` here. See
[Open Questions](#open-questions).

**Derived from:** AQ-AC4; closed-ticket handling per OD-3's recommended
default (not yet confirmed); response shape per OD-1's recommended default.

### FR-5: Customer Branch Unchanged

Given a customer holding no `tickets:*` scope, when
`GET /v1/support/tickets` is called, the system returns only that
customer's own tickets, exactly as US-4.1 specified, and no field in the
response exposes `assignee_id`.

**Derived from:** AQ-AC5.

### FR-6: Agent-Only Query Parameters Are Ignored for a Customer Caller

Given a customer holding no `tickets:read`, when `GET /v1/support/tickets`
is called with `assignee_id` or another agent-only filter, the system
ignores that filter and returns only the caller's own tickets — never
another customer's. A missing scope falls through to the customer branch; it
never returns an unfiltered list, and the unrecognized parameter is not
rejected with a `422` — the ownership filter, not parameter validation, is
what protects the data.

**Derived from:** AQ-AC6.

### FR-7: Assignment Requires `tickets:write`

Given a caller without `tickets:write`, when `POST` or
`DELETE /v1/support/tickets/{id}/assign` is called, the system responds
`404` for a customer (never confirming the ticket id exists) and `403` with
type `.../errors/insufficient-permission` for a caller holding
`tickets:read` but not `tickets:write`.

**Derived from:** AQ-AC7.

### FR-8: Assignee Must Hold `tickets:write`

Given an assign request naming a user who holds no `tickets:write`, when
`POST /v1/support/tickets/{id}/assign` is called, the system responds `422`
with type `.../errors/validation-failed`, because a ticket assigned to
someone who cannot act on it is an invisible dead end.

Whether this check also rejects a target account that holds `tickets:write`
but is deactivated is OD-4 — AQ-AC8's rationale ("cannot act on it") would
support it, but its literal wording names only the scope condition. Per
OD-4's recommended default, not yet human-confirmed: a deactivated target
account is also rejected with the same `422`. See
[Open Questions](#open-questions).

**Derived from:** AQ-AC8; deactivated-account handling per OD-4's
recommended default (not yet confirmed).

### FR-9: Assigning a Closed Ticket Is Rejected

Given a ticket in status `"closed"`, when
`POST /v1/support/tickets/{id}/assign` is called, the system responds `409`
with type `.../errors/invalid-state-transition`.

**Derived from:** AQ-AC9.

### FR-10: Concurrent Assignment

Given two agents assigning the same unassigned ticket simultaneously, when
both requests are processed, exactly one succeeds — via a conditional
update scoped to the ticket's expected current `assignee_id` — and the other
receives `409`, not a silent overwrite.

**Derived from:** AQ-AC10.

## Response Schemas

### Agent-Facing Response Shapes (OD-1 — Critical, not yet human-confirmed)

The source's API Contract table names the queue and assign/unassign
response types as `TicketListResponse`/`TicketStateRead` "(agent shape)",
while its own Assumption #7 and Non-Functional Requirements state
`assignee_id` MUST NOT appear on any customer-facing response shape.
`TicketRead` and `TicketStateRead` (`app/modules/support/schemas.py`) are
the same schemas already returned by `GET /v1/support/tickets`'s customer
branch and by the already-shipped, customer-reachable `/close` and
`/reopen` endpoints (US-4.3). Extending those shared schemas to carry
`assignee_id`, as the "(agent shape)" wording could be read to require,
would leak `assignee_id` into those customer-reachable responses — this is
OD-1 (`docs/decisions/US-4.4-open-decisions.md`), logged and **not
resolved**.

For drafting purposes, this spec follows OD-1's recommended default: two
new response shapes, scoped to this story's agent-only endpoints, carry
`assignee_id`; `TicketRead` and `TicketStateRead` are left exactly as
US-4.1/US-4.3 shipped them.

- **`AgentTicketRead`** — the agent-branch queue item shape (FR-1, FR-2):
  every `TicketRead` field, plus `assignee_id`.
- **`AgentTicketStateRead`** — the assign/unassign response shape (FR-3,
  FR-4, FR-9): every `TicketStateRead` field, plus `assignee_id`.

This is a drafting default, not a human decision. It must be confirmed — or
overridden — at `HUMAN_SPEC_APPROVAL` before `API_DESIGN` commits to a
schema shape. See [Open Questions](#open-questions).

## Non-Functional Requirements

- The agent branch of `GET /v1/support/tickets` MUST NOT widen what a
  customer sees: the two branches share one endpoint but not one query. A
  missing scope falls through to the customer branch, never to an
  unfiltered list (FR-6).
- `assignee_id` MUST NOT appear on any customer-facing response shape
  (Assumption #7; see [Response Schemas](#response-schemas) / OD-1).
- The queue query MUST be index-backed for its default ordering and every
  supported filter — a sequential scan over `tickets` is not acceptable as
  the queue grows.
- Every assign/unassign MUST write its audit entry in the same transaction
  as the write.
- Removing `reject_agent_queue_access` MUST update, not delete, the US-4.1
  tests that assert its `403` — the replacement assertion is the new agent
  branch (FR-1, FR-2).

**Derived from:** Non-Functional / Security Requirements section of the
source.

## Out of Scope

- Auto-assignment, round-robin, load balancing, or any routing rule.
- SLA targets, breach reporting, queue-level metrics.
- Multi-assignee / team-level ownership.
- Attachments (still blocked on the unwritten attachment-upload story).
- Any change to the resolve/close/reopen state machine (US-4.3).
- Notifying the assignee by email on assignment — the source's own stated
  default for its Open Question #2 is no notification in this story; it is
  an additive follow-up.
- Transitioning ticket status as a side effect of assign/unassign — the
  source's own stated default for its Open Question #1 is that assignment
  is orthogonal to the US-4.3 state machine.

**Derived from:** Out of Scope section of the source; the last two items
follow from the source's own Open Questions #1 and #2 and their stated
default assumptions.

## Open Questions

Four Open Decisions are logged in
`docs/decisions/US-4.4-open-decisions.md` (v1) and are not resolved by this
spec. Where an Open Decision's recommended default was usable for drafting,
it is stated in the relevant FR above, explicitly flagged as not yet
human-confirmed; none of the four is silently treated as final.

1. **OD-1 (Critical):** Do the queue and assign/unassign endpoints return
   distinct `AgentTicketRead`/`AgentTicketStateRead` shapes (this spec's
   drafting default, see [Response Schemas](#response-schemas)), or does the
   source's "(agent shape)" wording mean extending the shared
   `TicketRead`/`TicketStateRead` — which would leak `assignee_id` into the
   already-shipped, customer-reachable `/close` and `/reopen` responses?
   Must be confirmed at `HUMAN_SPEC_APPROVAL` before `API_DESIGN` commits to
   a schema shape.
2. **OD-2 (Medium):** Does `GET /v1/support/tickets/{id}`
   (`TicketDetailRead`) also gain `assignee_id` for an agent caller, or is
   In Scope's "agent-facing read shapes" limited to the two shapes the API
   Contract table actually names (queue item, assign/unassign response)?
   This spec does not extend `TicketDetailRead` — the API Contract table is
   treated as the authoritative, itemized list of endpoints this story
   touches, per the Open Decision's recommendation — but this has not been
   human-confirmed. No FR above covers `GET /{id}`.
3. **OD-3 (Medium):** Does `DELETE .../assign` on a `"closed"` ticket return
   `409` (FR-4's drafting default, mirroring FR-9's assign-on-closed
   restriction, for symmetry), or does it succeed with `200` /
   `assignee_id` cleared, since nulling a field on an already-terminal
   ticket has no further operational consequence? No Acceptance Criterion
   exercises this combination. Confirm at `HUMAN_SPEC_APPROVAL`.
4. **OD-4 (Low):** Does FR-8's "must hold `tickets:write`" check also
   reject a deactivated target account (this spec's drafting default), or
   is the check limited to the role/scope grant regardless of account
   status? Confirm at `HUMAN_SPEC_APPROVAL`.
5. The source's own Open Question #5 asks whether the queue should expose a
   display name alongside `assignee_id`, since `support_agent` may not hold
   `users:read` and a UI cannot resolve the UUID itself. No Acceptance
   Criterion or In Scope item proposes such a field, and the question is
   framed in the source as context for US-5.5 (frontend), not a requirement
   of this story. No FR above adds a display-name field; this is noted, not
   resolved, for whoever specs US-5.5.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AQ-AC1 | "Given an agent holding tickets:read When GET /v1/support/tickets is called Then respond 200 with every non-closed ticket regardless of requester, ordered oldest-updated first And each item carries assignee_id And the response pages by cursor with no total count" | FR-1 |
| AQ-AC2 | "Given an agent holding tickets:read When GET /v1/support/tickets is called with status, category or assignee_id Then only matching tickets are returned And assignee_id=me resolves to the calling agent's own id And assignee_id=none returns only unassigned tickets And status=closed is the only way a closed ticket appears" | FR-2 |
| AQ-AC3 | "Given an agent holding tickets:write and a ticket with no assignee When POST /v1/support/tickets/{id}/assign is called with another agent's id Then respond 200 with assignee_id set And an audit entry is written (event=ticket_assigned, actor=the caller, target=the ticket) And re-assigning an already-assigned ticket replaces the assignee and audits the change" | FR-3 |
| AQ-AC4 | "Given a ticket with an assignee When DELETE /v1/support/tickets/{id}/assign is called by a tickets:write holder Then respond 200 with assignee_id null And an audit entry is written (event=ticket_unassigned)" | FR-4 |
| AQ-AC5 | "Given a customer holding no tickets:* scope When GET /v1/support/tickets is called Then they receive only their own tickets, exactly as US-4.1 specified And no response field exposes assignee_id" | FR-5 |
| AQ-AC6 | "Given a customer holding no tickets:read When GET /v1/support/tickets is called with assignee_id or another agent's filter Then the filter is ignored and only their own tickets are returned — never another customer's Because the customer branch already ignores query parameters it does not declare; a 422 here would let an unauthenticated-for-the-queue caller probe which agent-only parameters exist, and the ownership filter is what actually protects the data" | FR-6 |
| AQ-AC7 | "Given a caller without tickets:write When POST or DELETE /v1/support/tickets/{id}/assign is called Then respond 404 for a customer (never confirming the ticket id exists, consistent with TR-AC4/TC-AC7) And 403 with type \".../errors/insufficient-permission\" for a tickets:read-only agent" | FR-7 |
| AQ-AC8 | "Given an assign request naming a user who holds no tickets:write When POST /v1/support/tickets/{id}/assign is called Then respond 422 with type \".../errors/validation-failed\" Because a ticket assigned to someone who cannot act on it is an invisible dead end" | FR-8 |
| AQ-AC9 | "Given a ticket in status \"closed\" When POST /v1/support/tickets/{id}/assign is called Then respond 409 with type \".../errors/invalid-state-transition\"" | FR-9 |
| AQ-AC10 | "Given two agents assigning the same unassigned ticket simultaneously When both requests are processed Then exactly one wins via a conditional update scoped to the expected assignee_id And the loser receives 409, not a silent overwrite" | FR-10 |
</content>
