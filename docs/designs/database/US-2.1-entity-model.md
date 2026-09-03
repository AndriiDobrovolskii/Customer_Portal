# Entity Model: US-2.1 Login

Traceability: every column below cites the FR it exists for.

## `users` (modify existing — `app/modules/users/models.py`)

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `last_login_at` *(new)* | `DateTime(timezone=True)` | Yes | none — set explicitly | FR-1 |
| `status` *(existing)* | `String(32)` | No | none (existing) | FR-4 (read: `"deactivated"` gate) |
| `email_verified` *(existing)* | `Boolean` | No | `false` (existing) | FR-4 (read: unverified gate) |

No other `users` columns change.

## `auth_audit_log` (new table)

```python
class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32))
    # Deliberately no FK: the row must survive the eventual 30-day-grace-
    # period account deletion/anonymization (BR-007), matching every other
    # audit table in this project.
    actor_id: Mapped[uuid.UUID | None] = mapped_column()
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text())
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `id` | UUID | No | app-side `uuid4()` | all |
| `event` | `String(32)` | No | — | FR-1 (`login_succeeded`), FR-2/FR-3/FR-4 (`login_failed`) |
| `reason` | `String(32)` | Yes | — | FR-2 (`bad_password`), FR-3 (`unknown_email`), FR-4 (`email_not_verified` / `account_deactivated`); `NULL` for FR-1 |
| `actor_id` | UUID (no FK) | Yes | — | FR-1, FR-2, FR-4 (set); FR-3 (`NULL` — no account matched) |
| `ip` | `String(45)` | No | — | FR-1–FR-4 (source IP of every logged attempt) |
| `user_agent` | `Text` | Yes | — | FR-1–FR-4 (`User-Agent` header; nullable — header is optional) |
| `request_id` | `String(64)` | No | — | FR-1–FR-4 (correlation id) |
| `occurred_at` | `DateTime(timezone=True)` | No | `func.now()` | FR-1–FR-4 |

**Indexes:** `ix_auth_audit_log_actor_id` on `actor_id`.

**Relationships:** none (no FK, no `relationship()` — see db-design.md rationale).

## `refresh_tokens` (new table, resolved OD-9)

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(nullable=False, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `id` | UUID | No | app-side `uuid4()` | — |
| `token_hash` | `String(64)` | No | — | FR-1 (SHA-256 hex of the raw cookie value) |
| `family_id` | UUID | No | app-side `uuid4()` | FR-1 (new family per login; US-2.3 extends within it) |
| `user_id` | UUID (FK, cascade) | No | — | FR-1 |
| `issued_at` | `DateTime(timezone=True)` | No | `func.now()` | FR-1 |
| `expires_at` | `DateTime(timezone=True)` | No | — | FR-1 |

**Indexes:** `ix_refresh_tokens_user_id` on `user_id`; unique index on `token_hash`.

**Relationships:** none added yet — no FR in this story reads the row back after inserting it.

**Not included here** (added by US-2.3/US-2.6 with their own migration): `consumed_at`, `ip`, `user_agent`, `last_used_at`.

## Not modeled here (explicitly out of scope for this design)

- Any change to `users.status`/`users.email_verified` definitions — this story only reads them (FR-4), it doesn't extend the `UserStatus` enum or add new gating values.
- The rate-limit counters (`login_fail:account:{user_id}`, `login_fail:ip:{ip}`) — these are Valkey keys per the source story's Data Model Notes, not a Postgres entity; they belong to `data-layer-builder`'s `cache.py`, not this schema design.
- `429`/`422` audit rows — resolved OD-6: neither response is written to `auth_audit_log` at all, so no schema accommodation is needed for them.
- `refresh_tokens.consumed_at`/`ip`/`user_agent`/`last_used_at` — US-2.3/US-2.6's own columns, not this story's.
