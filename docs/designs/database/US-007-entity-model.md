# Entity Model: US-2.3 Refresh Token

Traceability: every column below cites the FR it exists for.

## `refresh_tokens` (existing table, `app/modules/users/models.py`) — add `consumed_at`, `last_used_at`, `ip`, `user_agent`

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
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # new
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # new
    ip: Mapped[str | None] = mapped_column(String(45))  # new
    user_agent: Mapped[str | None] = mapped_column(Text())  # new
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `consumed_at` *(new)* | `DateTime(timezone=True)` | Yes | none — set explicitly | FR-1 (set on rotation), FR-2 (already set = reuse signal), FR-7 (the atomic `WHERE consumed_at IS NULL` guard) |
| `last_used_at` *(new)* | `DateTime(timezone=True)` | Yes | none — set on the new row at rotation time; `NULL` until a family's first rotation | FR-4 (idle-timeout reference point, `COALESCE(last_used_at, issued_at)`) |
| `ip` *(new)* | `String(45)` | Yes | none | Data Model Notes (for US-2.6); not read by any FR in this story |
| `user_agent` *(new)* | `Text` | Yes | none | Data Model Notes (for US-2.6); not read by any FR in this story |
| `revoked_at` *(existing, US-2.2)* | `DateTime(timezone=True)` | Yes | none | FR-2 (set on every row in a reused family) |
| `family_id` *(existing, indexed since US-2.2)* | UUID | No | app-side `uuid4()` | FR-1 (new row keeps the same value), FR-2 (family-wide `UPDATE` key) |
| `expires_at` *(existing)* | `DateTime(timezone=True)` | No | — | FR-1 (copied forward unchanged — this **is** the absolute cap), FR-5 |
| `token_hash`, `user_id`, `issued_at` *(existing)* | — | — | — | FR-1 (lookup key / new-row fields) |

**Indexes:** unchanged. The existing unique index on `token_hash` serves both the initial lookup and the atomic `UPDATE ... WHERE token_hash = :hash AND consumed_at IS NULL RETURNING *` (FR-7); the existing `ix_refresh_tokens_family_id` (US-2.2) serves FR-2's family-wide revocation.

**Relationships:** none added. FR-1 is an `INSERT` (new row) + a single-row atomic `UPDATE` (the presented row); FR-2 is the existing bulk `UPDATE ... WHERE family_id = :id`.

## `auth_audit_log` (existing table, `app/modules/users/models.py`) — add `severity`

```python
class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32))
    scope: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str | None] = mapped_column(String(16))  # new
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
| `severity` *(new)* | `String(16)` | Yes | — | FR-2 (`"high"` on `event=refresh_reuse_detected`; `NULL` on every other event type) |
| `event`, `reason`, `scope`, `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at` *(existing)* | — | — | — | FR-2 (populated identically to every other event type already written to this table; `reason`/`scope` remain `NULL` on this event, matching their own established single-purpose meanings) |

**Indexes:** no new index — same reasoning as US-2.2's `scope` column (`ix_auth_audit_log_actor_id` already serves the anticipated per-account audit query pattern; no FR/NFR here states a `severity`-only filter).

**Relationships:** none (unchanged — no FK, must survive account deletion).

## Not modeled here (explicitly out of scope for this design)

- A `family_id`-keyed Valkey rate-limit counter (resolved OD-1) — a cache-layer, not a Postgres, concern; deferred to `data-layer-builder`'s `cache.py`.
- Any link from `user_sessions` to `refresh_tokens.family_id` — explicitly not built, per resolved OD-6 (accepted ≤15-minute residual access-token window on reuse).
- Any CSRF-related table or column — unrelated to this story, standing follow-up from US-2.2's OD-4.
