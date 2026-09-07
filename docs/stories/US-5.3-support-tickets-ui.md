---
id: US-5.3
epic: EPIC-5
title: Support Tickets (Frontend)
slug: support-tickets-ui
priority: MEDIUM
track: frontend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: TODO   # not yet opened — see Open Questions #1
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/26
  last_synced_at: "2026-09-07T00:00:00Z"
---

# Epic 5 — Frontend: Support Tickets

**Story ID:** US-5.3
**Project:** Customer Portal
**Depends on:** US-5.1 (auth store, API client, route guards, problem+json rendering)

## User Story
As a customer,
I want to raise a support ticket, follow its thread, reply to it, and close or reopen it from a real web UI,
So that EPIC-4 (US-4.1/4.2/4.3) is usable end-to-end rather than only through raw API calls.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Stack | Reuses US-5.1's `frontend/` — React + Vite + TS + TanStack Query + React Hook Form, same API client and auth store | No second stack; this Story adds screens, not infrastructure |
| 2 | Audience | **Customer-side only.** No agent queue, no internal-note composer | `reject_agent_queue_access` (`app/modules/support/dependencies.py`) *rejects* any `tickets:read`/`tickets:write` holder from `GET /support/tickets` — there is no staff listing endpoint to build a queue on. See Dependencies & Blockers #1 |
| 3 | Attachments | Out of scope. Every create/reply request sends `attachment_ids: []` | No upload endpoint exists, and `TicketRead`/`ReplyRead` expose no attachment references at all (their own docstrings say so). See Dependencies & Blockers #2 |
| 4 | `Idempotency-Key` on create | Client generates a UUIDv4 **once per composed ticket** (when the form is opened/first submitted) and **reuses the same value on every retry** of that submission; a new value is minted only for a genuinely new ticket | The header is a *required* parameter — omitting it is a 422. Regenerating it on retry would defeat the backend's whole idempotency envelope and can duplicate tickets |
| 5 | `category` input | **Free-text field with `maxLength=50`**, not a dropdown | `CreateTicketRequest.category` is a bare `str(max_length=50)`; US-4.1 OD-3's valid value list is an unresolved stakeholder decision (`docs/decisions/US-4.1-open-decisions.md`). Inventing a dropdown would invent product policy |
| 6 | Pagination | Cursor-based "Load more" (list) and "Load older replies" (thread) | Every list response is `items` + `next_cursor` with **no total count** — page numbers or "X of Y" are not derivable |
| 7 | Post-login redirect | This Story flips US-5.1 Assumption #5: authenticated home becomes `/tickets` | US-5.1 chose a placeholder only because this Story did not exist yet |
| 8 | No backend changes | `API_DESIGN` / `DB_DESIGN` stages record `NOT_APPLICABLE` | Purely a frontend consuming an already-delivered contract; the two gaps above are recorded as dependencies on *new backend Stories*, not worked around here |

## In Scope
- Ticket list (`GET /support/tickets`) with the five-status filter and cursor "Load more"
- Create ticket (`POST /support/tickets`) with required `Idempotency-Key` handling
- Ticket detail + reply thread (`GET /support/tickets/{id}`, cursor-paged `replies`)
- Post a reply (`POST /support/tickets/{id}/replies`) — public visibility only
- Close (`POST /support/tickets/{id}/close`) and reopen (`POST /support/tickets/{id}/reopen`) from the customer side
- Status-driven affordances: only actions the ticket's current status permits are offered
- 429 rate-limit handling (create and reply both have their own limiter with `retry_after`)
- Loading, empty, and error states (RFC 7807 problem+json) on every screen above
- **Changes US-5.1's shipped code:** the authenticated post-login redirect and home route move from US-5.1's placeholder to `/tickets` (Assumption #7), and `/tickets` is added to the app shell's navigation

## Out of Scope
- Agent queue / agent ticket handling, internal-visibility replies, `POST /{id}/resolve` — no listing endpoint exists for staff, and `resolve` is agent-only (`TicketService.resolve_ticket` raises `InsufficientPermissionError` for any non-agent). Future Story, blocked on Dependencies & Blockers #1
- Attachment upload/preview — blocked on Dependencies & Blockers #2
- Account/profile & MFA enrollment — Story US-5.2; admin console — Story US-5.4
- Any backend/API/DB change

## Dependencies & Blockers (backend gaps — new Stories required, not frontend workarounds)
1. **No staff ticket-list endpoint.** `GET /support/tickets` explicitly rejects `tickets:read`/`tickets:write` holders (403). An agent queue UI is unbuildable until a backend Story adds one. This Story is therefore customer-only *by contract*, not by preference.
2. **No attachment-upload endpoint.** `docs/stories/README.md` already records "US-4.1 is blocked by an as-yet-unwritten attachment-upload story." `attachment_ids` is write-only and never read back, so even a stored attachment would be invisible in the UI.

## API Contract (existing backend — reference only, not designed by this Story)
| Method | Path | Auth | Request | Success |
|---|---|---|---|---|
| POST | `/api/v1/support/tickets` | Bearer + **`Idempotency-Key` header (required)** | `{subject≤150, body≤5000, category≤50, attachment_ids: []}` | 201 `TicketRead` |
| GET | `/api/v1/support/tickets` | Bearer (customer only) | `?status=&cursor=&limit=` | 200 `TicketListResponse` |
| GET | `/api/v1/support/tickets/{id}` | Bearer | `?cursor=&limit=` (1–100, default 50) | 200 `TicketDetailRead` (incl. `replies` page) |
| POST | `/api/v1/support/tickets/{id}/replies` | Bearer | `{body≤5000, visibility?, attachment_ids: []}` | 201 `ReplyRead` |
| POST | `/api/v1/support/tickets/{id}/close` | Bearer | `{reason?}` | 200 `TicketStateRead` |
| POST | `/api/v1/support/tickets/{id}/reopen` | Bearer | `{reason?}` | 200 `TicketStateRead` |
| POST | `/api/v1/support/tickets/{id}/resolve` | Bearer (**agent only**) | `{resolution_note}` | 200 — *out of scope* |

**Status values** (`_TicketStatus`): `open`, `waiting_on_support`, `waiting_on_customer`, `resolved`, `closed`.
**Verified transition eligibility** (from `app/modules/support/service.py`):
- close: `open`, `waiting_on_support`, `waiting_on_customer`, `resolved`
- reopen: `resolved` only, and only within an inclusive 7-day window (outside it → the same 409 an invalid transition gets)
- resolve: agent only — never offered to a customer
- reply: **every status except `closed`** (`TicketReplyService.create_reply` raises `TicketClosedError` only for `closed`) — so a `resolved` ticket still accepts replies
- side effect: a customer reply on a `waiting_on_customer` ticket transitions it to `waiting_on_support`

## Client State Notes
- `TicketRead.status` / `TicketDetailRead.status` are plain `str`, not an enum. Render an unrecognized value verbatim with neutral styling rather than crashing or hiding the row.
- No total count anywhere — no "X of Y", no page numbers. `next_cursor === null` is the only end-of-list signal.
- `ReplyRead.visibility` may be `"internal"` in the payload shape, but a customer caller never receives such a row (RLS + write-path). The customer composer has **no visibility control**; sending `internal` as a customer is a 403 by design.
- The reply thread's `replies.next_cursor` is independent of the list's cursor — two separate paginators.
- Idempotency key lives in transient form state for the lifetime of one composition; it is not persisted across a full page reload.

## Acceptance Criteria

### Happy path
**TK-AC1 — Ticket list**
```gherkin
Given an authenticated customer on /tickets
When the screen loads
Then GET /support/tickets is called and each ticket renders its ticket_number, subject, category, status and updated_at
And when next_cursor is non-null a "Load more" control appends the next page using that cursor
And when items is empty an explicit empty state with a "New ticket" call to action is shown, not a blank screen
```

**TK-AC2 — Status filter**
```gherkin
Given the ticket list
When the customer selects one of open / waiting_on_support / waiting_on_customer / resolved / closed
Then GET /support/tickets is re-called with that status and the cursor is reset
And clearing the filter re-requests the unfiltered list
```

**TK-AC3 — Create ticket**
```gherkin
Given an authenticated customer on the new-ticket form
When they submit a subject (1–150), body (1–5000) and category (≤50)
Then POST /support/tickets is called with an Idempotency-Key header and attachment_ids: []
And on 201 they land on that ticket's detail screen
```

**TK-AC4 — Idempotency key is stable across retries**
```gherkin
Given a create submission that failed with a network error or 5xx
When the customer retries the same composed ticket
Then the identical Idempotency-Key value is sent again
And starting a new ticket composition generates a different key
```

**TK-AC5 — Ticket detail and thread**
```gherkin
Given an authenticated customer opening a ticket they own
Then GET /support/tickets/{id} renders the ticket header (ticket_number, status, category, created_at, first_response_at when present) and the reply thread
And each reply shows its author_kind (customer / agent), body and created_at
And when replies.next_cursor is non-null an "Load older replies" control fetches the next page with that cursor
```

**TK-AC6 — Post a reply**
```gherkin
Given a ticket that is not closed
When the customer submits a reply body (1–5000)
Then POST /support/tickets/{id}/replies is called without a visibility field and with attachment_ids: []
And on 201 the new reply appears in the thread and the composer clears
And the ticket detail is invalidated/refetched, because a customer reply on a
  "waiting_on_customer" ticket transitions it to "waiting_on_support" server-side
  and ReplyRead carries no status field to report that
```

**TK-AC7 — Close**
```gherkin
Given a ticket in open, waiting_on_support, waiting_on_customer or resolved
When the customer chooses "Close ticket"
Then POST /support/tickets/{id}/close is called and the screen reflects status "closed"
And the reply composer becomes unavailable for a closed ticket
```

**TK-AC8 — Reopen**
```gherkin
Given a ticket in status "resolved"
When the customer chooses "Reopen"
Then POST /support/tickets/{id}/reopen is called and the screen reflects status "waiting_on_support"
And a 409 (outside the 7-day reopen window) renders the returned problem+json detail, not a generic failure
```

**TK-AC9 — Status-driven affordances**
```gherkin
Given any ticket detail screen
Then only actions valid for its current status are offered:
  | status                | offered            |
  | open                  | reply, close       |
  | waiting_on_support    | reply, close       |
  | waiting_on_customer   | reply, close       |
  | resolved              | reply, close, reopen |
  | closed                | (none)             |
And "Resolve" is never offered to a customer under any status
```

### Validation and errors
**TK-AC10 — Client-side validation**
```gherkin
Given the create-ticket or reply form
When a required field is empty or exceeds its max length (subject 150, body 5000, category 50)
Then submission is blocked with a field-level error and no API call is made
```

**TK-AC11 — problem+json errors**
```gherkin
Given any request in this Story returns a 4xx application/problem+json body
Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace
And a 422 validation-failed maps its errors array onto the matching form fields
And a 404 on a ticket id shows a "not found" state (the backend deliberately returns 404, not 403, for a ticket the caller does not own)
```

**TK-AC12 — Rate limiting**
```gherkin
Given POST /support/tickets or POST /{id}/replies returns 429 with a retry-after signal
Then the UI shows a message naming when the customer may retry and disables the submit control until then
And it does not auto-retry the request in a loop
```

**TK-AC13 — Network / server failure**
```gherkin
Given a network error or 5xx from any endpoint in this Story
Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception
```

**TK-AC14 — Auth interaction**
```gherkin
Given a request in this Story fails with 401
Then US-5.1's silent-refresh path handles it (single refresh, retry once, else clear state and redirect to /login)
Given the customer's account was deactivated
Then POST /support/tickets' 403 renders its problem+json detail rather than a generic error
```

## Non-Functional / Security Requirements
- No ticket body, reply body, or `Idempotency-Key` written to the browser console in production builds.
- Ticket and reply bodies are rendered as **plain text**, never as HTML/markdown-as-HTML — no `dangerouslySetInnerHTML` anywhere in this Story.
- Full keyboard navigation and visible focus on every control; the reply thread is reachable and announced in a sensible reading order (a11y).
- Responsive from ~375px through desktop.
- Every screen has an explicit loading state and an explicit error state; long threads must not block first paint of the ticket header.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| TK-AC1–3, TK-AC5–8 | Component/integration tests against the mocked API layer (MSW or equivalent) | `[gate]` |
| TK-AC4 | Test asserting the same `Idempotency-Key` on a retried submission and a different one on a new composition | `[gate]` |
| TK-AC9 | Table-driven test over all five statuses asserting the exact offered-action set | `[gate]` |
| TK-AC10 | Form-level unit tests (React Hook Form + validation schema, incl. max-length bounds) | `[gate]` |
| TK-AC11 | Test asserting problem+json `type`/`detail`/`errors` map to rendered messages/fields, incl. the 404 case | `[gate]` |
| TK-AC12 | Test forcing a 429 with `retry_after` on both create and reply | `[gate]` |
| TK-AC13 | Test forcing a network/5xx failure per screen | `[gate]` |
| TK-AC14 | Integration test for the 401→refresh→retry path from a ticket screen | `[gate]` |
| Plain-text rendering | Test asserting an HTML-bearing body renders escaped | `[gate]` |
| a11y bar | Automated a11y check (e.g. axe) on list, create and detail screens | `[gate]` |

## Open Questions
1. GitHub Issue for this Story is not yet opened — confirm before `source.issue_number` is filled in (opening it is a shared-state action needing explicit approval).
2. `category` (Assumption #5): confirm free-text, or resolve US-4.1 OD-3 first so a dropdown can be built against a real value list.
3. Reopen's 7-day window is not exposed as a field on any response shape — the UI cannot pre-disable "Reopen" for an out-of-window resolved ticket and will surface the 409 instead. Confirm this is acceptable, or raise a backend Story to expose the window.
4. `first_response_at` is present on `TicketDetailRead` but no SLA target is exposed anywhere — confirm it should be displayed as a plain timestamp with no SLA framing.
