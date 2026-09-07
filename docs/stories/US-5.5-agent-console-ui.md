---
id: US-5.5
epic: EPIC-5
title: Agent Console (Frontend)
slug: agent-console-ui
priority: MEDIUM
track: frontend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: 29
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/29
  last_synced_at: "2026-09-07T00:00:00Z"
---

# Epic 5 — Frontend: Agent Console

**Story ID:** US-5.5
**Project:** Customer Portal
**Depends on:** US-5.1 (auth store, API client, route guards, problem+json rendering), US-5.3 (ticket detail/thread components) and — **hard blocker** — **US-4.4** (agent queue + assignment backend)

## Blocked until US-4.4 ships
Today `GET /support/tickets` returns 403 to any `tickets:read`/`tickets:write` holder (`reject_agent_queue_access`), so an agent cannot discover a single ticket. Nothing in this Story is buildable until US-4.4 replaces that rejection with an agent branch and adds `assignee_id`. **Do not start this Story before US-4.4 is merged.**

## User Story
As a support agent,
I want to work the ticket queue — see what is waiting, take ownership, read the full thread including internal notes, reply publicly or internally, and resolve — through a real web UI,
So that EPIC-4's agent half is usable end-to-end rather than reachable only by hand-crafted API calls.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Stack | Reuses US-5.1's `frontend/`; the ticket detail and reply-thread components come from US-5.3 and are extended, not duplicated | The customer and agent views of one ticket differ in affordances, not in structure |
| 2 | Route namespace | `/agent/*`, distinct from the customer's `/tickets` | The same person may hold both roles; two namespaces keep "which hat am I wearing" unambiguous |
| 3 | Permission gating | `tickets:read` reveals the queue; `tickets:write` enables reply/assign/resolve. Scopes are decoded from the JWT `scopes` claim, cosmetically — every screen still handles a server 403 | Same model as US-5.4 Assumption #2/#3; `LoginResponse` carries no roles object |
| 4 | Default queue view | **No `assignee_id` filter applied** — every non-closed ticket, oldest-updated first — with `me` and `none` offered as one-click filter presets | US-4.4's `assignee_id` takes a **single** value (a UUID, `me`, or `none`); there is no union filter, so "unassigned + mine" is not expressible. The unfiltered queue is US-4.4 AQ-AC1's own default and is a strict superset of both presets |
| 5 | Internal notes | Visually distinct from public replies (separate styling and an explicit label), never merged into one undifferentiated stream | An agent posting an internal note into a customer-visible thread by mistake is the expensive failure here |
| 6 | Reply visibility default | The composer defaults to **public**, with `internal` a deliberate, visible choice | Matches the service default (`visibility=None` → `"public"`); an accidental default of `internal` would silently drop customer communication |
| 7 | No backend changes | `API_DESIGN` / `DB_DESIGN` record `NOT_APPLICABLE` **for this Story** — the backend work is US-4.4 | This Story consumes US-4.4's contract; it does not design it |

## In Scope
- Agent queue (`GET /support/tickets`, agent branch) with `status` / `category` / `assignee_id` filters (`me`, `none`, a specific agent) and cursor "Load more"
- Assign to me / assign to another agent (`POST /support/tickets/{id}/assign`) and unassign (`DELETE .../assign`)
- Agent ticket detail (`GET /support/tickets/{id}`) rendering the full thread **including internal-visibility replies**
- Reply composer with an explicit public / internal visibility control (`POST /support/tickets/{id}/replies`)
- Resolve with a mandatory, non-empty `resolution_note` (`POST /support/tickets/{id}/resolve`)
- Close and reopen from the agent side (`POST /{id}/close`, `POST /{id}/reopen`)
- Status- and scope-driven affordances; 429 rate-limit handling on reply

## Out of Scope
- Customer-facing ticket UI — Story US-5.3
- Account/profile self-service — US-5.2; admin console — US-5.4
- Auto-assignment, routing rules, SLA dashboards, queue metrics — explicitly out of US-4.4 too
- Attachments — still blocked on the unwritten attachment-upload story
- Any backend/API/DB change (that is US-4.4)

## API Contract (delivered by US-4.4 + existing backend — reference only)
| Method | Path | Scope | Request | Success |
|---|---|---|---|---|
| GET | `/api/v1/support/tickets` | `tickets:read` | `?status=&category=&assignee_id=&cursor=&limit=` | 200 `TicketListResponse` (agent shape, incl. `assignee_id`) |
| POST | `/api/v1/support/tickets/{id}/assign` | `tickets:write` | `{assignee_id}` | 200 (agent shape) |
| DELETE | `/api/v1/support/tickets/{id}/assign` | `tickets:write` | — | 200 (agent shape) |
| GET | `/api/v1/support/tickets/{id}` | agent branch | `?cursor=&limit=` | 200 `TicketDetailRead`, incl. internal replies |
| POST | `/api/v1/support/tickets/{id}/replies` | `tickets:write` | `{body≤5000, visibility: "public"\|"internal", attachment_ids: []}` | 201 `ReplyRead` |
| POST | `/api/v1/support/tickets/{id}/resolve` | `tickets:write` | `{resolution_note: 1..5000}` | 200 `TicketStateRead` |
| POST | `/api/v1/support/tickets/{id}/close` | agent or requester | `{reason?}` | 200 `TicketStateRead` |
| POST | `/api/v1/support/tickets/{id}/reopen` | agent or requester | `{reason?}` | 200 `TicketStateRead` |

**Verified transition eligibility** (from `app/modules/support/service.py`):
- resolve: `open`, `waiting_on_support`, `waiting_on_customer` — **state is checked before actor**, so a resolve on a `closed` ticket is 409 and a resolve by a non-agent on an eligible ticket is 403
- close: `open`, `waiting_on_support`, `waiting_on_customer`, `resolved`
- reopen: `resolved` only, inclusive 7-day window (outside it → the same 409)
- reply: every status except `closed`
- side effect: an **agent public** reply sets `first_response_at` on first use and moves a non-`resolved` ticket to `waiting_on_customer`; an **internal** note transitions nothing and stamps nothing

## Client State Notes
- `ReplyRead.visibility` is `"public"` or `"internal"`; the agent view receives both and must render them visually distinct (Assumption #5).
- Neither `ReplyRead` nor the assign responses report the ticket's resulting status reliably, and a reply changes it — every successful reply, assign, resolve, close or reopen invalidates the ticket detail and the queue.
- Queue and thread paginate independently; both are `items` + `next_cursor` with no total count.
- `assignee_id` is a raw UUID — resolving it to a display name needs `GET /admin/users/{id}` (`users:read`), which an agent may not hold. See Open Questions #1.

## Acceptance Criteria

**AG-AC1 — Queue**
```gherkin
Given an agent holding tickets:read on /agent/tickets
Then GET /support/tickets renders every non-closed ticket with ticket_number, subject, category, status, assignee and updated_at, oldest-updated first
And status / category / assignee_id filters re-request the queue and reset the cursor
And assignee_id=me and assignee_id=none are offered as one-click presets, mutually exclusive
  (US-4.4's assignee_id takes a single value; a union of the two is not expressible)
And a non-null next_cursor drives "Load more"; no total count or page number is displayed
```

**AG-AC2 — Assign / unassign**
```gherkin
Given an agent holding tickets:write on a ticket in the queue
When they choose "Assign to me"
Then POST /support/tickets/{id}/assign is called with their own id and the row reflects the new assignee
When they assign to another agent, or unassign
Then the corresponding assign / DELETE assign call is made and the queue is invalidated
And a 409 (closed ticket) or 422 (assignee is not an agent) renders its problem+json detail
```

**AG-AC3 — Agent ticket detail**
```gherkin
Given an agent opening a ticket
Then GET /support/tickets/{id} renders the ticket header and the full thread
And internal-visibility replies are rendered visually distinct from public ones and explicitly labelled "internal"
And "Load older replies" pages the thread by its own cursor
```

**AG-AC4 — Reply with visibility**
```gherkin
Given an agent on a ticket that is not closed
Then the composer's visibility control defaults to "public"
When they submit a public reply
Then POST /{id}/replies is called with visibility "public" and the ticket detail is invalidated,
  because the server may set first_response_at and move the status to waiting_on_customer
When they submit an internal note
Then visibility "internal" is sent and the note renders in the internal style, with no status change expected
And choosing "internal" is a deliberate, visible action — never the default and never a silent state
```

**AG-AC5 — Resolve**
```gherkin
Given an agent on a ticket in open, waiting_on_support or waiting_on_customer
When they resolve it with a non-empty resolution_note (1..5000)
Then POST /{id}/resolve is called and the screen reflects status "resolved"
And an empty note blocks submission client-side with a field-level error
And a 409 on a closed ticket renders the returned problem+json detail
```

**AG-AC6 — Status- and scope-driven affordances**
```gherkin
Given any agent ticket detail screen
Then only actions valid for its current status are offered:
  | status                | offered                          |
  | open                  | reply, assign, resolve, close    |
  | waiting_on_support    | reply, assign, resolve, close    |
  | waiting_on_customer   | reply, assign, resolve, close    |
  | resolved              | reply, assign, close, reopen     |
  | closed                | (none)                           |
And an agent holding tickets:read but not tickets:write sees a read-only view with every write control disabled
```

**AG-AC7 — problem+json errors**
```gherkin
Given any request in this Story returns a 4xx application/problem+json body
Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace
And a 422 validation-failed maps its errors array onto the matching form fields
```

**AG-AC8 — Rate limiting**
```gherkin
Given POST /{id}/replies returns 429 with a retry-after signal
Then the UI shows a message naming when the agent may retry and disables the submit control until then
And it does not auto-retry in a loop
```

**AG-AC9 — Network / server failure**
```gherkin
Given a network error or 5xx from any endpoint in this Story
Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception
```

## Non-Functional / Security Requirements
- An internal note MUST be unmistakable at a glance and in a screen reader — distinct styling *and* a text label, never colour alone.
- The visibility control's state MUST be re-asserted (not remembered from the previous reply) each time the composer opens, so a prior "internal" choice cannot leak into the next public reply.
- Ticket and reply bodies render as **plain text**; no `dangerouslySetInnerHTML` anywhere.
- Client-side scope decoding is never treated as authorization; every screen handles a server 403.
- Full keyboard navigation and visible focus; the queue table's cells are associated with their column headers (a11y).
- Responsive from ~375px through desktop; the queue table scrolls within its own container.
- Every screen has an explicit loading state and an explicit error state.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| AG-AC1–3, AG-AC5 | Component/integration tests against the mocked API layer (MSW or equivalent) | `[gate]` |
| AG-AC4 | Test asserting the composer defaults to public, that "internal" is never sticky across opens, and that a successful reply invalidates the ticket detail | `[gate]` |
| AG-AC6 | Table-driven test over all five statuses, plus a `tickets:read`-only token asserting the read-only view | `[gate]` |
| AG-AC7–9 | Tests per screen for problem+json, 429 and network/5xx failure | `[gate]` |
| Internal-note distinction | Test asserting an internal reply renders both a distinct style and a text label, not colour alone | `[gate]` |
| Plain-text rendering | Test asserting an HTML-bearing body renders escaped | `[gate]` |
| a11y bar | Automated a11y check (e.g. axe) on the queue and agent detail screens | `[gate]` |

## Open Questions
1. `assignee_id` is a raw UUID and resolving it to a name needs `GET /admin/users/{id}` (`users:read`), which `support_agent` may not hold. Either US-4.4 embeds a display name on the agent shape, or the UI shows a shortened UUID. **Recommend raising it against US-4.4** rather than working around it here.
2. Should the agent queue and the customer's own ticket list be reachable from one shell for a user who holds both roles, or should `/agent/*` be a separate entry point entirely?
3. US-4.4 Open Question **#6** (extended `TicketRead` vs. a distinct `AgentTicketRead`) determines this Story's type definitions — it must be resolved in US-4.4 first.
