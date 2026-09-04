---
artifact_type: api_design
story: US-4.1
version: 3
status: ARCHIVED
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: openapi-designer
inputs:
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
  - path: docs/reviews/designs/US-4.1-design-review.md
    version: 2
supersedes: 2
---

# API Design: Support Tickets (Create) (US-4.1 / spec US-4.1)

**Source spec:** docs/specifications/US-4.1-spec.md (version 1)
**Spec review:** docs/reviews/specifications/US-4.1-spec-review.md (PASS, version 1)
**OpenAPI fragment:** docs/designs/api/US-4.1-openapi.yaml

## Revision Note (v3)

Responds to `docs/reviews/designs/US-4.1-design-review.md` (version 2,
verdict `CHANGES_REQUIRED`, routed `changes_required_api`). This revision
addresses:

- **DR-4 (Critical, API design / cross-model BR-010).** Neither `POST` nor
  `GET /v1/support/tickets` stated which authorization mechanism actually
  gates the route, and the prior wording ("a caller without
  `tickets:write`-equivalent customer ownership context", "a staff-role
  account") named no real check. `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`
  and `docs/impact-analysis/US-3.2-impact-analysis.md` (human-resolved
  2026-09-01) confirm the shipped mapping: `customer` holds **zero**
  scopes; `tickets:read`/`tickets:write` belong only to `support_agent` and
  `admin`. This is now stated explicitly, per operation, below: `POST` and
  the customer-facing branch of `GET` are gated by identity/ownership only
  (`app/modules/users/dependencies.py`'s `CurrentUserDep` — proves a valid,
  non-revoked session only; it carries no `tickets:*` scope requirement),
  matching how this project's other self-service endpoints
  (`profile/router.py`, `account/router.py`) gate solely on `CurrentUserDep`
  with no scope dependency; `GET`'s staff-rejection branch checks
  the actual scope — caller holds `tickets:read` or `tickets:write` (i.e.
  is `support_agent` or `admin`) — via
  `app/modules/roles/dependencies.py`'s `require_scope(...)` factory, the
  same mechanism `audit/dependencies.py`'s `require_audit_read` builds on.
  `DB_DESIGN` needs no change — `customer` intentionally holding zero
  `tickets:*` scopes is already the correct, shipped state; only this
  document's and the contract's authorization language needed to say so.
- **DR-5 (Minor, internal consistency).** `US-4.1-openapi.yaml`'s
  `TicketRead.id` description said "not this contract's own addition,"
  contradicting this document's own Open Questions #7 ("`id` is this
  contract's own addition"). Fixed in `US-4.1-openapi.yaml` to match this
  document — `id` **is** this contract's own addition.

DR-1/DR-2/DR-3 were resolved by the prior revision (v2) and DB_DESIGN's own
re-run; DR-6 is a database-design accuracy note outside this stage's scope,
unaffected by this revision.

**Citation-accuracy note.** `CurrentUserDep` (`app/modules/users/dependencies.py`)
was read directly for this revision: it proves a valid, non-revoked session
only (via `UserService.get_authenticated_user`'s session/revoke_before/
perm_epoch checks) and carries no notion of account-active status. This
document does not claim `CurrentUserDep` itself enforces FR-5's
`403 account-deactivated` case — that response is unchanged from prior
versions of this contract, and how it reaches this route remains a
`service-and-router-builder` implementation concern, not something DR-4
required this stage to resolve.

## Endpoints

### `POST /v1/support/tickets`

Idempotent ticket creation (FR-1). **Authorization: identity/ownership only**
— `CurrentUserDep` (a valid, non-revoked session; carries no `tickets:*`
scope). This is deliberate, not an omission: the shipped role/permission
seed data (`migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`)
grants `tickets:write` only to `support_agent`/`admin`, and `customer` holds
zero scopes, so a `require_scope("tickets:write")` gate on this route would
make ST-AC1 unbuildable for real customers. FR-5's separate
`403 account-deactivated` case (see below) is an unchanged, already-covered
part of this contract, not part of this fix — read literally, `CurrentUserDep`
alone does not check account-active status (`get_authenticated_user` checks
session validity/revocation/permission-epoch only); how the account-active
check reaches this route is a `service-and-router-builder` implementation
concern this contract does not fix, consistent with the account-deactivated
response already being unchanged since v1. `201` with the created ticket — including a
`ticket_number` that must not be guessable or enumerable as an API identifier
(a data-layer generation concern for `db-designer`, not decided here; this
contract only states the constraint on the response field). `status` is
always `"open"`; no SLA field is present. A confirmation email is queued
(not sent inline, not modeled in this contract) and an audit trail entry
for `ticket_created` is written server-side — the destination table/schema
for that entry is a `db-designer` concern, not decided or named here.

Replaying the same `Idempotency-Key` within 24 hours returns `201` with the
**original** ticket (FR-4) — same status code as first creation, not `200`,
per the spec's own wording ("respond `201` with the original ticket").
Reusing the key with a different request body returns `422
idempotency-key-reuse`.

`422 validation-failed` covers: empty `subject`, `subject` over 150 chars,
`body` over 5000 chars, an unrecognized `category` (OD-3 — see Open
Questions), and a missing `Idempotency-Key` header (OD-2 recommendation,
since no AC states this case). `403 account-deactivated` for an
authenticated-but-deactivated caller (FR-5). `429` with `Retry-After` after 5
ticket creations in the last hour (FR-6). `422 attachment-not-owned` when
`attachment_ids` references an id owned by another user, already bound to
another ticket, or unknown (FR-7) — the response never distinguishes which
of the three applied.

### `GET /v1/support/tickets`

Cursor-paginated listing of the caller's own tickets, newest first (FR-2).
**Authorization is two-branch, not a single check:** the customer-facing
branch is identity/ownership only — `CurrentUserDep` (a valid, non-revoked
session), no `tickets:*` scope required, same as `POST`. Per OD-4's
recommendation, this story scopes the endpoint to customer callers only; a
caller who actually holds `tickets:read` or `tickets:write` (i.e. is
`support_agent` or `admin`, checked via
`roles.dependencies.require_scope("tickets:read")` /
`require_scope("tickets:write")`, the same mechanism
`audit/dependencies.py`'s `require_audit_read` builds on) is rejected with
`403 agent-queue-not-available` — full permission-scoped agent queue
behavior is explicitly Out of Scope for this story and belongs to a
not-yet-written queue-view story. `422 validation-failed` on a malformed
`cursor` or an out-of-range `limit`, mirroring the cursor-pagination
convention already established by `US-3.1-spec.md` FR-4 /
`US-3.1-api-design.md`.

## Cross-Cutting Patterns Reused, Not Invented

- **Authorization mechanism (DR-4 fix).** `POST` and `GET`'s customer
  branch use `app/modules/users/dependencies.py`'s `CurrentUserDep` alone —
  the same identity/ownership-only pattern this project's other
  self-service (non-admin) endpoints use — deliberately carrying no
  `tickets:*` scope requirement. `GET`'s staff-rejection branch reuses
  `app/modules/roles/dependencies.py`'s `require_scope(...)` factory, the
  same mechanism `audit/dependencies.py`'s `require_audit_read` wraps for
  `audit:read`. Neither is a new authorization mechanism for this project.
- `401` on both endpoints and the `application/problem+json` / RFC 7807
  `ProblemBase` envelope are the same shape every other module in this
  project uses (`US-3.1-openapi.yaml` `ProblemBase`, reused verbatim here).
- `422 validation-failed`'s body shape (`errors: [{field, message, code}]`)
  reuses `app/core/exceptions.py`'s `FieldError` dataclass — not a new
  shape.
- The `429`/`Retry-After` mechanism (FR-6) reuses
  `app/modules/email_verification/exceptions.py`'s `TooManyAttemptsError`
  pattern (a `ProblemError` subclass that sets `self.headers = {"Retry-
  After": ...}` dynamically); the `type` slug follows `US-3.1-openapi.yaml`'s
  more recent `too-many-requests` naming rather than
  `email_verification`'s own `too-many-attempts`, since US-3.1 is the newer
  precedent for a project-wide slug (see Open Questions #3 below — the spec
  itself names neither).
- Cursor-pagination query parameters (`cursor`, `limit`) and their `422`
  behavior on malformed/out-of-range input reuse `US-3.1-openapi.yaml`'s
  `GET /v1/admin/users` pattern verbatim, per OD-4's own recommendation to
  follow that precedent.
- `ProblemBase` (`type`, `title`, `status`, `detail`, `instance`) is the
  identical schema `US-3.1-openapi.yaml` defines — not redefined here beyond
  a `$ref`-equivalent restatement for this fragment's self-containment.

## Decisions Adopted From Open Decisions (engineering calls, not product/business ones)

The spec review passed with five Open Decisions still open (OD-1–OD-5),
each already carrying a reasoned candidate `Recommendation` in
`docs/decisions/US-4.1-open-decisions.md`. Consistent with this skill's own
rule — log a spec gap rather than silently deciding it — this design adopts
the *engineering-mechanism* recommendations (OD-1, OD-2, OD-4, OD-5) so the
contract is buildable, while explicitly declining to invent the one
*business/domain* value list (OD-3) the open-decisions doc itself flags as
needing a stakeholder, not the harness. Every adoption below is flagged in
Open Questions and is a design assumption for `PLANNING`/`DB_DESIGN` to
confirm or override, not a final resolution — only `/so:approve` at a human
gate resolves an Open Decision.

- **OD-1 (attachment binding built now, not rejected).** `attachment_ids` is
  a live request field and `attachment-not-owned` is a real `422`, per OD-1's
  recommendation (option a: minimal `attachments` table + binding logic now,
  no upload endpoint). If this recommendation is overridden before
  `DB_DESIGN`, this contract's `attachment_ids` field and its `422
  attachment-not-owned` response must be removed or replaced with an
  unconditional rejection.
- **OD-2 (idempotency mechanics).** The response contract only states what a
  caller observes: `201` (create or replay), `422 validation-failed` for a
  missing header, `422 idempotency-key-reuse` for a same-key/different-body
  retry. Per-user key scoping and full-payload-hash comparison are
  server-side mechanism, not visible in this contract, but are recorded here
  so `data-layer-builder` does not have to re-derive OD-2's recommendation.
- **OD-4 (GET scope + pagination).** Customer-only scope, `403` for a
  caller holding `tickets:read`/`tickets:write` (see DR-4 fix above for the
  actual mechanism), `cursor`/`limit` semantics borrowed from `US-3.1`. The
  accepted `status` query values (see Open Questions #2) are this contract's
  own choice, not OD-4's.
- **OD-5 (plain-text body).** No Markdown rendering pipeline is introduced;
  `body` is stored and returned as submitted plain text. This satisfies the
  NFR's hard requirement (never render user-supplied HTML) trivially and
  needs no schema-level representation beyond a length cap already covered
  by FR-3.

## Open Questions Not Resolved by the Spec (deferred to PLANNING/DB_DESIGN, not decided here)

1. **`category`'s enum values (OD-3).** This contract declares `category` as
   a required string in `CreateTicketRequest` but does **not** enumerate
   valid values — OD-3 explicitly states this needs a stakeholder-supplied
   list, not an inferred one. `schema-builder` cannot finalize
   `CreateTicketRequest.category`'s validation until OD-3 is resolved by a
   human decision; this is flagged, not guessed.
2. **`status` query parameter's accepted values on `GET`.** Not stated by
   the spec beyond "the caller's own tickets." This contract enumerates the
   full lifecycle from `business-glossary.md`'s `Support Ticket` entry
   (`open`, `waiting_on_support`, `waiting_on_customer`, `resolved`,
   `closed`) even though this story only ever produces `open` tickets —
   filtering by a status this story cannot produce simply yields an empty
   page, not an error, matching how other list endpoints in this project
   treat structurally valid but currently-empty filters.
3. **429 and idempotency-reuse `type` slug names.** Neither is named by the
   spec's Error Envelope. This contract uses `too-many-requests` (FR-6,
   following `US-3.1`'s naming) and `idempotency-key-reuse` (FR-4, taken
   verbatim from the spec's own prose, which is the one case where the spec
   does name its own slug).
4. **`agent-queue-not-available` is a slug this contract invents.** Not
   named anywhere in the spec (which only says agent behavior is Out of
   Scope); a future queue-view story may replace this `403` behavior
   entirely rather than reuse this slug.
5. **List response envelope field names (`items`/`next_cursor`).** Reused
   verbatim from `US-3.1-openapi.yaml`'s `UserListResponse` shape for
   consistency, not derived from this story's spec.
6. **`limit`'s valid range/default.** Not stated by the spec. This contract
   reuses `US-3.1`'s own unstated choice (`maximum: 100`) for consistency
   rather than picking an unrelated number.
7. **Ticket identifier fields.** The response exposes both an opaque `id`
   (UUID, not guessable, suitable as an internal/future path parameter) and
   the human-readable `ticket_number`. The spec only names `ticket_number`;
   `id` is this contract's own addition, matching this project's existing
   pattern of every `*Read` schema carrying a UUID `id` distinct from any
   human-facing identifier (e.g. `UserRead`).
