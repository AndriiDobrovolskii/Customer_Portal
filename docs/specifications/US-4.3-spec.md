---
artifact_type: specification
story: US-4.3
version: 2
status: DRAFT
created_at: "2026-09-06T07:00:00Z"
updated_at: "2026-09-06T09:00:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/evidence/US-4.3-clarification-report.md
    version: 1
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
supersedes: docs/specifications/US-4.3-spec.md
---

# Specification: Ticket Resolution

**Source:** docs/stories/US-4.3-ticket-resolution.md
**Story ID:** US-4.3
**Generated:** 2026-09-06 (revised 2026-09-06 after HUMAN_SPEC_APPROVAL rejection)
**Status:** Draft

## Summary

This spec covers the ticket resolution lifecycle: agent resolution, requester- or agent-initiated closure, automatic closure after a 7-day grace period with no reply, and reopening a resolved ticket either via a customer reply or a direct call — plus the permission, state-transition, concurrency, and validation rules enforced by the `/resolve`, `/close`, and `/reopen` endpoints.

## Background

As a support agent, I want to mark a ticket resolved and have it close itself if the customer is satisfied, so that the queue reflects real outstanding work and customers can still come back if the fix did not hold.

## Revision Note

This is version 2. Version 1 was rejected at `HUMAN_SPEC_APPROVAL` on
2026-09-06T08:15:00Z by sbruhov@gmail.com (recorded in
`docs/workflow/workflow-state.yaml` and `docs/workflow/history.jsonl`), which
resolved Open Decisions OD-1 through OD-8
(`docs/decisions/US-4.3-open-decisions.md`, v1) with the decisions applied
below. Where a resolution differs from OD-4's own recommended default (see
OD-4 below), the human decision governs.

- **OD-1 (Critical):** The reopen target status is `"waiting_on_support"`,
  matching already-shipped US-4.2 behavior. No `"reopened"` value is
  introduced; `tickets.status`'s value set does not include it.
- **OD-2:** The reopen notification recipient is the shared support-queue
  address (no per-ticket assignee exists), mirroring US-4.2 OD-2.
- **OD-3:** `POST /reopen`'s direct-call success path is in scope for this
  story (see FR-5).
- **OD-4:** The reply/reopen guard uses an **inclusive** comparison
  (`now - resolved_at <= 7 days`); the auto-close job predicate uses a
  **strict** comparison (`now - resolved_at > 7 days`). The auto-close job,
  not a reply or a `/reopen` call, owns the exact boundary instant.
- **OD-5:** `/resolve` is permitted from any active, non-closed status:
  `open`, `waiting_on_support`, `waiting_on_customer`.
- **OD-6:** An agent-initiated `/close` records `ticket_audit_log`
  `actor=agent:{id}`; a requester-initiated `/close` records `actor=self`.
- **OD-7:** `closed_by` is set to the acting user's id (requester or agent)
  for `/close`, and to a system-actor value for the auto-close job.
- **OD-8:** FR-1's resolution email links to the ticket detail page, where
  the requester can reply or reopen.

## Functional Requirements

### FR-1: Agent Resolves a Ticket

Given an agent holding `tickets:write` and a ticket in any active, non-closed status (`open`, `waiting_on_support`, or `waiting_on_customer`), when `POST /v1/support/tickets/{id}/resolve` is called with a `resolution_note`, the system responds `200` with status `"resolved"` and `resolved_at` set. `resolved_at` is the only timing field written; no SLA target is evaluated. The requester is emailed the resolution note plus a link to the ticket detail page, where they can reply or reopen. A `ticket_audit_log` entry is written (`event=ticket_resolved`, `actor=agent:{id}`).

**Derived from:** TC-AC1; source-state scope resolved per OD-5, reopen-link target resolved per OD-8 (both human-confirmed at `HUMAN_SPEC_APPROVAL`, 2026-09-06T08:15:00Z).

### FR-2: Ticket Closed by Requester or Agent

Given a ticket in any non-closed status, when `POST /v1/support/tickets/{id}/close` is called by the ticket's requester or by an agent holding `tickets:write`, the system responds `200` with status `"closed"` and `closed_at` set. The `ticket_audit_log` entry records `actor=self` when the requester closes and `actor=agent:{id}` when an agent closes. `closed_by` is set to the closing user's id (requester or agent) in either case.

**Derived from:** TC-AC2; agent-close path and audit actor resolved per OD-6, `closed_by` value resolved per OD-7 (human-confirmed).

### FR-3: Auto-Close After the Grace Period

Given a ticket resolved more than 7 days ago (`now - resolved_at > 7 days`, strict) with no reply since, when the scheduled auto-close job runs, the system sets status to `"closed"`, `closed_at` to the current time, and `closed_by` to a system-actor value, and writes a `ticket_audit_log` entry (`event=ticket_auto_closed`, `actor=system`). The job's update is conditioned on the ticket still being resolved with the same `resolved_at`, so a reply that commits first makes the job a no-op.

**Derived from:** TC-AC3; boundary comparison resolved per OD-4, `closed_by` value resolved per OD-7 (human-confirmed).

### FR-4: Reply Reopens a Resolved Ticket

Given a ticket resolved 7 days ago or less (`now - resolved_at <= 7 days`, inclusive), when the requester posts a reply (per US-4.2), the system sets status to `"waiting_on_support"` and clears `resolved_at`. A notification is sent to the shared support-queue address.

**Derived from:** TC-AC4; target status resolved per OD-1, boundary comparison per OD-4, notification recipient per OD-2 (all human-confirmed).

### FR-5: Direct Reopen of a Resolved Ticket

Given a ticket resolved 7 days ago or less (`now - resolved_at <= 7 days`, inclusive), when `POST /v1/support/tickets/{id}/reopen` is called by the ticket's requester or by an agent holding `tickets:write`, the system responds `200`, sets status to `"waiting_on_support"`, clears `resolved_at`, and writes a `ticket_audit_log` entry (`event=ticket_reopened`, `actor=self` for the requester or `actor=agent:{id}` for an agent).

**Derived from:** the source's API Contract and State Machine table (normative), whose direct-call success path had no covering Acceptance Criterion; scope and behavior confirmed per OD-3 at `HUMAN_SPEC_APPROVAL` (2026-09-06T08:15:00Z).

### FR-6: Illegal Transition Rejected

Given a ticket that is already `"closed"`, when `POST /v1/support/tickets/{id}/resolve` or `/reopen` is called, the system responds `409` with a `problem+json` body of type `.../errors/invalid-state-transition` (per [Error Envelope Schema](#error-envelope-schema)), whose `allowed_events` field lists the transitions actually permitted from the current state.

**Derived from:** TC-AC5; `allowed_events` field name per source Error Envelope section.

### FR-7: Customer Attempts to Resolve

Given the ticket's requester, who does not hold `tickets:write`, when `POST /v1/support/tickets/{id}/resolve` is called, the system responds `403` with a `problem+json` body of type `.../errors/insufficient-permission` — a customer may close their own ticket (FR-2) but only an agent may declare it resolved.

**Derived from:** TC-AC6.

### FR-8: Acting on Someone Else's Ticket

Given customer A and a ticket belonging to customer B, when any of `/resolve`, `/close`, or `/reopen` is called, the system responds `404` with a `problem+json` body of type `.../errors/not-found`.

**Derived from:** TC-AC7.

### FR-9: Concurrent Resolution

Given two agents resolving the same ticket simultaneously, when both requests are processed, exactly one succeeds — the transition is a conditional update scoped to the expected current status — and the loser receives `409`, not a silent overwrite of the first agent's `resolution_note`.

**Derived from:** TC-AC8.

### FR-10: Missing Resolution Note Rejected

Given a resolve request with an empty or absent `resolution_note`, when `POST /v1/support/tickets/{id}/resolve` is called, the system responds `422` with a `problem+json` body of type `.../errors/validation-failed`, because the note is what the customer receives and what the next agent reads.

**Derived from:** TC-AC9.

## Response Schemas

### Error Envelope Schema

Applies to the `problem+json` response referenced by FR-6 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/invalid-state-transition",
  "title": "Invalid State Transition",
  "status": 409,
  "detail": "A closed ticket cannot be resolved.",
  "instance": "/v1/support/tickets/{id}/resolve",
  "allowed_events": []
}
```

Error `type` slugs introduced by this story: `invalid-state-transition` (shared with US-3.1.5). FR-7's `insufficient-permission` and FR-8's `not-found` slugs follow the same envelope shape but are not introduced by this story.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- The state machine MUST be one explicit transition table in a single module; scattered `if status == …` checks are how invalid states get in.
- State is checked before actor: a customer resolving an open ticket gets `403` (FR-7), anyone resolving a closed one gets `409` (FR-6). The reverse order would leak the ticket's state to an actor who may not act on it.
- The 7-day window MUST be evaluated by the database, in the same statement that performs the write, from a single shared constant. Per OD-4 (human-confirmed at `HUMAN_SPEC_APPROVAL`, 2026-09-06T08:15:00Z): the reply/reopen guard (FR-4, FR-5) uses an inclusive comparison (`now - resolved_at <= 7 days`) and the auto-close job predicate (FR-3) uses a strict comparison (`now - resolved_at > 7 days`), so the auto-close job owns the exact boundary instant.
- The auto-close job MUST be batched and idempotent (safe to re-run); `rowcount == 0` is the expected, non-error outcome for a ticket that moved in the meantime.
- A reply and its resulting status change MUST commit in one transaction — otherwise the system accumulates replies attached to closed tickets that nobody is notified about.

**Derived from:** Non-Functional / Security Requirements section of the source; boundary-comparison assignment per OD-4.

## Out of Scope

- CSAT survey on resolution — a later, asynchronous consumer of the `closed` transition.
- SLA targets and breach reporting.
- `related_ticket_id` back-reference from a new ticket to a closed one (belongs to US-4.1 if adopted).
- An `"reopened"` status value distinct from `"waiting_on_support"` (superseded by OD-1's resolution; not part of `tickets.status`'s value set).

**Derived from:** Out of Scope section of the source; the fourth item follows from OD-1.

## Open Questions

OD-1 through OD-8 (`docs/decisions/US-4.3-open-decisions.md`, v1) were
resolved by human decision at `HUMAN_SPEC_APPROVAL` on 2026-09-06T08:15:00Z
(recorded in `docs/workflow/workflow-state.yaml` and
`docs/workflow/history.jsonl`) and are reflected in the FRs above; they are
not repeated here as open. The following two items are the source's own
stated open questions, unrelated to OD-1–OD-8, and remain open with a
documented default:

1. May an agent post a public reply on a resolved ticket without reopening it, and if so, does that reply reset the auto-close clock? Default assumption per the source: permitted, status unchanged, `resolved_at` untouched.
2. Should a new ticket created after a closure carry a `related_ticket_id` back-reference? Affects US-4.1's schema and is not decided here.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| TC-AC1 | "Given an agent with tickets:write and a ticket in an open state When POST /v1/support/tickets/{id}/resolve is called with {resolution_note} Then respond 200 with status \"resolved\" and resolved_at set And resolved_at is the only timing field written; no SLA target is evaluated And the requester is emailed the resolution note plus a link to reopen And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})" | FR-1 |
| TC-AC2 | "Given the ticket's requester and a ticket in any non-closed state When POST /v1/support/tickets/{id}/close is called Then respond 200 with status \"closed\" and closed_at set And the audit entry records actor=self" | FR-2 |
| TC-AC3 | "Given a ticket resolved more than 7 days ago with no reply since When the scheduled auto-close job runs Then status becomes \"closed\" and closed_at is set And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system) And the job's update is conditioned on the ticket still being resolved with the same resolved_at, so a reply committed first makes the job a no-op" | FR-3 |
| TC-AC4 | "Given a ticket resolved less than 7 days ago When the requester posts a reply (US-4.2) Then status becomes \"reopened\" and resolved_at is cleared And the previously assigned agent is notified" | FR-4 (target status corrected to `waiting_on_support` per OD-1; recipient per OD-2 — see Revision Note) |
| TC-AC5 | "Given a ticket that is already \"closed\" When POST /v1/support/tickets/{id}/resolve or /reopen is called Then respond 409 with type \".../errors/invalid-state-transition\" And the problem+json body lists the transitions actually permitted from the current state" | FR-6 |
| TC-AC6 | "Given the ticket's requester, who does not hold tickets:write When POST /v1/support/tickets/{id}/resolve is called Then respond 403 with type \".../errors/insufficient-permission\" Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved" | FR-7 |
| TC-AC7 | "Given customer A and a ticket belonging to customer B When any of /resolve, /close or /reopen is called Then respond 404 with type \".../errors/not-found\"   # consistent with TR-AC4" | FR-8 |
| TC-AC8 | "Given two agents resolving the same ticket simultaneously When both requests are processed Then exactly one succeeds; the transition is a conditional update scoped to the expected current status And the loser receives 409, not a silent overwrite of the first agent's resolution_note" | FR-9 |
| TC-AC9 | "Given a resolve request with an empty or absent resolution_note When POST /v1/support/tickets/{id}/resolve is called Then respond 422 with type \".../errors/validation-failed\" Because the note is what the customer receives and what the next agent reads" | FR-10 |

FR-5 (direct `/reopen` success path) has no covering Acceptance Criterion in
the source; it is derived from the source's normative API Contract and State
Machine table plus OD-3's human-confirmed resolution — see FR-5's own
"Derived from" line.
