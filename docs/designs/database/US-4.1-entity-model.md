---
artifact_type: entity_model
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

# Entity Model: Support Tickets (Create) (US-4.1 / spec US-4.1)

## Revision Note (v3)

DR-6 fix: the `AuditLog.actor_role` row below now names the actual
resolution mechanism — a service-to-service call from
`app/modules/audit/service.py`'s `_resolve_actor_role` to
`app/modules/roles/service.py`'s `get_role_grants_for_user` (via the
`RoleServiceProtocol` collaborator), not "auth middleware." `Ticket` /
`Attachment` are otherwise unchanged from v2; `docs/designs/api/US-4.1-api-design.md`
v3 is authorization-wording-only and states explicitly that it requires no
DB design change.

## Entities

### `Ticket` (`tickets`) — new

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `ticket_number` | `Mapped[str]` → `String(20)` | No | Server-computed from `ticket_number_seq`, formatted `CP-{year}-{seq:07d}` (hand-written migration `DEFAULT` expression, `server_default=FetchedValue()`, same style as `AuditLog.previous_hash`) | `unique=True` |
| `requester_id` | `Mapped[uuid.UUID]` | No | — | FK → `users.id`, no `ondelete` (defaults `RESTRICT` — BR-007 gap, see db-design), `index=True` |
| `subject` | `Mapped[str]` → `String(150)` | No | — | Matches FR-3's 150-char cap exactly |
| `body` | `Mapped[str]` → `String(5000)` | No | — | Matches FR-3's 5000-char cap exactly; plain text only (OD-5) |
| `category` | `Mapped[str]` → `String(50)` | No | — | No enum/CHECK — OD-3 unresolved, see db-design; matches `CreateTicketRequest.category`/`TicketRead.category` `maxLength: 50` (`US-4.1-openapi.yaml` v3) |
| `status` | `Mapped[str]` → `String(32)` | No | `server_default="open"` | Plain string, matches `users.status` precedent; this story only ever writes `"open"` |
| `created_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — |
| `updated_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()`, `onupdate=func.now()` | Not written by any code path in this story; set up for US-4.2/US-4.3 |

### `Attachment` (`attachments`) — new

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK; UUIDv4 per spec NFR (non-enumerable) |
| `uploaded_by` | `Mapped[uuid.UUID]` | No | — | FK → `users.id`, no `ondelete` (defaults `RESTRICT` — same BR-007 gap), `index=True` |
| `ticket_id` | `Mapped[uuid.UUID \| None]` | Yes | — | FK → `tickets.id`, no `ondelete` (defaults `RESTRICT`); `NULL` until bound, never cleared once set (service-enforced, not DB-enforced — see db-design), `index=True` |
| `created_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | Drives the 24h unbound-purge job |

### `AuditLog` (`audit_log`) — existing, not owned by this story

Defined by `docs/designs/database/US-3.3-db-design.md` /
`app/modules/audit/models.py`; restated here only for traceability of this
story's write, not redefined or altered. This story adds no column, index,
or migration to `audit_log` — it adds one new row shape (a new `category`
literal and `event` value) via the existing table.

| Column | Type (as shipped) | Value this story writes |
|---|---|---|
| `id` | `Mapped[uuid.UUID]` (PK) | Server-assigned (`default=uuid.uuid4`) |
| `occurred_at` | `Mapped[datetime]` (PK, partition key) | Server-assigned (`server_default=func.now()`) |
| `category` | `Mapped[str]` → `String(32)` | `"tickets"` (new literal) |
| `actor_id` | `Mapped[uuid.UUID \| None]`, no FK | `requester_id` |
| `actor_role` | `Mapped[str \| None]` → `String(32)` | Caller's role(s) if available at the call site, else `NULL`. **(DR-6 fix)** Resolved by `app/modules/audit/service.py`'s `_resolve_actor_role`, a service-to-service call to `app/modules/roles/service.py`'s `get_role_grants_for_user` (via the `RoleServiceProtocol` collaborator) — not auth middleware; sorted role names are comma-joined when a user holds more than one |
| `event` | `Mapped[str]` → `String(64)` | `"ticket_created"` |
| `target_id` | `Mapped[uuid.UUID \| None]`, no FK | `ticket.id` |
| `outcome` | `Mapped[str \| None]` → `String(32)` | `"success"` |
| `request_id` | `Mapped[str \| None]` → `String(64)` | Per-request id, if threaded through to this module |
| `ip` / `user_agent` | `Mapped[str \| None]` | `NULL` — not required by FR-1 |
| `payload` | `Mapped[dict[str, Any] \| None]` (`JSONB`) | `{"ticket_number": <str>, "category": <str>}` |
| `previous_hash` / `row_hash` | `Mapped[str]` (trigger-computed) | Not written by application code — `BEFORE INSERT` trigger |

## Relationships

```
User (1) ──< Ticket.requester_id >── (0..n)
User (1) ──< Attachment.uploaded_by >── (0..n)
Ticket (1) ──< Attachment.ticket_id >── (0..n, nullable until bound, immutable after)
Ticket (1) ──< AuditLog.target_id >── (0..n, no FK — must survive account/record lifecycle per US-3.3's own design)
User (1) ──< AuditLog.actor_id >── (0..n, no FK — survives account erasure)
```

No `relationship()` declared on `Ticket`/`Attachment`, and none added to
`AuditLog` by this story — every query this story's endpoints issue is a
direct single-table lookup or a keyset-filtered list, never a traversed
graph (`TicketRead` carries no nested `attachments` or audit data). No
`joinedload`/`selectinload` strategy applies. The `audit_log` write is a
plain insert via the audit module's own service layer (service → service,
`AGENTS.md` §3), not an ORM relationship traversal from `Ticket`.

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `tickets` | unique on `ticket_number` | Human-facing lookup/display uniqueness |
| `tickets` | composite `(requester_id, created_at DESC, id DESC)` | FR-2 keyset pagination, "newest first," `id` breaks same-timestamp ties |
| `attachments` | on `ticket_id` | Bind lookup |
| `attachments` | on `uploaded_by` | FR-7 ownership check |
| `attachments` | partial, on `created_at` `WHERE ticket_id IS NULL` | 24h unbound-purge job scan |
| `audit_log` | (existing, unchanged) `(occurred_at DESC, actor_id, event)` | Already covers `ticket_created` rows; no new index added for this story |

## Traceability

| Entity/Column | Functional Requirement(s) |
|---|---|
| `Ticket` (all columns except `updated_at`) | FR-1 |
| `Ticket.status`, `Ticket.category` validation gap | FR-3 |
| `Ticket` composite `(requester_id, created_at, id)` index | FR-2 |
| `Attachment` (all columns) | FR-7 |
| `AuditLog` row with `category="tickets"`, `event="ticket_created"` | FR-1 (`event=ticket_created`) |
| Valkey `idempotency:{user_id}:{key}` (see db-design.md) | FR-4 |
| Valkey `ticket_create_rate:{user_id}` (see db-design.md) | FR-6 |

## Known Gaps (not decided at this stage)

- `ticket_number`'s year-reset behavior (single global sequence vs. per-year
  reset) — either satisfies every stated AC; see db-design.md.
- `category`'s enumerated value set — OD-3, stakeholder decision.
- `requester_id`/`uploaded_by`'s `ondelete` behavior once BR-007's
  account-deletion/anonymization job mechanics are decided — currently
  `RESTRICT`-by-default (safe, not silent).
- `attachments.ticket_id` immutability is service-enforced only; no DB
  trigger/constraint prevents a future code path from rebinding it.
- The exact `app/modules/audit/service.py`/`repository.py` method signature
  this story's write uses — fixed at `IMPLEMENTATION_PLANNING`, not here.
