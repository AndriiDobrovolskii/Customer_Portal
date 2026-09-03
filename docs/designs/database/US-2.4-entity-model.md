# Entity Model: Password Reset (US-2.4 / spec US-2.4)

**Written:** 2026-09-01

## New Entity: `PasswordResetToken`

```python
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Column-for-column identical to `app/modules/email_verification/models.py::EmailVerificationToken`, per the source story's own stated precedent. No relationship attribute is declared on `User` (no back-reference needed — see `db-design.md`), so no eager-loading strategy applies to this entity in either direction.

## Existing Entities Touched (no schema change)

| Entity | Change | Why no migration needed |
|---|---|---|
| `User` (`app/modules/users/models.py`) | `hashed_password` overwritten on success (FR-2) | Existing column, existing write path (same as registration/login). |
| `AuthAuditLog` (`app/modules/users/models.py`) | Two new `event` values: `password_reset_requested`, `password_reset_completed` | `event` is `String(32)`; both values (25 chars) fit. `scope`/`severity` stay `None` for these events — no established scope variant applies here (mirrors `refresh_reuse_detected`'s `scope=None`), and no elevated `severity` is stated by the spec (mirrors `login_failed`'s `severity=None`; only `refresh_reuse_detected` uses `severity="high"`). <!-- pragma: allowlist secret --> |
| Valkey revocation cache (`revoke_before:{user_id}`) | Set to now on successful reset (FR-2) | Existing mechanism (`app/core/revocation_cache.py`), already documented in `docs/product/business-glossary.md`'s **Revocation** entry as one of this story's own triggers — no new cache key. |

## Relationships Diagram

```
User (1) ──< (0..N) PasswordResetToken     [ondelete=CASCADE]
User (1) ──< (0..N) AuthAuditLog            [no FK — actor_id survives account deletion]
```

## Migration Impact

Additive only: one new table (`password_reset_tokens`), zero `ALTER` statements on existing tables. Follows the same guarded-additive pattern as `9f9d9263bdfc` (US-2.2) and `c8eeaa6b5ff6` (US-2.3).
