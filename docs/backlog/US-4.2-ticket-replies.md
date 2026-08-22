# Epic 4 — Feedback / Support: Ticket Replies

**Story ID:** US-4.2
**Project:** Customer Portal

## User Story
As a customer or support agent,
I want to exchange messages on a ticket in one threaded conversation,
So that the full history stays in one place and nobody has to reconstruct context from scattered emails.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Cross-customer access | 404, not 403 | A 403 confirms the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7 |
| 2 | Internal notes | `visibility="internal"`, agents only | Customer-visible internal notes are a real incident, not a cosmetic bug |
| 3 | Enforcement of internal-note isolation | Two layers: shared repository filter **and** PostgreSQL Row-Level Security | The second layer holds when someone writes a new query and forgets the first |
| 4 | Status side effects | Agent public reply → `waiting_on_customer`; customer reply → `waiting_on_support` | Keeps the queue honest without manual status juggling |
| 5 | Reply on a resolved ticket | Customer reply reopens (US-4.3 TC-AC4); closed tickets reject | Reopening is the customer's affordance, closure is final |
| 6 | Mutability | Append-only; no edit or delete | Preserves the record; edits would need their own audit design |
| 7 | Rate limit | 30 replies / user / hour | Bounds abuse of the notification path |

## In Scope
- `POST /v1/support/tickets/{id}/replies` — add a public or internal reply
- `GET /v1/support/tickets/{id}` — the thread, filtered by the caller's visibility
- Status side effects and `first_response_at` stamping

## Out of Scope
- Resolution, closure and reopening transitions (US-4.3)
- Inbound reply-by-email ingestion — would need its own spoofing controls
- Reply editing and deletion

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/support/tickets/{id}/replies` | Required (requester or `tickets:write`) | `{"body", "visibility"?, "attachment_ids"?}` | 201 with the reply |
| GET | `/v1/support/tickets/{id}` | Required (requester or `tickets:read`) | — | 200 with the ticket and its visible replies |

## Data Model Notes
- `ticket_replies`: `id`, `ticket_id`, `author_id`, `author_kind`, `body`, `visibility` ∈ {`public`, `internal`}, `created_at`
- `CHECK (visibility = 'public' OR author_kind = 'agent')` — TR-AC5 restated where it cannot be bypassed
- RLS policies on `ticket_replies` read `app.actor_kind` / `app.actor_id`, set with `SET LOCAL` inside the request's transaction
- `tickets.first_response_at` stamped on the first public agent reply — a plain timestamp, no SLA target attached

## Acceptance Criteria

### Happy path
**TR-AC1 — Agent replies publicly**
```gherkin
Given a support agent with tickets:write and an open ticket
When POST /v1/support/tickets/{id}/replies is called with {body, visibility: "public"}
Then respond 201 with the created reply
And the ticket's status becomes "waiting_on_customer"
And first_response_at is stamped if this is the first public agent reply
    (a plain timestamp for later reporting — no SLA target is evaluated)
And the requester is notified by email
```

**TR-AC2 — Customer replies**
```gherkin
Given the ticket's requester and a ticket in "waiting_on_customer"
When POST /v1/support/tickets/{id}/replies is called with {body}
Then respond 201
And the ticket's status becomes "waiting_on_support"
And the assigned agent (or the queue, if unassigned) is notified
```

**TR-AC3 — Internal notes are invisible to the customer**
```gherkin
Given an agent has added a reply with visibility "internal"
When the requester calls GET /v1/support/tickets/{id}
Then the internal reply is absent from the response entirely
And it is absent from every notification email
And when an agent calls the same endpoint, the internal reply IS returned, marked as internal
And the exclusion holds even if the application layer forgets to filter, because a PostgreSQL
    Row-Level Security policy on ticket_replies hides visibility='internal' rows from any
    connection whose session context carries the customer role
```

### Negative paths
**TR-AC4 — Another customer's ticket**
```gherkin
Given customer A authenticated, and a ticket belonging to customer B
When POST /v1/support/tickets/{id}/replies or GET /v1/support/tickets/{id} is called
Then respond 404 with type ".../errors/not-found"
Because 403 would confirm the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7
```

**TR-AC5 — Customer requests an internal note**
```gherkin
Given the ticket's requester
When POST /v1/support/tickets/{id}/replies is called with {visibility: "internal"}
Then respond 403 with type ".../errors/insufficient-permission"
And no reply is created
And visibility defaults to "public" when the field is omitted by a customer
```

**TR-AC6 — Replying to a closed ticket**
```gherkin
Given a ticket whose status is "closed"
When any actor calls POST /v1/support/tickets/{id}/replies
Then respond 409 with type ".../errors/ticket-closed"
And the response points to creating a new ticket
And a "resolved" ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)
```

**TR-AC7 — Invalid body**
```gherkin
Given an empty body or one exceeding 5000 characters
When POST /v1/support/tickets/{id}/replies is called
Then respond 422 with type ".../errors/validation-failed"
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/ticket-closed",
  "title": "Ticket Closed",
  "status": 409,
  "detail": "This ticket is closed. Create a new ticket if you still need help.",
  "instance": "/v1/support/tickets/{id}/replies"
}
```
Error `type` slugs introduced by this story: `ticket-closed`.

## Non-Functional / Security Requirements
- TR-AC3 is the highest-risk requirement in this epic. Visibility filtering lives in **one shared repository query**, never per-serializer, and RLS backs it at the database.
- RLS requires the actor and role to reach the database session: set them with `SET LOCAL` (`app.actor_kind`, `app.actor_id`) inside the same transaction, via a shared dependency so no session can start without them.
- The RLS policy needs its own test that queries through a customer-context connection **with the application filter deliberately disabled** — otherwise the second layer is untested and may silently be misconfigured.
- Sanitise on render as well as on write; strip tracking pixels and remote images from agent-facing views.
- Notification emails MUST NOT quote internal notes.
- **Performance:** thread fetch p95 ≤ 300 ms for 100 replies, paginated at 50.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| TR-AC1–2 | Integration test suite asserting the status side effects | `[gate]` |
| TR-AC3 | Integration test from both perspectives, **plus** an RLS test with the app filter disabled, **plus** a notification-payload assertion | `[gate]` |
| TR-AC4 | Integration test asserting 404 for both the read and the write path | `[gate]` |
| TR-AC5–7 | Integration test suite | `[gate]` |
| No HTML rendering | Snapshot test on the render pipeline | `[gate]` |

## Open Questions
1. Should an agent's public reply on a **resolved** ticket be permitted (keeping the status resolved), or should the agent be required to reopen first? Product call; see US-4.3.