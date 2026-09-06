---
artifact_type: api_design
story: US-4.3
version: 2
status: ARCHIVED
created_at: "2026-09-06T11:00:00Z"
updated_at: "2026-09-06T14:00:00Z"
produced_by: openapi-designer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/reviews/specifications/US-4.3-spec-review.md
    version: 3
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 1
supersedes: docs/designs/api/US-4.3-api-design.md
---

# API Design: Ticket Resolution (US-4.3 / spec US-4.3)

**Generated:** 2026-09-06 (revised 2026-09-06 after DESIGN_REVIEW CHANGES_REQUIRED, DR-3)
**Source spec:** docs/specifications/US-4.3-spec.md (version 2)
**Spec review:** docs/reviews/specifications/US-4.3-spec-review.md (PASS, version 3, one carried-forward non-blocking Low finding — see Open Questions #1 below)
**Design review:** docs/reviews/designs/US-4.3-design-review.md (CHANGES_REQUIRED, version 1) — DR-3 (resolution_note maxLength) addressed in this revision; DR-1/DR-2 are database-design-owned and addressed by DB_DESIGN, not here.
**OpenAPI fragment:** docs/designs/api/US-4.3-openapi.yaml

## Endpoints

### `POST /v1/support/tickets/{id}/resolve`

Agent marks a ticket resolved (FR-1). **Authorization:** caller must hold
`tickets:write` (`support_agent`/`admin`, via `require_scope("tickets:write")`
— same mechanism US-4.2's agent branch already uses). Not ownership-scoped:
an agent may resolve any ticket, not just ones "assigned" to them (no
assignment concept exists, per OD-2 precedent from US-4.2).

**Check order** (per the spec's own NFR, "state is checked before actor"):

1. Ticket lookup / ownership-equivalent check — unknown ticket, or a
   *customer* caller who is not the ticket's requester → `404 not-found`
   (FR-8). An agent caller always clears this check regardless of which
   ticket it names — agent scope grants visibility across all tickets, not
   ownership.
2. Transition validity — ticket status is not one of
   `open`/`waiting_on_support`/`waiting_on_customer` (i.e. it is `resolved`
   or `closed`) → `409 invalid-state-transition` (FR-6, generalized — see
   Open Questions #2). This is evaluated **before** step 3, so a `closed`
   ticket yields `409` for every caller, including one who also lacks
   permission — never `403`, so the response never confirms an
   unauthorized-but-otherwise-legitimate caller could have acted on it if
   the ticket had been in a resolvable state (FR-6's own stated rationale).
3. Permission — caller lacks `tickets:write` (the ticket's own requester,
   already confirmed a legitimate caller by step 1) → `403
   insufficient-permission` (FR-7, TC-AC6).
4. Concurrency (FR-9): the transition is a single conditional `UPDATE ...
   WHERE status IN (...)` scoped to the expected source statuses. A second,
   simultaneous resolve that loses the race finds `rowcount == 0` and is
   reported identically to step 2's `409` — not a distinct error shape; the
   loser cannot tell a genuine race from a ticket that was already in the
   wrong state when its request arrived.

Request body validation (`422 validation-failed`, FR-10: empty/absent
`resolution_note`) happens at the Pydantic schema boundary, before any of
the above — FastAPI never invokes the route body for a malformed request.

`200` on success: status becomes `"resolved"`, `resolved_at` is set (the
only timing field written — FR-1). The requester is emailed the resolution
note plus a link to the ticket detail page (FR-1/OD-8); this is a side
effect not modeled in the response body. A `ticket_audit_log` entry is
written (`event=ticket_resolved`, `actor=agent:{id}`) — also not part of the
response.

### `POST /v1/support/tickets/{id}/close`

Requester or agent closes a ticket (FR-2). **Authorization:** caller is
either the ticket's requester (`CurrentUserDep`, ownership only, no scope —
same pattern as US-4.2's customer branch) or holds `tickets:write`.

**Check order**, same shape as `/resolve`:

1. Lookup / ownership-equivalent — unknown ticket, or a customer caller who
   is neither the requester nor an agent → `404 not-found` (FR-8).
2. Transition validity — ticket status is already `"closed"` →
   `409 invalid-state-transition`. **Not literally stated by any TC-AC**
   (TC-AC5 names only `/resolve` and `/reopen`) — generalized directly from
   the story's own normative State Machine table, whose only row for
   `closed` is `"closed | — | (terminal)"`. Flagged, not silently decided —
   see Open Questions #2.
3. No permission check beyond step 1: FR-2 grants both the requester and any
   `tickets:write` agent the same success path: `200`, status `"closed"`,
   `closed_at` set. `ticket_audit_log` records `actor=self` for the
   requester or `actor=agent:{id}` for an agent (OD-6); `closed_by` is set
   to the acting user's id in both cases (OD-7).

### `POST /v1/support/tickets/{id}/reopen`

Requester or agent reopens a resolved ticket directly (FR-5; this endpoint's
success path has no covering Acceptance Criterion in the source — derived
from the source's own normative API Contract/State Machine table plus OD-3's
human-confirmed scope decision). **Authorization:** same requester-or-agent
shape as `/close`.

**Check order:**

1. Lookup / ownership-equivalent — unknown ticket, or a customer caller who
   is neither the requester nor an agent → `404 not-found` (FR-8).
2. Transition validity:
   - Ticket status is `"closed"` → `409 invalid-state-transition` (FR-6,
     TC-AC5 — this one *is* literally AC-covered for `/reopen`).
   - Ticket status is `open`, `waiting_on_support`, or `waiting_on_customer`
     (never resolved in the first place) → `409 invalid-state-transition`,
     generalized from the same normative table (only `resolved` is a valid
     `/reopen` source) — see Open Questions #2, same treatment as `/close`.
   - Ticket status is `"resolved"` **and** `now - resolved_at > 7 days` but
     the auto-close job has not yet run — **response undefined by this
     contract.** This is the spec review's own carried-forward Low finding
     (`docs/reviews/specifications/US-4.3-spec-review.md` v3, Missing Edge
     Cases): it matches neither a success path nor the closed-ticket `409`,
     and no FR states it. Not resolved here — see Open Questions #1.
   - Ticket status is `"resolved"` and `now - resolved_at <= 7 days`
     (inclusive, OD-4) → proceed to `200`.
3. No further permission check: requester and agent share the same success
   path.

`200` on success: status becomes `"waiting_on_support"` (OD-1 — **not**
`"reopened"`, which does not exist in `tickets.status`'s shipped value set
and is not introduced by this story), `resolved_at` is cleared, and a
`ticket_audit_log` entry is written (`event=ticket_reopened`, `actor=self`
for the requester or `actor=agent:{id}` for an agent).

### Side effect on the existing `POST /v1/support/tickets/{id}/replies` endpoint (FR-4, not a new operation)

FR-4 modifies the *already-shipped* US-4.2 endpoint's behavior, not this
story's own contract: when a requester posts a reply (via
`US-4.2-openapi.yaml`'s `POST .../replies`) on a ticket that is `"resolved"`
with `now - resolved_at <= 7 days` (inclusive, OD-4), status becomes
`"waiting_on_support"` and `resolved_at` is cleared — the same target status
`/reopen` produces. A notification goes to the shared support-queue address
(OD-2), not "the previously assigned agent" (no such concept exists). This
story does not re-emit or modify `US-4.2-openapi.yaml`; `service.py`'s
existing `create_reply` status-transition table gains one more row, which is
`service-and-router-builder`'s concern, not this contract's.

The auto-close job (FR-3) is a scheduled batch process, not an HTTP
endpoint, and so has no entry in `US-4.3-openapi.yaml`. It is described here
because the 7-day boundary constant it shares with FR-4/FR-5 is this
story's own cross-cutting concern (OD-4): the job's predicate is
`now - resolved_at > 7 days` (strict), and the reply/`/reopen` guards use
`now - resolved_at <= 7 days` (inclusive) — the job, not a reply or a
`/reopen` call, owns the exact boundary instant.

## Cross-Cutting Patterns Reused, Not Invented

- **Scope-check mechanism.** `require_scope("tickets:write")`
  (`app/modules/roles/dependencies.py`), identical to `/resolve`'s
  precedent set by US-4.2's agent branch. No new authorization mechanism.
- **Ownership/ambient-identity check.** `CurrentUserDep` + comparing
  `requester_id`, same pattern as US-4.2's customer branches on `POST
  .../replies` and `GET .../{id}`.
- **`404` for enumeration prevention.** Same rationale and response shape as
  US-4.2's `TicketNotFoundError` (FR-4 there, FR-8 here) — not a new slug.
- **`403 insufficient-permission`.** Reuses `app/modules/roles/exceptions.py`
  / US-4.2's `InsufficientPermissionError` slug and shape for the same
  "authenticated, wrong permission" condition (FR-7), via this module's own
  subclass (module-ownership convention already established by
  `AccountDeactivatedError`/`InsufficientPermissionError` in
  `app/modules/support/exceptions.py`).
- **`422 validation-failed`.** Same `errors: [{field, message, code}]` shape
  as every other module's `ValidationFailedError` (FR-10).
- **`409 invalid-state-transition`.** Slug already shipped by
  `app/modules/admin_users/exceptions.py::InvalidStateTransitionError`
  (US-3.1, referenced by the spec's own Error Envelope section as "shared
  with US-3.1.5"). This story's own subclass adds the `allowed_events`
  field the spec's Error Envelope Schema requires — US-3.1's version carries
  no such field, so this is a new (additively-shaped) subclass reusing the
  slug/status, not the identical class.
- **`ProblemBase` (RFC 7807) envelope.** Restated here for this fragment's
  self-containment, identical shape to every prior fragment
  (US-4.2-openapi.yaml, US-3.1-openapi.yaml, ...).
- **Single conditional-`UPDATE` concurrency pattern.** Same approach cited
  by the spec's own Assumptions & Defaults #6 ("mirrors US-1.2 FR-1 and
  US-1.4 FR-1/FR-9") — no new concurrency mechanism.

## Decisions Adopted From Open Decisions (engineering calls, not product/business ones)

Consistent with this skill's own rule — log a spec gap rather than silently
deciding it — this design adopts OD-1 through OD-8 exactly as resolved by
the human at `HUMAN_SPEC_APPROVAL` (2026-09-06T08:15:00Z) and incorporated
into specification v2. Nothing here is a new resolution; each is traced to
its FR above (OD-1/FR-4/FR-5's target status, OD-2/FR-4's notification
recipient, OD-3/FR-5's endpoint scope, OD-4/FR-3-4-5's boundary comparisons,
OD-5/FR-1's source-state set, OD-6/FR-2's audit actor, OD-7/FR-2-3's
`closed_by`, OD-8/FR-1's email link target).

## Open Questions Not Resolved by the Spec (deferred to DB_DESIGN/PLANNING, not decided here)

1. **Response for `/resolve` or `/reopen` on a `"resolved"` ticket outside
   the 7-day window but not yet auto-closed.** Carried directly from
   `SPEC_REVIEW` v3's own non-blocking Low finding — no FR or AC states this
   case's outcome. This contract deliberately leaves it undefined rather
   than inventing a response; `service-and-router-builder` will need an
   answer before writing the transition-validity branch completely. Given
   the window is narrow (bounded by how often the auto-close job runs), the
   practical exposure is small, but it is not zero.
2. **Generalizing FR-6's `409 invalid-state-transition` beyond "the ticket
   is closed."** TC-AC5's own wording — "the problem+json body lists the
   transitions actually permitted from **the current state**" — reads as
   general-purpose, and the spec review flagged exactly this ambiguity as
   inherited and non-blocking. This contract adopts the general reading for
   all three endpoints (any call from a state the normative State Machine
   table does not list as a valid source for that event gets `409`, not an
   unspecified response), because leaving most of the state space
   undefined would fail this stage's own completion criterion that every
   validation rule be represented. `DESIGN_REVIEW` should confirm this
   generalization is intended, not just convenient — same caveat US-4.2's
   own API design carried for its analogous `POST`-authorization
   generalization (its Open Questions #2).
3. **`resolution_note`'s maximum length — resolved by `DB_DESIGN`.**
   `US-4.3-db-design.md` (v1) fixed the backing column to `String(5000)` and
   directed `schema-builder` to match it. `US-4.3-openapi.yaml`
   `ResolveTicketRequest.resolution_note` now carries `maxLength: 5000`
   alongside its existing `minLength: 1` (DR-3,
   `docs/reviews/designs/US-4.3-design-review.md` v1). No longer open.
4. **`reason` field on `/close` and `/reopen`.** The source story's own API
   Contract table lists `{"reason"?: str}` for both endpoints, but no FR
   describes its purpose, persistence, or whether it appears in
   `ticket_audit_log`. This contract carries the field through as optional
   and unconstrained (accepted, reserved) rather than dropping it — its
   backing behavior is undefined here and is `service-and-router-builder`'s
   decision to make or defer further.
5. **`closed_by` and `resolution_note` exposure on the `200` responses.** No
   FR states that either write-only-at-creation field is echoed back by any
   of these three endpoints (contrast `first_response_at`, which US-4.2
   states is later visible via `GET`). Per this project's data-minimization
   convention (`docs/product/non-functional-requirements.md` NFR-012) and
   the precedent that a not-yet-finalized system-actor sentinel value
   (OD-7) shouldn't leak into a contract before `db-designer` settles its
   representation, `TicketStateRead` exposes only `id`, `ticket_number`,
   `status`, `resolved_at`, `closed_at`, and `updated_at`. If a future
   `GET` needs to surface `closed_by`/`resolution_note`, that is
   `US-4.2-openapi.yaml`'s `TicketDetailRead` to extend, not this contract.
