# Entity Model: US-2.2 Logout

Traceability: every column below cites the FR it exists for.

## `user_sessions` (existing table, `app/modules/users/models.py`) — no schema change

```python
class UserSession(Base):
    __tablename__ = "user_sessions"

    jti: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

All columns already exist (added by US-2.1). This story writes `revoked_at = now()` on the row matching the presented jti (FR-1) — no new column, no migration needed for this table. `get_session_by_jti` (existing repository method) is the lookup this story reuses.

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `revoked_at` *(existing, written by this story)* | `DateTime(timezone=True)` | Yes | none — set explicitly | FR-1 (single jti), FR-4 (idempotent re-write of the same row — see db-design.md) |

## `refresh_tokens` (existing table, `app/modules/users/models.py`) — add `revoked_at`

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # new
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `revoked_at` *(new)* | `DateTime(timezone=True)` | Yes | none — set explicitly | FR-1 (whole family, resolved OD-3) |
| `family_id` *(existing, gains an index)* | UUID | No | app-side `uuid4()` (existing) | FR-1 (lookup key for the family-wide `UPDATE`) |
| `token_hash`, `user_id`, `issued_at`, `expires_at` *(existing)* | — | — | — | FR-1 (read: resolves the presented cookie to its row) |

`consumed_at` and single-use rotation tracking are **not** added — remain US-2.3's responsibility (resolved OD-3).

**Indexes:** `ix_refresh_tokens_family_id` on `family_id` *(new — needed for FR-1's "revoke every row sharing this family_id" `UPDATE`, which previously had no index to use since this story is the first to query by `family_id`)*. `ix_refresh_tokens_user_id` on `user_id` and the unique index on `token_hash` are existing and unchanged.

**Relationships:** none added — this story looks up a single row by `token_hash`, then updates by `family_id`; no ORM relationship traversal is needed.

## `auth_audit_log` (existing table, `app/modules/users/models.py`) — add `scope`

```python
class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32))
    scope: Mapped[str | None] = mapped_column(String(32))  # new
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text())
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `scope` *(new)* | `String(32)` | Yes | — | FR-1 (`session`), FR-2 (`all_sessions`); `NULL` for every non-logout event (`login_succeeded`, `login_failed`, etc.) |
| `event` *(existing)* | `String(32)` | No | — | FR-1, FR-2 (`logout`, shared value for both scopes) |
| `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at` *(existing)* | — | — | — | FR-1, FR-2 (populated identically to every other event type already written to this table) |

`reason` is deliberately left `NULL` on logout rows — per resolved OD-5, `scope` is a distinct column rather than overloading `reason`'s established "why did this fail" meaning.

**Indexes:** no new index. The existing `ix_auth_audit_log_actor_id` on `actor_id` already serves the anticipated "audit history for this account" query pattern (per US-2.1's own precedent); no FR or NFR in this story states a query pattern filtering by `scope` alone.

**Relationships:** none (unchanged — no FK, per the existing "must survive account deletion" rationale).

## Not modeled here (explicitly out of scope for this design)

- `refresh_tokens.consumed_at` and any single-use rotation columns — US-2.3's own migration.
- `user_sessions` — no new column; this story only writes the existing `revoked_at`.
- Any CSRF-related table or column — resolved OD-4, descoped from this story entirely.
