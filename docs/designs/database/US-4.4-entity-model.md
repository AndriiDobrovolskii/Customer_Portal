---
artifact_type: entity_model
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T20:00:00Z"
updated_at: "2026-09-08T09:30:00Z"
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

# Entity Model: Agent Ticket Queue & Assignment (US-4.4 / spec US-4.4)

Narrative rationale for every decision below is in
`docs/designs/database/US-4.4-db-design.md`. This document states only the
concrete shape. No column, constraint, or index already shipped by
US-4.1/US-4.2/US-4.3 is repeated or modified — only what this story adds.

## `tickets` (existing table — one additive column)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `assignee_id` | `uuid.UUID`, `ForeignKey("users.id")` | Yes | none (starts `NULL`) | Set by `POST .../assign` (FR-3, including re-assignment); cleared by `DELETE .../assign` (FR-4). No `ondelete` override (`RESTRICT`-by-default, same BR-007-pending placeholder as `requester_id`/`uploaded_by`). No inline single-column index — served by the composite index below. |

```python
assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

No `CHECK` constraint added tying `assignee_id` to `status` — see
db-design.md for why one would be actively wrong (a closed ticket may still
carry its last `assignee_id`). OD-3 (unassign-on-closed 409-vs-200) does not
change this column either way.

### New indexes

```python
Index(
    "ix_tickets_queue_default_updated_at_id",
    "updated_at",
    "id",
    postgresql_where=text("status != 'closed'"),
)
Index(
    "ix_tickets_status_updated_at_id",
    "status",
    "updated_at",
    "id",
)
Index(
    "ix_tickets_assignee_id_updated_at_id",
    "assignee_id",
    "updated_at",
    "id",
)
```

The first is this design's own addition beyond the story's literal
`(status, updated_at, id)` + `(assignee_id, updated_at, id)` pair — see
db-design.md "Indexes" for why FR-1's default (filterless) query needs a
dedicated partial index rather than relying on the status-led composite
alone, and for the required literal `status != 'closed'` predicate form
(not an `IN`-list) the repository's query must use for this index to be
selected. The other two match the story's Data Model Notes verbatim.

RLS was checked and confirmed absent on `tickets` (only `ticket_replies`
carries a policy, `migrations/versions/9132a68b73c8_add_ticket_replies.py`)
— see db-design.md "Indexes" note. `updated_at`'s existing `onupdate=func.now()`
means assign/unassign will bump it (a real, stated consequence for the new
"oldest `updated_at` first" queue ordering) — see db-design.md's
"`updated_at`'s write semantics" note.

### `tickets.__table_args__` after this story (illustrative — full tuple)

```python
__table_args__ = (
    Index(
        "ix_tickets_requester_id_created_at_id",
        "requester_id",
        "created_at",
        "id",
    ),  # US-4.1, unchanged
    Index(
        "ix_tickets_resolved_at_pending_autoclose",
        "resolved_at",
        postgresql_where=text("status = 'resolved'"),
    ),  # US-4.3, unchanged
    CheckConstraint(
        "(status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL)",
        name="ck_tickets_closed_requires_closed_fields",
    ),  # US-4.3, unchanged
    CheckConstraint(
        "status != 'resolved' OR (resolved_at IS NOT NULL AND resolution_note IS NOT NULL)",
        name="ck_tickets_resolved_requires_resolution_fields",
    ),  # US-4.3, unchanged
    Index(
        "ix_tickets_queue_default_updated_at_id",
        "updated_at",
        "id",
        postgresql_where=text("status != 'closed'"),
    ),  # US-4.4, new
    Index(
        "ix_tickets_status_updated_at_id",
        "status",
        "updated_at",
        "id",
    ),  # US-4.4, new
    Index(
        "ix_tickets_assignee_id_updated_at_id",
        "assignee_id",
        "updated_at",
        "id",
    ),  # US-4.4, new
)
```

## `audit_log` (existing table, `app/modules/audit/models.py`) — new `event` values only

No column, constraint, or index change. Two new `event` string values are
written via the existing `record_event(...)` service method (US-4.1's
generic write path):

| `event` | `category` | `actor_id` | `target_id` | `outcome` | `payload` |
|---|---|---|---|---|---|
| `ticket_assigned` | `"tickets"` | the caller (assigner) | `ticket.id` | `"success"` | `{"assignee_id": <new value, uuid>}` |
| `ticket_unassigned` | `"tickets"` | the caller | `ticket.id` | `"success"` | `{"assignee_id": null}` |

`actor_role`, `request_id`, `ip`, `user_agent` follow the existing
`record_event` call shape (`actor_role` resolved via `_resolve_actor_role`;
the other three always `NULL`, unchanged from US-4.1/US-4.3's usage).
`payload` carrying `assignee_id` is story-mandated (Data Model Notes:
"each recording `actor_id` and the target `assignee_id`"), not this design's
invention — it departs from US-4.1/US-4.3's `payload: NULL` precedent
because, unlike `resolution_note`/`closed_at`, `assignee_id` is overwritten
by every subsequent assign/unassign, so `target_id` alone can't reconstruct
history; see db-design.md "Audit trail".

## Relationships / loading strategy

One new FK, no new `relationship()`:

```
User (1) ──< Ticket.assignee_id >── (0..n, FK, RESTRICT-by-default, nullable)
```

`Ticket` continues to declare no `relationship()` (unchanged US-4.1/US-4.2/
US-4.3 precedent) — no read this story's endpoints perform needs an
eager-loaded `User` object; `AgentTicketRead`/`AgentTicketStateRead` carry
only the raw `assignee_id` UUID. See db-design.md for the deferred
display-name/relationship note (spec Open Question #5).

## No changes to `attachments` or `ticket_replies`

Neither table is touched by this story.
