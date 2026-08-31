# Entity Model: US-004 Deactivate Account

Traceability: every column below cites the FR it exists for.

## `users` (modify existing — `app/modules/users/models.py`)

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `deactivated_at` *(new)* | `DateTime(timezone=True)` | Yes | none — set explicitly | FR-1 (set), FR-8 (cleared) |
| `status` *(existing, new value used)* | `String(32)` | No | none (existing) | FR-1 (`"deactivated"`), FR-8 (`"active"`) |

No other `users` columns change.

## `account_lifecycle_audit_log` (new table)

```python
class AccountLifecycleAuditLog(Base):
    __tablename__ = "account_lifecycle_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Deliberately no FK: FR-9 removes the users row this entry describes,
    # after writing the entry — the audit trail must survive that deletion.
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `id` | UUID | No | app-side `uuid4()` | all |
| `user_id` | UUID (no FK) | No | — | FR-1, FR-8, FR-9, FR-10 |
| `event` | `String(32)` | No | — | FR-1 (`deactivated`), FR-8 (`reactivated`), FR-9 (`permanently_deleted`) |
| `actor` | `String(64)` | No | — | FR-1/FR-10 (`self` / `admin:{admin_id}`), FR-9 (`system`) |
| `occurred_at` | `DateTime(timezone=True)` | No | `func.now()` | FR-9 (must precede row removal — NFR) |

**Indexes:** `ix_account_lifecycle_audit_log_user_id` on `user_id`.

**Relationships:** none (no FK, no `relationship()` — see db-design.md rationale).

## Not modeled here (explicitly out of scope for this design)

- Valkey `revoke_before:{user_id}` key — substrate undecided, see `US-004-db-design.md` §"Explicitly deferred".
- Any `user_sessions` schema change — existing table (`app/modules/users/models.py:UserSession`) is unmodified by this design; whether FR-1 needs a bulk-revoke query against it is a service/repository decision, not a schema one.
