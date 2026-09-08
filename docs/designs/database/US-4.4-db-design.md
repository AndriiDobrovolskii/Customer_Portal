---
artifact_type: database_design
story: US-4.4
version: 1
status: DRAFT
created_at: "2026-09-07T20:00:00Z"
updated_at: "2026-09-07T20:00:00Z"
produced_by: db-designer
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# DB Design: Agent Ticket Queue & Assignment (US-4.4 / spec US-4.4)

**Source spec:** docs/specifications/US-4.4-spec.md (version 1, APPROVED)
**API design:** docs/designs/api/US-4.4-api-design.md, US-4.4-openapi.yaml (version 1, DRAFT)

## Overview

One additive, nullable column on the existing `tickets` table
(`assignee_id`), three new indexes to support the queue's default ordering
and its two agent-only filters, and writes of two new `event` values
(`ticket_assigned`, `ticket_unassigned`) into the existing `audit_log`
table — same architecture `US-4.1-db-design.md` established and
`US-4.2-db-design.md`/`US-4.3-db-design.md` reused: this project's
`ticket_audit_log` language in the spec/story always means a new `audit_log`
event type, never a dedicated table. No new table. No change to
`attachments` or `ticket_replies`. Nothing in `app/modules/support/models.py`
outside `Ticket` is touched.

Confirmed by reading `app/modules/support/models.py` before drafting: no
`assignee_id` column exists today (US-4.1/US-4.2/US-4.3 deliberately deferred
it, per `US-4.1-db-design.md`'s own "central scoping decision" note) — this
story adds exactly that column and nothing US-4.1/4.2/4.3 already shipped is
re-designed here.

## Existing table: `tickets` — one additive column

- **`assignee_id`**: `Mapped[uuid.UUID | None]`, `ForeignKey("users.id")`,
  `nullable=True`, no default (starts `NULL`), no `ondelete` override
  (defaults to `RESTRICT`). Set by a successful `POST .../assign` (FR-3,
  including re-assignment) and cleared by a successful `DELETE .../assign`
  (FR-4). No index declared inline on the column itself — the composite
  index below (`ix_tickets_assignee_id_updated_at_id`) already serves
  single-column equality/`IS NULL` lookups via its leading column, matching
  this module's existing precedent of not adding a redundant single-column
  index when a composite index's leading column already covers it
  (`ticket_replies.ticket_id`, `US-4.2-db-design.md`).

  - **FK / `ondelete`**: real FK to `users.id`, `RESTRICT`-by-default (no
    `ondelete` specified) — the identical placeholder reasoning
    `US-4.1-db-design.md` already established for `requester_id`/
    `uploaded_by`: `BR-007`'s account-erasure job mechanics are still
    "pending legal/DPO sign-off," so this design cannot know today whether a
    deactivated/erased agent's assigned tickets should be unassigned,
    reassigned, or block the deletion outright. `RESTRICT` fails loud rather
    than silently orphaning an assignment. This also matches the story's own
    Data Model Notes ("nullable, no cascade delete (US-1.4's retention job
    owns erasure)") verbatim in intent (`RESTRICT` is the SQL default that
    *is* "no cascade delete").
  - **No `CHECK` constraint ties `assignee_id` to `status`.** Assignment is
    explicitly orthogonal to the resolve/close/reopen state machine (spec
    Out of Scope: "Transitioning ticket status as a side effect of
    assign/unassign" is out of scope, and the reverse — status transitions
    clearing `assignee_id` — is likewise never described by any FR). A
    ticket assigned before being closed via `/close` keeps its
    `assignee_id` after closure (no code path this story or US-4.3 clears
    it), so a constraint forbidding `assignee_id IS NOT NULL WHEN status =
    'closed'` would be actively wrong, not merely unnecessary. **OD-3
    carried forward per the resolved-input instruction:** whether `DELETE
    .../assign` on a `"closed"` ticket returns `409` (API design's adopted
    default) or succeeds with `200`/cleared `assignee_id` does not change
    this column's nullability or require a `CHECK` either way — both
    outcomes are the same nullable column; the difference is entirely in
    the service's conditional `UPDATE`'s `WHERE status != 'closed'`
    predicate (API design "Check order" step 3/4), not in the schema. No
    schema-level artifact needs to change if OD-3 is later reversed.

## Indexes

The story's own Data Model Notes (surfaced via the spec review's completeness
note, since the spec's NFR only states the generic "MUST be index-backed")
name two index shapes: `(status, updated_at, id)` and `(assignee_id,
updated_at, id)`. Checking those against FR-1's actual default query
(`AQ-AC1`: no filter, every non-`"closed"` ticket, ordered oldest-`updated_at`
first) surfaces a gap: a composite index led by `status` orders rows
`status` first, `updated_at` second — it does not, by itself, give a single
global `updated_at` ordering across the four non-`"closed"` status values
FR-1's default (filterless) query must scan. Relying on the query planner to
merge four per-status range scans into one `updated_at` order is not a safe
assumption to design against. This design therefore adds a third, partial
index dedicated to that specific, most-common (AQ-AC1) query, and keeps both
of the story's named indexes for the filtered cases they do serve directly —
the same kind of literal-notes correction `US-4.3-db-design.md` already made
to its `CHECK` constraint, flagged the same way, for `DESIGN_REVIEW` to
confirm:

```python
# FR-1 (AQ-AC1): the default, filterless agent queue - every ticket not
# "closed", ordered oldest-updated first. Partial so the index only ever
# holds rows the default query (and any *non-closed* status=X filter) can
# match; the same partial-index pattern this module already uses
# (ix_tickets_resolved_at_pending_autoclose, ix_attachments_created_at_unbound).
Index(
    "ix_tickets_queue_default_updated_at_id",
    "updated_at",
    "id",
    postgresql_where=text("status != 'closed'"),
)

# FR-2 (AQ-AC2): an explicit status=X filter, any of the five values
# including "closed" ("status=closed is the only way a closed ticket
# appears"). As named in the story's Data Model Notes.
Index(
    "ix_tickets_status_updated_at_id",
    "status",
    "updated_at",
    "id",
)

# FR-2: assignee_id=<uuid> / assignee_id=me (equality) and assignee_id=none
# (IS NULL - a btree index serves this directly, NULLs are indexed and
# sortable). As named in the story's Data Model Notes.
Index(
    "ix_tickets_assignee_id_updated_at_id",
    "assignee_id",
    "updated_at",
    "id",
)
```

**Predicate form required for `ix_tickets_queue_default_updated_at_id` to be
selected.** PostgreSQL only uses a partial index when it can prove the
query's `WHERE` clause implies the index predicate; that proof is reliable
for a literal `status != 'closed'` comparison but is **not** reliably proven
for a semantically-equivalent `status IN ('open', 'waiting_on_support',
'waiting_on_customer', 'resolved')` list (a `ScalarArrayOpExpr`, which the
planner's predicate-implication check does not generally reduce to the
`<>` form). FR-1's default (filterless) query must therefore be written by
the repository as `status != 'closed'` literally, not as an enumerated
`IN`-list of the four non-closed values, or this index goes unused and the
story's own Enforcement Matrix `[gate]` EXPLAIN assertion on index coverage
fails. Flagged here since it is otherwise an invisible implementation detail
this design's index choice depends on.

**RLS confirmed absent on `tickets`.** Checked `migrations/versions/` before
finalizing this section, since `US-4.4-api-design.md` mentions
`GET /{id}` being "actor-kind-aware via `resolve_actor_kind`/RLS" and FR-1
requires the agent branch to see tickets "regardless of requester" —
if a Row-Level-Security policy restricted `tickets` rows to
`requester_id = current_user`, no index design here could make FR-1's query
return other customers' tickets to an agent. `ENABLE`/`FORCE ROW LEVEL
SECURITY` and both `CREATE POLICY` statements in this codebase
(`migrations/versions/9132a68b73c8_add_ticket_replies.py`) target only
`ticket_replies`, not `tickets` — the API design's "RLS" reference is to
that same `ticket_replies` policy pair (relevant to `GET /{id}`'s nested
replies, not to this story's queue/assign endpoints). `tickets` itself
carries no RLS policy today, and this story adds none — FR-1's
"regardless of requester" scope is enforced entirely by the service-layer
query (no `requester_id` filter on the agent branch), which no schema
element here blocks or needs to accommodate.

**`updated_at`'s write semantics under assign/unassign — stated, not
newly decided.** This story is the first to make `updated_at` a queue sort
key (Assumption #8, "oldest `updated_at` first"). `tickets.updated_at`
already carries `onupdate=func.now()` (US-4.1, unchanged); a
`POST/DELETE .../assign` issued as an ORM-mapped `UPDATE` therefore bumps
`updated_at` as a side effect, moving the ticket to the back of the
"longest-waiting" queue on every assign or unassign — including an
assign-then-immediate-unassign cycle, which resets the wait clock twice.
No FR or the story's own text states whether this is intended (the state
machine's `updated_at` bump was designed for status/content transitions,
not for a purely-ownership change). This design does not add a mechanism to
suppress it (e.g. a raw `UPDATE` bypassing the ORM's `onupdate`) — doing so
would be inventing behavior no requirement asks for. Flagged as a real,
observable consequence of reusing the existing column for `service-and-router-builder`
to confirm is acceptable, not a defect in this design.

`category` gets no index of its own — consistent with US-4.1's still-open
OD-3 (no fixed value list, no enum, no existing index on `category`
anywhere in this module). A `category`-only query (no `status`/`assignee_id`
filter) is still bounded by `ix_tickets_queue_default_updated_at_id` (the
default partial index), which filters `category` in-scan rather than
sequentially scanning the whole table; a `category` filter combined with
`status`/`assignee_id` rides whichever of the other two indexes matches
those predicates and filters `category` the same way. This satisfies the
NFR's "index-backed... for every supported filter" without inventing an
index no AC calls for.

**Combined filters** (e.g. `status=X AND assignee_id=Y`): the planner picks
one of the three indexes above as its primary access path and filters the
remaining predicate(s) in-scan (bounded by the cursor's own keyset range
either way, so this is never a full-table scan). A single composite index
covering every 2–3-way filter combination is not built — no AC requires
guaranteed index-only access for every combination, and building one for
each would be speculative beyond what FR-1/FR-2 actually specify.

No index changes to `attachments`, `ticket_replies`, or `audit_log`.

## Audit trail: writes into the existing `audit_log` table (no new table)

Same architecture US-4.1/US-4.2/US-4.3 already established: `audit_log`
(`app/modules/audit/models.py`, `US-3.3-db-design.md`) is the write target
for every new event type; FR-3/FR-4's two `ticket_audit_log` mentions are two
new `event` values on that one table, written via the existing
`app/modules/audit/service.py` `record_event(...)` generic path (US-4.1's
own addition, already service-to-service per `AGENTS.md` §3 — no new
audit-module method needed).

| FR | `event` | `actor_id` | `actor_role` | `target_id` | `outcome` | `payload` |
|---|---|---|---|---|---|---|
| FR-3 | `ticket_assigned` | the caller (assigner) | resolved via `_resolve_actor_role` | `ticket.id` | `"success"` | `{"assignee_id": <new value, uuid>}` |
| FR-4 | `ticket_unassigned` | the caller | resolved via `_resolve_actor_role` | `ticket.id` | `"success"` | `{"assignee_id": null}` |

- **`category`**: `"tickets"` for both — the same literal US-4.1/US-4.2/
  US-4.3 already write, not a new one.
- **`payload` carries `assignee_id` — story-mandated, not this design's
  invention.** The source story's Data Model Notes state: "Audit events:
  `ticket_assigned`, `ticket_unassigned`, each recording `actor_id` and the
  target `assignee_id`" — i.e. the audit row for each event must record the
  `assignee_id` value the operation produced, not only `target_id` (the
  ticket). This departs from US-4.1's/US-4.3's own "`payload` is `NULL`,
  the value is already durably readable via `target_id`" pattern for a
  reason that pattern doesn't hold here: `resolution_note`/`closed_at`/etc.
  stay on the `tickets` row forever once set, so a reviewer can always
  re-derive them from `target_id`; `tickets.assignee_id` is overwritten by
  every subsequent assign and cleared by unassign, so the *current* row
  value alone tells a reviewer nothing about who was assigned yesterday.
  This design places the story's required value in `payload` (the existing,
  already-`JSONB` column this project's audit architecture reserves for
  exactly this kind of per-event detail, `US-3.3-db-design.md`) rather than
  inventing a new place to put it.
- **`request_id`/`ip`/`user_agent`**: `NULL` for both — unchanged from the
  existing `record_event` generic-path call shape (US-4.1/US-4.3's usage);
  no FR requires capturing them.
- **Idempotent no-op `DELETE .../assign` (API design Open Questions #5,
  unresolved by any AC): whether a repeat unassign on an already-unassigned
  ticket still writes a fresh `ticket_unassigned` row is a service-layer
  branch decision, not a schema difference** — either choice writes the
  identical row shape above when it does write, so this design does not
  need to and does not resolve it.
- **Cross-module layering note (unchanged precedent, restated for this
  story):** the tickets service calls `app/modules/audit/service.py`'s
  `record_event(...)` inside the same transaction as its own `tickets`
  `UPDATE` (the conditional assign/unassign write), per `AGENTS.md` §3's
  "cross-module calls go service → service" rule — it does not import
  `AuditRepository`/`AuditLog` directly. No new audit-module code is
  needed; `record_event` already exists and is already used exactly this
  way by US-4.1/US-4.3.
- **No new index on `audit_log`** — `US-3.3-db-design.md`'s existing
  `(occurred_at DESC, actor_id, event)` covering index already supports a
  future "this event type" or "this actor's history" query over these two
  new `event` values the same way it does every other type; no FR in this
  story reads `audit_log` back.

## Concurrency (FR-10)

No new mechanism: the same conditional-`UPDATE` pattern the spec's own
Assumptions & Defaults #6 cites (US-1.2 FR-1, US-1.4 FR-1/FR-9, US-4.3 FR-9)
applies to `assignee_id`, exactly as `US-4.4-api-design.md`'s "Concurrency
Design" section already states at the contract level:

```sql
UPDATE tickets SET assignee_id = :new
WHERE id = :id AND status != 'closed'
  AND assignee_id IS NOT DISTINCT FROM :expected
```

`:expected` is the `assignee_id` value read earlier in the same request
(`NULL` for a first assignment). This design's only obligation is that the
column supports this usage without a special case: `assignee_id` is a plain
nullable column with no unique constraint blocking repeated `NULL` values,
and `IS NOT DISTINCT FROM` (rather than `=`) correctly treats `NULL =
NULL` as a match for the first-assignment case. A losing `UPDATE` (zero rows
affected) is what the service reports as `409 assignment-conflict`
(API design) — no `SELECT ... FOR UPDATE` or other locking construct is
introduced, matching every prior conditional-`UPDATE` use in this codebase.

`unassign`'s `WHERE id = :id AND status != 'closed'` (API design) is
**unconditional** on the prior `assignee_id` value (no optimistic-concurrency
guard) — no schema element supports or blocks this either way; it is a
service-layer choice already fixed at `API_DESIGN`, restated here only
because the column itself imposes no constraint that would prevent it.

## Relationships / loading strategy

No SQLAlchemy `relationship()` is added. `Ticket` continues to declare none
(unchanged `US-4.1`/`US-4.2`/`US-4.3` precedent: every read this module's
endpoints perform is a single-row lookup by `id` or a keyset-filtered list,
never a graph traversal). The new FK (`Ticket.assignee_id → users.id`,
many-to-one) exists purely for referential integrity; no read path this
story's endpoints implement needs the related `User` row loaded —
`AgentTicketRead`/`AgentTicketStateRead` (OD-1's adopted schemas) carry only
the raw `assignee_id` UUID, never a nested user object (per OD-1's response
shapes in the API design and the spec's own deferral of a display-name field
to whoever specs US-5.5, Open Question #5/OD note). If a future story adds a
nested assignee display name to either response shape, that story's own
`DB_DESIGN` stage would need to add a `relationship()` with `joinedload()`
per `AGENTS.md` §3's eager-loading mandate — not needed here, and not built
speculatively.

```
User (1) ──< Ticket.assignee_id >── (0..n, FK, RESTRICT-by-default, nullable)
Ticket (1) ──< AuditLog.target_id >── (0..n, no FK — unchanged, US-3.3 design)
User (1) ──< AuditLog.actor_id >── (0..n, no FK — unchanged, US-3.3 design)
```

## Migration

Additive only: one nullable `FK`-backed column plus three indexes on an
existing table. No backfill, no destructive step — matches the story's own
Data Model Notes ("Migration is additive only... no expand→migrate→contract
cycle is required") and `AGENTS.md` §4's rule that only destructive changes
need that cycle. Concrete migration mechanics (autogenerate, `if_not_exists`
guards, the `upgrade → downgrade → upgrade` proof) are `migration-manager`'s
job, not decided further here — flagged only that
`ix_tickets_queue_default_updated_at_id` and
`ix_tickets_resolved_at_pending_autoclose` (US-4.3, already shipped) are both
partial indexes on `tickets`, so `migration-manager` should expect the
`Rewriter` guard-injection caveat (`AGENTS.md` §4) to apply the same way it
already did for the existing partial index.

## Sensitive columns

`assignee_id` holds a plain FK to a `users.id` value — an internal user
identifier already exposed elsewhere in this project's API surface (e.g.
`requester_id`, `author_id`), not a password, token, or MFA secret. It is
already scoped to agent-only response shapes (`AgentTicketRead`/
`AgentTicketStateRead`) and explicitly excluded from any customer-facing
shape (`TicketRead`/`TicketStateRead`/`TicketListResponse` — Assumption #7,
NFR, OD-1) at the schema layer, not by runtime redaction — no additional
storage requirement (e.g. encryption) is invented here since neither the
spec nor `business-rules.md` states one. `audit_log.payload` for
`ticket_assigned`/`ticket_unassigned` carries only the (new) `assignee_id`
value — no PII beyond what `tickets` itself already stores, consistent with
`US-3.3-db-design.md`'s existing note that `payload` redaction is a
per-write-call-site responsibility.

## Explicitly deferred / not decided here

1. **OD-3 (unassign-on-closed 409 vs. 200)** — does not change this column's
   schema either way; only the service's conditional `UPDATE`'s `WHERE`
   predicate. See "No `CHECK` constraint ties `assignee_id` to `status`"
   above.
2. **OD-4 (deactivated-target-account check)** — reads the existing
   `users.status` column at the service layer; no schema change here.
3. **Idempotent no-op unassign audit-write question** (API design Open
   Questions #5) — a service-layer branch, not a schema difference; see
   "Audit trail" above.
4. **`category`'s valid value set (US-4.1 OD-3, still open)** — unaffected
   by this story; no `category` index added, per "Indexes" above.
5. **A future assignee display-name field / relationship** (spec Open
   Question #5, source Open Question #5) — explicitly out of scope for this
   story (OD-1's adopted response shapes carry only the raw UUID); not built
   here, and would require its own `relationship()`/eager-loading decision
   in whichever story adds it.
6. **BR-007's account-erasure mechanics** — `assignee_id`'s `ondelete`
   behavior is `RESTRICT`-by-default pending that job's own design, the
   identical gap `US-4.1-db-design.md` already flagged for
   `requester_id`/`uploaded_by`; not re-argued differently here.
