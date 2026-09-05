---
artifact_type: database_design
story: US-4.2
version: 3
status: ARCHIVED
created_at: "2026-09-04T21:00:00Z"
updated_at: "2026-09-05T11:00:00Z"
produced_by: db-designer
inputs:
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/designs/database/US-4.2-db-design.md (v2)
---

# DB Design: Ticket Replies (US-4.2 / spec US-4.2)

**Source spec:** docs/specifications/US-4.2-spec.md (version 6)
**API design:** docs/designs/api/US-4.2-api-design.md, US-4.2-openapi.yaml (version 3)

## Revision Note (v3)

v2 of this document treated OD-8 as confirmed to candidate (a) — a customer
reply on a `"resolved"` ticket stays `"resolved"` — on the strength of
`HUMAN_SPEC_APPROVAL`'s silent, comment-free approval of specification v5.
`DESIGN_REVIEW` v2 (`docs/reviews/designs/US-4.2-design-review.md`) found that
reading incorrect (Finding DR-1) and returned `BLOCKED`: that approval was not
an actual per-item OD-8 resolution matching how OD-1–OD-7 were confirmed. The
human then supplied OD-8's actual resolution directly in-session
(2026-09-05T09:00:00Z), formalized as `docs/decisions/US-4.2-open-decisions.md`
v3: **a customer reply on a `"resolved"` ticket is accepted (`201`) and
`tickets.status` transitions to `"waiting_on_support"`** — reopening the
ticket, using the same target status FR-2's ordinary
`"waiting_on_customer"` → `"waiting_on_support"` case already produces. This
is candidate (b), not v2's candidate (a). Specification v6 / spec review v6 /
API design v3 (all PASS) now state this directly.

This changes **no column, type, constraint, index, or RLS policy** below:
`"waiting_on_support"` is not a new value — `tickets.status` is an
unconstrained `String(32)` with no enum or CHECK restricting its values (this
codebase has never used a DB-level enum type for status columns), and
`"waiting_on_support"` is already written by this same story's FR-2 ordinary
case. The only thing this revision corrects is the narrative text below that
described the resolved-ticket customer-reply case as status-preserving; the
underlying design was already schema-neutral to either outcome, as v1 and v2
both noted before OD-8 was actually resolved. `resolved_at`'s confirmed
absence (v2 point 2) and the `TicketThreadHeader`→`TicketDetailRead` naming
correction (v2 point 3) are unaffected and carry forward unchanged.

## Overview

One new table (`ticket_replies`), one additive column on the existing
`tickets` table (`first_response_at`), one additive nullable column on the
existing `attachments` table (`ticket_reply_id`, Resolution OD-1), and one new
mechanism this codebase has not used before: PostgreSQL Row-Level Security on
`ticket_replies` (FR-3 / BR-015). No table is dropped or narrowed.

## New table: `ticket_replies`

Shape fixed by the story's own Data Model Notes and Resolution OD-1/OD-6:
`id`, `ticket_id`, `author_id`, `author_kind`, `body`, `visibility`,
`created_at`.

- `ticket_id` is a real FK to `tickets.id`, `nullable=False` — a reply always
  belongs to exactly one ticket, unlike `attachments.ticket_id`'s nullable
  unbound state. No `ondelete` is specified (defaults to `RESTRICT`), matching
  `Ticket.requester_id`/`Attachment.uploaded_by`'s existing precedent — no
  ticket-deletion feature exists in this codebase, so the gap is moot in
  practice but the safe default is kept consistent with the rest of this
  module.
- `author_id` is a real FK to `users.id`, same no-`ondelete` treatment. No
  index is added on this column alone: no acceptance criterion or NFR queries
  "replies by this author" — the 30/user/hour rate limit (Assumptions &
  Defaults #7) is a Valkey counter (`cache.py` concern), not a DB query, per
  the open-decisions doc's "Resolved by precedent" note pointing at US-4.1's
  own Valkey-only rate-limit mechanism.
- `author_kind` is `String(20)`, `nullable=False`, no default — the service
  always knows which actor is posting and must state it explicitly, matching
  `Ticket.category`'s no-default precedent. Its two values are `"customer"`
  and `"agent"` (`ReplyRead.author_kind`'s enum, `US-4.2-openapi.yaml` v2) — a
  coarser two-way split than the four-entry role catalogue (BR-010:
  `customer`/`support_agent`/`admin`/`auditor`). Mapping a caller's actual
  role to this column's two values (e.g. both `support_agent` and `admin`
  write `"agent"`) is a service-layer decision, not a schema one; flagged
  below under Explicitly deferred.
- `body` is `String(5000)`, `nullable=False`, matching `Ticket.body`'s own
  cap exactly (FR-7) and, like `Ticket.body`, carries no rendering pipeline —
  Resolution OD-4 already settled this as plain text only, so "sanitised on
  render," "strip tracking pixels," and the Enforcement Matrix's "No HTML
  rendering" gate are satisfied by construction, the same reasoning
  `US-4.1-db-design.md` applied to `tickets.body`.
- `visibility` is `String(20)`, `nullable=False`, `server_default="public"` —
  same server-side-default style as `Ticket.status`'s `server_default="open"`,
  and matches Resolution OD-6's "defaults to public regardless of actor kind."
  Not a PostgreSQL `ENUM` type, consistent with this codebase's existing
  choice (`Ticket.status`, `Ticket.category`, `User.status`) to never use a
  DB-level enum type anywhere.
- `created_at` is `DateTime(timezone=True)`, `nullable=False`,
  `server_default=func.now()`. No `updated_at` — Assumptions & Defaults #6
  states replies are append-only (no edit/delete), so there is nothing for an
  `onupdate` clause to ever fire on; adding one would be a column no FR reads
  or writes, which `US-4.1-db-design.md`'s own DR-1 finding already flagged as
  a mistake to avoid repeating.

### `CHECK` constraint (FR-5 / BR-015, application-unbypassable by design)

```
CheckConstraint(
    "visibility = 'public' OR author_kind = 'agent'",
    name="ck_ticket_replies_visibility_agent_only",
)
```

Verbatim from the story's own Data Model Notes. Guarantees a customer-authored
row can never carry `visibility = 'internal'`, independent of whatever the
application layer does or fails to do — the write-side half of BR-015's
two-layer isolation guarantee. This is the first `CheckConstraint` in this
codebase; named explicitly (`ck_` prefix, mirroring this project's existing
`ix_` index-naming habit) since no `naming_convention` is registered on
`Base.metadata` (`app/db/base.py`) and an unnamed constraint would get an
autogenerated name migration-manager would need to guess at consistently
across `upgrade`/`downgrade`.

**Layering note (AGENTS.md §4's three-tier error rule):** this `CHECK` is a
backstop, not the primary FR-5 enforcement path. The contract's `403
insufficient-permission` response is a `DomainError` the service raises after
its own explicit visibility/actor-kind check — a repository never raises
(`AGENTS.md` §4), and an `IntegrityError` bubbling up from a `CHECK`
violation is not a `DomainError` a router's exception handlers are designed
to translate into `403 insufficient-permission`. In the design this document
specifies, the service's own check makes the constraint unreachable in normal
operation; a request that somehow reaches the database and trips the `CHECK`
is a bug in that service-layer check, not a contract path this story defines
a response for. `service-and-router-builder` must not rely on catching the
`IntegrityError` as its FR-5 implementation.

### Row-Level Security (FR-3, TR-AC3, BR-015 — the read-side half)

This is the first table in this codebase to use PostgreSQL RLS. The
application connects through a single database role (`app/db/session.py`
creates one engine from one `database_url`; there is no per-actor-kind
connection role), and that role is also the table owner (it ran the
migrations). Two consequences follow directly from that, not from any
judgment call:

1. **`FORCE ROW LEVEL SECURITY` is mandatory, not optional.** PostgreSQL
   exempts a table's owning role from its own RLS policies by default —
   `ENABLE ROW LEVEL SECURITY` alone would make the policy a no-op for every
   request this application ever issues, since every request runs as the
   owning role. `FORCE ROW LEVEL SECURITY` closes that exemption. Missing
   this is the single most likely way this story's "holds even if the
   application layer forgets to filter" guarantee (TR-AC3) would silently not
   hold in production.
2. **A policy must exist for every command RLS-enabled rows go through, or
   that command is denied outright**, not merely unfiltered. `ticket_replies`
   receives exactly two commands from this story's own scope: `SELECT`
   (thread fetch) and `INSERT` (reply creation) — Assumptions & Defaults #6
   rules out `UPDATE`/`DELETE` entirely (append-only, no edit/delete). Two
   narrow, command-scoped policies are used rather than one `FOR ALL` policy:
   a `FOR ALL` policy would additionally attach its `USING` clause to
   `UPDATE`/`DELETE`, a surface this table never exercises and that a reader
   of a single `FOR ALL` policy could mistake for an intentional guarantee
   about those commands. Two policies, each naming the one command it
   actually governs, is the more literal statement of what this table needs
   and removes that ambiguity — not a mechanically forced choice, a
   deliberate one.

```sql
CREATE POLICY ticket_replies_read ON ticket_replies
  FOR SELECT
  USING (visibility = 'public' OR current_setting('app.actor_kind', true) = 'agent');

CREATE POLICY ticket_replies_write ON ticket_replies
  FOR INSERT
  WITH CHECK (visibility = 'public' OR current_setting('app.actor_kind', true) = 'agent');

ALTER TABLE ticket_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_replies FORCE ROW LEVEL SECURITY;
```

If a future story adds edit/delete to replies (contradicting today's
append-only default), that story's own DB design must add `UPDATE`/`DELETE`
policies explicitly — this design does not pre-authorize commands no current
FR issues.

The predicate is deliberately the same shape as the `CHECK` constraint above
(`visibility = 'public' OR author_kind = 'agent'`), substituting the
session-local `app.actor_kind` GUC for the row's own `author_kind` column —
RLS is asking "is *this connection* allowed to see/write an internal row,"
the `CHECK` is asking "did *this row's own author* have the right to mark it
internal." Both must independently hold; neither substitutes for the other.

**Fail-closed by construction, not by an extra guard clause:**
`current_setting('app.actor_kind', true)` returns `NULL` when the GUC was
never set for the session (the `true` second argument suppresses the error
PostgreSQL would otherwise raise). `NULL = 'agent'` evaluates to `NULL`
(neither true nor false) in the `USING`/`WITH CHECK` boolean expression, which
PostgreSQL treats as "does not pass" — so a connection that never ran the
`SET LOCAL app.actor_kind = ...` step (a bug in the shared dependency the
story's NFR requires, or a future ad-hoc script bypassing it) sees and can
write only `visibility = 'public'` rows, never `'internal'` ones. The story's
own NFR text ("no session can start without them") is the intended contract;
this policy shape means a violation of that contract degrades to
over-hiding/under-writing internal notes, not to leaking them.

`app.actor_id` (also named by the story's Data Model Notes and the NFR) is
not read by this policy — ticket-level ownership (customer A vs. a ticket
belonging to customer B, FR-4) is an application-layer authorization check
before the replies query ever runs, not a row-visibility rule this table's
RLS needs to duplicate. `app.actor_id` is set for future use (e.g. if a later
story adds a policy keyed on authorship) but this story's own policy needs
only `app.actor_kind`. The `SET LOCAL app.actor_kind = ...` / `SET LOCAL
app.actor_id = ...` mechanics themselves — the "shared dependency" the NFR
names — are `service-and-router-builder`'s concern, not decided further here;
this design only fixes what the database-side policy reads.

**Migration mechanics note (not decided here, per this skill's own
constraints):** `CREATE POLICY`/`ENABLE`/`FORCE ROW LEVEL SECURITY` are
hand-written DDL — SQLAlchemy's autogenerate has no construct for any of the
three, the same reason `AuditLog`'s partitioning/trigger DDL in
`US-3.3-db-design.md` is hand-written rather than autogenerated. `AGENTS.md`
§4's guard rule applies: hand-written `op.execute()` is not reached by
`env.py`'s `Rewriter`, so `migration-manager` must guard it with its own
`sa.inspect(op.get_bind())` idempotency check, and prove the shape via a real
`upgrade → downgrade → upgrade` cycle (`downgrade()` drops the policy and
disables RLS, never `pass`).

## Existing table: `tickets` — additive column only

`first_response_at: Mapped[datetime | None]` → `DateTime(timezone=True)`,
`nullable=True`, no default (starts `NULL`). Stamped exactly once, on the
first public agent reply (FR-1) — "a plain timestamp for later reporting, no
SLA target evaluated" per the spec, so no trigger or computed-column mechanism
is needed, only a plain nullable column the service sets with an `UPDATE`
inside the same transaction as the reply insert. No index: no AC filters or
sorts by this column, only reads it back on the ticket record
(`TicketDetailRead.first_response_at`, `US-4.2-openapi.yaml` v2).

This is an ordinary additive, nullable `ALTER TABLE ... ADD COLUMN` — no
backfill needed (every existing ticket has no prior public agent reply to
retroactively stamp), no expand/migrate/contract sequencing required per
`AGENTS.md` §4.

No `resolved_at` column is added. API design v2's Open Question #3 asks this
design to confirm that explicitly: `Ticket` (`app/modules/support/models.py`)
has no `resolved_at` column today, this story's FRs describe no write to one,
and FR-2/FR-6's "`resolved_at` is not cleared" language is vacuously true —
there is no such column for the customer-reply-on-`"resolved"` case to clear.
Confirmed: no such column is expected by this story.

## Existing table: `attachments` — additive column only (Resolution OD-1)

`ticket_reply_id: Mapped[uuid.UUID | None]` → FK to `ticket_replies.id`,
`nullable=True`, `index=True`. Mirrors `ticket_id`'s existing shape on the
same table exactly: nullable until bound, no `ondelete` specified (defaults
`RESTRICT`), and — per Resolution OD-1's own text — "bound once and never
reassigned," which is service-enforced (no `UPDATE` code path clears or
rebinds it once set), not DB-trigger-enforced, the identical gap
`US-4.1-db-design.md` already flagged and left open for `attachments.ticket_id`
itself. `index=True` is added for the same reason `ticket_id` already carries
it on this table — a future "attachments on this reply" lookup — even though
no AC in this story reads that list back; kept for consistency with the
sibling binding column rather than invented as a new requirement.

An attachment keeps its existing nullable `ticket_id` unchanged — Resolution
OD-1 adds reply-level binding *in addition to* ticket-level binding, it does
not replace it (the API design's `attachment_ids` field on
`CreateReplyRequest` reuses `US-4.1-openapi.yaml`'s
`CreateTicketRequest.attachment_ids` mechanics verbatim, including the
`attachment-not-owned` `422` per BR-016). The exact bind sequence
(`AttachmentRepository.bind_to_ticket`'s existing conditional-`UPDATE`
pattern extended to also set `ticket_reply_id`, or a new
`bind_to_reply` method) is an `IMPLEMENTATION_PLANNING`/`service-and-router-builder`
call, not decided further here.

## Relationships / loading strategy

```
Ticket (1) ──< TicketReply.ticket_id >── (0..n)
User   (1) ──< TicketReply.author_id >── (0..n)
TicketReply (1) ──< Attachment.ticket_reply_id >── (0..n, nullable until bound, immutable after)
```

No SQLAlchemy `relationship()` is declared on `Ticket`/`TicketReply`/
`Attachment` — this matches `US-4.1-db-design.md`'s explicit precedent (no
`relationship()` anywhere in `app/modules/support/models.py`) and this
codebase's project-wide pattern of direct, explicit queries over ORM graph
traversal (`TicketRepository.list_for_requester`'s keyset-query shape, not a
loaded collection). `GET /v1/support/tickets/{id}`'s `TicketDetailRead`
(`{..., replies: ReplyThreadPage}`, `US-4.2-openapi.yaml` v2) is composed by
the service from two direct repository calls — `get_by_id(ticket_id)` and a
new keyset-paginated `list_for_ticket(ticket_id, cursor, limit)` on a new
`TicketReplyRepository`, mirroring `TicketRepository.list_for_requester`'s
existing cursor-encode/decode pattern — not a `joinedload`/`selectinload` off
a declared relationship. No `MissingGreenlet` risk exists because no
lazy-loadable relationship exists to trigger one.

## Indexes

- `ticket_replies`: composite `(ticket_id, created_at, id)` for the thread
  fetch's cursor pagination (Resolution OD-3: same keyset shape as
  `Ticket`'s own `(requester_id, created_at, id)` index, ascending here since
  the thread reads oldest-first / "newest-last" per the API design's
  `ReplyThreadPage` description, versus `Ticket`'s own newest-first
  list). Deliberately no separate single-column index on `ticket_id` — unlike
  `Ticket.requester_id`'s belt-and-suspenders `index=True` *plus* a composite
  index covering the same leading column, the composite index alone already
  serves an equality lookup on `ticket_id` efficiently (a multi-column B-tree
  index supports a prefix match on its leading column), so a second index
  would only add write overhead with no query this story needs it for. Named
  as a deliberate deviation from `Ticket.requester_id`'s pattern, not a silent
  omission.
- `tickets`: no new index — `first_response_at` is never filtered or sorted
  on by any AC.
- `attachments`: `index=True` on the new `ticket_reply_id` column, matching
  `ticket_id`'s existing single-column index on the same table.

## Sensitive columns

None. `ticket_replies.body` is free-text agent/customer content, same
category as `tickets.body` — plain text only (Resolution OD-4), no
password/token/MFA-secret/PII-beyond-what-`tickets`-already-stores. No new
column here holds anything `US-4.1-db-design.md`'s "Sensitive columns"
section didn't already cover for this module.

## Explicitly deferred / not decided here

1. **Mapping a caller's role (`support_agent`/`admin`) to `author_kind`'s
   two-value (`customer`/`agent`) vocabulary, and to the `app.actor_kind`
   session GUC the RLS policy reads.** This design fixes the vocabulary both
   the `CHECK` constraint and the RLS policy must agree on; which
   service-layer code path sets `app.actor_kind` to exactly `"agent"` for
   both `support_agent` and `admin` callers is `service-and-router-builder`'s
   call.
2. **The exact repository method signature for `ticket_replies`' cursor
   pagination and `attachments.ticket_reply_id`'s bind sequence** — fixed at
   `IMPLEMENTATION_PLANNING`, not here, consistent with `US-4.1-db-design.md`'s
   own precedent of leaving method signatures to that stage.

Item 3 in v1 of this document ("customer reply on a `"resolved"` ticket") was
removed from this list in v2 on the (later found incorrect, see Revision Note
above) premise that OD-8 was confirmed to candidate (a). It stays removed in
v3, now that OD-8 is actually resolved (candidate (b), a reopening
transition): as v1 and v2 both already stated, this was never a schema-shape
question — this table's columns, constraints, and indexes are identical
whether the resolved-ticket customer reply is a no-op or a status transition
to an existing status value. Nothing here changes as a result of the actual
resolution; it is recorded as resolved, not as still-deferred.
