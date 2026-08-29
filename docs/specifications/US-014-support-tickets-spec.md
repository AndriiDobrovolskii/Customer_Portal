# Specification: Support Tickets (Create)

**Source:** docs/stories/US-4.1-create-ticket.md
**Story ID:** US-014
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/specifications/US-014-spec-review.md)

## Summary

This spec covers self-service creation of support tickets by authenticated customers: idempotent ticket creation with a human-readable ticket number, listing the caller's own tickets, input validation, rate limiting, authentication/eligibility gating, and attachment binding with its ownership (IDOR) check. Attachment *upload* itself is out of scope, per the source story.

## Background

As a customer, I want to raise a support ticket from inside the portal, so that my problem is tracked with a reference number instead of disappearing into an inbox.

## Functional Requirements

### FR-1: Successful Ticket Creation

Given an authenticated, active customer, when `POST /v1/support/tickets` is called with `{subject, body, category}` and an `Idempotency-Key` header, the system responds `201` with the created ticket, including a human-readable `ticket_number` (e.g. `CP-2026-0000431`) that is sequential but non-guessable as an API identifier, so it cannot be used to enumerate other tickets; sets `status` to `"open"` and `requester_id` to the caller; writes no SLA target field — only the raw timestamps other stories stamp; queues a confirmation email containing the ticket number to the requester; and writes a `ticket_audit_log` entry (`event=ticket_created`).

**Derived from:** ST-AC1; `ticket_number` non-guessability per source Assumptions & Defaults table

### FR-2: Listing Own Tickets

Given an authenticated customer with existing tickets, when `GET /v1/support/tickets` is called (accepting `status`, `cursor`, and `limit` query parameters per the source's API Contract table), the system responds `200`, cursor-paginated, with only that customer's tickets, newest first. When the same endpoint is called by a support agent, the response is scoped to the queue that agent's permissions allow, not to other customers' private ticket views (the exact permission/scope model for agent visibility is not defined in this story — see Open Questions).

**Derived from:** ST-AC2; query parameters and pagination style per source API Contract table

### FR-3: Invalid Input Rejected

Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category, when `POST /v1/support/tickets` is called, the system responds `422` with a `problem+json` body of type `.../errors/validation-failed`, whose `errors` array names each offending field, and no ticket is created.

**Derived from:** ST-AC3

### FR-4: Duplicate Submission Returns the Original Ticket

Given a request that is retried with the same `Idempotency-Key` within 24 hours, when `POST /v1/support/tickets` is called again, the system responds `201` with the original ticket, and no second ticket exists.

**Derived from:** ST-AC4

### FR-5: Idempotency Key Reused With a Different Body

Given the same `Idempotency-Key` is reused with a different body, when `POST /v1/support/tickets` is called, the system responds `422` with a `problem+json` body of type `.../errors/idempotency-key-reuse`.

**Derived from:** ST-AC4

### FR-6: Unauthenticated Request Rejected

Given a request with no valid access token, when `POST /v1/support/tickets` is called, the system responds `401`.

**Derived from:** ST-AC5

### FR-7: Deactivated Account Rejected at Ticket Creation

Given an authenticated user whose account is deactivated, when `POST /v1/support/tickets` is called, the system responds `403` with a `problem+json` body of type `.../errors/account-deactivated`.

**Derived from:** ST-AC5

### FR-8: Rate Limiting on Ticket Creation

Given a customer who has created 5 tickets in the last hour, when `POST /v1/support/tickets` is called again, the system responds `429` with a `Retry-After` header, and the customer's existing open tickets are unaffected.

**Derived from:** ST-AC6

### FR-9: Attachment Ownership Validation (IDOR Prevention)

Given a ticket-creation request containing an `attachment_id` that was uploaded by a different user, is already bound to another ticket, or does not exist, the system responds `422` with a `problem+json` body of type `.../errors/attachment-not-owned`; no ticket is created; and the response does not reveal which of the three cases applied. (The source's parallel clause for the reply endpoint, US-4.2, is out of scope for this spec.)

**Derived from:** ST-AC7

### FR-10: Attachment Binding on Successful Ownership Check

Given an `attachment_id` uploaded by the caller and not yet bound to a ticket, when the ticket is created, the attachment is bound to that ticket and becomes immutable — an attachment belongs to exactly one ticket forever. Unbound attachments older than 24 hours are purged by a scheduled job.

**Derived from:** ST-AC7

## Non-Functional Requirements

- Ticket bodies must be rendered as plain text or sanitised Markdown; user-supplied HTML must never be rendered, since an agent's console is a high-value XSS target.
- The attachment-ownership check (FR-9) must verify both `uploaded_by == caller` and `ticket_id IS NULL`; accepting an `attachment_id` without checking both is a textbook IDOR.
- Attachment ids must be UUIDv4, never sequential; attachment download is authorised against the *ticket's* access rules (US-4.2 TR-AC4), not against possession of the id.
- p95 latency for `POST /v1/support/tickets` must be ≤ 400 ms; the confirmation email (FR-1) is queued, never sent inline.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Attachment **upload** (size caps, MIME allowlist, antivirus scanning, signed URLs) — a separate story, blocking for Epic 4.
- Replies (US-4.2) and status transitions (US-4.3).
- Agent queue views, assignment and routing.
- SLA targets and CSAT.

**Derived from:** Out of Scope section of the source.

## Open Questions

- The source's own Open Questions note: "The attachment-upload story must be scheduled ahead of this one; until it lands, `attachment_ids` should be rejected rather than silently ignored. Needs an owner." What is the exact response (status code and error type) when `attachment_ids` is submitted before the attachment-upload story ships — is it the same `.../errors/attachment-not-owned` response used by FR-9, a distinct error type, or a schema-level rejection of the field? And who owns scheduling the attachment-upload story relative to this one?
- What response does `POST /v1/support/tickets` return when the `Idempotency-Key` header is missing entirely? The Assumptions table marks the header "required," but no Acceptance Criterion specifies the response code or error type for a request that omits it.
- For the "reused with a different body" check in ST-AC4, does the idempotency comparison consider only the `body` field, or the full request payload — as the `(request_hash, response)` shape in Data Model Notes suggests, which would also cover `subject`, `category`, and `attachment_ids`?
- What specifically determines "the queue their permissions allow" when a support agent calls `GET /v1/support/tickets` (ST-AC2)? This story does not define the permission/scope model for agent ticket visibility.
- The source's API Contract table names `status`, `cursor`, and `limit` as query parameters for `GET /v1/support/tickets`, but neither ST-AC2 nor any other AC specifies the `status` filter's accepted values, a maximum `limit`, or the response to an invalid/expired `cursor`. Should this filtering/pagination behavior be specified before implementation?
- Neither ST-AC3 nor the source elsewhere enumerates the valid `category` values — what is the complete set a ticket's `category` may take, against which "unknown category" (FR-3) is checked?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| ST-AC1 | "Given an authenticated, active customer When POST /v1/support/tickets is called with {subject, body, category} and an Idempotency-Key header Then respond 201 with the ticket, including a human-readable ticket_number And status is \"open\" and requester_id is the caller And no SLA target field is written — only the raw timestamps other stories stamp And a confirmation email containing the ticket number is queued to the requester And a ticket_audit_log entry is written (event=ticket_created)" | FR-1 |
| ST-AC2 | "Given an authenticated customer with existing tickets When GET /v1/support/tickets is called Then respond 200 with only that customer's tickets, newest first And a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views" | FR-2; Open Question (agent queue scope) |
| ST-AC3 | "Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category When POST /v1/support/tickets is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names each offending field And no ticket is created" | FR-3 |
| ST-AC4 | "Given a request that is retried with the same Idempotency-Key within 24 hours When POST /v1/support/tickets is called again Then respond 201 with the ORIGINAL ticket, and no second ticket exists Given the same key is reused with a different body Then respond 422 with type \".../errors/idempotency-key-reuse\"" | FR-4, FR-5; Open Questions (missing header, comparison scope) |
| ST-AC5 | "Given a request with no valid access token Then respond 401 Given an authenticated user whose account is deactivated Then respond 403 with type \".../errors/account-deactivated\"" | FR-6, FR-7 |
| ST-AC6 | "Given a customer who has created 5 tickets in the last hour When POST /v1/support/tickets is called again Then respond 429 with a Retry-After header And the existing open tickets are unaffected" | FR-8 |
| ST-AC7 | "Given a request containing an attachment_id that was uploaded by a different user, or is already bound to another ticket, or does not exist When POST /v1/support/tickets (or a reply, US-4.2) is called Then respond 422 with type \".../errors/attachment-not-owned\" And no ticket or reply is created, and the response does not reveal which of the three cases applied Given an attachment_id uploaded by the caller and not yet bound Then it is bound to this ticket and becomes immutable — an attachment belongs to exactly one ticket forever And unbound attachments older than 24 hours are purged by a scheduled job" | FR-9, FR-10; Open Question (interim attachment_ids handling before upload story lands) |
