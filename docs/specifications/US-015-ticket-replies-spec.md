# Specification: Ticket Replies

**Source:** docs/backlog/US-4.2-ticket-replies.md
**Story ID:** US-015
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-015-spec-review.md)

## Summary

This spec covers threaded ticket replies: agents and customers posting public replies (with ticket status side effects and `first_response_at` stamping), agents posting internal notes that are isolated from customers at both the application and database layers, cross-customer access rejection, rejection of internal-note requests from customers, rejection of replies on closed tickets, and reply body validation.

## Background

As a customer or support agent, I want to exchange messages on a ticket in one threaded conversation, so that the full history stays in one place and nobody has to reconstruct context from scattered emails.

## Functional Requirements

### FR-1: Agent Public Reply Creates Response and Advances Status

Given a support agent with `tickets:write` and an open ticket, when `POST /v1/support/tickets/{id}/replies` is called with `{body, visibility: "public"}`, the system responds `201` with the created reply, sets the ticket's status to `"waiting_on_customer"`, stamps `first_response_at` (a plain timestamp for later reporting — no SLA target is evaluated) if this is the first public agent reply on the ticket, and notifies the requester by email.

**Derived from:** TR-AC1

### FR-2: Customer Reply Creates Response and Reverts Status

Given the ticket's requester and a ticket in `"waiting_on_customer"`, when `POST /v1/support/tickets/{id}/replies` is called with `{body}`, the system responds `201`, sets the ticket's status to `"waiting_on_support"`, and notifies the assigned agent (or the queue, if the ticket is unassigned).

**Derived from:** TR-AC2

### FR-3: Internal Notes Are Isolated From Customers

Given an agent has added a reply with visibility `"internal"`, when the ticket's requester calls `GET /v1/support/tickets/{id}`, the internal reply is absent from the response entirely and absent from every notification email. When an agent calls the same endpoint, the internal reply is returned and marked as internal. This exclusion is backed by a PostgreSQL Row-Level Security policy on `ticket_replies` that hides `visibility='internal'` rows from any connection whose session context carries the customer role, so the exclusion holds even if the application layer forgets to filter.

**Derived from:** TR-AC3

### FR-4: Cross-Customer Access Returns 404

Given customer A is authenticated and a ticket belongs to customer B, when customer A calls `POST /v1/support/tickets/{id}/replies` or `GET /v1/support/tickets/{id}` for that ticket, the system responds `404` with type `.../errors/not-found`, because a `403` would confirm the ticket id exists.

**Derived from:** TR-AC4

### FR-5: Customer Cannot Create Internal Notes

Given the ticket's requester, when `POST /v1/support/tickets/{id}/replies` is called with `{visibility: "internal"}`, the system responds `403` with type `.../errors/insufficient-permission` and no reply is created. When a customer omits the `visibility` field, it defaults to `"public"`. This restriction is also enforced at the database by a `CHECK (visibility = 'public' OR author_kind = 'agent')` constraint on `ticket_replies`, so it cannot be bypassed.

**Derived from:** TR-AC5

### FR-6: Replying to a Closed Ticket Is Rejected

Given a ticket whose status is `"closed"`, when any actor calls `POST /v1/support/tickets/{id}/replies`, the system responds `409` with a `problem+json` body of type `.../errors/ticket-closed` (per [Error Envelope Schema](#error-envelope-schema)), whose `detail` points the caller to creating a new ticket. A ticket in `"resolved"` status behaves differently — a reply reopens it, per US-4.3 TC-AC4 — and that behavior is not defined by this story.

**Derived from:** TR-AC6; error envelope per source Error Envelope section

### FR-7: Reply Body Validation

Given an empty body, or a body exceeding 5000 characters, when `POST /v1/support/tickets/{id}/replies` is called, the system responds `422` with type `.../errors/validation-failed`.

**Derived from:** TR-AC7

## Response Schemas

### Error Envelope Schema

Applies to the `problem+json` response referenced by FR-6 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/ticket-closed",
  "title": "Ticket Closed",
  "status": 409,
  "detail": "This ticket is closed. Create a new ticket if you still need help.",
  "instance": "/v1/support/tickets/{id}/replies"
}
```

Error `type` slugs introduced by this story: `ticket-closed`. FR-4's `not-found`, FR-5's `insufficient-permission`, and FR-7's `validation-failed` slugs follow the same envelope shape but are not introduced by this story.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- Visibility filtering for internal replies lives in one shared repository query, never per-serializer, and is backed at the database by PostgreSQL Row-Level Security.
- RLS policies read `app.actor_kind` and `app.actor_id`, set with `SET LOCAL` inside the request's transaction, via a shared dependency so no session can start without them.
- The RLS policy needs its own test that queries through a customer-context connection with the application filter deliberately disabled, so the database-level layer is verified independently of the application-level filter.
- Replies are sanitised on render as well as on write; tracking pixels and remote images are stripped from agent-facing views.
- Notification emails must not quote internal notes.
- Thread fetch performance: p95 ≤ 300 ms for 100 replies, paginated at 50.
- Replies are rate-limited to 30 per user per hour (default chosen in the source's Assumptions & Defaults table, pending confirmation), to bound abuse of the notification path.

**Derived from:** Non-Functional / Security Requirements section of the source; Assumptions & Defaults #7 (Rate limit).

## Out of Scope

- Resolution, closure and reopening transitions (US-4.3).
- Inbound reply-by-email ingestion — would need its own spoofing controls.
- Reply editing and deletion (replies are append-only once created).

**Derived from:** Out of Scope section of the source; Assumptions & Defaults #6 (Mutability).

## Open Questions

- Should an agent's public reply on a resolved ticket be permitted (keeping the status `"resolved"`), or should the agent be required to reopen the ticket first? The source flags this explicitly as a product call, deferred to US-4.3.
- What response (status code, error type) does `POST /v1/support/tickets/{id}/replies` return when a caller exceeds the 30-replies-per-user-per-hour rate limit stated in Assumptions & Defaults #7? No Acceptance Criterion specifies the rate-limit-exceeded behavior.
- The request body for `POST /v1/support/tickets/{id}/replies` accepts an optional `attachment_ids` field (per the API Contract table), but no Acceptance Criterion specifies validation or error handling for invalid, missing, or unauthorized attachment ids.
- What visibility does a reply default to when an agent (rather than a customer) omits the `visibility` field? TR-AC5 only specifies the default for a customer-submitted reply.
- The Enforcement Matrix gates a "No HTML rendering" requirement (via a snapshot test on the render pipeline) that does not otherwise appear in the source's Acceptance Criteria or Non-Functional / Security Requirements section. Is HTML in reply bodies prohibited outright, or is the stated sanitise-on-render/strip-tracking-pixels behavior sufficient?
- No Acceptance Criterion specifies the authorization requirement or the unauthenticated/insufficient-scope response for `GET /v1/support/tickets/{id}`, though the API Contract table requires the caller to be the requester or hold `tickets:read`.
- The Non-Functional Requirements state thread-fetch performance is measured "paginated at 50," implying `GET /v1/support/tickets/{id}` paginates its reply list, but no Acceptance Criterion or other spec section defines the pagination interface — query parameters, cursor/page semantics, or response shape — needed to retrieve replies beyond the first 50.
- FR-2's "notifies the assigned agent (or the queue, if unassigned)" states no delivery channel, unlike FR-1's explicit "notifies the requester by email." Does this reuse the same email pathway, or a different mechanism (e.g. in-app/queue notification)?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| TR-AC1 | "Given a support agent with tickets:write and an open ticket When POST /v1/support/tickets/{id}/replies is called with {body, visibility: \"public\"} Then respond 201 with the created reply And the ticket's status becomes \"waiting_on_customer\" And first_response_at is stamped if this is the first public agent reply (a plain timestamp for later reporting — no SLA target is evaluated) And the requester is notified by email" | FR-1 |
| TR-AC2 | "Given the ticket's requester and a ticket in \"waiting_on_customer\" When POST /v1/support/tickets/{id}/replies is called with {body} Then respond 201 And the ticket's status becomes \"waiting_on_support\" And the assigned agent (or the queue, if unassigned) is notified" | FR-2 |
| TR-AC3 | "Given an agent has added a reply with visibility \"internal\" When the requester calls GET /v1/support/tickets/{id} Then the internal reply is absent from the response entirely And it is absent from every notification email And when an agent calls the same endpoint, the internal reply IS returned, marked as internal And the exclusion holds even if the application layer forgets to filter, because a PostgreSQL Row-Level Security policy on ticket_replies hides visibility='internal' rows from any connection whose session context carries the customer role" | FR-3 |
| TR-AC4 | "Given customer A authenticated, and a ticket belonging to customer B When POST /v1/support/tickets/{id}/replies or GET /v1/support/tickets/{id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7" | FR-4 |
| TR-AC5 | "Given the ticket's requester When POST /v1/support/tickets/{id}/replies is called with {visibility: \"internal\"} Then respond 403 with type \".../errors/insufficient-permission\" And no reply is created And visibility defaults to \"public\" when the field is omitted by a customer" | FR-5 |
| TR-AC6 | "Given a ticket whose status is \"closed\" When any actor calls POST /v1/support/tickets/{id}/replies Then respond 409 with type \".../errors/ticket-closed\" And the response points to creating a new ticket And a \"resolved\" ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)" | FR-6 |
| TR-AC7 | "Given an empty body or one exceeding 5000 characters When POST /v1/support/tickets/{id}/replies is called Then respond 422 with type \".../errors/validation-failed\"" | FR-7 |
