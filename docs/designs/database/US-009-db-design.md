# DB Design: Multi-Factor Authentication / TOTP (US-2.5 / spec US-009)

**Source spec:** docs/specifications/US-009-mfa-totp-spec.md (Data Model Notes: `users.mfa_enabled`, `users.mfa_secret_encrypted`, `users.mfa_activated_at`, `mfa_recovery_codes`, Valkey replay key, `auth_audit_log` event names)
**Spec review:** docs/reviews/specifications/US-009-spec-review.md (Pass with Issues, resolved 2026-09-01)
**API design:** docs/designs/api/US-009-openapi.yaml

## Overview

Three additive changes: four new columns on `users`, one new table (`mfa_recovery_codes`), and one new column on the already-merged `user_roles` (US-3.2). No existing column changes type or nullability, and `auth_audit_log`'s existing `String(32) event` column already fits every new event name this story introduces (`mfa_enabled`, `mfa_disabled`, `mfa_verify_failed`, `mfa_recovery_used`) — confirmed against `app/modules/users/models.py::AuthAuditLog`.

## `users` (modified — 4 new columns)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `mfa_enabled` | `Boolean` | No | `server_default=false()` | Matches this table's existing `email_verified` column's exact pattern. `true` only after activation (FR-2). |
| `mfa_secret_encrypted` | `LargeBinary` (`bytea`) | Yes | — | AES-GCM ciphertext (nonce + tag + ciphertext), never the raw secret (OD-2). `NULL` when never enrolled or after a disable (FR-8) purges it; non-`NULL` while PENDING or ACTIVE. |
| `mfa_activated_at` | `DateTime(timezone=True)` | Yes | — | Set once, at FR-2 activation. `NULL` while PENDING or never enrolled. Not reset by OD-11 re-enrolment (a PENDING secret being overwritten doesn't touch this column, since it's still `NULL` at that point). |
| `mfa_reenrollment_required` | `Boolean` | No | `server_default=false()` | New (OD-5 — not in the story's own Data Model Notes, since the story never described this state). Set `true` on recovery-code consumption (FR-7); cleared on the next successful activation (FR-2's exit condition). |

**Enrolment state is derived, not a separate enum column** (the story never calls for one): "never enrolled" = `mfa_secret_encrypted IS NULL AND mfa_enabled = false`; "PENDING" = `mfa_secret_encrypted IS NOT NULL AND mfa_enabled = false`; "ACTIVE" = `mfa_enabled = true`. This mirrors the existing `PENDING_VERIFICATION`-via-`email_verified=false` pattern already used on this same table for a different lifecycle.

## `mfa_recovery_codes` (new)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid4()` | PK, matches this project's uniform UUID-PK convention. |
| `user_id` | UUID | No | — | FK → `users.id`, `ondelete="CASCADE"`, indexed. |
| `code_hash` | `String(255)` | No | — | Argon2id hash (BR-003), never plaintext. Same column length as `users.hashed_password` — Argon2id's encoded output is variable-length but well under 255 chars. No uniqueness constraint: Argon2id salts each hash independently, so two codes never collide in storage even if the plaintext were reused (which it isn't — codes are randomly generated). |
| `created_at` | `DateTime(timezone=True)` | No | `server_default=func.now()` | Matches `issued_at`'s pattern on `PasswordResetToken`/`RefreshToken`. |
| `consumed_at` | `DateTime(timezone=True)` | Yes | — | `NULL` until used (FR-7); set exactly once, matching the single-use semantics `PasswordResetToken.consumed_at` already establishes. |

**Verification pattern:** a submitted recovery code can't be looked up by hash equality (each hash is independently salted), so `verify` (FR-7) loads all of a user's `consumed_at IS NULL` rows and checks the submitted code against each with Argon2id's constant-time verify — the same one-of-N pattern this project doesn't yet have precedent for elsewhere, but is the only correct approach for salted hashes. Flagged for `planner`/`service-and-router-builder`, not a DB-layer concern.

**Deletion on disable (FR-8):** all rows for a user are hard-deleted, not soft-marked, when MFA is disabled — the story and OD-8's resolution are explicit that disable purges codes entirely ("worthless without a secret, keeping them is pure liability"), unlike the consumed-but-kept pattern `PasswordResetToken` uses.

## `user_roles` (modified — 1 new column, on the already-merged US-3.2 table)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `granted_at` | `DateTime(timezone=True)` | No | `server_default=func.now()` | New (spec-review resolution, resolved 2026-09-01 — not part of US-3.2's original design). `NOT NULL` with a `server_default` means `ADD COLUMN` backfills every existing row to the migration's execution time automatically — no separate `UPDATE` statement needed. `PUT /v1/admin/users/{id}/roles` (US-012 FR-1) sets this explicitly to `now()` on every row it inserts (a full-replacement write deletes and re-inserts, so every surviving grant gets a fresh timestamp — acceptable, since the grace period is meant to measure "since this user most recently needed to comply," not archival history). |

This is a small, additive change to an already-shipped, already-merged table — no other column, constraint, or endpoint of US-3.2 changes.

## Valkey (not a DB table — noted for `cache.py`, not decided further here)

- `mfa_used_step:{user_id}:{step}` — replay protection (FR-4), TTL one time step (30s), per the story's own Data Model Notes.
- The brute-force counter (FR-5) reuses this project's existing per-`mfa_token` Valkey-counter pattern (the same shape login's own lockout counter uses) — no new cache-key scheme invented here.

## Security

- `mfa_secret_encrypted`: AES-GCM ciphertext, key from settings (OD-2, a dev-only stand-in for a real KMS-managed key) — never the raw secret, never returned in any response after enrolment (spec NFR).
- `mfa_recovery_codes.code_hash`: Argon2id, never plaintext, consistent with BR-003's project-wide hashing rule.
- `mfa_reenrollment_required` and `granted_at`: not sensitive — plain operational state, no PII/credential material.

## Migration Note

Per `AGENTS.md` §4's migrations bullet: the migration itself (guards, `if_not_exists` where autogenerate reaches it, and the `ADD COLUMN ... NOT NULL DEFAULT` mechanics for `user_roles.granted_at`) belongs to `migration-manager` at IMPLEMENTATION, not this design. `migrations/env.py` must not be edited (`AGENTS.md` §7.9), matching the precedent already established when US-3.2 added its own tables.
