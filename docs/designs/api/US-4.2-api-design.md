---
artifact_type: api_design
story: US-4.2
version: 3
status: ARCHIVED
created_at: "2026-09-04T20:30:00Z"
updated_at: "2026-09-05T10:15:00Z"
produced_by: openapi-designer
inputs:
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/designs/api/US-4.2-api-design.md (v2)
---

# API Design: Ticket Replies (US-4.2 / spec US-4.2)

**Source spec:** docs/specifications/US-4.2-spec.md (version 6)
**Spec review:** docs/reviews/specifications/US-4.2-spec-review.md (PASS, version 6, no blocking findings — one carried-forward non-blocking Low, see Open Questions #1)
**OpenAPI fragment:** docs/designs/api/US-4.2-openapi.yaml

## Revision Note (v3)

v2 of this document was produced against specification v5 / review v5 /
open-decisions v2, on the reading that `HUMAN_SPEC_APPROVAL`'s silent,
comment-free approval of v5 confirmed OD-8's v5 working default (a customer
reply on a `"resolved"` ticket stays `"resolved"`). `DESIGN_REVIEW` v2
(`docs/reviews/designs/US-4.2-design-review.md`) found that reading incorrect
— that approval did not constitute an actual per-item OD-8 resolution the way
OD-1–OD-7 were confirmed — and returned `BLOCKED` (Finding DR-1). The human
then supplied OD-8's actual resolution directly in-session
(`docs/decisions/US-4.2-open-decisions.md` v3, 2026-09-05T09:00:00Z):
**a customer reply on a `"resolved"` ticket is accepted (`201`) and the
ticket's status transitions to `"waiting_on_support"`** — reopening it, using
the same target status the ordinary `"waiting_on_customer"` case already
produces. This is candidate (b), not v2's candidate (a). Specification v6 /
review v6 (PASS) now state this directly in FR-2/FR-6. This revision updates
every place v2 described the resolved-ticket customer-reply case as
status-preserving; no other endpoint shape, schema, or authorization rule
changes from v2 — the contract's structure was already correct, only this one
status-transition outcome was wrong.

## Endpoints

### `POST /v1/support/tickets/{id}/replies`

Creates a threaded reply on a ticket (FR-1, FR-2, FR-5, FR-6, FR-7).
**Authorization is actor-kind-dependent, not a single check:**

- **Agent branch (FR-1):** caller holds `tickets:write`
  (`support_agent`/`admin`, per the shipped seed data —
  `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`, the same
  scope US-4.1's `GET` staff branch checks), via
  `app/modules/roles/dependencies.py`'s `require_scope("tickets:write")`
  factory. Not ownership-scoped — an agent may reply to any ticket, not just
  ones assigned to them (this codebase has no assignment concept — OD-2).
- **Customer branch (FR-2):** caller is the ticket's `requester_id`
  (`CurrentUserDep` — a valid, non-revoked session; no `tickets:*` scope
  required, matching `customer` holding zero scopes). Checked by loading the
  ticket and comparing `requester_id`, the same ownership pattern this
  project already uses for self-service resources.
- **Neither branch:** an authenticated caller who is neither the ticket's
  requester nor holds `tickets:write` responds `404 not-found`, generalizing
  FR-4's cross-customer/insufficient-scope enumeration-prevention rule
  (stated by FR-4 for `GET`) to this endpoint's own authorization surface.
  Under the shipped role seed, `tickets:read` and `tickets:write` are always
  granted together (`support_agent`, `admin`) — so in practice this branch
  only ever fires for "a different customer" or a staff account holding
  neither scope, not for a hypothetical read-only-agent caller. **Not
  literally stated by any FR** — flagged in Open Questions #2, not silently
  decided as a spec fact.

`201` with the created reply (`ReplyRead`). `first_response_at` is stamped on
the ticket (once, on the first public agent reply — FR-1) but is **not**
returned by this response; it is only visible via `GET`'s `TicketDetailRead`.
Requester/queue email notification (FR-1/FR-2) is a side effect not modeled
in this contract.

**Status-transition side effects** (not part of the response body, described
here because they gate which branch fires, per FR-1/FR-2/FR-6):

| Actor | Ticket status before | Result |
|---|---|---|
| Agent, public reply | any status except `"closed"` | `201`; status stays `"resolved"` if it was `"resolved"` (Resolution OD-5), else becomes `"waiting_on_customer"` |
| Agent, internal note | any status except `"closed"` | `201`; no status transition (internal notes are not customer-facing communication) |
| Customer | `"waiting_on_customer"` | `201`; status becomes `"waiting_on_support"` |
| Customer | `"resolved"` | `201`; status **transitions to `"waiting_on_support"`** — reopens the ticket (Resolution OD-8, human decision 2026-09-05T09:00:00Z; this story implements only this reply-side half of BR-017 — the 7-day auto-close job and its shared boundary constant remain unbuilt, see US-4.2-spec.md Out of Scope) |
| Customer | any other status (`"open"`, `"waiting_on_support"`) | **Not stated by any FR or AC** — see Open Questions #1 (carried from spec review's own Low finding) |
| Any actor | `"closed"` | `409 ticket-closed` (FR-6), no reply created |

**Internal-note restriction (FR-5):** a customer-submitted `visibility:
"internal"` responds `403 insufficient-permission`, no reply created. Omitted
`visibility` defaults to `"public"` for both actor kinds (Resolution OD-6 —
agent-omission defaults the same as customer-omission). This is also enforced
at the database by a `CHECK` constraint on `ticket_replies` (db-designer's
concern, not this contract's), so a request that somehow bypassed this
route's own check would still be rejected at the data layer — this contract
only describes the observable `403`.

The request body accepts the same optional `attachment_ids` array as
US-4.1's `POST /v1/support/tickets` (FR-1/FR-2, source API Contract defines
one shape for both actors). Binding is reply-scoped (a new nullable
`ticket_reply_id` column on `attachments`, Resolution OD-1) — this contract
states only the observable `422 attachment-not-owned` behavior (same shape,
same non-disclosure rule as US-4.1 FR-7/BR-016), not the persistence
mechanism.

`422 validation-failed` covers an empty `body` or one exceeding 5000
characters (FR-7). `429` with `Retry-After` after 30 replies by this caller
in the last hour (NFR, following US-4.1 FR-6's shipped pattern).

### `GET /v1/support/tickets/{id}`

Returns one ticket plus its reply thread, cursor-paginated (FR-3, FR-4, GET
Thread Pagination / Resolution OD-3). **Authorization:**

- **Customer branch:** caller is the ticket's `requester_id`
  (`CurrentUserDep`, identity/ownership only — same pattern as `POST`'s
  customer branch and US-4.1's `GET /v1/support/tickets`). Internal-visibility
  replies are excluded from the response **and** cannot leak via the
  application layer even if it forgets to filter, because a PostgreSQL Row
  Level Security policy on `ticket_replies` hides
  `visibility='internal'` rows from any connection whose session context
  carries the customer role (FR-3; RLS mechanics are db-designer's concern).
- **Agent branch:** caller holds `tickets:read` (or `tickets:write`, which
  the shipped seed grants alongside it), same
  `require_scope("tickets:read")` mechanism as US-4.1's staff branch. Sees
  every reply, `internal` ones included and marked as such.
- **Neither branch:** a different customer's ticket, or an authenticated
  agent lacking `tickets:read`, responds `404 not-found` (FR-4) —
  deliberately not `403`, to avoid confirming the ticket id exists (same
  enumeration-prevention rationale as US-1.3's self-scoped profile
  endpoint's exception, TR-AC4's own citation).
- **No token at all:** `401` (Resolution OD-7).

Reply-thread pagination reuses the `cursor`/`limit` query-parameter and
`items`/`next_cursor` envelope convention already established by US-4.1's
`GET /v1/support/tickets` (itself following `US-3.1`), per Resolution OD-3.
`422 validation-failed` on a malformed `cursor` or out-of-range `limit`,
mirroring that same precedent.

## Cross-Cutting Patterns Reused, Not Invented

- **Scope-check mechanism.** `require_scope("tickets:write")` /
  `require_scope("tickets:read")` (`app/modules/roles/dependencies.py`) —
  the same factory US-4.1's `GET` staff-rejection branch and
  `audit/dependencies.py`'s `require_audit_read` already use. No new
  authorization mechanism introduced.
- **`404` for enumeration prevention.** Same rationale and response shape as
  US-4.1's cross-customer case and TR-AC4's own citation of US-1.3 UP-AC7.
- **`401` / `ProblemBase` (RFC 7807) envelope.** Identical shape to
  US-4.1-openapi.yaml's `UnauthorizedProblem`/`ProblemBase`, restated here
  for this fragment's self-containment (this project's fragments do not
  cross-reference each other's files — same precedent as US-4.1 restating
  `US-3.1-openapi.yaml`'s `ProblemBase`).
- **`422 validation-failed` shape.** `errors: [{field, message, code}]`,
  reusing `app/core/exceptions.py`'s `FieldError` dataclass — identical to
  US-4.1's own `ValidationFailedProblem`.
- **`422 attachment-not-owned`.** Same slug, same status, same
  non-disclosure rule as US-4.1-openapi.yaml's `AttachmentNotOwnedProblem`
  (FR-7/BR-016 there; FR-1/BR-016 here) — not a new error shape.
- **`403 insufficient-permission`.** Reuses the slug already shipped by
  `app/modules/roles/exceptions.py` (`InsufficientPermissionError`) for the
  same "authenticated but lacks the required permission" condition, rather
  than inventing a new slug for FR-5.
- **`429`/`Retry-After`.** Same mechanism and `too-many-requests` slug as
  US-4.1-openapi.yaml's `TooManyRequestsProblem` (FR-6 there; the 30/hour
  NFR here) — the underlying rate-limit cache implementation is a
  `data-layer-builder` concern, not decided here.
- **Cursor-pagination query parameters and `items`/`next_cursor` envelope.**
  Reused verbatim from US-4.1's own `GET /v1/support/tickets` pattern
  (Resolution OD-3's own recommendation), applied here to a ticket's reply
  sub-collection rather than the top-level ticket list.
- **`ticket-closed` (409).** New slug, introduced by this story (FR-6);
  no precedent to reuse — the `problem+json` body shape (`ProblemBase`) is
  still the shared one.
- **`waiting_on_support` (status value).** Not a new status value — reuses
  the same `_TicketStatus` literal value FR-2's ordinary
  `"waiting_on_customer"` → `"waiting_on_support"` transition already
  produces (`app/modules/support/router.py`), for the resolved-ticket
  reopening case too (Resolution OD-8).

## Decisions Adopted From Open Decisions (engineering calls, not product/business ones)

Consistent with this skill's own rule — log a spec gap rather than silently
deciding it — this design adopts the already-human-resolved OD-1–OD-7
recommendations and OD-8's actual human resolution (not this document's own
prior candidate-(a) reading), all as incorporated into specification v6.
Nothing here is a new resolution; each is traced to its spec FR above.

## Open Questions Not Resolved by the Spec (deferred to PLANNING/DB_DESIGN, not decided here)

1. **FR-2's status transition for a customer reply on a ticket that is
   neither `"waiting_on_customer"` nor `"resolved"`** (e.g. `"open"` before
   any agent reply, or already `"waiting_on_support"`). Carried forward from
   `SPEC_REVIEW` v6's own non-blocking Low finding — no AC requires an
   answer (TR-AC2's Given is scoped to `"waiting_on_customer"` only), but
   `service-and-router-builder` will need one before writing FR-2's
   status-gating branches completely. This contract's `POST` response
   description states the gap explicitly rather than inventing a transition.
2. **POST's authorization for a caller who is neither the ticket's requester
   nor holds `tickets:write`.** Generalized from FR-4's `GET`-specific
   404-for-enumeration-prevention rule, not literally stated for `POST` by
   any FR. Currently unreachable in practice under the shipped role seed
   (`tickets:read`/`tickets:write` are always granted together), but the
   contract states an explicit `404` for it rather than leaving the
   `POST` endpoint's full authorization surface undefined. `DESIGN_REVIEW`
   should confirm this generalization is intended, not just convenient.
3. **`Ticket.resolved_at` does not exist in this codebase.** No FR in
   specification v6 references a `resolved_at` field or clearing behavior
   (v5's "resolved_at is not cleared" language was dropped when FR-2/FR-6
   were revised to state OD-8's actual resolution — a status transition, not
   a no-op — so this is no longer even a vacuous statement to reconcile).
   This contract's `TicketDetailRead` schema does not expose a `resolved_at`
   field, since no column exists anywhere in
   `app/modules/support/models.py` and this story does not add one.
   `db-designer` should confirm no such column is expected by this story
   before treating this as final.
4. **`first_response_at`'s exposure.** FR-1 requires stamping it but no AC
   states it must be returned by any response. This contract exposes it on
   `TicketDetailRead` (`GET`) only, matching how the spec frames it as
   ticket-level state a caller can observe, not something `POST /replies`
   itself returns.
5. **Reply-level attachment exposure.** Neither this story nor US-4.1 states
   that a reply's (or ticket's) response body must list its bound
   attachments — US-4.1's own `TicketRead` is write-only for
   `attachment_ids` (never echoed back). This contract follows the same
   precedent: `ReplyRead` does not expose attachment references. If a future
   story needs to list attachments, that is its own contract change, not
   assumed here.
6. **`limit`'s valid range/default for the reply-thread pagination.** Not
   stated by the spec. This contract reuses US-4.1's own unstated choice
   (`maximum: 100`, default `50` — matching the NFR's own pagination
   example, "paginated at 50") for consistency rather than picking an
   unrelated number.
