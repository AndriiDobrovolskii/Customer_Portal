---
artifact_type: specification
story: US-5.3
version: 1
status: APPROVED
created_at: "2026-09-08T16:50:30Z"
updated_at: "2026-09-08T16:50:30Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/evidence/US-5.3-clarification-report.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Specification: Support Tickets (Frontend)

**Source:** docs/stories/US-5.3-support-tickets-ui.md
**Story ID:** US-5.3
**Generated:** 2026-09-08
**Status:** Draft

## Summary

This spec covers the frontend support-ticket surface for the Customer Portal: a customer-facing ticket list with status filtering and cursor pagination, ticket creation with required `Idempotency-Key` handling, ticket detail and reply-thread viewing, posting a public reply, closing and reopening a ticket, status-driven action affordances, and the client-side validation, problem+json error rendering, 429/network/5xx handling, and 401 auth interaction common to all of these screens. It also covers one change to already-shipped US-5.1 code: the authenticated post-login redirect and home route move to `/tickets`, and `/tickets` is added to the app shell's navigation.

## Background

As a customer, the actor wants to raise a support ticket, follow its thread, reply to it, and close or reopen it from a real web UI, so that EPIC-4 (US-4.1 create, US-4.2 reply, US-4.3 resolve/close/reopen — all shipped on the backend) is usable end-to-end rather than only through raw API calls. This Story reuses US-5.1's frontend infrastructure (React + Vite + TS + TanStack Query + React Hook Form, the same API client and auth store) and, per the source, makes no backend/API/DB change of its own.

This Story is customer-side only: no agent queue, no internal-note composer, and no `resolve` action. The source's own stated reason for that exclusion needs a correction, carried forward from clarification: it originally cited `GET /support/tickets` rejecting `tickets:read`/`tickets:write` holders with a 403 (`reject_agent_queue_access`) as a technical blocker making an agent queue "unbuildable." That rejection was retired when US-4.4 (Agent Ticket Queue & Assignment) shipped an agent-branch response on the same route. The customer-only scope itself is still correct — `docs/catalog/stories.yaml` records a deliberate US-5.3 (customer)/US-5.5 (agent console) split — but this Story is customer-only by design, not because the backend still blocks anything else. See Out of Scope below.

## Functional Requirements

### FR-1: Ticket List

On `/tickets`, for an authenticated customer, the screen calls `GET /support/tickets` on load and renders each ticket's `ticket_number`, `subject`, `category`, `status`, and `updated_at`. `status` is a plain string, not an enum; an unrecognized value is rendered verbatim with neutral styling rather than causing a crash or being hidden. When the response's `next_cursor` is non-null, a "Load more" control appends the next page using that cursor. No total count is available anywhere in the response — there is no "X of Y" and no page numbers; `next_cursor === null` is the only end-of-list signal. When `items` is empty, an explicit empty state with a "New ticket" call to action is shown instead of a blank screen.

**Derived from:** TK-AC1, Client State Notes

### FR-2: Status Filter

From the ticket list, when the customer selects one of the five statuses (`open`, `waiting_on_support`, `waiting_on_customer`, `resolved`, `closed`), `GET /support/tickets` is re-called with that status and the pagination cursor is reset. Clearing the filter re-requests the unfiltered list.

**Derived from:** TK-AC2

### FR-3: Create Ticket

On the new-ticket form, when the customer submits a subject (1–150 characters), body (1–5000 characters), and category (≤50 characters), the client calls `POST /support/tickets` with an `Idempotency-Key` header and `attachment_ids: []`. On a `201` response, the customer lands on that ticket's detail screen.

**Derived from:** TK-AC3

### FR-4: Idempotency Key Stability Across Retries

For a create submission that failed with a network error or a 5xx response, retrying the same composed ticket sends the identical `Idempotency-Key` value again. Starting a new ticket composition generates a different key. The key lives in transient form state for the lifetime of one composition; it is not persisted across a full page reload.

**Derived from:** TK-AC4, Client State Notes

### FR-5: Ticket Detail and Reply Thread

When an authenticated customer opens a ticket they own, `GET /support/tickets/{id}` renders the ticket header (`ticket_number`, `status`, `category`, `created_at`, and `first_response_at` when present) and the reply thread. Each reply shows its `author_kind` (customer or agent), `body`, and `created_at`. When `replies.next_cursor` is non-null, a "Load older replies" control fetches the next page with that cursor. This thread cursor is independent of the ticket list's own cursor (FR-1) — they are two separate paginators.

**Derived from:** TK-AC5, Client State Notes

### FR-6: Post a Reply

On a ticket that is not `closed`, when the customer submits a reply body (1–5000 characters), the client calls `POST /support/tickets/{id}/replies` without a `visibility` field and with `attachment_ids: []`. The composer offers no visibility control at all — a reply row with `visibility: "internal"` may appear in the `ReplyRead` payload shape, but a customer caller never receives one, and sending `internal` as a customer is a 403 by design. On a `201` response, the new reply appears in the thread and the composer clears. The ticket detail is invalidated/refetched after posting, because a customer reply on a `waiting_on_customer` ticket transitions it to `waiting_on_support` server-side and `ReplyRead` carries no status field to report that change.

**Derived from:** TK-AC6, Client State Notes

### FR-7: Close a Ticket

On a ticket in `open`, `waiting_on_support`, `waiting_on_customer`, or `resolved`, when the customer chooses "Close ticket," the client calls `POST /support/tickets/{id}/close` and the screen reflects status `closed`. The reply composer becomes unavailable once a ticket is closed.

**Derived from:** TK-AC7

### FR-8: Reopen a Ticket

On a ticket in status `resolved`, when the customer chooses "Reopen," the client calls `POST /support/tickets/{id}/reopen` and the screen reflects status `waiting_on_support`. A `409` response (returned when the reopen falls outside the 7-day reopen window) renders the returned problem+json `detail` rather than a generic failure.

**Derived from:** TK-AC8

### FR-9: Status-Driven Affordances

On any ticket detail screen, only the actions valid for the ticket's current status are offered:

| status | offered |
|---|---|
| open | reply, close |
| waiting_on_support | reply, close |
| waiting_on_customer | reply, close |
| resolved | reply, close, reopen |
| closed | (none) |

"Resolve" is never offered to a customer, under any status.

**Derived from:** TK-AC9

### FR-10: Client-Side Validation

On the create-ticket or reply form, when a required field is empty or exceeds its maximum length (subject 150, body 5000, category 50), submission is blocked with a field-level error and no API call is made.

**Derived from:** TK-AC10

### FR-11: problem+json Error Rendering

When any request in this Story returns a 4xx `application/problem+json` body, the UI renders its `detail` (or a mapped, user-friendly message keyed by `type`), with no raw JSON or stack trace shown. A `422` validation-failure response's `errors` array is mapped onto the matching form fields. A `404` on a ticket id shows a "not found" state — the backend deliberately returns `404`, not `403`, for a ticket the caller does not own.

**Derived from:** TK-AC11

### FR-12: Rate-Limit Handling

When `POST /support/tickets` or `POST /support/tickets/{id}/replies` returns `429` with a retry-after signal, the UI shows a message naming when the customer may retry and disables the submit control until then. The request is not auto-retried in a loop.

The retry-after value exists only in the response's `Retry-After` HTTP header, never in the JSON body, and the shared `httpClient.ts` error path does not currently pass response headers into the thrown `ApiError`. This requirement therefore cannot be implemented as literally stated without a scoped change to that shared client, and how that change should be shaped is not yet decided — this FR states the required behavior, not the mechanism by which the header is expected to reach the UI. See Open Question 1 (OD-1).

**Derived from:** TK-AC12

### FR-13: Network / Server Failure Handling

When a network error or a 5xx response occurs on any endpoint in this Story, a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception.

**Derived from:** TK-AC13

### FR-14: Auth Interaction

When a request in this Story fails with `401`, US-5.1's silent-refresh path handles it (single refresh, retry once, else clear state and redirect to `/login`). When the customer's account was deactivated, `POST /support/tickets`'s `403` renders its problem+json `detail` rather than a generic error.

**Derived from:** TK-AC14

### FR-15: Post-Login Redirect and Navigation Entry

The authenticated post-login redirect and home route move from US-5.1's placeholder to `/tickets`, and `/tickets` is added to the app shell's navigation.

**Derived from:** In Scope section ("Changes US-5.1's shipped code"), Assumption #7

## Non-Functional Requirements

- No ticket body, reply body, or `Idempotency-Key` written to the browser console in production builds.
- Ticket and reply bodies are rendered as plain text, never as HTML/markdown-as-HTML — no `dangerouslySetInnerHTML` anywhere in this Story.
- Full keyboard navigation and visible focus on every control; the reply thread is reachable and announced in a sensible reading order (accessibility).
- Responsive from ~375px through desktop.
- Every screen has an explicit loading state and an explicit error state; long threads must not block first paint of the ticket header.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Agent queue / agent ticket handling, internal-visibility replies, `POST /{id}/resolve` — `resolve` remains agent-only regardless of the point below (`TicketService.resolve_ticket` raises `InsufficientPermissionError` for any non-agent caller). **Correction to the source's stated rationale, carried forward from clarification:** the source's Dependencies & Blockers #1 attributes this exclusion to `GET /support/tickets` rejecting `tickets:read`/`tickets:write` holders with a 403 (`reject_agent_queue_access`). That technical rejection was retired when US-4.4 (Agent Ticket Queue & Assignment) shipped an agent-branch response on the same route. The customer-only scope itself is unaffected — `docs/catalog/stories.yaml` records a deliberate US-5.3 (customer)/US-5.5 (agent console) split — so this Story remains customer-only by design, not by a remaining technical blocker. A future Story (US-5.5) is the agent-side counterpart.
- Attachment upload/preview — no upload endpoint exists, and `TicketRead`/`ReplyRead` expose no attachment references to read back.
- Account/profile & MFA enrollment — Story US-5.2; admin console — Story US-5.4.
- Any backend/API/DB change. This Story implements only against already-shipped backend endpoints; it does not add, modify, or design any API route, request/response contract, or database schema/table/column. `API_DESIGN` and `DB_DESIGN` are `NOT_APPLICABLE` for US-5.3.

**Derived from:** Out of Scope and Dependencies & Blockers sections of the source; the agent-queue bullet's rationale corrected per the Clarification Report's cited finding (US-4.4 retired `reject_agent_queue_access`; the customer/agent split recorded in `docs/catalog/stories.yaml` is the current, correct justification).

## Open Questions

The following six items are carried forward, unresolved, from `docs/decisions/US-5.3-open-decisions.md` (version 1). Resolution happens at `HUMAN_SPEC_APPROVAL`, not in this document.

1. **(OD-1, High)** TK-AC12 (FR-12) requires reading the response's `Retry-After` header on a 429, but the shared `httpClient.ts` error path (`parseResponse` → `normalizeApiError`) never receives `response.headers` — only `status`/`contentType`/`body`. Should `ApiError` be extended to carry a retry-after value sourced from that header (and if so, generically or only for `429` responses), or is a different mechanism intended? As the client stands today, FR-12 cannot be implemented without this decision.
2. **(OD-2, Medium)** Should `category` (FR-3) ship as free-text (`maxLength=50`, Assumption #5's default), or does this Story need to wait on US-4.1's still-open OD-3 (a stakeholder-supplied category value list) before the control is finalized?
3. **(OD-3, Medium)** Is it acceptable that "Reopen" (FR-8, FR-9) cannot be pre-disabled for a `resolved` ticket outside its 7-day reopen window, relying entirely on the resulting `409` to communicate ineligibility — or should a backend Story be raised to expose the deadline so the UI can disable the control proactively?
4. **(OD-4, Low)** Should `first_response_at` (FR-5) render as a plain timestamp with no SLA framing, and if so, what exact label/copy should the ticket-detail header use for it?
5. **(OD-5, Low)** Should this Story continue US-5.1/US-5.2's hand-built-components convention (no headless-UI/component-library dependency; reuse existing shared primitives such as `ErrorState`, `FieldError`), or does this Story's set of new interactive surfaces (status filter, cursor-paginated list, reply composer, close/reopen confirmation) change that calculus?
6. **(OD-6, Medium)** When a create submission fails and the customer edits the subject/body/category before resubmitting (rather than retrying verbatim), should the client reuse the same `Idempotency-Key` — which the backend rejects with a `422 IdempotencyKeyReuseError` given the now-different body — or should any field edit mint a new key? Neither Assumption #4 nor TK-AC4 addresses this case.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| TK-AC1 | "Given an authenticated customer on /tickets When the screen loads Then GET /support/tickets is called and each ticket renders its ticket_number, subject, category, status and updated_at And when next_cursor is non-null a \"Load more\" control appends the next page using that cursor And when items is empty an explicit empty state with a \"New ticket\" call to action is shown, not a blank screen" | FR-1 |
| TK-AC2 | "Given the ticket list When the customer selects one of open / waiting_on_support / waiting_on_customer / resolved / closed Then GET /support/tickets is re-called with that status and the cursor is reset And clearing the filter re-requests the unfiltered list" | FR-2 |
| TK-AC3 | "Given an authenticated customer on the new-ticket form When they submit a subject (1–150), body (1–5000) and category (≤50) Then POST /support/tickets is called with an Idempotency-Key header and attachment_ids: [] And on 201 they land on that ticket's detail screen" | FR-3 |
| TK-AC4 | "Given a create submission that failed with a network error or 5xx When the customer retries the same composed ticket Then the identical Idempotency-Key value is sent again And starting a new ticket composition generates a different key" | FR-4 |
| TK-AC5 | "Given an authenticated customer opening a ticket they own Then GET /support/tickets/{id} renders the ticket header (ticket_number, status, category, created_at, first_response_at when present) and the reply thread And each reply shows its author_kind (customer / agent), body and created_at And when replies.next_cursor is non-null an \"Load older replies\" control fetches the next page with that cursor" | FR-5 |
| TK-AC6 | "Given a ticket that is not closed When the customer submits a reply body (1–5000) Then POST /support/tickets/{id}/replies is called without a visibility field and with attachment_ids: [] And on 201 the new reply appears in the thread and the composer clears And the ticket detail is invalidated/refetched, because a customer reply on a \"waiting_on_customer\" ticket transitions it to \"waiting_on_support\" server-side and ReplyRead carries no status field to report that" | FR-6 |
| TK-AC7 | "Given a ticket in open, waiting_on_support, waiting_on_customer or resolved When the customer chooses \"Close ticket\" Then POST /support/tickets/{id}/close is called and the screen reflects status \"closed\" And the reply composer becomes unavailable for a closed ticket" | FR-7 |
| TK-AC8 | "Given a ticket in status \"resolved\" When the customer chooses \"Reopen\" Then POST /support/tickets/{id}/reopen is called and the screen reflects status \"waiting_on_support\" And a 409 (outside the 7-day reopen window) renders the returned problem+json detail, not a generic failure" | FR-8 |
| TK-AC9 | "Given any ticket detail screen Then only actions valid for its current status are offered: status \| offered ; open \| reply, close ; waiting_on_support \| reply, close ; waiting_on_customer \| reply, close ; resolved \| reply, close, reopen ; closed \| (none) And \"Resolve\" is never offered to a customer under any status" | FR-9 |
| TK-AC10 | "Given the create-ticket or reply form When a required field is empty or exceeds its max length (subject 150, body 5000, category 50) Then submission is blocked with a field-level error and no API call is made" | FR-10 |
| TK-AC11 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields And a 404 on a ticket id shows a \"not found\" state (the backend deliberately returns 404, not 403, for a ticket the caller does not own)" | FR-11 |
| TK-AC12 | "Given POST /support/tickets or POST /{id}/replies returns 429 with a retry-after signal Then the UI shows a message naming when the customer may retry and disables the submit control until then And it does not auto-retry the request in a loop" | FR-12 — implementation depends on OD-1's resolution (see Open Questions) |
| TK-AC13 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | FR-13 |
| TK-AC14 | "Given a request in this Story fails with 401 Then US-5.1's silent-refresh path handles it (single refresh, retry once, else clear state and redirect to /login) Given the customer's account was deactivated Then POST /support/tickets' 403 renders its problem+json detail rather than a generic error" | FR-14 |

*TK-AC9's source text embeds a markdown table inside its Gherkin block. That table is flattened above into semicolon-separated rows with pipes escaped (`\|`) so it survives inside this outer table cell — no wording was changed.*
