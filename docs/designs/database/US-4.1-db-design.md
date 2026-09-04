---
artifact_type: database_design
story: US-4.1
version: 3
status: ARCHIVED
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: db-designer
inputs:
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
  - path: docs/reviews/designs/US-4.1-design-review.md
    version: 2
supersedes: 2
---

# DB Design: Support Tickets (Create) (US-4.1 / spec US-4.1)

**Source spec:** docs/specifications/US-4.1-spec.md (version 1)
**API design:** docs/designs/api/US-4.1-api-design.md, US-4.1-openapi.yaml (version 3)

## Revision Note (v3)

Responds to `docs/designs/api/US-4.1-api-design.md` v3 (which itself resolved
`docs/reviews/designs/US-4.1-design-review.md` version 2's DR-4/DR-5) and
fixes DR-6, the one version-2 finding still open against this stage:

- **API_DESIGN v3 (authorization language only).** v3's own Revision Note is
  explicit: "`DB_DESIGN` needs no change — `customer` intentionally holding
  zero `tickets:*` scopes is already the correct, shipped state; only this
  document's and the contract's authorization language needed to say so."
  This design was already consistent with that shipped state (it declares no
  role/scope column or check anywhere) — this revision therefore carries no
  substantive schema change from v2, only the version bump of the `api_design`
  input this staleness re-run requires.
- **DR-6 (Minor).** v2's `audit_log` table below described `actor_role` as
  "already resolved by auth middleware upstream." Read directly,
  `app/modules/audit/service.py`'s `_resolve_actor_role` is not middleware —
  it is a service-to-service call from the audit service to
  `app/modules/roles/service.py`'s `get_role_grants_for_user` (via the
  `RoleServiceProtocol` collaborator the audit service already takes),
  following exactly the `AGENTS.md` §3 "cross-module calls go service →
  service" rule this design's own "Cross-module layering note" (below)
  already states for the write path. Corrected in the `audit_log` table
  below.

DR-1/DR-2/DR-3 were resolved by v2 and remain fixed, unaffected by this
revision. Everything else in this design (the `tickets`/`attachments` shape,
indexes, BR-007 FK gap, OD-3 deferral, Valkey mechanisms) is materially
unchanged from v2 — restated below for a single coherent document, not
re-litigated.

## Overview

Two new tables (`tickets`, `attachments`) plus a new write path into the
existing `audit_log` table, and two Valkey-only mechanisms (idempotency
replay, ticket-creation rate limiting — noted for `cache.py`, not decided
further here). No existing table's schema changes.

## The central scoping decision, and why it narrows the story's own Data Model Notes

The source story's Data Model Notes list a `tickets` shape spanning the whole
ticket lifecycle: `assignee_id`, `first_response_at`, `resolved_at`,
`resolution_note`, `closed_at`, `closed_by` — none of which this story's FRs
read or write. The spec's own Out of Scope section is explicit: "Replies
(US-4.2) and status transitions (US-4.3)" and "Agent queue views, assignment
and routing" belong to later stories. This design builds only the columns
FR-1 through FR-7 actually require and defers the rest — adding them later is
an ordinary additive (`ALTER TABLE ... ADD COLUMN`, nullable) migration in
whichever of US-4.2/US-4.3 first needs them, not a destructive change this
story would need to plan around under `AGENTS.md` §4's expand/migrate/contract
rule. Building unused columns now would also leave them untested until those
stories land, which is worse than adding them when their own acceptance
criteria exist to verify them.

## New table: `tickets`

The ticket record itself (FR-1, FR-2, FR-3). Unchanged from v2.

- `ticket_number` is generated server-side from a dedicated PostgreSQL
  `SEQUENCE` (`ticket_number_seq`), formatted `CP-{year}-{seq:07d}` — this
  keeps the numeric portion monotonic and collision-free under concurrent
  inserts without an application-level lock, the same reason `AuditLog`'s
  `row_hash`/`previous_hash` are computed server-side rather than in Python.
  **FR-1's non-guessability requirement is satisfied structurally, not by
  obscuring the number:** the API design (Open Question #7) already makes
  the opaque UUID `id` the only identifier any future lookup/path parameter
  would use, so `ticket_number` looking sequential is a display convenience,
  never an authorization boundary — guessing the next number reveals
  nothing reachable through the API contract this story defines.
- `category` is a plain `String`, not a PostgreSQL `ENUM` or a `CHECK`
  constraint — OD-3's value list is explicitly a stakeholder decision, not
  an inferable one (`docs/decisions/US-4.1-open-decisions.md`). Adding an
  enum type now would mean guessing the very list OD-3 says not to guess.
  Once OD-3 resolves, a follow-up migration can convert the column without
  this story's data needing a backfill (only four rows worth of categories
  would ever exist as `open`-only tickets from this story). `String(50)`
  already matches `CreateTicketRequest.category`'s/`TicketRead.category`'s
  `maxLength: 50` (`US-4.1-openapi.yaml` v3, unchanged from v2's DR-2 fix).
- `status` reuses the plain-`String` pattern `users.status` already
  establishes in this codebase (not a DB-level enum) — this story only ever
  writes `"open"`, but the column must already accept the full lifecycle
  business-glossary.md's Support Ticket entry names, since US-4.3 changes
  this same column's value, not its type.
- `requester_id` is a real FK to `users.id` — unlike this project's audit
  tables, a ticket is a primary business record, not a forensic log entry,
  so referential integrity during normal operation is worth having. No
  `ondelete` is specified (defaults to `RESTRICT`), which is a deliberate
  gap, not an oversight: `BR-007`'s account-deletion/anonymization job
  mechanics are explicitly "pending legal/DPO sign-off," so this design
  cannot know today whether a customer's tickets should be reassigned,
  anonymized in place, or block the deletion outright. `RESTRICT` is the
  safe default until that job's own story states an answer — it fails loud
  (a blocked delete) rather than silently orphaning or cascading away a
  customer's support history. Flagged for whichever story implements
  BR-007's deletion job.

## New table: `attachments`

Per OD-1's adopted recommendation (`docs/decisions/US-4.1-open-decisions.md`
OD-1, adopted in `US-4.1-api-design.md`): minimal ownership/binding tracking
now, no upload endpoint. Unchanged from v2. Deliberately excludes every
column the actual upload mechanic would need — `filename`, MIME type, size,
storage location/key — since upload itself (with its own size caps, MIME
allowlist, AV scanning) is out of scope for this story per the spec; a future
upload-story migration adds those columns additively. This story's tests
seed `attachments` rows directly, exactly as OD-1's recommendation says.

- `id` is `UUIDv4`, generated application-side (`default=uuid.uuid4`) — the
  spec's own NFR states attachment ids "MUST be UUIDv4, never sequential,"
  which the same non-enumerability reasoning as `ticket_number` applies to
  directly (unlike `ticket_number`, here the UUID *is* the id used in the
  ownership check, so it must actually be unguessable, not just display).
- `uploaded_by` is a real FK to `users.id`, same `RESTRICT`-by-default,
  same BR-007 gap as `tickets.requester_id` above — not re-argued twice.
- `ticket_id` is nullable (unbound state) and, once set, is never
  cleared or reassigned by any code path this story builds — "an
  attachment belongs to exactly one ticket forever" (FR-7) is enforced at
  the service layer (no `UPDATE ... SET ticket_id = NULL` code path exists
  to write), not by a DB trigger; the schema permits a later `UPDATE` in principle,
  but this story never issues one. A DB-level immutability trigger would be a
  reasonable hardening step but is not something the spec's ACs require, and
  is flagged here rather than invented.
- `created_at` exists specifically for the 24-hour unbound-attachment purge
  job (FR-7's last sentence) to filter on; no `updated_at` — nothing about
  an attachment changes after creation in this story's scope besides the
  one-time `ticket_id` bind, which isn't itself surfaced in any response.

## Audit trail: writes into the existing `audit_log` table (DR-1 fix — no new table)

v1 invented a `ticket_audit_log` table on a cited precedent
(`AuthAuditLog`/`AdminAuditLog`/`AccountLifecycleAuditLog`) that does not
exist in this codebase, and contradicted this project's actual,
already-decided audit architecture: `docs/designs/database/US-3.3-db-design.md`
(and its shipped model, `app/modules/audit/models.py`) resolved `audit_log`
— a single, physical, daily-partitioned, hash-chained table — as *"the write
target for [new] event types"* going forward. `ticket_created` is exactly
that: a new event type from a new module, not a continuation of one of the
four frozen-shape legacy tables (`auth_audit_log`, `admin_audit_log`,
`profile_audit_log`, `account_lifecycle_audit_log`). No new table is added by
this story for auditing.

FR-1's `ticket_audit_log` entry (`event=ticket_created`) is a new row in
`audit_log`, using its existing columns:

| `audit_log` column | Value for `ticket_created` |
|---|---|
| `category` | `"tickets"` — a new literal; the four `US-3.3` string literals (`auth`/`admin`/`profile`/`account_lifecycle`) are the four legacy tables' own `category` values in the `audit_log_history` view, not an exhaustive enum on `audit_log` itself, so adding a fifth literal here doesn't touch that view or those tables |
| `actor_id` | `requester_id` (the caller who created the ticket) |
| `actor_role` | Caller's role at creation time, if available at the call site; `NULL` otherwise — this FR does not require capturing it, matching the "not every event populates every field" rule `US-3.3-db-design.md` already states for this column. **(DR-6 fix)** Resolved via a service-to-service call, not middleware: `app/modules/audit/service.py`'s `_resolve_actor_role` helper calls the `RoleServiceProtocol` collaborator's `get_role_grants_for_user` (backed by `app/modules/roles/service.py`), joining sorted role names with a comma when a user holds more than one — the same `AGENTS.md` §3 service-to-service pattern this design's own "Cross-module layering note" below already requires for the ticket-creation write path itself |
| `event` | `"ticket_created"` |
| `target_id` | `ticket.id` — the record the event is about, same semantic `US-3.3-db-design.md` documents for `admin_audit_log`'s `target_id` mapping |
| `outcome` | `"success"` — this event is only ever written after the ticket row and its idempotency/rate-limit checks have all passed; there is no `ticket_creation_failed` event this story defines |
| `request_id` | Populated from the same per-request id every other module's audit write already threads through (`record_self_audit`/`record_access_denied` precedent in `app/modules/audit/repository.py`), if the request middleware exposes one to this module; not a new concept |
| `ip` / `user_agent` | `NULL` — FR-1 does not require capturing them for this event, and inventing forensic columns no AC reads would repeat exactly the mistake DR-1 flagged (columns no requirement asks for) |
| `payload` (`JSONB`) | `{"ticket_number": <str>, "category": <str>}` — enough for a human reviewing the audit trail to identify the ticket without re-deriving it from `target_id`, and nothing duplicative of `tickets.subject`/`.body` (no reason to copy free-text customer content into a second table) |
| `previous_hash` / `row_hash` | Trigger-computed on insert, same as every other `audit_log` row — `ticket_created` gets the same tamper-evidence guarantee AU-AC7 already built, which `ticket_audit_log` (no hash columns, no trigger) would not have provided |

**Cross-module layering note (for `IMPACT_ANALYSIS`/`ARCHITECTURE_PLANNING`,
not decided further here):** `audit_log` and `AuditRepository` are owned by
`app/modules/audit`, not by this story's `support`/`tickets` module.
`AGENTS.md` §3's "cross-module calls go **service → service**" rule means the
tickets service must not import `AuditRepository`/`AuditLog` directly — it
calls a service-layer method on `app/modules/audit/service.py` (a new one,
parameterized the same way `record_self_audit`/`record_access_denied` already
are, or a new equivalent) inside the *same transaction* as ticket creation.
This is a build-sequencing implication, not a schema decision; flagged here
because `IMPACT_ANALYSIS` needs to know `app/modules/audit/service.py` (and
possibly `repository.py`, to add a generic-enough write method) is now
in this story's blast radius, not only `app/modules/support`'s own new
files.

`ticket_audit_log`'s indexes and relationships (below) are removed along
with the table.

## Valkey (not a DB table — noted for `cache.py`, not decided further here)

- **Idempotency replay (FR-4) — atomicity mechanism (DR-3 fix).** Per OD-2's
  adopted recommendation, the key is scoped per user —
  `idempotency:{user_id}:{key}`, not the story's own Data Model Notes'
  unscoped `idempotency:{key}`, which would let one customer's key collide
  with another's. Reuses this codebase's existing per-user Valkey-key
  pattern (`revoke_before:{user_id}`, `login_fail:account:{user_id}`) — no
  new keying scheme invented.

  The value is a small JSON envelope, `{"request_hash": <sha256 of the full
  request payload>, "ticket_id": <uuid or null>}` — a hash of the full
  request payload plus the UUID of the ticket that was actually created
  (once known), not a serialized response body; a replay re-fetches and
  re-serializes the ticket from `tickets` via `ticket_id` rather than
  duplicating the response shape in two places. TTL 24 hours per FR-4 and
  the story's own Data Model Notes.

  **Atomic create/replay gate**, reusing this codebase's existing
  compare-and-set primitive (`app/modules/users/cache.py`'s
  `MfaReplayCache.mark_step_used`, `SET key value NX EX ttl`) rather than
  inventing a new one:

  1. `SET idempotency:{user_id}:{key} {"request_hash": H, "ticket_id":
     null} NX EX 86400`. A `True` result means this request atomically
     claimed the key — it is the sole writer for this `Idempotency-Key` and
     proceeds to create the ticket and write the `audit_log` row, then
     overwrites the key with `{"request_hash": H, "ticket_id": <new id>}`
     (a plain `SET`, no `NX`, same 24h `EX`) immediately before returning
     `201` — the same request that won the claim is the only one permitted
     to resolve it, so no second compare-and-set is needed for the
     overwrite.
  2. A `False`/falsy result means the key already exists. The service `GET`s
     the existing envelope and branches:
     - Stored `request_hash != H` → `422 idempotency-key-reuse` (FR-4), no
       ticket created — unchanged from v1's contract-level behavior.
     - Stored `request_hash == H` and `ticket_id` is not `null` → a genuine
       replay: re-fetch that `tickets` row via `ticket_id` and return `201`
       with it (FR-4's "the original ticket").
     - Stored `request_hash == H` and `ticket_id` is still `null` → the
       **race DR-3 flags**: a first request is still mid-flight (between
       step 1's claim and its own overwrite). The service performs a short
       bounded poll — re-`GET`ting the key every 100 ms, up to 5 times
       (500 ms total, comfortably inside the p95 ≤ 400 ms NFR's own budget
       for the *first* request, so a concurrent second request resolving
       within this window is the expected case, not the exception) — until
       `ticket_id` is populated, then behaves as the case above. If the
       poll budget is exhausted (the in-flight request itself stalled or
       failed before overwriting the key), this request is treated as an
       unhandled server error (`500`) rather than inventing a new `4xx`
       contract slug no AC or `US-4.1-openapi.yaml` response names for this
       pathological case — this is the framework's ordinary default for an
       unhandled internal condition, requiring no new named contract slug;
       it is not a claim that `500` is itself part of the approved
       response set.

     This is a new, minimal polling pattern for this codebase (no prior
     module blocks on another in-flight request); flagged as a design
     assumption for `PLAN_REVIEW`/`IMPLEMENTATION_PLANNING` to confirm, not
     a silent invention — the alternative (immediately failing the second
     request) would violate FR-4's "no second ticket exists" guarantee
     without a safe way to still return `201` with the eventual ticket.

  **Ordering against the rate limit (FR-6), stated explicitly since DR-3's
  fix makes the idempotency gate a multi-step sequence a second check
  could otherwise race against:** the idempotency gate above runs, and a
  replay branch (case 2's "not `null`" or "still `null` → resolved by
  poll" outcomes) returns before the rate-limit counter is touched at all.
  Only a genuinely new request — the `NX` claim in step 1 succeeding —
  reaches the `ticket_create_rate:{user_id}` check below. This is
  required, not incidental: a customer retrying an already-succeeded
  request under the same `Idempotency-Key` after already hitting 5
  creations that hour must still get `201` with the original ticket
  (FR-4), never `429` — a replay is not a new creation attempt and must
  not consume or be blocked by the creation-rate budget.

- **Ticket-creation rate limit (FR-6).** `ticket_create_rate:{user_id}`,
  atomic `INCR`+`EXPIRE` pipeline, 3600 s window — the identical shape
  `LoginThrottleCache`/`RefreshRateLimitCache` already use in
  `app/modules/users/cache.py` (`_incr_with_ttl`/`record_request`, both a
  `client.pipeline(transaction=True)` of `incr`+`expire` — verified against
  the current file, not assumed), not a new pattern. Checked only after
  the idempotency gate above has determined this is a new creation
  attempt, not a replay. Unchanged from v1 otherwise.

## Relationships / loading strategy

```
User (1) ──< Ticket.requester_id >── (0..n)
User (1) ──< Attachment.uploaded_by >── (0..n)
Ticket (1) ──< Attachment.ticket_id >── (0..n, nullable until bound)
Ticket (1) ──< AuditLog.target_id >── (0..n, no FK — audit_log has no FK on
                                        target_id/actor_id by its own
                                        US-3.3 design, must survive account
                                        erasure)
User (1) ──< AuditLog.actor_id >── (0..n, no FK — same reason)
```

No SQLAlchemy `relationship()` is declared on `Ticket`/`Attachment` for any
of the above. `TicketRead` (`US-4.1-openapi.yaml`) carries no nested
`attachments` array and no nested audit-log data — every read this story's
endpoints perform is a direct, single-table lookup or a keyset-filtered
`tickets` list, never a graph traversal. This matches the project's existing
precedent (`US-3.1`'s `InvitationToken.user_id`) of not adding a
`relationship()` where no story requirement reads one as a collection.
Binding an attachment and writing the `audit_log` row are independent
single-row writes issued by the service in the same transaction as ticket
creation, not relationship-mediated cascades. `AuditLog` itself declares no
`relationship()` either (`US-3.3-db-design.md`) — this story's write is a
plain `session.add(AuditLog(...))`-shaped insert via the audit module's own
service, not a traversal from `Ticket`.

## Indexes

- `tickets`: unique on `ticket_number`; composite
  `(requester_id, created_at DESC, id DESC)` for FR-2's keyset-paginated
  "this customer's tickets, newest first" query — `id` breaks ties within
  the same `created_at` value, since two tickets can share a timestamp at
  typical clock resolution.
- `attachments`: index on `ticket_id` (bind/lookup); index on `uploaded_by`
  (ownership check, FR-7); partial index on `created_at`
  `WHERE ticket_id IS NULL` for the 24-hour unbound-purge job's scan, so
  that job never has to scan already-bound rows it will never touch.
- No new index on `audit_log` for this story — `US-3.3-db-design.md`'s
  existing `(occurred_at DESC, actor_id, event)` covering index already
  supports a future "this actor's audit history" or "this event type" query
  over `ticket_created` rows the same way it does every other event type;
  `target_id` lookups (a future "this ticket's audit history" view) are not
  required by any FR-1–FR-7 acceptance criterion, so no new index is added
  speculatively.

## Sensitive columns

None of `tickets`/`attachments` hold a password, token, or MFA secret.
`tickets.body` is free-text customer input rendered back to the requester
and to support staff — OD-5 resolves this to plain text only (no
Markdown/HTML rendering pipeline), which is the NFR's actual security
requirement ("MUST NEVER render user-supplied HTML") satisfied at the
storage/display layer, not by sanitization logic this design would need to
specify. `audit_log.payload` for `ticket_created` carries only
`ticket_number`/`category` (see above) — no PII beyond what `tickets` itself
already stores, consistent with `US-3.3-db-design.md`'s existing note that
`payload` redaction is a per-write-call-site responsibility.

## Explicitly deferred / not decided here

1. **`ticket_number`'s year-reset behavior.** The example (`CP-2026-0000431`)
   implies a per-year-reset counter; the spec never states whether the
   numeric portion resets each calendar year or is a single lifetime
   sequence. This design uses one global monotonic sequence (no reset) —
   flagged as a gap, not a guessed requirement, since either behavior
   satisfies every stated AC.
2. **`category`'s valid value set (OD-3)** — stakeholder decision, not
   modeled as an enum/CHECK constraint here; see above.
3. **BR-007's account-erasure mechanics** — `requester_id`/`uploaded_by`'s
   `ondelete` behavior is `RESTRICT`-by-default pending that job's own
   design; see above.
4. **A DB-level immutability guard on `attachments.ticket_id`** — not built;
   FR-7's "belongs to exactly one ticket forever" is enforced by the service
   never issuing a rebind, not by a trigger/constraint. Flagged as a
   hardening option, not invented as a requirement.
5. **The exact new method(s) `app/modules/audit/service.py`/`repository.py`
   need** for a generic `ticket_created`-shaped write — this design fixes
   the target table and column values, not the method signature; that is
   `IMPLEMENTATION_PLANNING`/`service-and-router-builder`'s call.
