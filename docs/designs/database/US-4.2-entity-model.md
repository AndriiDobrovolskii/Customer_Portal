---
artifact_type: entity_model
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
supersedes: docs/designs/database/US-4.2-entity-model.md (v2)
---

# Entity Model: Ticket Replies (US-4.2 / spec US-4.2)

## Revision Note (v3)

Regenerated against specification v6 / API design v3 / open-decisions v3 (see
`US-4.2-db-design.md` v3's Revision Note for the full rationale). No entity,
column, constraint, or index below changed from v2 — only the resolution
status of OD-8 is corrected: `DESIGN_REVIEW` v2 found v2's "confirmed to
candidate (a), status stays `"resolved"`" reading was never an actual human
decision; the human then resolved OD-8 directly to candidate (b) — a customer
reply on a `"resolved"` ticket transitions `tickets.status` to
`"waiting_on_support"`, reopening it. This remains a status-transition detail
with no schema impact, per Known Gaps below — `"waiting_on_support"` is an
existing, unconstrained string value already written by this story's FR-2
ordinary case, not a new column or enum value.

## Entities

### `TicketReply` (`ticket_replies`) — new

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `ticket_id` | `Mapped[uuid.UUID]` | No | — | FK → `tickets.id`, no `ondelete` (defaults `RESTRICT`) |
| `author_id` | `Mapped[uuid.UUID]` | No | — | FK → `users.id`, no `ondelete` (defaults `RESTRICT`), no index (no query needs it) |
| `author_kind` | `Mapped[str]` → `String(20)` | No | — | Values `"customer"` \| `"agent"`; no default — service states it explicitly |
| `body` | `Mapped[str]` → `String(5000)` | No | — | Matches `Ticket.body`'s cap exactly (FR-7); plain text only (OD-4) |
| `visibility` | `Mapped[str]` → `String(20)` | No | `server_default="public"` | Values `"public"` \| `"internal"`; default per Resolution OD-6 |
| `created_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — |

**Table-level constraints:**
- `CheckConstraint("visibility = 'public' OR author_kind = 'agent'", name="ck_ticket_replies_visibility_agent_only")` — FR-5 / BR-015 write-side enforcement.
- `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + two command-scoped policies (`ticket_replies_read` FOR SELECT, `ticket_replies_write` FOR INSERT) — FR-3 / BR-015 read-side enforcement. See db-design.md for the full `CREATE POLICY` statements and the fail-closed rationale.

### `Ticket` (`tickets`) — existing, additive column

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `first_response_at` | `Mapped[datetime \| None]` → `DateTime(timezone=True)` | Yes | None (starts `NULL`) | Stamped once, on the first public agent reply (FR-1); no index |

Every other `Ticket` column is unchanged from `US-4.1-entity-model.md`. No
`resolved_at` column is added — confirmed absent, per `US-4.2-db-design.md`
(API design Open Question #3, raised in v2 and unaffected by the v3
OD-8 correction).

### `Attachment` (`attachments`) — existing, additive column

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `ticket_reply_id` | `Mapped[uuid.UUID \| None]` | Yes | — | FK → `ticket_replies.id`, no `ondelete` (defaults `RESTRICT`), `index=True`; `NULL` until bound, never cleared/reassigned once set (service-enforced, not DB-enforced — same gap as `ticket_id`) |

Every other `Attachment` column, including the existing `ticket_id`, is
unchanged from `US-4.1-entity-model.md`. `ticket_id` and `ticket_reply_id`
are independent nullable bindings — Resolution OD-1 adds reply-level binding
alongside ticket-level binding, not instead of it.

## Relationships

```
Ticket (1) ──< TicketReply.ticket_id >── (0..n)
User   (1) ──< TicketReply.author_id >── (0..n)
TicketReply (1) ──< Attachment.ticket_reply_id >── (0..n, nullable until bound, immutable after)
Ticket (1) ──< Attachment.ticket_id >── (0..n, nullable until bound, immutable after — unchanged from US-4.1)
User   (1) ──< Attachment.uploaded_by >── (0..n — unchanged from US-4.1)
```

No `relationship()` declared on `TicketReply`, and none added to `Ticket`/
`Attachment` by this story — consistent with `US-4.1-entity-model.md`'s
existing precedent of direct repository queries over ORM graph traversal.
`GET /v1/support/tickets/{id}`'s `TicketDetailRead` response
(`US-4.2-openapi.yaml` v2: ticket fields plus a `replies: ReplyThreadPage`
of `{items, next_cursor}`) is composed from two direct queries: `Ticket.get_by_id`
(existing) and a new keyset-paginated `list_for_ticket` on a new
`TicketReplyRepository`. No `joinedload`/`selectinload` strategy applies —
no relationship exists to load eagerly or lazily.

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `ticket_replies` | composite `(ticket_id, created_at, id)` | Thread-fetch keyset pagination (Resolution OD-3), oldest-first; `id` breaks same-timestamp ties |
| `tickets` | none new | `first_response_at` is never filtered/sorted on |
| `attachments` | `index=True` on `ticket_reply_id` | Mirrors existing `ticket_id` index; future "attachments on this reply" lookup |

## Traceability

| Entity/Column | Functional Requirement(s) |
|---|---|
| `TicketReply.ticket_id`, `.author_id`, `.body`, `.created_at` | FR-1, FR-2, FR-7 |
| `TicketReply.author_kind`, `.visibility`, CHECK constraint | FR-5 (customer cannot create internal notes) |
| `ticket_replies` RLS policy | FR-3, TR-AC3 (internal-note isolation, database-layer guarantee) |
| `ticket_replies` composite `(ticket_id, created_at, id)` index | GET Thread Pagination (Resolution OD-3) |
| `Ticket.first_response_at` | FR-1 (stamped on first public agent reply) |
| `Attachment.ticket_reply_id` | FR-1 (`attachment_ids` bound to a specific reply, Resolution OD-1) |

## Known Gaps (not decided at this stage)

- Mapping a caller's actual role (`support_agent`/`admin`) to `author_kind`'s
  two-value vocabulary and to the `app.actor_kind` RLS session GUC —
  `service-and-router-builder`'s call; see db-design.md.
- `TicketReplyRepository`'s exact method signatures — `IMPLEMENTATION_PLANNING`'s
  call.
- Customer reply on a `"resolved"` ticket: OD-8 is resolved (human decision,
  2026-09-05T09:00:00Z, `docs/decisions/US-4.2-open-decisions.md` v3) as
  `201`, `tickets.status` transitions to `"waiting_on_support"` — reopening
  the ticket. This remains a service-layer status-write decision, not a
  schema one — this entity model is unaffected either way, as v1/v2 already
  noted before the actual resolution.
- `ticket_id`/`author_id`'s `ondelete` behavior once BR-007's account-erasure
  job mechanics are decided — currently `RESTRICT`-by-default, same
  placeholder as `Ticket.requester_id`/`Attachment.uploaded_by`.
