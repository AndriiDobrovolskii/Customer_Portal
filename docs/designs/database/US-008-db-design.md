# DB Design: Password Reset (US-2.4 / spec US-008)

**Spec:** `docs/specifications/US-008-password-reset-spec.md`
**Spec review:** `docs/reviews/specifications/US-008-spec-review.md` (Pass with Issues, accepted 2026-09-01)
**API design:** `docs/designs/api/US-008-openapi.yaml`, `docs/designs/api/US-008-api-design.md`
**Written:** 2026-09-01

## Summary

One new table, `password_reset_tokens`, additive-only. No change to any existing table — `auth_audit_log`'s existing `event` (`String(32)`) column already accommodates this story's two new event names (`password_reset_requested`, `password_reset_completed`, both 25 characters) without a migration, and its `scope`/`severity` columns (added by US-2.2/US-2.3) are already nullable and reusable as-is.

## `password_reset_tokens` (new table)

Per the spec (FR-1) and the source story's Data Model Notes: "same shape as `email_verification_tokens` in US-1.2." This design follows `app/modules/email_verification/models.py::EmailVerificationToken` column-for-column, since that table is the story's own explicitly cited precedent, with one addition (`family_invalidated_at` — see below) needed for FR-1's "any previously issued, unconsumed reset token for that account is invalidated" clause, which `EmailVerificationToken` has no equivalent for (email verification never needed to invalidate a prior token when a new one issues).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid4()` (app-side) | Primary key. |
| `user_id` | UUID | No | — | `ForeignKey("users.id", ondelete="CASCADE")`, indexed. Row does not need to survive account deletion (unlike `auth_audit_log`) — a reset token has no meaning once the account is gone. |
| `token_hash` | `String(64)` | No | — | SHA-256 hex digest (64 chars) of the raw `secrets.token_urlsafe(32)` token. Unique constraint — this is the lookup key on `confirm`, and collision would mean two live tokens resolve to the same row. |
| `issued_at` | `DateTime(timezone=True)` | No | `server_default=func.now()` | |
| `expires_at` | `DateTime(timezone=True)` | No | — | App-computed: `issued_at + 30 minutes` (FR-1). |
| `consumed_at` | `DateTime(timezone=True)` | Yes | `NULL` | Set atomically on successful `confirm` (spec-review resolution: `UPDATE...WHERE consumed_at IS NULL RETURNING`, guarding the concurrent-request race). |

**Indexes:**
- Unique index on `token_hash` (lookup path for `confirm`, and the uniqueness guarantee itself).
- Index on `user_id` (lookup path for `request`'s "invalidate any previously issued, unconsumed token for that account" — needs an efficient `WHERE user_id = ? AND consumed_at IS NULL` scan).

**Relationships:** many-to-one to `User` (`ondelete="CASCADE"`). No collection relationship needs eager loading here — the repository queries this table directly by `token_hash` or `user_id`, never traverses it from a loaded `User` object, so no `joinedload`/`selectinload` is required on the `User` side either (mirrors `EmailVerificationToken`, which has no back-reference on `User`).

**On "invalidating a previously issued, unconsumed token" (FR-1):** this is implemented as setting `consumed_at = now()` on any prior unconsumed row for the same `user_id` when a new token issues — reusing the `consumed_at` column itself as the invalidation marker (a row consumed by invalidation is indistinguishable at the DB level from one consumed by actual use, which is fine: both states must reject the token identically at `confirm`, per FR-4). This needs no new column; the design note above is a repository-behavior note, not a schema change — flagged here only because the source story's Data Model Notes call it out as a distinct requirement worth a reader's attention.

## Sensitive Data

- `token_hash`: SHA-256 hash only — the raw token is never persisted anywhere, matching `EmailVerificationToken`/`RefreshToken` precedent and NFR-001.
- No password material touches this table (the new password is written to `users.hashed_password` via the existing Argon2id path — no design change needed there).

## Deferred to PLANNING / IMPLEMENTATION

- **Breached-password list/bloom filter (OD-1) storage:** not a database table — a bundled static asset (file or in-process structure) shipped with the application, outside this design's scope. `implementation-planner`/`data-layer-builder` decide the concrete form (OQ-1 in the API design).
- **Rate-limit Valkey keys (OD-2):** the three-limit throttle (60 s cooldown, 5/account/hour, 10/IP/hour) is Valkey-backed advisory state, not a Postgres table — out of this design's scope, same precedent as US-2.3's `RefreshRateLimitCache` (`data-layer-builder`'s `cache.py`). OQ-2 in the API design.

## Migration Standard

Per `AGENTS.md` §4's Migrations bullet: the eventual migration adds `password_reset_tokens` as a wholly new, additive table (no `ALTER` on any existing table), guarded via `sa.inspect(op.get_bind())` per this project's standard pattern, and must be proven through a real `upgrade → downgrade → upgrade` cycle before IMPLEMENTATION's gate.
