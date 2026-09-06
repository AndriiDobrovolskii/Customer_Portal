---
artifact_type: entity_model
story: US-4.3
version: 3
status: ARCHIVED
created_at: "2026-09-06T12:00:00Z"
updated_at: "2026-09-06T17:00:00Z"
produced_by: db-designer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 2
supersedes: docs/designs/database/US-4.3-entity-model.md
---

# Entity Model: Ticket Resolution (US-4.3 / spec US-4.3)

Narrative rationale for every decision below is in
`docs/designs/database/US-4.3-db-design.md`. This document states only the
concrete shape. No `tickets` column, constraint, or index shape changed as
part of `DESIGN_REVIEW`'s DR-1/DR-2 (v1, narrative-only) or DR-4 (v2, this
revision) corrections. DR-4 adds one row to the `audit_log` write table below
(FR-4 now writes `event=ticket_reopened`, previously unaudited) — no schema
change, since `audit_log` already exists and takes no new column for it.

## `tickets` (existing table — additive columns only)

No column below already listed in `US-4.1-db-design.md` /
`US-4.2-db-design.md` is repeated; only what this story adds.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `resolved_at` | `DateTime(timezone=True)` | Yes | none (starts `NULL`) | Set once by `/resolve` (FR-1); cleared by `/reopen` (FR-5) or an FR-4 reopening reply; **not** cleared by `/close` or the auto-close job. |
| `resolution_note` | `String(5000)` | Yes | none | Set once by `/resolve` (FR-1); non-empty enforced at the Pydantic boundary (FR-10); never cleared. Length matches `Ticket.body`/`TicketReply.body`'s existing `String(5000)` cap — resolves `US-4.3-api-design.md` Open Questions #3. |
| `closed_at` | `DateTime(timezone=True)` | Yes | none | Set once, by `/close` (FR-2) or the auto-close job (FR-3). Never cleared (`"closed"` is terminal). |
| `closed_by` | `uuid.UUID` (no `ForeignKey`) | Yes | none | Set once, to the acting user's id (`/close`, FR-2) or to the system-actor sentinel UUID (auto-close job, FR-3). Deliberately no FK — see db-design.md. Resolves OD-7. |

### New / corrected `CHECK` constraints

```python
CheckConstraint(
    "(status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL)",
    name="ck_tickets_closed_requires_closed_fields",
)
CheckConstraint(
    "status != 'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)",
    name="ck_tickets_resolved_requires_resolution_fields",
)
```

The second corrects the story's literal biconditional to a one-directional
implication — see db-design.md's "CHECK constraints" section for why the
literal form breaks FR-2/FR-3.

### New index

```python
Index(
    "ix_tickets_resolved_at_pending_autoclose",
    "resolved_at",
    postgresql_where=text("status = 'resolved'"),
)
```

### `tickets.status` value set — unchanged from US-4.1/US-4.2

`{open, waiting_on_support, waiting_on_customer, resolved, closed}` — no
`"reopened"` value (OD-1; the source story's own literal value set is not
adopted). Still a plain `String(32)`, no DB-level enum or `CHECK` on the
value set itself (unchanged project convention).

## `audit_log` (existing table, `app/modules/audit/models.py`) — new `event` values only

No column, constraint, or index changes. Four new `event` string values are
written via the existing `record_event(...)` service method (US-4.1's
generic write path):

| `event` | `category` | `actor_id` | `target_id` | `outcome` | `payload` |
|---|---|---|---|---|---|
| `ticket_resolved` | `"tickets"` | resolving agent's id | `ticket.id` | `"success"` | `NULL` |
| `ticket_closed` *(inferred, see db-design.md)* | `"tickets"` | closing user's id | `ticket.id` | `"success"` | `NULL` |
| `ticket_auto_closed` | `"tickets"` | system-actor sentinel UUID | `ticket.id` | `"success"` | `NULL` |
| `ticket_reopened` *(FR-5, direct reopen)* | `"tickets"` | reopening user's id | `ticket.id` | `"success"` | `NULL` |
| `ticket_reopened` *(FR-4, reply-driven reopen — reused per DR-4)* | `"tickets"` | replying requester's id | `ticket.id` | `"success"` | `NULL` |

`actor_role`, `request_id`, `ip`, `user_agent` follow the existing
`record_event` call shape (`actor_role` resolved via `_resolve_actor_role`;
the other three always `NULL` for this generic path, unchanged from US-4.1's
usage). FR-4 (reply reopens via US-4.2's reply endpoint) now writes this
`audit_log` entry too — `DESIGN_REVIEW` v2's DR-4 finding — reusing
`ticket_reopened` since FR-4 performs the identical `resolved` →
`waiting_on_support` transition FR-5 already audits under that name; see
db-design.md for the full rationale and call-site note.

## Relationships / loading strategy

No new relationship; no new FK. `Ticket` continues to declare no
`relationship()` (unchanged `US-4.1`/`US-4.2` precedent). `closed_by`'s
absence of a `ForeignKey` is a deliberate deviation from `requester_id`
(`Ticket`) / `uploaded_by` (`Attachment`) / `author_id` (`TicketReply`),
which are all real FKs — `closed_by` alone must also represent a non-real
"system" actor.

```
Ticket (1) ──< AuditLog.target_id >── (0..n, no FK — unchanged, US-3.3 design)
```

## No changes to `attachments` or `ticket_replies`

Neither table is touched by this story.
