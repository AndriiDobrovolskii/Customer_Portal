# Specification: Ticket Resolution

**Source:** docs/stories/US-4.3-ticket-resolution.md
**Story ID:** US-016
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/specifications/US-016-spec-review.md)

## Summary

This spec covers the ticket resolution lifecycle: agent resolution, requester- or agent-initiated closure, automatic closure after a 7-day grace period with no reply, reopening a resolved ticket via a customer reply, and the permission, state-transition, concurrency, and validation rules enforced by the `/resolve`, `/close`, and `/reopen` endpoints.

## Background

As a support agent, I want to mark a ticket resolved and have it close itself if the customer is satisfied, so that the queue reflects real outstanding work and customers can still come back if the fix did not hold.

## Functional Requirements

### FR-1: Agent Resolves a Ticket

Given an agent holding `tickets:write` and a ticket in an open state, when `POST /v1/support/tickets/{id}/resolve` is called with a `resolution_note`, the system responds `200` with status `"resolved"` and `resolved_at` set. `resolved_at` is the only timing field written; no SLA target is evaluated. The requester is emailed the resolution note plus a link to reopen. A `ticket_audit_log` entry is written (`event=ticket_resolved`, `actor=agent:{id}`).

**Derived from:** TC-AC1

### FR-2: Customer Closes Their Own Ticket

Given the ticket's requester and a ticket in any non-closed state, when `POST /v1/support/tickets/{id}/close` is called, the system responds `200` with status `"closed"` and `closed_at` set. The audit entry records `actor=self`.

**Derived from:** TC-AC2

### FR-3: Auto-Close After the Grace Period

Given a ticket resolved more than 7 days ago with no reply since, when the scheduled auto-close job runs, the system sets status to `"closed"` and `closed_at`, and writes a `ticket_audit_log` entry (`event=ticket_auto_closed`, `actor=system`). The job's update is conditioned on the ticket still being resolved with the same `resolved_at`, so a reply that commits first makes the job a no-op.

**Derived from:** TC-AC3

### FR-4: Reply Reopens a Resolved Ticket

Given a ticket resolved less than 7 days ago, when the requester posts a reply (per US-4.2), the system sets status to `"reopened"` and clears `resolved_at`, and the previously assigned agent is notified.

**Derived from:** TC-AC4

### FR-5: Illegal Transition Rejected

Given a ticket that is already `"closed"`, when `POST /v1/support/tickets/{id}/resolve` or `/reopen` is called, the system responds `409` with a `problem+json` body of type `.../errors/invalid-state-transition` (per [Error Envelope Schema](#error-envelope-schema)), whose `allowed_events` field lists the transitions actually permitted from the current state.

**Derived from:** TC-AC5; `allowed_events` field name per source Error Envelope section

### FR-6: Customer Attempts to Resolve

Given the ticket's requester, who does not hold `tickets:write`, when `POST /v1/support/tickets/{id}/resolve` is called, the system responds `403` with a `problem+json` body of type `.../errors/insufficient-permission` — a customer may close their own ticket (FR-2) but only an agent may declare it resolved.

**Derived from:** TC-AC6

### FR-7: Acting on Someone Else's Ticket

Given customer A and a ticket belonging to customer B, when any of `/resolve`, `/close`, or `/reopen` is called, the system responds `404` with a `problem+json` body of type `.../errors/not-found`.

**Derived from:** TC-AC7

### FR-8: Concurrent Resolution

Given two agents resolving the same ticket simultaneously, when both requests are processed, exactly one succeeds — the transition is a conditional update scoped to the expected current status — and the loser receives `409`, not a silent overwrite of the first agent's `resolution_note`.

**Derived from:** TC-AC8

### FR-9: Missing Resolution Note Rejected

Given a resolve request with an empty or absent `resolution_note`, when `POST /v1/support/tickets/{id}/resolve` is called, the system responds `422` with a `problem+json` body of type `.../errors/validation-failed`, because the note is what the customer receives and what the next agent reads.

**Derived from:** TC-AC9

## Response Schemas

### Error Envelope Schema

Applies to the `problem+json` response referenced by FR-5 (`application/problem+json`, RFC 7807):

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

Error `type` slugs introduced by this story: `invalid-state-transition` (shared with US-3.1.5). FR-6's `insufficient-permission` and FR-7's `not-found` slugs follow the same envelope shape but are not introduced by this story.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- The state machine MUST be one explicit transition table in a single module; scattered `if status == …` checks are how invalid states get in.
- State is checked before actor: a customer resolving an open ticket gets `403` (FR-6), anyone resolving a closed one gets `409` (FR-5). The reverse order would leak the ticket's state to an actor who may not act on it.
- The 7-day window MUST be evaluated by the database, in the same statement that performs the write, from a single shared constant. The reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them.
- The auto-close job MUST be batched and idempotent (safe to re-run); `rowcount == 0` is the expected, non-error outcome for a ticket that moved in the meantime.
- A reply and its resulting status change MUST commit in one transaction — otherwise the system accumulates replies attached to closed tickets that nobody is notified about.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- CSAT survey on resolution — a later, asynchronous consumer of the `closed` transition.
- SLA targets and breach reporting.
- `related_ticket_id` back-reference from a new ticket to a closed one (belongs to US-4.1 if adopted).

**Derived from:** Out of Scope section of the source.

## Open Questions

- May an agent post a public reply on a resolved ticket without reopening it, and if so, does that reply reset the auto-close clock? The source's default assumption: permitted, status unchanged, `resolved_at` untouched. (From the source's own Open Questions.)
- Should a new ticket created after a closure carry a `related_ticket_id` back-reference? This affects US-4.1's schema and is not decided here. (From the source's own Open Questions.)
- FR-4 (TC-AC4) states the previously assigned agent "is notified" when a reply reopens a resolved ticket, but does not specify the channel — unlike TC-AC1, which explicitly says the requester is "emailed." Is the agent notification email, in-app, or both?
- The state machine table and API Contract list `POST /v1/support/tickets/{id}/reopen` with a direct-call success path (`resolved → reopen (within 7 days) → reopened`, actor "customer or agent"), but no TC-AC describes this endpoint succeeding — TC-AC4 covers reopening via a reply, and TC-AC5 only covers `/reopen` called on an already-`closed` ticket (409). Does this story require a success-path spec for `POST /reopen` itself, and if so: does it clear `resolved_at`, notify the assigned agent (as in FR-4), and what `ticket_audit_log` event name does it write?
- FR-1 (TC-AC1) says resolve applies to "a ticket in an open state," but the normative state machine table permits `resolve` from four states (`open`, `waiting_on_support`, `waiting_on_customer`, `reopened`), and separately notes `open` is "an entry state only... never the target of a transition." Does FR-1's resolve behavior apply to all four states the transition table permits, or only to status `open` as TC-AC1 literally states?
- The Non-Functional Requirements state "the reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them," but do not say which of the two (FR-4's reply-reopen guard, or FR-3's auto-close job predicate) uses the strict comparison and which uses the inclusive one. Which comparison applies to which?
- The API Contract table lists the auth for `POST /v1/support/tickets/{id}/close` as "Requester or `tickets:write`," and the state machine table names the actor as "requester or agent," but FR-2 (derived from TC-AC2) only exercises the requester path and states the audit entry records `actor=self`. What happens, and what audit-actor value is recorded, when an agent (not the requester) calls `/close`?
- The Data Model Notes' constraint `CHECK ((status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL))` requires a `closed_by` value whenever a ticket is closed, but neither FR-2 (customer close) nor FR-3 (system auto-close) states what value `closed_by` takes. Is it set to `system` for FR-3, mirroring the audit log's `actor=system`, and what value does FR-2 set it to?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| TC-AC1 | "Given an agent with tickets:write and a ticket in an open state When POST /v1/support/tickets/{id}/resolve is called with {resolution_note} Then respond 200 with status \"resolved\" and resolved_at set And resolved_at is the only timing field written; no SLA target is evaluated And the requester is emailed the resolution note plus a link to reopen And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})" | FR-1 |
| TC-AC2 | "Given the ticket's requester and a ticket in any non-closed state When POST /v1/support/tickets/{id}/close is called Then respond 200 with status \"closed\" and closed_at set And the audit entry records actor=self" | FR-2 |
| TC-AC3 | "Given a ticket resolved more than 7 days ago with no reply since When the scheduled auto-close job runs Then status becomes \"closed\" and closed_at is set And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system) And the job's update is conditioned on the ticket still being resolved with the same resolved_at, so a reply committed first makes the job a no-op" | FR-3 |
| TC-AC4 | "Given a ticket resolved less than 7 days ago When the requester posts a reply (US-4.2) Then status becomes \"reopened\" and resolved_at is cleared And the previously assigned agent is notified" | FR-4 (see Open Questions for notification channel) |
| TC-AC5 | "Given a ticket that is already \"closed\" When POST /v1/support/tickets/{id}/resolve or /reopen is called Then respond 409 with type \".../errors/invalid-state-transition\" And the problem+json body lists the transitions actually permitted from the current state" | FR-5 |
| TC-AC6 | "Given the ticket's requester, who does not hold tickets:write When POST /v1/support/tickets/{id}/resolve is called Then respond 403 with type \".../errors/insufficient-permission\" Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved" | FR-6 |
| TC-AC7 | "Given customer A and a ticket belonging to customer B When any of /resolve, /close or /reopen is called Then respond 404 with type \".../errors/not-found\"   # consistent with TR-AC4" | FR-7 |
| TC-AC8 | "Given two agents resolving the same ticket simultaneously When both requests are processed Then exactly one succeeds; the transition is a conditional update scoped to the expected current status And the loser receives 409, not a silent overwrite of the first agent's resolution_note" | FR-8 |
| TC-AC9 | "Given a resolve request with an empty or absent resolution_note When POST /v1/support/tickets/{id}/resolve is called Then respond 422 with type \".../errors/validation-failed\" Because the note is what the customer receives and what the next agent reads" | FR-9 |
