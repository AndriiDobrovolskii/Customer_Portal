# Entity Model: Manage Users (US-3.1 / spec US-011)

## Entities

### `User` (`users`) — no schema change

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `status` | `Mapped[str]` → `String(32)` | No | — | Existing column; `"invited"` is a new valid value, not a new column. |

New indexes only (see below) — no `Mapped[]`/`mapped_column()` change to `app/modules/users/models.py`'s `User` class.

### `InvitationToken` (`invitation_tokens`) — new

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `user_id` | `Mapped[uuid.UUID]` | No | — | FK → `users.id`, `ondelete="CASCADE"`, `index=True` |
| `token_hash` | `Mapped[str]` → `String(64)` | No | — | `unique=True` |
| `issued_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — |
| `expires_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | — | Set by application code to `issued_at + 24h` |
| `consumed_at` | `Mapped[datetime \| None]` → `DateTime(timezone=True)` | Yes | — | `NULL` until setup completion or resend-invalidation (see db-design's Gap note) |

### `AdminAuditLog` (`admin_audit_log`) — existing (US-3.2), extended

| Column | Type | Nullable | Default | Constraints | Status |
|---|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK | unchanged |
| `event` | `Mapped[str]` → `String(32)` | No | — | — | unchanged |
| `actor_id` | `Mapped[uuid.UUID \| None]` | Yes | — | `index=True`, no FK | unchanged |
| `target_id` | `Mapped[uuid.UUID \| None]` | Yes | — | `index=True`, no FK | unchanged |
| `old_roles` | `Mapped[list[str] \| None]` → `ARRAY(String(32))` | Yes | — | — | unchanged |
| `new_roles` | `Mapped[list[str] \| None]` → `ARRAY(String(32))` | Yes | — | — | unchanged |
| `severity` | `Mapped[str \| None]` → `String(16)` | Yes | — | — | unchanged |
| `request_id` | `Mapped[str]` → `String(64)` | No | — | — | unchanged |
| `occurred_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — | unchanged |
| `field` | `Mapped[str \| None]` → `String(64)` | Yes | — | — | **new (OD-1)** |
| `old_value` | `Mapped[str \| None]` → `Text` | Yes | — | — | **new (OD-1)** |
| `new_value` | `Mapped[str \| None]` → `Text` | Yes | — | — | **new (OD-1)** |
| `reason` | `Mapped[str \| None]` → `Text` | Yes | — | — | **new (OD-1)** |

### `AccountLifecycleAuditLog` (`account_lifecycle_audit_log`) — existing (US-1.4), extended

| Column | Type | Nullable | Default | Constraints | Status |
|---|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK | unchanged |
| `user_id` | `Mapped[uuid.UUID]` | No | — | `index=True`, no FK | unchanged |
| `event` | `Mapped[str]` → `String(32)` | No | — | — | unchanged |
| `actor` | `Mapped[str]` → `String(64)` | No | — | — | unchanged |
| `occurred_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — | unchanged |
| `reason` | `Mapped[str \| None]` → `Text` | Yes | — | — | **new (OD-2)** |

## Relationships

```
User (1) ──< InvitationToken >── (0..1 outstanding)
User (1) ──< AdminAuditLog.target_id >── (0..n, no FK — matches AuthAuditLog's precedent)
User (1) ──< AccountLifecycleAuditLog.user_id >── (0..n, no FK — must outlive account deletion)
```

`InvitationToken.user_id` is the only new/changed foreign-key relationship. No SQLAlchemy `relationship()` is required on `User` for it (no story requirement reads "a user's invitation tokens" as a collection — `resend-invite`'s repository query is a direct `WHERE user_id = :id AND consumed_at IS NULL` lookup, not a traversed relationship), matching this codebase's existing precedent of not adding a `relationship()` for `PasswordResetToken`/`EmailVerificationToken` either.

No `joinedload`/`selectinload` strategy is introduced by this story — no new collection relationship is added to any `Mapped[]` model.

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `users` | composite `(status, created_at)` | `GET /v1/admin/users`'s `status` filter + list ordering (FR-1) |
| `users` | `GIN` trigram (`gin_trgm_ops`) on `email`, `display_name` | `q` prefix/substring search (FR-1) — column assumption flagged as a gap, see db-design |
| `invitation_tokens` | unique on `token_hash` | Token lookup on setup completion |
| `invitation_tokens` | on `user_id` | Per-user unconsumed-token lookup (FR-18 resend-invalidation) |
| `admin_audit_log` | none new | Existing `actor_id`/`target_id` indexes already cover this story's write pattern |
| `account_lifecycle_audit_log` | none new | Existing `user_id` index already covers this story's write pattern |

## Traceability

| Entity/Column | Functional Requirement(s) |
|---|---|
| `users.status = "invited"` (existing column, new value) | FR-5, FR-18, FR-19 |
| `users` `(status, created_at)` index | FR-1 |
| `users` trigram index | FR-1 (`q` search) |
| `InvitationToken` | FR-5, FR-18, FR-19 |
| `AdminAuditLog.field/old_value/new_value/reason` | FR-9 (OD-1) |
| `AccountLifecycleAuditLog.reason` | FR-13 (OD-2) |

## Known Gaps (not decided at this stage)

- `q`'s matched column(s) assumed to be `email`/`display_name` — not stated by the spec (db-design's own note, cross-referenced from `US-011-api-design.md` Open Question 3).
- FR-18's "invalidated" mechanism for a prior unconsumed `invitation_tokens` row (reuse `consumed_at` vs. a new `invalidated_at` column vs. hard-delete) is unresolved — this design assumes reusing `consumed_at`.
- Whether `PATCH /v1/admin/users/{id}`'s request body needs its own `reason` field (for `AdminAuditLog.reason`, OD-1) is unresolved by the API design — `US-011-openapi.yaml`'s `UpdateUserRequest` does not currently declare one.
