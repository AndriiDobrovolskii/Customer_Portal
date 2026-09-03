# Entity Model: Multi-Factor Authentication / TOTP (US-2.5 / spec US-2.5)

## Entities

### `User` (`users`) — 4 new columns

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `mfa_enabled` | `Mapped[bool]` → `Boolean` | No | `server_default=false()` | — |
| `mfa_secret_encrypted` | `Mapped[bytes \| None]` → `LargeBinary` | Yes | — | — |
| `mfa_activated_at` | `Mapped[datetime \| None]` → `DateTime(timezone=True)` | Yes | — | — |
| `mfa_reenrollment_required` | `Mapped[bool]` → `Boolean` | No | `server_default=false()` | — |

### `MfaRecoveryCode` (`mfa_recovery_codes`) — new

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK |
| `user_id` | `Mapped[uuid.UUID]` | No | — | FK → `users.id`, `ondelete="CASCADE"`, index |
| `code_hash` | `Mapped[str]` → `String(255)` | No | — | — |
| `created_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — |
| `consumed_at` | `Mapped[datetime \| None]` → `DateTime(timezone=True)` | Yes | — | — |

### `UserRole` (`user_roles`) — 1 new column, on the already-merged US-3.2 table

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `granted_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | — |

## Relationships

```
User (1) ──< MfaRecoveryCode >── (many)
```

| Owning side | Relationship | Cardinality | Loading strategy | Used by |
|---|---|---|---|---|
| `User` | `mfa_recovery_codes` (collection) | one-to-many | `selectinload` | FR-7 verify (load all unconsumed codes for one-of-N Argon2id check); FR-8 disable (hard-delete all rows for the user) |

No many-to-one relationship is introduced by this story (`MfaRecoveryCode.user` would be many-to-one, but nothing in this story's flows needs to navigate from a code back to its user as an object — the FK is used directly as a filter column, not traversed as a relationship). `lazy="raise_on_sql"` is the default on `User.mfa_recovery_codes` per this project's data-layer convention.

No relationship changes on `UserRole`/`Role` — `granted_at` is a plain column read directly via the existing `user_roles` query path US-3.2 already established (`resolve_scopes_for_user` and its sibling role-name-lookup method, per `docs/specifications/US-2.5-spec.md` FR-6's OD-7 resolution), not a new join.

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `mfa_recovery_codes` | on `user_id` (via FK) | Load a user's unconsumed codes for verification (FR-7) and bulk-delete on disable (FR-8) |
| `users` | none new | The 4 new columns are read alongside every other `users` row fetch (by `id`), no new access pattern needing its own index |
| `user_roles` | none new | `granted_at` is read together with the existing `user_id`-keyed lookup path US-3.2 already indexes |

## Traceability

| Entity/Column | Functional Requirement(s) |
|---|---|
| `User.mfa_enabled`, `mfa_secret_encrypted`, `mfa_activated_at` | FR-1 (enroll, PENDING state), FR-2 (activate) |
| `User.mfa_reenrollment_required` | FR-7 (set on recovery-code use), FR-2 (cleared on activation — shared exit condition with FR-6) |
| `MfaRecoveryCode` | FR-2 (issued 10-at-a-time), FR-7 (consumed one-at-a-time), FR-8 (purged on disable) |
| `UserRole.granted_at` | FR-6 (14-day grace-period clock — spec-review resolution) |

## Known Gaps (not decided at this stage)

- The exact one-of-N Argon2id verification pattern for recovery codes (loop-and-verify vs. some indexable pre-check) is a service-layer algorithm decision, not a schema decision — flagged for `planner`.
- `MfaRecoveryCode`'s hard-delete-on-disable (FR-8) vs. `PasswordResetToken`'s keep-but-mark-consumed precedent is a deliberate divergence (per OD-8's resolution), not an oversight — noted here so `data-layer-builder` doesn't "fix" it to match the other pattern.
