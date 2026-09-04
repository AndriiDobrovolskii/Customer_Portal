---
artifact_type: specification
story: US-4.1
version: 1
status: DRAFT
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-03T00:00:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/evidence/US-4.1-clarification-report.md
    version: 1
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
supersedes: null
---

# Specification: Support Tickets (Create)

**Source:** docs/stories/US-4.1-create-ticket.md
**Story ID:** US-4.1
**Generated:** 2026-09-03
**Status:** Draft

> Replaces the pre-migration draft that previously lived at this path (dated
> 2026-08-22). That draft predated the current codebase and is retained only
> as historical context per `docs/catalog/stories.yaml`; this version is
> written fresh against `docs/evidence/US-4.1-clarification-report.md` and
> `docs/decisions/US-4.1-open-decisions.md`.

## Summary

This spec covers self-service creation of support tickets by authenticated
customers: idempotent ticket creation with a human-readable, non-guessable
ticket number, listing the caller's own tickets, input validation, rate
limiting, authentication/eligibility gating, and attachment binding with its
ownership (IDOR) check. Attachment *upload* itself is out of scope, per the
source story.

## Background

As a customer, I want to raise a support ticket from inside the portal, so
that my problem is tracked with a reference number instead of disappearing
into an inbox.

## Functional Requirements

### FR-1: Successful Ticket Creation

Given an authenticated, active customer, when `POST /v1/support/tickets` is
called with `{subject, body, category}` and an `Idempotency-Key` header, the
system responds `201` with the created ticket. The ticket includes a
human-readable `ticket_number` (e.g. `CP-2026-0000431`) that is sequential in
presentation but MUST NOT be guessable or enumerable as an API identifier —
this non-guessability is a deliberate security property of the identifier,
not just an example format. `status` is set to `"open"` and `requester_id` to
the caller. No SLA target field is written — only the raw timestamps other
stories stamp. A confirmation email containing the ticket number is queued to
the requester (never sent inline). A `ticket_audit_log` entry is written
(`event=ticket_created`).

**Derived from:** ST-AC1; `ticket_number` non-guessability per source
Assumptions & Defaults table (#2)

### FR-2: Listing Own Tickets

Given an authenticated customer with existing tickets, when
`GET /v1/support/tickets` is called, the system responds `200`,
cursor-paginated, with only that customer's tickets, newest first.

The source additionally states that a support agent calling the same
endpoint "sees the queue their permissions allow, not other customers'
private views" — but the same story's Out of Scope section excludes "Agent
queue views, assignment and routing." This is a direct conflict the source
does not resolve; see Open Question 1 (OD-4). The accepted `status` values,
the maximum `limit`, and the response to a malformed or expired `cursor` are
likewise not stated by any Acceptance Criterion; see Open Question 1.

**Derived from:** ST-AC2

### FR-3: Invalid Input Rejected

Given a request with an empty subject, a subject over 150 characters, a body
over 5000 characters, or an unknown `category`, when
`POST /v1/support/tickets` is called, the system responds `422` with type
`.../errors/validation-failed`, the errors array names each offending field,
and no ticket is created.

The set of valid `category` values is not defined anywhere in the source or
in `business-glossary.md`/`business-rules.md`; see Open Question 2 (OD-3).

**Derived from:** ST-AC3

### FR-4: Duplicate Submission (Idempotency)

Given a request that is retried with the same `Idempotency-Key` within 24
hours, when `POST /v1/support/tickets` is called again, the system responds
`201` with the original ticket, and no second ticket exists. Given the same
key is reused with a different body, the system responds `422` with type
`.../errors/idempotency-key-reuse`.

The source's Data Model Notes describe the key as `idempotency:{key}` with no
stated scoping, and do not state the response to a missing
`Idempotency-Key` header or whether "different body" compares the full
request payload or only `body`. See Open Question 3 (OD-2).

**Derived from:** ST-AC4

### FR-5: Not Authenticated or Not Eligible

Given a request with no valid access token, the system responds `401`. Given
an authenticated user whose account is deactivated, the system responds `403`
with type `.../errors/account-deactivated`.

**Derived from:** ST-AC5

### FR-6: Ticket Flooding (Rate Limit)

Given a customer who has created 5 tickets in the last hour, when
`POST /v1/support/tickets` is called again, the system responds `429` with a
`Retry-After` header, and the customer's existing open tickets are
unaffected.

**Derived from:** ST-AC6

### FR-7: Attachment Ownership (IDOR Prevention)

Given a request containing an `attachment_id` that was uploaded by a
different user, is already bound to another ticket, or does not exist, when
`POST /v1/support/tickets` (or a reply, US-4.2) is called, the system
responds `422` with type `.../errors/attachment-not-owned`, no ticket or
reply is created, and the response does not reveal which of the three cases
applied. Given an `attachment_id` uploaded by the caller and not yet bound,
it is bound to this ticket and becomes immutable — an attachment belongs to
exactly one ticket forever. Unbound attachments older than 24 hours are
purged by a scheduled job.

No `attachments` table, upload endpoint, or upload story exists in the
current codebase, and the source's own Assumptions table and Open Questions
section give conflicting interim defaults for what this story should do in
the meantime (build minimal attachment tracking now vs. reject any non-empty
`attachment_ids`). See Open Question 4 (OD-1) — this determines whether this
FR is buildable as stated or must be replaced with a rejection behavior for
this story.

**Derived from:** ST-AC7

## Non-Functional Requirements

- Ticket bodies are rendered as plain text or sanitised Markdown. The system
  MUST NEVER render user-supplied HTML — an agent's console is a high-value
  XSS target. Which of the two (plain text vs. sanitised Markdown) is not
  decided by the source; see Open Question 5 (OD-5).
- Accepting an `attachment_id` without checking `uploaded_by == caller` AND
  `ticket_id IS NULL` is a textbook IDOR: an attacker could attach, and then
  read back, another customer's file by guessing an id.
- Attachment ids MUST be UUIDv4, never sequential, and download is authorised
  against the *ticket's* access rules (US-4.2 TR-AC4), not against possession
  of the id.
- Performance: p95 ≤ 400 ms. The confirmation email is queued, never sent
  inline.

## Out of Scope

- Attachment **upload** (size caps, MIME allowlist, antivirus scanning,
  signed URLs) — separate story, blocking for Epic 4
- Replies (US-4.2) and status transitions (US-4.3)
- Agent queue views, assignment and routing
- SLA targets and CSAT

## Open Questions

1. **`GET /v1/support/tickets` agent-facing scope and query parameters
   (OD-4).** The source's In Scope list and ST-AC2 both describe
   permission-scoped agent visibility for this endpoint, while its Out of
   Scope section excludes agent queue views entirely — a direct conflict.
   Separately, `status`, `cursor`, and `limit` are named as query parameters
   with no stated accepted values, maximum `limit`, or malformed/expired
   cursor behavior. See `docs/decisions/US-4.1-open-decisions.md` OD-4 for
   the full analysis and a candidate resolution (customer-only scope for this
   story, agent callers receive `403` for now).

2. **`category` enumeration (OD-3).** ST-AC3 and the API Contract require
   rejecting an "unknown category," but no valid value list exists in the
   source, `business-glossary.md`, or `business-rules.md`. This needs a
   product/stakeholder-supplied list, not an inferred one. See
   `docs/decisions/US-4.1-open-decisions.md` OD-3.

3. **Idempotency-Key mechanics (OD-2).** Three sub-questions are unresolved:
   whether the Valkey key is scoped per-user or global; the response when the
   header is omitted entirely; and whether the "reused with a different body"
   comparison covers the full request payload or only `body`. See
   `docs/decisions/US-4.1-open-decisions.md` OD-2 for a candidate resolution.

4. **Attachment binding: build now or reject until the upload story ships
   (OD-1).** No `attachments` table or upload story exists yet in this
   codebase. The source's own Assumptions table and Open Questions section
   give conflicting interim defaults. This determines whether FR-7 is built
   as a real binding/ownership check in this story, or replaced with a
   rejection of any non-empty `attachment_ids`. See
   `docs/decisions/US-4.1-open-decisions.md` OD-1 for a candidate resolution.

5. **Body rendering: plain text vs. sanitised Markdown (OD-5).** The source
   states either as acceptable but does not choose one, and no prior story in
   this codebase renders user-supplied rich text. See
   `docs/decisions/US-4.1-open-decisions.md` OD-5 for a candidate resolution.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| ST-AC1 | "Given an authenticated, active customer / When POST /v1/support/tickets is called with {subject, body, category} and an Idempotency-Key header / Then respond 201 with the ticket, including a human-readable ticket_number / And status is \"open\" and requester_id is the caller / And no SLA target field is written — only the raw timestamps other stories stamp / And a confirmation email containing the ticket number is queued to the requester / And a ticket_audit_log entry is written (event=ticket_created)" | FR-1 |
| ST-AC2 | "Given an authenticated customer with existing tickets / When GET /v1/support/tickets is called / Then respond 200 with only that customer's tickets, newest first / And a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views" | FR-2, Open Question 1 |
| ST-AC3 | "Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category / When POST /v1/support/tickets is called / Then respond 422 with type \".../errors/validation-failed\" / And the errors array names each offending field / And no ticket is created" | FR-3, Open Question 2 |
| ST-AC4 | "Given a request that is retried with the same Idempotency-Key within 24 hours / When POST /v1/support/tickets is called again / Then respond 201 with the ORIGINAL ticket, and no second ticket exists / Given the same key is reused with a different body / Then respond 422 with type \".../errors/idempotency-key-reuse\"" | FR-4, Open Question 3 |
| ST-AC5 | "Given a request with no valid access token / Then respond 401 / Given an authenticated user whose account is deactivated / Then respond 403 with type \".../errors/account-deactivated\"" | FR-5 |
| ST-AC6 | "Given a customer who has created 5 tickets in the last hour / When POST /v1/support/tickets is called again / Then respond 429 with a Retry-After header / And the existing open tickets are unaffected" | FR-6 |
| ST-AC7 | "Given a request containing an attachment_id that was uploaded by a different user, or is already bound to another ticket, or does not exist / When POST /v1/support/tickets (or a reply, US-4.2) is called / Then respond 422 with type \".../errors/attachment-not-owned\" / And no ticket or reply is created, and the response does not reveal which of the three cases applied / Given an attachment_id uploaded by the caller and not yet bound / Then it is bound to this ticket and becomes immutable — an attachment belongs to exactly one ticket forever / And unbound attachments older than 24 hours are purged by a scheduled job" | FR-7, Open Question 4 |
