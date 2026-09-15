---
artifact_type: specification
story: US-5.5
version: 2
status: ARCHIVED
created_at: "2026-09-14T01:15:00Z"
updated_at: "2026-09-14T03:15:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/evidence/US-5.5-clarification-report.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/specifications/US-5.5-spec.md (v1)
---

# Specification: Agent Console (Frontend)

**Source:** docs/stories/US-5.5-agent-console-ui.md
**Story ID:** US-5.5
**Generated:** 2026-09-14
**Status:** Draft

> **Revision (v2):** `version: 1` of this specification (`status: APPROVED`)
> still carried five Open Decisions (OD-1–OD-5) as unresolved Open Questions,
> deferring their resolution to `HUMAN_SPEC_APPROVAL`. That approval did not
> carry a resolution back into the spec text, and `PLAN_REVIEW` returned
> `BLOCKED` on that basis (`docs/reviews/plans/US-5.5-plan-review.md`,
> `docs/workflow/history.jsonl` at `2026-09-14T02:10:00Z`) — the same root
> cause already seen once on the sibling story US-5.4.
> `story-orchestrator` recorded a `HUMAN_REDIRECTED` transition from
> `PLAN_REVIEW` back to `CLARIFICATION`
> (`docs/workflow/history.jsonl` at `2026-09-14T02:20:00Z`), where a human
> stakeholder supplied an explicit resolution for each of the five items in
> that same session, today (2026-09-14). Those resolutions are formalized in
> `docs/decisions/US-5.5-open-decisions.md` (version 2) and
> `docs/evidence/US-5.5-clarification-report.md` (version 2), and are
> incorporated directly into FR-1, FR-2, FR-3, FR-6, and FR-7 below, and into
> new FR-11, replacing the forward-references those sections carried in v1.
> Open Questions no longer lists OD-1–OD-5; see
> [Decisions Resolved by Human (2026-09-14)](#decisions-resolved-by-human-2026-09-14).
> FR-1, FR-2, FR-3, FR-6, and FR-7 are the only pre-existing Functional
> Requirements whose text changed; FR-11 is new. All other sections are
> otherwise unchanged from v1.

## Summary

This spec covers the frontend agent console for the Customer Portal: the
agent ticket queue with status/category/assignee filters and cursor
pagination, assign-to-me/assign-to-another-agent/unassign, agent ticket
detail rendering the full thread including internal-visibility replies, a
reply composer with an explicit public/internal visibility control, resolve
with a mandatory resolution note, close/reopen, status- and scope-driven
affordances, a shared app-shell navigation entry, and the problem+json,
rate-limit, and network/server-failure handling common to every screen in
this Story. It makes no backend, API, or database change; it consumes only
US-4.4's already-shipped agent-side contract.

## Background

As a support agent, the actor wants to work the ticket queue — see what is
waiting, take ownership, read the full thread including internal notes,
reply publicly or internally, and resolve — through a real web UI, so that
EPIC-4's agent-side backend (US-4.1–US-4.4) is usable end-to-end rather than
reachable only by hand-crafted API calls. This Story reuses US-5.1's shared
frontend infrastructure (auth store, API client, route guards, problem+json
rendering) and extends, rather than duplicates, the ticket detail and
reply-thread components US-5.3 built for the customer-facing view — the
customer and agent views of one ticket differ in affordances, not in
structure (Assumption #1). Per the source's own Assumption #7,
`API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` — this Story is a pure
frontend consumer of an already-delivered backend contract (US-4.4).

## Functional Requirements

### FR-1: Agent Queue

An agent holding `tickets:read` sees `GET /support/tickets` (agent branch)
rendered as a list of every non-closed ticket's `ticket_number`, `subject`,
`category`, `status`, assignee, and `updated_at`, ordered oldest-updated
first. Where present, the assignee column renders the assigned agent's
identity as a shortened/truncated `assignee_id` UUID — no backend-provided
display name exists, and no name-resolution call is made opportunistically,
since only some agents hold the `users:read` scope that a
`GET /admin/users/{id}` lookup would require and an opportunistic call would
produce an inconsistent UI depending on the viewer's own permission set
(Resolution OD-1).

The `status`, `category`, and `assignee_id` filters each re-issue the
request and reset the cursor. `assignee_id=me` and `assignee_id=none` are
offered as one-click presets that are mutually exclusive, since US-4.4's
`assignee_id` takes a single value and a union of the two is not
expressible. A specific agent is filtered on via a raw-UUID text input —
the target agent's id — since no agent-directory/enumeration endpoint is
reachable by a caller holding only `tickets:write`/`tickets:read`
(Resolution OD-2); this input is a third, independent way to set
`assignee_id`, alongside the `me`/`none` presets. A non-null `next_cursor`
drives a "Load more" control; no total count or page number is displayed
anywhere on this screen.

**Derived from:** AG-AC1; assignee display per Resolution OD-1;
specific-agent filter mechanism per Resolution OD-2

### FR-2: Assign / Unassign

An agent holding `tickets:write` on a ticket in the queue can choose "Assign
to me," which calls `POST /support/tickets/{id}/assign` with their own id;
the row reflects the new assignee on success. Assigning to another agent is
done by entering that agent's id into a raw-UUID text input — no
agent-directory/enumeration endpoint exists for a caller holding only
`tickets:write` to pick from (Resolution OD-2) — which calls the same
`assign` endpoint with the entered id. Unassigning calls
`DELETE .../assign`. Both a successful assign and a successful unassign
invalidate the queue. A `409` (closed ticket) or `422` (assignee is not an
agent) renders its problem+json detail.

**Derived from:** AG-AC2; assign-target mechanism per Resolution OD-2

### FR-3: Agent Ticket Detail

Opening a ticket calls `GET /support/tickets/{id}` and renders the ticket
header and the full thread. The header's current-assignee display is
sourced as a navigation-state handoff: the `assignee_id` from the queue row
the agent clicked to open this screen is carried into the detail screen's
local state and rendered there (shortened/truncated UUID, per Resolution
OD-1); it is updated afterward from the response of any assign/unassign
call made on this screen (FR-6). If the screen is opened by a direct URL
rather than by clicking a queue row, no handed-off value exists and the
assignee is treated as unknown/stale until the first assign/unassign call
on this screen resolves it — no workaround endpoint is called to recover it
(Resolution OD-3). Internal-visibility replies are rendered visually
distinct from public ones and are explicitly labelled "internal." "Load
older replies" pages the thread by its own cursor.

**Derived from:** AG-AC3; assignee source per Resolution OD-3; assignee
display per Resolution OD-1

### FR-4: Reply with Visibility

On a ticket that is not closed, the composer's visibility control defaults
to "public." Submitting a public reply calls `POST /{id}/replies` with
visibility `"public"` and invalidates the ticket detail, since the server
may set `first_response_at` and move the status to `waiting_on_customer`.
Submitting an internal note sends visibility `"internal"` and renders the
note in the internal style, with no status change expected. Choosing
"internal" is a deliberate, visible action — it is never the default and
never a silent state.

**Derived from:** AG-AC4

### FR-5: Resolve

On a ticket in `open`, `waiting_on_support`, or `waiting_on_customer`, an
agent resolves it by supplying a non-empty `resolution_note` (1–5000
characters); this calls `POST /{id}/resolve`, and the screen reflects status
`"resolved"` on success. An empty note blocks submission client-side with a
field-level error. A `409` on a closed ticket renders the returned
problem+json detail.

**Derived from:** AG-AC5

### FR-6: Status- and Scope-Driven Affordances

On any agent ticket detail screen, only the actions valid for the ticket's
current status are offered:

| status | offered |
|---|---|
| `open` | reply, assign, resolve, close |
| `waiting_on_support` | reply, assign, resolve, close |
| `waiting_on_customer` | reply, assign, resolve, close |
| `resolved` | reply, assign, close, reopen |
| `closed` | (none) |

An agent holding `tickets:read` but not `tickets:write` sees a read-only
view with every write control disabled.

The "assign" action, offered by this table at every non-`closed` status,
operates against the assignee value FR-3 sourced via navigation-state
handoff: choosing "assign" (to self or to another agent, per FR-2's
raw-UUID input) or "unassign" from this screen calls the corresponding
endpoint and, on success, updates that local assignee value from the
response (`AgentTicketStateRead`), since the invalidated-and-refetched
`TicketDetailRead` (per the story's Client State Notes) carries no
`assignee_id` field of its own to source it from (Resolution OD-3).

**Derived from:** AG-AC6; assign-affordance data source per Resolution OD-3

### FR-7: Close and Reopen

When offered per FR-6's status table, choosing "Close" calls
`POST /{id}/close`; choosing "Reopen" calls `POST /{id}/reopen`. Each is a
single action button: neither interaction collects the endpoints' optional
`reason` field, and neither sits behind a confirmation step, mirroring the
customer-facing pattern (`docs/specifications/US-5.3-spec.md` FR-7/FR-8)
(Resolution OD-5).

**Derived from:** AG-AC6; interaction shape per Resolution OD-5

### FR-8: problem+json Error Rendering

For any request in this Story that returns a 4xx `application/problem+json`
body, the UI renders that response's detail (or a mapped, user-friendly
message keyed by `type`) — with no raw JSON or stack trace. A `422`
validation-failure response's `errors` array is mapped onto the matching
form fields.

**Derived from:** AG-AC7

### FR-9: Rate Limiting

When `POST /{id}/replies` returns `429` with a retry-after signal, the UI
shows a message naming when the agent may retry and disables the submit
control until then. It does not auto-retry in a loop.

**Derived from:** AG-AC8

### FR-10: Network / Server Failure Handling

For a network error or a `5xx` response from any endpoint in this Story, a
retry-capable error state is shown — never a blank screen, an indefinite
spinner, or an unhandled exception.

**Derived from:** AG-AC9

### FR-11: Shared App Shell Navigation

The agent console and the customer's own ticket list are reachable from one
shared authenticated app shell, not a separate entry point. A top-level
`/agent/*` navigation entry is gated on `tickets:read` and offered alongside
the existing `/tickets` entry within that same shell — extending the
scope-derived navigation pattern this codebase already established
(`docs/specifications/US-5.4-spec.md` FR-9) — with no separate entry point
and no role switcher for a user who holds both a customer identity and
agent scopes (Resolution OD-4).

**Derived from:** Story's own Open Question #2, resolved as Decision OD-4

## Non-Functional Requirements

- An internal note MUST be unmistakable at a glance and in a screen reader —
  distinct styling *and* a text label, never colour alone.
- The visibility control's state MUST be re-asserted (not remembered from
  the previous reply) each time the composer opens, so a prior "internal"
  choice cannot leak into the next public reply.
- Ticket and reply bodies render as plain text; no `dangerouslySetInnerHTML`
  anywhere.
- Client-side scope decoding is never treated as authorization; every screen
  handles a server `403`.
- Full keyboard navigation and visible focus; the queue table's cells are
  associated with their column headers (accessibility).
- Responsive from ~375px through desktop; the queue table scrolls within its
  own container.
- Every screen has an explicit loading state and an explicit error state.

**Derived from:** Non-Functional / Security Requirements section of the
source.

## Out of Scope

- Customer-facing ticket UI — Story US-5.3.
- Account/profile self-service — US-5.2; admin console — US-5.4.
- Auto-assignment, routing rules, SLA dashboards, queue metrics — explicitly
  out of US-4.4 too.
- Attachments — blocked on the unwritten attachment-upload story.
- Any backend/API/DB change. This Story implements only against already-shipped
  backend endpoints; it does not add, modify, or design any API route,
  request/response contract, or database schema/table/column. `API_DESIGN`
  and `DB_DESIGN` are `NOT_APPLICABLE` for US-5.5, per Assumption #7.

**Derived from:** Out of Scope section of the source (backend-change bullet
expanded per Assumption #7: "`API_DESIGN` / `DB_DESIGN` record
`NOT_APPLICABLE`").

## Open Questions

None. All five Open Decisions raised by `us-clarifier`
(`docs/decisions/US-5.5-open-decisions.md`, OD-1–OD-5) have been resolved by
explicit human decision on 2026-09-14. See
[Decisions Resolved by Human (2026-09-14)](#decisions-resolved-by-human-2026-09-14)
below for the resolution text and where each lands in this specification.

## Decisions Resolved by Human (2026-09-14)

`version: 1` of this specification carried OD-1–OD-5 as unresolved Open
Questions, deferring their resolution to `HUMAN_SPEC_APPROVAL` — an approval
that did not in fact carry any resolution back into the spec text.
`PLAN_REVIEW` returned `BLOCKED` on that basis, and `story-orchestrator`
redirected the story to `CLARIFICATION`
(`docs/workflow/history.jsonl`, `2026-09-14T02:20:00Z`), where a human
stakeholder supplied the following resolutions, each now incorporated into
the Functional Requirement(s) named:

| OD | Resolution | Incorporated in |
|----|------------|------------------|
| OD-1 | Assignee identity (queue + detail) renders as a shortened/truncated UUID; no backend-provided display name exists and no opportunistic name-resolution call is made. | FR-1, FR-3 |
| OD-2 | No agent-directory/enumeration endpoint exists; "assign to another agent" and the queue's "a specific agent" filter are both a raw-UUID text input. | FR-1, FR-2 |
| OD-3 | The detail screen's current-assignee value (backing the "assign" affordance) is a navigation-state handoff from the queue row that opened it, updated afterward from assign/unassign responses; treated as unknown/stale if opened by direct URL. | FR-3, FR-6 |
| OD-4 | The agent console and the customer ticket list share one authenticated app shell with a `tickets:read`-gated `/agent/*` nav entry, alongside `/tickets` — no separate entry point, no role switcher. | FR-11 (new) |
| OD-5 | Close/reopen is a single action button — no `reason` field collected, no confirmation modal — mirroring US-5.3 FR-7/FR-8. | FR-7 |

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AG-AC1 | "Given an agent holding tickets:read on /agent/tickets Then GET /support/tickets renders every non-closed ticket with ticket_number, subject, category, status, assignee and updated_at, oldest-updated first And status / category / assignee_id filters re-request the queue and reset the cursor And assignee_id=me and assignee_id=none are offered as one-click presets, mutually exclusive (US-4.4's assignee_id takes a single value; a union of the two is not expressible) And a non-null next_cursor drives \"Load more\"; no total count or page number is displayed" | FR-1 |
| AG-AC2 | "Given an agent holding tickets:write on a ticket in the queue When they choose \"Assign to me\" Then POST /support/tickets/{id}/assign is called with their own id and the row reflects the new assignee When they assign to another agent, or unassign Then the corresponding assign / DELETE assign call is made and the queue is invalidated And a 409 (closed ticket) or 422 (assignee is not an agent) renders its problem+json detail" | FR-2 |
| AG-AC3 | "Given an agent opening a ticket Then GET /support/tickets/{id} renders the ticket header and the full thread And internal-visibility replies are rendered visually distinct from public ones and explicitly labelled \"internal\" And \"Load older replies\" pages the thread by its own cursor" | FR-3 |
| AG-AC4 | "Given an agent on a ticket that is not closed Then the composer's visibility control defaults to \"public\" When they submit a public reply Then POST /{id}/replies is called with visibility \"public\" and the ticket detail is invalidated, because the server may set first_response_at and move the status to waiting_on_customer When they submit an internal note Then visibility \"internal\" is sent and the note renders in the internal style, with no status change expected And choosing \"internal\" is a deliberate, visible action — never the default and never a silent state" | FR-4 |
| AG-AC5 | "Given an agent on a ticket in open, waiting_on_support or waiting_on_customer When they resolve it with a non-empty resolution_note (1..5000) Then POST /{id}/resolve is called and the screen reflects status \"resolved\" And an empty note blocks submission client-side with a field-level error And a 409 on a closed ticket renders the returned problem+json detail" | FR-5 |
| AG-AC6 | "Given any agent ticket detail screen Then only actions valid for its current status are offered: | status | offered | open | reply, assign, resolve, close | waiting_on_support | reply, assign, resolve, close | waiting_on_customer | reply, assign, resolve, close | resolved | reply, assign, close, reopen | closed | (none) And an agent holding tickets:read but not tickets:write sees a read-only view with every write control disabled" | FR-6, FR-7 |
| AG-AC7 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | FR-8 |
| AG-AC8 | "Given POST /{id}/replies returns 429 with a retry-after signal Then the UI shows a message naming when the agent may retry and disables the submit control until then And it does not auto-retry in a loop" | FR-9 |
| AG-AC9 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | FR-10 |

FR-11 has no corresponding row above: it traces to resolved Decision OD-4
(the story's own Open Question #2), not to an Acceptance Criterion — no AC
in this Story tests navigation placement.
