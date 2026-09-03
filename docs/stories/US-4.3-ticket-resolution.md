# Epic 4 — Feedback / Support: Ticket Resolution

**Story ID:** US-4.3
**Project:** Customer Portal

## User Story
As a support agent,
I want to mark a ticket resolved and have it close itself if the customer is satisfied,
So that the queue reflects real outstanding work and customers can still come back if the fix did not hold.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Reopen window / auto-close delay | 7 days, expressed as **one** configuration constant | The two must never drift apart |
| 2 | `closed` | Terminal; no reopen | Makes retention and reporting unambiguous |
| 3 | Who may resolve | Any actor with `tickets:write` | Assignment is not a prerequisite; the actor is audited |
| 4 | Who may close | The requester or an agent | A customer confirming "that fixed it" should not wait 7 days |
| 5 | Resolution note | Mandatory, non-empty | It is what the customer receives and what the next agent reads |
| 6 | Concurrency | Conditional update scoped to the expected current status | Mirrors US-1.2 FR-1 and US-1.4 FR-1/FR-9 |
| 7 | Time-window evaluation | In SQL, against the database clock, in the same statement as the write | App/DB clock skew must not decide the boundary |

## In Scope
- `POST /v1/support/tickets/{id}/resolve`, `/close`, `/reopen`
- The auto-close job and its race handling
- The state machine as a single normative transition table

## Out of Scope
- CSAT survey on resolution — a later, asynchronous consumer of the `closed` transition
- SLA targets and breach reporting
- `related_ticket_id` back-reference from a new ticket to a closed one (belongs to US-4.1 if adopted)

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/support/tickets/{id}/resolve` | `tickets:write` | `{"resolution_note": str}` | 200 |
| POST | `/v1/support/tickets/{id}/close` | Requester or `tickets:write` | `{"reason"?: str}` | 200 |
| POST | `/v1/support/tickets/{id}/reopen` | Requester or `tickets:write` | `{"reason"?: str}` | 200 |

## State machine (normative)
| From | Event | To | Who |
|---|---|---|---|
| open / waiting_on_support / waiting_on_customer / reopened | resolve | resolved | agent |
| resolved | customer reply (within 7 days) | reopened | customer |
| resolved | reopen (within 7 days) | reopened | customer or agent |
| resolved | auto-close job (7 days idle) | closed | system |
| any non-closed | close | closed | requester or agent |
| closed | — | *(terminal)* | — |

`open` is an entry state only: it is produced by US-4.1 and is never the target of a transition.

## Data Model Notes
- `tickets.status` ∈ {`open`, `waiting_on_support`, `waiting_on_customer`, `resolved`, `reopened`, `closed`}
- `CHECK ((status = 'resolved') = (resolved_at IS NOT NULL AND resolution_note IS NOT NULL))`
- `CHECK ((status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL))`
- Partial index `(resolved_at) WHERE status = 'resolved'` — the auto-close job scans exactly this
- `ticket_audit_log` records every transition, including system-driven ones (`actor=system`)

## Acceptance Criteria

### Happy path
**TC-AC1 — Agent resolves**
```gherkin
Given an agent with tickets:write and a ticket in an open state
When POST /v1/support/tickets/{id}/resolve is called with {resolution_note}
Then respond 200 with status "resolved" and resolved_at set
And resolved_at is the only timing field written; no SLA target is evaluated
And the requester is emailed the resolution note plus a link to reopen
And a ticket_audit_log entry is written (event=ticket_resolved, actor=agent:{id})
```

**TC-AC2 — Customer closes their own ticket**
```gherkin
Given the ticket's requester and a ticket in any non-closed state
When POST /v1/support/tickets/{id}/close is called
Then respond 200 with status "closed" and closed_at set
And the audit entry records actor=self
```

**TC-AC3 — Auto-close after the grace period**
```gherkin
Given a ticket resolved more than 7 days ago with no reply since
When the scheduled auto-close job runs
Then status becomes "closed" and closed_at is set
And a ticket_audit_log entry is written (event=ticket_auto_closed, actor=system)
And the job's update is conditioned on the ticket still being resolved with the same resolved_at,
    so a reply committed first makes the job a no-op
```

**TC-AC4 — Reply reopens a resolved ticket**
```gherkin
Given a ticket resolved less than 7 days ago
When the requester posts a reply (US-4.2)
Then status becomes "reopened" and resolved_at is cleared
And the previously assigned agent is notified
```

### Negative paths
**TC-AC5 — Illegal transition**
```gherkin
Given a ticket that is already "closed"
When POST /v1/support/tickets/{id}/resolve or /reopen is called
Then respond 409 with type ".../errors/invalid-state-transition"
And the problem+json body lists the transitions actually permitted from the current state
```

**TC-AC6 — Customer attempts to resolve**
```gherkin
Given the ticket's requester, who does not hold tickets:write
When POST /v1/support/tickets/{id}/resolve is called
Then respond 403 with type ".../errors/insufficient-permission"
Because a customer may close their ticket (TC-AC2) but only an agent may declare it resolved
```

**TC-AC7 — Acting on someone else's ticket**
```gherkin
Given customer A and a ticket belonging to customer B
When any of /resolve, /close or /reopen is called
Then respond 404 with type ".../errors/not-found"   # consistent with TR-AC4
```

**TC-AC8 — Concurrent resolution**
```gherkin
Given two agents resolving the same ticket simultaneously
When both requests are processed
Then exactly one succeeds; the transition is a conditional update scoped to the expected current status
And the loser receives 409, not a silent overwrite of the first agent's resolution_note
```

**TC-AC9 — Missing resolution note**
```gherkin
Given a resolve request with an empty or absent resolution_note
When POST /v1/support/tickets/{id}/resolve is called
Then respond 422 with type ".../errors/validation-failed"
Because the note is what the customer receives and what the next agent reads
```

## Error Envelope (RFC 7807 `application/problem+json`)
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
Error `type` slugs introduced by this story: `invalid-state-transition` (shared with US-3.1.5).

## Non-Functional / Security Requirements
- The state machine MUST be **one explicit transition table** in a single module; scattered `if status == …` checks are how invalid states get in.
- State is checked before actor: a customer resolving an *open* ticket gets 403 (TC-AC6), anyone resolving a *closed* one gets 409 (TC-AC5). The reverse order would leak the ticket's state to an actor who may not act on it.
- The 7-day window MUST be evaluated by the database, in the same statement that performs the write, from a single shared constant. The reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them.
- The auto-close job MUST be batched and idempotent (safe to re-run); `rowcount == 0` is the expected, non-error outcome for a ticket that moved in the meantime.
- A reply and its resulting status change MUST commit in one transaction — otherwise the system accumulates replies attached to closed tickets that nobody is notified about.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| TC-AC1–2 | Integration test suite | `[gate]` |
| TC-AC3 | Integration test with a fixed database clock, including the reply-wins and job-wins orderings | `[gate]` |
| TC-AC4 | Integration test asserting resolved_at is cleared | `[gate]` |
| TC-AC5–7 | Integration test suite, asserting the 409/403/404 split | `[gate]` |
| TC-AC8 | Concurrency test: two simultaneous resolves; asserts one 200, one 409, note preserved | `[gate]` |
| TC-AC9 | Schema test on the Pydantic request model | `[gate]` |
| Single transition table | Architecture/import-linter rule preventing status branching outside the module | `[gate]` if enforceable, otherwise `[manual]` |

## Open Questions
1. May an agent post a public reply on a **resolved** ticket without reopening it, and if so, does that reply reset the auto-close clock? Default assumption: permitted, status unchanged, `resolved_at` untouched.
2. Should a new ticket created after a closure carry a `related_ticket_id` back-reference? Affects US-4.1's schema.