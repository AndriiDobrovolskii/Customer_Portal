# Epic 4 — Feedback / Support: Support Tickets (Create)

**Story ID:** US-4.1
**Project:** Customer Portal

## User Story
As a customer,
I want to raise a support ticket from inside the portal,
So that my problem is tracked with a reference number instead of disappearing into an inbox.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Idempotency | `Idempotency-Key` header required; replay returns the original 201 | Support forms are exactly where double-submits happen |
| 2 | Public reference | `ticket_number` (e.g. `CP-2026-0000431`), sequential but non-guessable as an API identifier | Human-readable reference without enabling enumeration |
| 3 | Field limits | subject 1–150, body 1–5000 characters | Keeps rendering and notification payloads predictable |
| 4 | Rate limit | 5 tickets / user / hour | Bounds abuse without hampering genuine users |
| 5 | SLA fields | None written in this story | The SLA table does not exist yet; only raw timestamps are recorded |
| 6 | Attachments | `attachment_ids` referencing already-uploaded objects, bound at creation | Upload is a separate, blocking story |

## In Scope
- `POST /v1/support/tickets` — create a ticket
- `GET /v1/support/tickets` — list the caller's own tickets
- Attachment binding and its ownership check

## Out of Scope
- Attachment **upload** (size caps, MIME allowlist, antivirus scanning, signed URLs) — separate story, **blocking for Epic 4**
- Replies (US-4.2) and status transitions (US-4.3)
- Agent queue views, assignment and routing
- SLA targets and CSAT

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/v1/support/tickets` | Required; `Idempotency-Key` header | `{"subject", "body", "category", "attachment_ids"?}` | 201 with the ticket |
| GET | `/v1/support/tickets` | Required | — (query: `status`, `cursor`, `limit`) | 200, cursor-paginated |

## Data Model Notes
- `tickets`: `id` (UUID), `ticket_number` (unique), `subject`, `requester_id`, `assignee_id`, `status`, `created_at`, `updated_at`, `first_response_at`, `resolved_at`, `resolution_note`, `closed_at`, `closed_by`
- `attachments.ticket_id` is NULL until bound; binding is permanent
- Valkey `idempotency:{key}` → `(request_hash, response)`, 24-hour TTL
- `ticket_audit_log` `event=ticket_created`

## Acceptance Criteria

### Happy path
**ST-AC1 — Creating a ticket**
```gherkin
Given an authenticated, active customer
When POST /v1/support/tickets is called with {subject, body, category} and an Idempotency-Key header
Then respond 201 with the ticket, including a human-readable ticket_number
And status is "open" and requester_id is the caller
And no SLA target field is written — only the raw timestamps other stories stamp
And a confirmation email containing the ticket number is queued to the requester
And a ticket_audit_log entry is written (event=ticket_created)
```

**ST-AC2 — Listing my own tickets**
```gherkin
Given an authenticated customer with existing tickets
When GET /v1/support/tickets is called
Then respond 200 with only that customer's tickets, newest first
And a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views
```

### Validation, idempotency and access
**ST-AC3 — Invalid input**
```gherkin
Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category
When POST /v1/support/tickets is called
Then respond 422 with type ".../errors/validation-failed"
And the errors array names each offending field
And no ticket is created
```

**ST-AC4 — Duplicate submission**
```gherkin
Given a request that is retried with the same Idempotency-Key within 24 hours
When POST /v1/support/tickets is called again
Then respond 201 with the ORIGINAL ticket, and no second ticket exists
Given the same key is reused with a different body
Then respond 422 with type ".../errors/idempotency-key-reuse"
```

**ST-AC5 — Not authenticated or not eligible**
```gherkin
Given a request with no valid access token
Then respond 401
Given an authenticated user whose account is deactivated
Then respond 403 with type ".../errors/account-deactivated"
```

**ST-AC6 — Ticket flooding**
```gherkin
Given a customer who has created 5 tickets in the last hour
When POST /v1/support/tickets is called again
Then respond 429 with a Retry-After header
And the existing open tickets are unaffected
```

**ST-AC7 — Attachment ownership (IDOR)**
```gherkin
Given a request containing an attachment_id that was uploaded by a different user,
    or is already bound to another ticket, or does not exist
When POST /v1/support/tickets (or a reply, US-4.2) is called
Then respond 422 with type ".../errors/attachment-not-owned"
And no ticket or reply is created, and the response does not reveal which of the three cases applied
Given an attachment_id uploaded by the caller and not yet bound
Then it is bound to this ticket and becomes immutable — an attachment belongs to exactly one ticket forever
And unbound attachments older than 24 hours are purged by a scheduled job
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/attachment-not-owned",
  "title": "Attachment Not Available",
  "status": 422,
  "detail": "One or more attachments could not be attached to this ticket.",
  "instance": "/v1/support/tickets"
}
```
Error `type` slugs introduced by this story: `idempotency-key-reuse`, `attachment-not-owned`.

## Non-Functional / Security Requirements
- Ticket bodies are rendered as plain text or sanitised Markdown. **Never** render user-supplied HTML — an agent's console is a high-value XSS target.
- Accepting an `attachment_id` without checking `uploaded_by == caller` **and** `ticket_id IS NULL` is a textbook IDOR: an attacker could attach, and then read back, another customer's file by guessing an id.
- Attachment ids MUST be UUIDv4, never sequential, and download is authorised against the *ticket's* access rules (US-4.2 TR-AC4), not against possession of the id.
- **Performance:** p95 ≤ 400 ms; the confirmation email is queued, never sent inline.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| ST-AC1–2 | Integration test suite | `[gate]` |
| ST-AC3 | Schema test on the Pydantic request model | `[gate]` |
| ST-AC4 | Integration test replaying the same key, and replaying it with a changed body | `[gate]` |
| ST-AC5–6 | Integration test with a fixed Valkey clock | `[gate]` |
| ST-AC7 | Integration test per case: other user's attachment, already-bound, unknown | `[gate]` |
| No HTML rendering | Snapshot test on the render pipeline | `[gate]` |

## Open Questions
1. The attachment-upload story must be scheduled ahead of this one; until it lands, `attachment_ids` should be rejected rather than silently ignored. Needs an owner.