---
artifact_type: specification
story: US-4.2
version: 6
status: DRAFT
created_at: "2026-09-04T17:00:00Z"
updated_at: "2026-09-05T09:30:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/evidence/US-4.2-clarification-report.md
    version: 3
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: null
---

# Specification: Ticket Replies

**Source:** docs/stories/US-4.2-ticket-replies.md
**Story ID:** US-4.2
**Generated:** 2026-09-04
**Status:** Draft

> Note: this file previously held a pre-existing draft spec dated 2026-08-22
> that predated the current codebase (US-4.1 not yet shipped) and carried no
> harness front matter. This version is produced against the current
> codebase via CLARIFICATION (`docs/evidence/US-4.2-clarification-report.md`)
> and `docs/decisions/US-4.2-open-decisions.md`, and replaces it as the
> canonical `specification` artifact.
>
> **Revision (v2):** `version: 1` of this spec reached `HUMAN_SPEC_APPROVAL`
> and was rejected on 2026-09-04T18:15:00Z (`docs/workflow/history.jsonl`)
> because Open Decisions OD-1 through OD-7 were left as Open Questions rather
> than resolved. The human decision-maker supplied explicit resolutions for
> all seven in that rejection. This revision incorporates them as settled
> requirements; see [Decisions Resolved by Human](#decisions-resolved-by-human-2026-09-04)
> below for the resolution text and where each lands in the spec.
>
> **Revision (v3):** `version: 2` passed `HUMAN_SPEC_APPROVAL` and both
> designs, but `IMPACT_ANALYSIS` (`docs/impact-analysis/US-4.2-impact-analysis.md`,
> 2026-09-04T22:00:00Z) returned `changes_required_specification`: FR-6's
> sentence "a customer reply reopens it (US-4.3 TC-AC4)" is a self-contradiction
> that carries an error forward from the *source story itself*
> (`docs/stories/US-4.2-ticket-replies.md`, Assumptions & Defaults #5) rather
> than from anything OD-1–OD-7 addressed. Concretely: (a) no `"reopened"` (or
> equivalent) `Ticket.status` value exists anywhere in this codebase, (b) it
> cites `docs/specifications/US-4.3-spec.md`, which does not exist, and (c)
> this very spec's own Out of Scope section excludes "Resolution, closure and
> reopening transitions (US-4.3)" outright. The human's OD-5 resolution
> settled only the **agent**-reply-on-a-resolved-ticket case (the story's
> Open Question #1); it never addressed the **customer**-reply-on-a-resolved-
> ticket case that Assumptions & Defaults #5 and TR-AC6's closing clause
> describe. Per this skill's own rule ("don't guess — write it up as an Open
> Question"), FR-6 and FR-2 below no longer assert that transition; it is
> withdrawn to a new Open Question (OQ-1) for a human/product decision. This
> is not a re-litigation of OD-1–OD-7, which remain settled as recorded.
>
> **Revision (v4):** `version: 3` was reviewed by `SPEC_REVIEW` v3
> (`docs/reviews/specifications/US-4.2-spec-review.md`), which found that
> withdrawing the resolved-ticket customer-reply clause to a free-standing
> Open Question (OQ-1, below) still left TR-AC6 Partially Covered and in
> direct Contradiction with the source story — correctly forcing
> `CHANGES_REQUIRED` rather than `PASS`, since the review's own rule treats
> an irreducible gap as blocking even when it is well-documented. Because the
> root defect traces to the *story* itself (Assumptions & Defaults #5 asserts
> a status transition this codebase has no value for, citing a US-4.3 spec
> that does not exist, while this same story's own Out of Scope section
> excludes reopening transitions outright) rather than to anything
> `story-spec-writer` could infer, `story-orchestrator` routed this back to
> `CLARIFICATION` (loop_back key `changes_required_clarification`) instead of
> straight back to this stage. `CLARIFICATION` re-ran and formalized the gap
> as **OD-8** (`docs/decisions/US-4.2-open-decisions.md` v2,
> `docs/evidence/US-4.2-clarification-report.md` v2). OD-8 is not yet
> resolved by a human decision, so per this skill's own rule ("don't
> guess — write it up as an Open Question") this revision makes no new
> assertion about the resolved-ticket customer-reply case: FR-2 and FR-6
> below are otherwise unchanged from v3, and the question itself is now
> tracked as OD-8 rather than as the free-standing OQ-1 (see
> [Open Questions](#open-questions)). OD-1–OD-7 remain settled and
> unchanged.
>
> **Revision (v5):** `version: 4` was reviewed by `SPEC_REVIEW` v4
> (`docs/reviews/specifications/US-4.2-spec-review.md`), which returned
> `CHANGES_REQUIRED` (loop_back key `changes_required`) on two points, both
> addressed in this revision:
>
> 1. **TR-AC6 remained Partially Covered / in Contradiction.** v4 left the
>    resolved-ticket customer-reply case as "not defined by this FR" even
>    though `CLARIFICATION` had already formalized it as **OD-8**
>    (`docs/decisions/US-4.2-open-decisions.md` v2) with a fully-specified,
>    testable recommended default. Per this codebase's own OD-1–OD-7
>    precedent — a formalized-but-unresolved Open Decision is incorporated
>    into its FR as a working default pending human confirmation, not left
>    undefined — FR-2 and FR-6 below now state OD-8's recommended default
>    explicitly: a customer reply on a `"resolved"` ticket is accepted
>    normally (`201`), and the ticket's `status` stays `"resolved"`
>    (`resolved_at` is not cleared). This default is **not yet a human
>    decision** — it is OD-8's own recommendation, carried into the spec the
>    same way OD-1–OD-7's recommendations were before `HUMAN_SPEC_APPROVAL`
>    confirmed (and in some cases could have overridden) them — and remains
>    subject to human confirmation or override at that gate.
> 2. **FR-1 (Low, repeated since v3).** OD-1's resolution was recorded as
>    incorporated but the attachment-not-owned error behavior was never
>    actually stated in FR-1's own text. FR-1 below now states it directly,
>    citing BR-016 and US-4.1 FR-7's shipped error shape
>    (`422 .../errors/attachment-not-owned`).
>
> **Revision (v6):** `HUMAN_SPEC_APPROVAL` approved v5 with no comment
> (`docs/workflow/history.jsonl`, 2026-09-05T03:15:00Z). `DESIGN_REVIEW` v2
> (`docs/reviews/designs/US-4.2-design-review.md`) found that both
> `api_design` v2 and `db_design` v2 had treated that silent approval as
> confirming OD-8's recommended default — a customer reply on a `"resolved"`
> ticket stays `"resolved"` — without an actual per-item resolution matching
> how OD-1–OD-7 were confirmed, and returned `BLOCKED`
> (`docs/workflow/history.jsonl`, 2026-09-05T05:00:00Z). The user then
> supplied an explicit resolution directly in-session
> (2026-09-05T09:00:00Z), routed through `CLARIFICATION` to formalize it
> (`docs/decisions/US-4.2-open-decisions.md` v3,
> `docs/evidence/US-4.2-clarification-report.md` v3;
> `docs/workflow/history.jsonl` `HUMAN_REDIRECTED` event,
> 2026-09-05T09:00:00Z). **The actual resolution is not v5's default**: a
> customer reply on a `"resolved"` ticket is accepted (`201`) and the
> ticket's status transitions to `"waiting_on_support"` — reopening it,
> using the same target status FR-2's ordinary `"waiting_on_customer"` →
> `"waiting_on_support"` case already produces, not a new status value. FR-2
> and FR-6 below are revised accordingly; the Out of Scope section is
> narrowed to reflect that this story now performs one reopening transition
> itself; and a note is added stating that BR-017's 7-day auto-close job and
> shared boundary constant remain unbuilt — this story implements only the
> reply-side half of that rule. OD-1–OD-7 are unaffected.

## Summary

This spec covers threaded ticket replies: agents and customers posting public
replies (with ticket status side effects and `first_response_at` stamping),
agents posting internal notes that are isolated from customers at both the
application and database layers, cross-customer access rejection, rejection
of internal-note requests from customers, rejection of replies on closed
tickets, and reply body validation.

## Background

As a customer or support agent, I want to exchange messages on a ticket in
one threaded conversation, so that the full history stays in one place and
nobody has to reconstruct context from scattered emails.

## Functional Requirements

### FR-1: Agent Public Reply Creates Response and Advances Status

Given a support agent with `tickets:write` and an open ticket, when
`POST /v1/support/tickets/{id}/replies` is called with
`{body, visibility: "public"}`, the system responds `201` with the created
reply, stamps
`first_response_at` (a plain timestamp for later reporting — no SLA target
is evaluated) if this is the first public agent reply on the ticket, and
notifies the requester by email. If the ticket's status is `"resolved"`,
it remains `"resolved"` (per FR-6 / Resolution OD-5); otherwise it becomes
`"waiting_on_customer"`.

The request body may also include an optional `attachment_ids` array
(source API Contract). Each referenced attachment is bound to this specific
reply, not just the ticket, by setting a new nullable `ticket_reply_id`
column on the existing `attachments` table (Resolution: OD-1). If any
referenced `attachment_id` was uploaded by a different user, is already
bound to another ticket or reply, or does not exist, the system responds
`422` with type `.../errors/attachment-not-owned`, no reply is created, and
the response does not reveal which of the three cases applied (BR-016; same
error shape as `US-4.1-spec.md` FR-7).

**Derived from:** TR-AC1; attachment binding per Resolution OD-1;
attachment-not-owned error per BR-016 / OD-1

### FR-2: Customer Reply Creates Response and Reverts Status

Given the ticket's requester and a ticket in `"waiting_on_customer"`, when
`POST /v1/support/tickets/{id}/replies` is called with `{body}`, the system
responds `201`, sets the ticket's status to `"waiting_on_support"`, and
notifies the assigned agent (or the queue, if the ticket is unassigned).

Because the current schema has no agent-assignment concept (US-4.1 left
assignment out of scope), every ticket is treated as unassigned for this
story: the notification is always sent by email to a single configured
support-queue address (e.g. `support-queue@portal.internal`), the same
delivery mechanism FR-1 uses for the requester notification. This story does
not add an assignment column (Resolution: OD-2).

The request body accepts the same optional `attachment_ids` array as FR-1
(source API Contract defines one request shape for both actors); attachment
binding and the `attachment-not-owned` error described in FR-1 apply
identically here.

This FR's `201`/notification/status-transition behavior above applies when
the ticket is already in `"waiting_on_customer"`. When the ticket's status
is `"resolved"` instead, the system still responds `201` with the created
reply and still notifies the queue, and the status **transitions to
`"waiting_on_support"`** — the same target status this FR's ordinary case
already produces — reopening the ticket. This is Resolution OD-8 (see
[Decision Resolved by Human (2026-09-05)](#decision-resolved-by-human-2026-09-05)):
a human decision, not a default. This story implements only this
reply-side transition; the 7-day auto-close job and shared boundary
constant BR-017 also describes are not built here (see
[Out of Scope](#out-of-scope)).

**Derived from:** TR-AC2; notification channel and unassigned-only handling
per Resolution OD-2; resolved-ticket case per Resolution OD-8; attachment
handling per FR-1 / BR-016 / OD-1

### FR-3: Internal Notes Are Isolated From Customers

Given an agent has added a reply with visibility `"internal"`, when the
ticket's requester calls `GET /v1/support/tickets/{id}`, the internal reply
is absent from the response entirely and absent from every notification
email. When an agent calls the same endpoint, the internal reply is returned
and marked as internal. This exclusion is backed by a PostgreSQL Row-Level
Security policy on `ticket_replies` that hides `visibility='internal'` rows
from any connection whose session context carries the customer role, so the
exclusion holds even if the application layer forgets to filter.

**Derived from:** TR-AC3

### FR-4: Cross-Customer and Unauthorized Access Returns 404; Unauthenticated Returns 401

Given customer A is authenticated and a ticket belongs to customer B, when
customer A calls `POST /v1/support/tickets/{id}/replies` or
`GET /v1/support/tickets/{id}` for that ticket, the system responds `404`
with type `.../errors/not-found`, because a `403` would confirm the ticket
id exists.

The same `404` (not `403`) response applies to `GET /v1/support/tickets/{id}`
when the caller is an authenticated agent who lacks the required
`tickets:read` scope, for the same enumeration-prevention reason. A caller
with no valid access token at all instead receives `401` (Resolution: OD-7).

**Derived from:** TR-AC4; GET-endpoint auth-failure responses per
Resolution OD-7

### FR-5: Customer Cannot Create Internal Notes

Given the ticket's requester, when `POST /v1/support/tickets/{id}/replies`
is called with `{visibility: "internal"}`, the system responds `403` with
type `.../errors/insufficient-permission` and no reply is created. When a
customer omits the `visibility` field, it defaults to `"public"`. This
restriction is also enforced at the database by a
`CHECK (visibility = 'public' OR author_kind = 'agent')` constraint on
`ticket_replies`, so it cannot be bypassed.

When an agent omits `visibility`, it also defaults to `"public"` — the same
default as the customer-omission case, since an agent who wants an internal
note must say so explicitly (Resolution: OD-6).

**Derived from:** TR-AC5; agent-omission default per Resolution OD-6

### FR-6: Reply Handling on Closed and Resolved Tickets

Given a ticket whose status is `"closed"`, when any actor calls
`POST /v1/support/tickets/{id}/replies`, the system responds `409` with a
`problem+json` body of type `.../errors/ticket-closed` (per
[Error Envelope Schema](#error-envelope-schema)), whose `detail` points the
caller to creating a new ticket. An agent's public reply on a `"resolved"`
ticket is permitted and does not change its status: the ticket's status
remains `"resolved"` (Resolution: OD-5).

A **customer** reply on a `"resolved"` ticket is also accepted (`201`) — it
is not rejected the way a `"closed"`-ticket reply is — but unlike the agent
case, it **reopens the ticket**: status transitions to
`"waiting_on_support"` (the same target FR-2's ordinary case already
produces). This is Resolution OD-8 (see
[Decision Resolved by Human (2026-09-05)](#decision-resolved-by-human-2026-09-05)): the
source's Assumptions & Defaults #5 asserted such a reply "reopens" the
ticket (citing `US-4.3 TC-AC4`), which could not be formalized as stated —
no `Ticket.status` value this codebase has was named, and the cited
`US-4.3` specification does not exist — but the human resolution confirms
the underlying intent (reopening) while fixing the mechanism: an existing
status value (`"waiting_on_support"`), not a new one, and no dependency on
US-4.3's not-yet-built auto-close job or shared boundary constant (BR-017;
see [Out of Scope](#out-of-scope)). This FR therefore covers the
`"closed"`-ticket case (TR-AC6's first clause), the `"resolved"`-ticket
agent case (Resolution OD-5, status unchanged), and the `"resolved"`-ticket
customer case (Resolution OD-8, status reopens to `"waiting_on_support"`).

**Derived from:** TR-AC6 (closed-ticket clause); error envelope per source
Error Envelope section; resolved-ticket agent-reply behavior per Resolution
OD-5; resolved-ticket customer-reply behavior per Resolution OD-8

### FR-7: Reply Body Validation

Given an empty body, or a body exceeding 5000 characters, when
`POST /v1/support/tickets/{id}/replies` is called, the system responds `422`
with type `.../errors/validation-failed`.

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

Error `type` slugs introduced by this story: `ticket-closed`. FR-4's
`not-found`, FR-5's `insufficient-permission`, and FR-7's
`validation-failed` slugs follow the same envelope shape but are not
introduced by this story.

**Derived from:** source Error Envelope section.

### GET Thread Pagination

`GET /v1/support/tickets/{id}` paginates its reply list using the same
cursor-pagination interface already established for
`GET /v1/support/tickets` (US-4.1): `cursor` and `limit` query parameters,
returning a response envelope with an `items` array and a `next_cursor`
field.

**Derived from:** Resolution OD-3.

## Non-Functional Requirements

- Visibility filtering for internal replies lives in one shared repository
  query, never per-serializer, and is backed at the database by PostgreSQL
  Row-Level Security.
- RLS policies read `app.actor_kind` and `app.actor_id`, set with
  `SET LOCAL` inside the request's transaction, via a shared dependency so
  no session can start without them.
- The RLS policy needs its own test that queries through a customer-context
  connection with the application filter deliberately disabled, so the
  database-level layer is verified independently of the application-level
  filter.
- Reply bodies are stored and rendered strictly as plain text, following the
  same precedent US-4.1 established for ticket bodies — no markdown/HTML
  rendering pipeline exists. "Sanitised on render as well as on write" and
  "strip tracking pixels and remote images from agent-facing views" are
  satisfied by construction: since no HTML is ever stored, none is ever
  rendered, so there is no tracking pixel or remote image to strip
  (Resolution: OD-4).
- Notification emails must not quote internal notes.
- Thread fetch performance: p95 ≤ 300 ms for 100 replies, paginated at 50
  (pagination interface specified in [GET Thread Pagination](#get-thread-pagination)).
- Replies are rate-limited to 30 per user per hour (Assumptions & Defaults
  #7), to bound abuse of the notification path. This story's rate-limit
  precedent is the one US-4.1 already shipped for ticket creation: a `429`
  response carrying a `Retry-After` header (`docs/specifications/US-4.1-spec.md`
  FR-6 / `ST-AC6`).

**Derived from:** Non-Functional / Security Requirements section of the
source; Assumptions & Defaults #7 (Rate limit); rate-limit response shape
per `docs/decisions/US-4.2-open-decisions.md` "Resolved by precedent";
plain-text rendering per Resolution OD-4.

## Out of Scope

- Resolution and closure transitions (US-4.3) — this story neither resolves
  nor closes a ticket.
- The auto-close job and its shared 7-day boundary constant (BR-017), and
  any reopening transition other than the one FR-2/FR-6 define: this story
  performs exactly one reopening transition (a customer reply reopening a
  `"resolved"` ticket to `"waiting_on_support"`, Resolution OD-8) as the
  reply-side half of BR-017; the auto-close job and boundary constant that
  would complete that rule are US-4.3's to build. No other reopening path
  is introduced.
- Inbound reply-by-email ingestion — would need its own spoofing controls.
- Reply editing and deletion (replies are append-only once created).

**Derived from:** Out of Scope section of the source; Assumptions &
Defaults #6 (Mutability); reopening narrowed per Resolution OD-8
(`docs/decisions/US-4.2-open-decisions.md` v3).

## Open Questions

None. All eight Open Decisions raised by `us-clarifier`
(`docs/decisions/US-4.2-open-decisions.md`, OD-1–OD-8) have been resolved by
explicit human decision — OD-1–OD-7 on 2026-09-04 (see
[Decisions Resolved by Human (2026-09-04)](#decisions-resolved-by-human-2026-09-04)
below) and OD-8 on 2026-09-05 (see
[Decision Resolved by Human (2026-09-05)](#decision-resolved-by-human-2026-09-05)
below). OD-8 was first raised by v3 as a free-standing Open Question (OQ-1),
formalized by `CLARIFICATION` v2 as OD-8, carried through v4/v5 as a working
default pending confirmation, found by `DESIGN_REVIEW` v2 to not actually be
confirmed by the record, and finally resolved directly by the human in
conversation.

## Decisions Resolved by Human (2026-09-04)

`version: 1` of this spec carried OD-1–OD-7 as unresolved Open Questions.
`HUMAN_SPEC_APPROVAL` rejected that version on 2026-09-04T18:15:00Z
(`docs/workflow/history.jsonl`, `decided_by: sbruhov@gmail.com`) and supplied
the following resolutions, each now incorporated into the FR/NFR named:

| OD | Resolution | Incorporated in |
|----|------------|------------------|
| OD-1 | `attachments` gets a new nullable `ticket_reply_id` (UUID) column for reply-level persistence. | FR-1 |
| OD-2 | No assignment concept exists; queue notifications go by email to a shared support address (e.g. `support-queue@portal.internal`). | FR-2 |
| OD-3 | Reuse US-4.1's cursor pagination: `cursor`/`limit` query params, `items`/`next_cursor` response envelope. | GET Thread Pagination |
| OD-4 | Follow US-4.1 precedent: body stored/rendered strictly as plain text; tracking pixels/HTML do not apply. | Non-Functional Requirements |
| OD-5 | An agent can publicly reply on a resolved ticket; status remains `"resolved"` (no reopening). | FR-6 |
| OD-6 | Agent-omitted `visibility` also defaults to `"public"`. | FR-5 |
| OD-7 | Unauthenticated GET callers get `401`; callers without ticket access (wrong customer or agent lacking scope) get `404`. | FR-4 |

## Decision Resolved by Human (2026-09-05)

`version: 5` of this spec carried OD-8 as a working default (candidate (a):
status stays `"resolved"`), explicitly flagged as pending confirmation, not
yet a human decision. `DESIGN_REVIEW` v2
(`docs/reviews/designs/US-4.2-design-review.md`) found that `HUMAN_SPEC_APPROVAL`'s
silent, comment-free approval of v5 (2026-09-05T03:15:00Z) did not actually
constitute that confirmation, and returned `BLOCKED`. The user then supplied
an explicit resolution directly in conversation on 2026-09-05T09:00:00Z,
formalized via `CLARIFICATION` v3 (`docs/decisions/US-4.2-open-decisions.md`
v3):

| OD | Resolution | Incorporated in |
|----|------------|------------------|
| OD-8 | A customer reply on a `"resolved"` ticket is accepted (`201`) and the ticket's status transitions to `"waiting_on_support"` — candidate (b), not the v5 default (a). No new `Ticket.status` value; the auto-close job / shared boundary constant half of BR-017 remains unbuilt. | FR-2, FR-6, Out of Scope |

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| TR-AC1 | "Given a support agent with tickets:write and an open ticket When POST /v1/support/tickets/{id}/replies is called with {body, visibility: \"public\"} Then respond 201 with the created reply And the ticket's status becomes \"waiting_on_customer\" And first_response_at is stamped if this is the first public agent reply (a plain timestamp for later reporting — no SLA target is evaluated) And the requester is notified by email" | FR-1 |
| TR-AC2 | "Given the ticket's requester and a ticket in \"waiting_on_customer\" When POST /v1/support/tickets/{id}/replies is called with {body} Then respond 201 And the ticket's status becomes \"waiting_on_support\" And the assigned agent (or the queue, if unassigned) is notified" | FR-2 |
| TR-AC3 | "Given an agent has added a reply with visibility \"internal\" When the requester calls GET /v1/support/tickets/{id} Then the internal reply is absent from the response entirely And it is absent from every notification email And when an agent calls the same endpoint, the internal reply IS returned, marked as internal And the exclusion holds even if the application layer forgets to filter, because a PostgreSQL Row-Level Security policy on ticket_replies hides visibility='internal' rows from any connection whose session context carries the customer role" | FR-3 |
| TR-AC4 | "Given customer A authenticated, and a ticket belonging to customer B When POST /v1/support/tickets/{id}/replies or GET /v1/support/tickets/{id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm the ticket id exists — unlike the self-scoped profile case in US-1.3 UP-AC7" | FR-4 |
| TR-AC5 | "Given the ticket's requester When POST /v1/support/tickets/{id}/replies is called with {visibility: \"internal\"} Then respond 403 with type \".../errors/insufficient-permission\" And no reply is created And visibility defaults to \"public\" when the field is omitted by a customer" | FR-5 |
| TR-AC6 | "Given a ticket whose status is \"closed\" When any actor calls POST /v1/support/tickets/{id}/replies Then respond 409 with type \".../errors/ticket-closed\" And the response points to creating a new ticket And a \"resolved\" ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)" | FR-6 (closed-ticket clause; resolved-ticket agent clause per Resolution OD-5, status unchanged; resolved-ticket customer clause per Resolution OD-8, status reopens to `"waiting_on_support"` — confirms the source's "reopens" intent via an existing status value rather than the unformalizable `US-4.3 TC-AC4` citation) |
| TR-AC7 | "Given an empty body or one exceeding 5000 characters When POST /v1/support/tickets/{id}/replies is called Then respond 422 with type \".../errors/validation-failed\"" | FR-7 |
