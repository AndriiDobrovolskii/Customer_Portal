---
artifact_type: api_design
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T00:00:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: openapi-designer
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# API Design: Agent Ticket Queue & Assignment (US-4.4 / spec US-4.4)

**Generated:** 2026-09-07
**Source spec:** docs/specifications/US-4.4-spec.md (version 1, APPROVED)
**Spec review:** docs/reviews/specifications/US-4.4-spec-review.md (PASS, version 1)
**Open decisions:** docs/decisions/US-4.4-open-decisions.md (version 1, DRAFT — OD-1..OD-4 carried forward as drafting defaults, none human-confirmed)
**OpenAPI fragment:** docs/designs/api/US-4.4-openapi.yaml

## Endpoints

### `GET /v1/support/tickets` (extended, not new)

Single route, two branches selected purely by whether the caller's token
carries `tickets:read` — no ticket lookup or ownership check is needed to
pick the branch, so the branch decision itself costs nothing. The
`operationId` (`listOwnTickets`) is kept verbatim from US-4.1 — no FR calls
for renaming published contract surface, and FR-5 requires the customer
branch to stay byte-identical, so this design treats the operationId the
same way; only the summary/description broaden in prose. Path and method
are unchanged.

**Agent branch** (`tickets:read` present, FR-1/FR-2): every ticket not in
status `"closed"` (unless `status=closed` is given explicitly), regardless
of requester, ordered oldest-`updated_at` first, stable-tiebroken by `id`.
Supports `status`, `category` (new), and `assignee_id` (new — a UUID, `me`,
or `none`) filters, cursor-paginated with no total count. Each item is an
`AgentTicketRead`, carrying `assignee_id`.

**Customer branch** (`tickets:read` absent, FR-5/FR-6): unchanged from
US-4.1 — the caller's own tickets only, `status`/`cursor`/`limit` as before.
`category` and `assignee_id` are silently ignored, never validated or
rejected (FR-6's own stated rationale: the ownership filter, not parameter
validation, is what protects the data — a `422` here would let an
unauthenticated-for-the-queue caller probe which agent-only parameters
exist). Response is `TicketListResponse` of `TicketRead` items — no field
anywhere in this branch's response exposes `assignee_id` (FR-5,
Assumption #7).

**Removed:** the `reject_agent_queue_access` dependency and
`AgentQueueNotAvailableError`/its `403 agent-queue-not-available` response
(In Scope). There is no longer any `403` on this route at all — a caller
holding neither `tickets:read` nor an owned ticket simply gets an empty
customer-branch page.

## Two Branches, One Route

This is the first endpoint in the project whose success response genuinely
differs in *shape* by caller, not just by content. The fragment models the
`200` as `anyOf: [TicketListResponse, AgentTicketListResponse]` — not
`oneOf`: `TicketRead` (an outbound schema) carries no
`additionalProperties: false` — this project's `extra="forbid"` convention
is inbound-only (AGENTS.md §4) — so an `AgentTicketRead` item (every
`TicketRead` field plus `assignee_id`) validates against both schemas at
once; `oneOf`'s exactly-one-match rule would reject every agent-branch body
outright. At the FastAPI layer this most naturally becomes
`response_model=TicketListResponse | AgentTicketListResponse` on the route
decorator, with the handler returning whichever concrete Pydantic model
matches the resolved branch — Pydantic still resolves the `Union` to the
correct member via each model's field set (`assignee_id` present/absent)
when serializing a specific instance, even though the *schema-level*
`anyOf` alone can't express mutual exclusivity. This is a contract-shape
decision, not a code decision; the concrete mechanism (`Union`
response_model vs. some other technique) is `service-and-router-builder`'s
call to make when it implements this route — flagged here only because it
is a new pattern for this codebase, not because this design leaves it
unresolved. See Open Questions #1.

## Cursor Is Branch-Specific

The customer branch's cursor keeps US-4.1's `(created_at, id)` encoding,
newest first. The agent branch needs a different total order —
`(updated_at, id)`, oldest first (Assumption #8) — so its cursor is encoded
differently. Both are opaque strings from the caller's point of view (per
this project's existing pagination convention), but a cursor obtained from
one branch is not valid input to the other. Nothing in the spec states what
happens if a caller crosses branches with a stale cursor (e.g., an agent's
scope is revoked mid-pagination); this design does not manufacture a
dedicated error for that case — a mismatched cursor is expected to fail the
same way any other malformed cursor does (`422 validation-failed`).

### `POST /v1/support/tickets/{id}/assign` (new)

Agent takes or reassigns ownership of a ticket (FR-3). **Authorization:**
caller must hold `tickets:write`.

**Check order:**

1. **Permission gate** — differentiated by scope, not ownership, and
   requires no ticket lookup at all:
   - `tickets:write` present → continue.
   - `tickets:write` absent, `tickets:read` present (a read-only agent) →
     `403 insufficient-permission` (FR-7).
   - Neither present (a customer) → `404 not-found` (FR-7) — never `403`,
     so the response never confirms the ticket id exists, consistent with
     TR-AC4/TC-AC7 (FR-7's own citation).

   This is a genuinely different check order from US-4.3's resolve/close/
   reopen ("state checked before actor," so a closed ticket 409s for every
   caller regardless of permission). Here the permission gate runs first
   because it needs no DB lookup and is purely a function of the caller's
   own token — reversing US-4.3's order would require querying the ticket
   just to decide whether to even evaluate the caller's scope. Not fixed by
   any AC either way; flagged as a design choice, not a spec requirement —
   see Open Questions #1.

2. **Ticket lookup** — unknown ticket id → `404 not-found` (same shape as
   step 1's customer case; the two 404 sources are indistinguishable by
   design).

3. **Transition validity** — ticket status is `"closed"` →
   `409 invalid-state-transition` (FR-9), reusing
   `app/modules/support/exceptions.py::InvalidStateTransitionError`
   (US-4.3) with `allowed_events=[]` rather than introducing a parallel
   exception class for the same underlying "ticket is closed" condition.

4. **Target validation** — the named `assignee_id` does not currently hold
   `tickets:write` (FR-8), or — per OD-4's unconfirmed drafting default —
   holds it but the account is deactivated → `422 validation-failed`. Runs
   after the closed-ticket check: whether the *target* is a legitimate agent
   is a separate question from whether the *ticket* can be assigned at all,
   and checking ticket-assignability first avoids a caller learning
   anything about a named user's account state on a ticket that could never
   be assigned anyway. Not spec-mandated either way — see Open
   Questions #4.

5. **Concurrency** (FR-10) — the write is a single conditional
   `UPDATE tickets SET assignee_id = :new WHERE id = :id AND status !=
   'closed' AND assignee_id IS NOT DISTINCT FROM :expected` (`:expected` is
   the `assignee_id` value read in step 2/3, `NULL` for a first assignment).
   Zero rows affected means someone else changed `assignee_id` between the
   read and this write → `409 assignment-conflict`. See "Concurrency
   Design" below for why this generalizes beyond FR-10's literal
   "unassigned ticket" wording, and why it gets its own slug rather than
   reusing `invalid-state-transition`.

`200` on success: `assignee_id` set to the target (self-assignment,
Assumption #5, follows the identical path — no FR or AC treats it
differently). A `ticket_audit_log` entry (`event=ticket_assigned`,
`actor=`the caller, `target=`the ticket) is written in the same transaction
as the write (NFR).

### `DELETE /v1/support/tickets/{id}/assign` (new)

Agent releases ownership of a ticket (FR-4). **Authorization:** identical
gate to `assign` — `tickets:write` required, same `403`/`404` split (FR-7).

**Check order:**

1. Permission gate — identical to `assign` step 1.
2. Ticket lookup — unknown ticket id → `404 not-found`.
3. Transition validity — ticket status is `"closed"` →
   `409 invalid-state-transition`, per OD-3's drafting default (**not yet
   human-confirmed** — see Open Questions #5 and spec OD-3). Reuses the same
   `InvalidStateTransitionError`/`allowed_events=[]` shape as `assign`.
4. Write — `UPDATE tickets SET assignee_id = NULL WHERE id = :id AND status
   != 'closed'`, **unconditional** on the prior `assignee_id` value (see
   "Concurrency Design" below for why this has no analogous
   `assignment-conflict` case).

`200` on success: `assignee_id` cleared to `null`. Idempotent — calling this
on a ticket that already has no assignee still returns `200`, not `404` or
`409` (no FR states otherwise, and BR-009's "logout everywhere is idempotent"
precedent is the closest analogue this project has for a repeat-clear
operation). Whether the idempotent no-op case still writes a fresh
`ticket_unassigned` audit entry is not settled by any AC — see Open
Questions #5.

## Concurrency Design

FR-10/AQ-AC10 states the requirement narrowly: two agents racing to assign
the *same currently-unassigned* ticket, exactly one wins, the other gets
`409`. This design generalizes the mechanism (a conditional `UPDATE` scoped
to whatever `assignee_id` value was just read) to cover re-assignment too —
the same conditional-update pattern the spec's own Assumptions & Defaults #6
cites as precedent (US-1.2 FR-1, US-1.4 FR-1/FR-9) — rather than writing a
narrower guard that only fires on the literal "was `NULL`" case. This mirrors
how `US-4.3-api-design.md` generalized its own `409` beyond its literal AC
wording (that design's Open Questions #2) and is flagged the same way: not
forced by any AC, but adopted because leaving re-assignment's race condition
unguarded while assign-to-unassigned is guarded would be an inconsistent,
arbitrary gap.

`unassign`, by contrast, is designed as an **unconditional** clear rather
than an optimistic-concurrency-guarded write. Unassigning is idempotent by
its nature — the operation's own postcondition (`assignee_id IS NULL`) does
not depend on what the prior value was, unlike assign's postcondition (a
*specific* target must win), so there is no "loser" to report. No AC
exercises a race on `unassign`, and this design does not invent one.

The two `409` conditions on `assign` (`invalid-state-transition` for a
closed ticket, `assignment-conflict` for a lost race) get **different**
`type` slugs deliberately: the closed-ticket case is a ticket-status-machine
violation (same family as `/resolve`/`/close`/`/reopen`'s existing `409`s),
while the lost-race case is a field-level optimistic-concurrency conflict
that has nothing to do with ticket status — collapsing them into one slug
the way US-4.3 collapsed "closed" and "lost the resolve race" (both
literally *are* status-transition failures there) would misrepresent this
one. `assignment-conflict` is a new slug, first use in this project.

## Cross-Cutting Patterns Reused, Not Invented

- **Scope-check via `current_user.scopes`.** Same source US-4.2/US-4.3's
  `resolve_actor_kind`/`reject_agent_queue_access` already read directly —
  no new authorization mechanism, though the differentiated 404-vs-403 shape
  (step 1 above) is a new *combination*, closer to
  `reject_agent_queue_access`'s if/elif shape than to
  `roles.dependencies.require_scope`'s uniform 403.
- **`404 not-found` / `TicketNotFoundError`.** Reused verbatim
  (`app/modules/support/exceptions.py`, US-4.2) for the same
  "deliberately-uniform, IDOR-safe" condition (FR-7).
- **`403 insufficient-permission` / `InsufficientPermissionError`.** Reused
  verbatim (`app/modules/support/exceptions.py`, US-4.2) — same slug/shape,
  same "authenticated, wrong permission" condition (FR-7).
- **`409 invalid-state-transition` / `InvalidStateTransitionError`.** Reused
  verbatim (`app/modules/support/exceptions.py`, US-4.3) with
  `allowed_events=[]` rather than a parallel class — same underlying
  "ticket is closed" condition US-4.3 already models (FR-9; FR-4's OD-3
  default).
- **`422 validation-failed`.** Same `errors: [{field, message, code}]` shape
  as every other module's `ValidationFailedError` (FR-8).
- **`ProblemBase` (RFC 7807) envelope.** Restated for this fragment's
  self-containment, identical shape to every prior fragment.
- **Single conditional-`UPDATE` concurrency pattern.** Same approach the
  spec's own Assumptions & Defaults #6 cites (US-1.2 FR-1, US-1.4 FR-1/FR-9,
  US-4.3 FR-9) — generalized to `assign`'s re-assignment case, per
  "Concurrency Design" above.
- **`AgentTicketRead`/`AgentTicketStateRead` as distinct schemas.** OD-1's
  recommended default, adopted as the spec's own drafting default and
  carried through unchanged here — `TicketRead`/`TicketStateRead`/
  `TicketListResponse` are restated in this fragment (for self-containment)
  but not modified.

## Decisions Adopted From Open Decisions (drafting defaults, not resolved here)

Per this skill's own rule — log a spec gap rather than silently deciding it
— this design adopts OD-1 through OD-4 exactly as the approved specification
v1 already drafted them (each explicitly marked "not yet human-confirmed" in
the spec itself). Nothing here is a new resolution:

- **OD-1 (Critical) — response schema shape.** `AgentTicketRead`/
  `AgentTicketStateRead` as distinct schemas, `TicketRead`/`TicketStateRead`
  untouched. Adopted; this is the single most structurally consequential
  decision in this design (it is why `GET /v1/support/tickets`'s `200` is
  now `anyOf`-shaped instead of a single schema). If `HUMAN_SPEC_APPROVAL`
  reverses this, the `GET` endpoint's contract collapses back to a single
  schema and the `anyOf`/branch-shape discussion above becomes moot — this
  is the design's largest single point of rework risk.
- **OD-2 (Medium) — `GET /{id}` (`TicketDetailRead`) is not extended.**
  Adopted (spec does not extend it; no FR covers it). This fragment does not
  touch `US-4.2-openapi.yaml`'s `TicketDetailRead` contract at all.
- **OD-3 (Medium) — `DELETE .../assign` on a closed ticket returns `409`.**
  Adopted for `unassign`'s step 3 above. If reversed, `unassign` would
  instead return `200`/`assignee_id: null` unconditionally, and its `409`
  response and `InvalidStateTransitionProblem` reference would be removed
  from that operation (assign's own `409` for FR-9 is unaffected either
  way).
- **OD-4 (Low) — assign-target validation also rejects a deactivated
  account.** Adopted for `assign` step 4 above, same `422 validation-failed`
  slug either way (OD-4 itself notes this only affects test coverage, not
  the contract shape) — no rework risk if reversed.

## Open Questions Not Resolved by the Spec (deferred, not decided here)

1. **`GET`'s `anyOf` response and its FastAPI mechanism.** The contract-level
   shape (`anyOf: [TicketListResponse, AgentTicketListResponse]`) is fixed
   here; the concrete `response_model` technique is left to
   `service-and-router-builder`. Also open: whether the permission gate for
   `assign`/`unassign` (404-vs-403, no ticket lookup) should be a reusable
   dependency (mirroring `reject_agent_queue_access`'s now-removed shape) or
   inlined in the service — not a contract-level decision, noted for that
   stage.
2. **Validation of a malformed `assignee_id` filter on the agent branch of
   `GET`.** Neither FR-1 nor FR-2 states what happens when `assignee_id` is
   present but is none of UUID/`me`/`none`. This design's default —
   `422 validation-failed`, mirroring the already-inherited malformed-
   `cursor`/`limit` precedent from US-4.1 — is this contract's own addition,
   not spec-mandated. Likewise, `category`'s only stated behavior (FR-2) is
   "only matching tickets are returned"; an unrecognized category value is
   simply an empty page, not an error (no allow-list exists for `category`
   at all, per US-4.1 OD-3, still unresolved).
3. **`limit`'s bounds (1-100, default 100).** Carried forward unchanged from
   US-4.1-openapi.yaml's own unstated choice — flagged there as an Open
   Question, flagged again here (spec review's Low finding) because this
   story's spec still does not state it. Not a new gap this story
   introduces.
4. **Check order between the closed-ticket check (step 3) and the
   assign-target validation (step 4) on `POST .../assign`.** No AC exercises
   a request that is simultaneously "ticket closed" and "target invalid" —
   this design picks state-before-target (see rationale in the endpoint
   section above) but the reverse order would not violate any stated AC
   either. Flagged for `DESIGN_REVIEW` to confirm, same treatment US-4.3's
   own check-order choices received.
5. **Does an idempotent no-op `DELETE .../assign` (already unassigned) still
   write a `ticket_unassigned` audit entry?** AQ-AC4 is written against "a
   ticket with an assignee" and does not cover the already-`null` case. This
   design does not commit to an answer — `service-and-router-builder` will
   need one before implementing the audit-write branch. Writing an entry
   only when the column value actually changes is the more conservative
   default (avoids audit-log noise for a genuine no-op) but is not fixed
   here.
6. **`assignee_id` display name / `users:read` gap (source Open Question
   #5).** Restated from the spec's own Open Questions — `support_agent` may
   not hold `users:read`, so a UI consuming `AgentTicketRead`/
   `AgentTicketStateRead` cannot resolve the UUID to a name itself. No FR
   proposes a display-name field and none is added here; this is context for
   whoever specs US-5.5, not a gap in this contract.
