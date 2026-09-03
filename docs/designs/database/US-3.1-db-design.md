# DB Design: Manage Users (US-3.1 / spec US-3.1)

**Source spec:** docs/specifications/US-3.1-spec.md (revised 2026-09-02; Data Model Notes: `users.status`, `invitation_tokens`, `admin_audit_log`)
**Spec review:** docs/reviews/specifications/US-3.1-spec-review.md (Pass with Issues, accepted 2026-09-02)
**API design:** docs/designs/api/US-3.1-openapi.yaml

## Overview

This story touches one existing table with no schema change (`users` — the `"invited"` status value, already representable in its existing unconstrained `String(32)` column), extends two existing tables with nullable columns per `us-clarifier`'s OD-1/OD-2 resolutions (`admin_audit_log`, built by US-3.2; `account_lifecycle_audit_log`, built by US-1.4), and introduces one new table (`invitation_tokens`, following the `email_verification_tokens`/`password_reset_tokens` precedent exactly).

## `users` (no schema change)

`status` is already `Mapped[str]` → `String(32)`, `nullable=False`, with no `CHECK` constraint (confirmed by inspection of `app/modules/users/models.py`) — application-layer validation already governs its values (`invited`/`active`/`deactivated`/implicit `pending_verification`, per `business-glossary.md`'s "Account" entry). `"invited"` is a new value within this existing, unconstrained column; no migration needed for the column itself.

**New index:** composite `(status, created_at)`, per the spec's Data Model Notes, supporting `GET /v1/admin/users`'s `status` filter combined with the list's implied recency ordering (FR-1).

**New index (search):** `q`'s prefix/substring match (FR-1) needs a trigram or `tsvector` index on the columns it searches. Per `us-clarifier`'s OD-3/api-design Open Question 3, the spec does not state which column(s) `q` matches — this design assumes `email` and `display_name` (the only two free-text, human-searchable columns FR-1's response item includes), but that assumption is not authoritative; confirm at PLANNING. Recommend `pg_trgm` (`GIN` index using `gin_trgm_ops`) over a generated `tsvector` column, since a substring/prefix match on names and emails is a better fit for trigram similarity than full-text tokenization, and this project has no existing full-text search precedent to weigh against. **`pg_trgm` has no prior use anywhere in this codebase** — the migration will need `CREATE EXTENSION IF NOT EXISTS pg_trgm` (a one-time, database-wide operation, not per-table), which is new infrastructure this story introduces, not simply a new column.

## `invitation_tokens` (new table)

Matches the spec's Data Model Notes and the `email_verification_tokens`/`password_reset_tokens` precedent exactly (both already shipped, identical shape).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid4()` | PK, this project's uniform UUID-PK convention. |
| `user_id` | UUID | No | — | FK → `users.id`, `ondelete="CASCADE"`, indexed — matches every existing FK-to-`users.id` convention (`UserSession`, `RefreshToken`, `PasswordResetToken`, `EmailVerificationToken`). |
| `token_hash` | `String(64)` | No | — | Unique. SHA-256 hex digest of the raw token (spec: "SHA-256"), never the raw token itself — matches `PasswordResetToken.token_hash`/`EmailVerificationToken.token_hash` exactly. |
| `issued_at` | `DateTime(timezone=True)` | No | `func.now()` | Server default, matching the identical precedent columns. |
| `expires_at` | `DateTime(timezone=True)` | No | — | Set by the application to `issued_at + 24h` (FR-5's 24-hour TTL); not a DB-computed default, matching precedent (neither `PasswordResetToken` nor `EmailVerificationToken` computes this at the DB layer). |
| `consumed_at` | `DateTime(timezone=True)` | Yes | — | `NULL` until the invitee completes setup; also written (to the current time, or the row itself invalidated — see Gap below) when FR-18's resend invalidates a still-outstanding prior token. |

**Indexes:** unique index on `token_hash` (token lookup on setup-completion, matching precedent); index on `user_id` (needed by FR-18's "any previously issued, unconsumed invitation token for that account is invalidated" — a per-user query filtered on `consumed_at IS NULL`).

**Gap not decided here:** FR-18 says a prior unconsumed token is "invalidated" on resend, but neither the story nor the spec states the mechanism — set `consumed_at` to now (reusing the existing column, distinguishable from a genuine consumption only by cross-referencing whether the account's status changed), add a separate `invalidated_at` column, or hard-delete the row. This design assumes reusing `consumed_at` (no new column) since it requires no schema addition and every consumer of this table already treats `consumed_at IS NOT NULL` as "not usable," but the service layer's ability to distinguish "used to complete setup" from "invalidated by a resend" (relevant if that distinction is ever needed for audit purposes) is not resolved by this choice — flag for PLANNING.

## `admin_audit_log` (existing, US-3.2 — extended per OD-1)

Existing columns unchanged: `id`, `event`, `actor_id`, `target_id`, `old_roles`, `new_roles`, `severity`, `request_id`, `occurred_at` (`app/modules/roles/models.py`'s `AdminAuditLog`).

**Actor representation note:** MU-AC5/MU-AC9/MU-AC18 all describe the audit entry's actor as `actor=admin:{id}` (a formatted string), but the shipped column is `actor_id: UUID` (not a string), matching how US-3.2 already writes it for role-replacement rows. This is not a mismatch to resolve: every row this table holds is written by an admin by construction (only admin-gated service methods ever call the write path), so a bare `actor_id` UUID satisfies the story's `admin:{id}` intent without needing a formatted-string column — unlike `account_lifecycle_audit_log.actor`, which is a `String(64)` because that table's rows come from *both* the self-service (`"self"`) and admin (`"admin:{id}"`) paths and genuinely needs to distinguish them in-band.

**New columns** (all nullable — populated only by rows this story's Update slice writes; existing US-3.2 role-replacement rows leave them `NULL`):

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `field` | `String(64)` | Yes | — | The changed field's name (e.g. `"display_name"`) — one row per changed field, per FR-9/MU-AC9. `64` chosen to comfortably exceed any current or plausible future column-name length; not stated by the spec. |
| `old_value` | `Text` | Yes | — | Stringified pre-change value. `Text`, not a bounded `String`, since the whitelisted editable fields include `avatar_url` (`String(2048)` on `User`) — a bounded column here would risk truncating a legitimate value. |
| `new_value` | `Text` | Yes | — | Stringified post-change value, same rationale as `old_value`. |
| `reason` | `Text` | Yes | — | Per MU-AC9's "(old_value, new_value, actor, reason)" — the admin's stated reason for the field change. The story's own PATCH request/API Contract does not name a `reason` field in the request body, unlike deactivate's explicit `{reason}`; this design assumes the same request-level `reason` field the deactivate endpoint uses is also accepted (optionally) by `PATCH`, since MU-AC9 requires it be persisted per changed field — **flagged as a gap, not decided here**: whether `PATCH`'s request schema needs its own `reason` field is an API-design question, not resolved by `US-3.1-openapi.yaml` (which did not include one — see that design's own gap list, now cross-referenced here). |

**No new index needed:** `actor_id`/`target_id` are already indexed (existing US-3.2 columns); no query pattern implied by FR-9 needs a new index on `field`/`old_value`/`new_value`/`reason`.

## `account_lifecycle_audit_log` (existing, US-1.4 — extended per OD-2)

Existing columns unchanged: `id`, `user_id`, `event`, `actor`, `occurred_at` (`app/modules/account/models.py`'s `AccountLifecycleAuditLog`).

**New column:**

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `reason` | `Text` | Yes | — | Populated only by admin-initiated deactivation (FR-13/MU-AC13's mandatory `{reason}`); self-service deactivation (DA-AC1) leaves it `NULL`, preserving DA-AC10's "identical side effects" invariant for every pre-existing column. `Text`, not a bounded `String`, since no length limit is stated anywhere in the story or spec. |

**No new index needed:** `user_id` is already indexed; no query pattern reads `account_lifecycle_audit_log` by `reason`.

## Security

- `invitation_tokens.token_hash`: SHA-256 hash only, never the raw token — matches `PasswordResetToken`/`EmailVerificationToken` precedent exactly. No encryption requirement stated or implied.
- `admin_audit_log.old_value`/`new_value`: these hold the whitelisted editable fields' values (`display_name`, `locale`, `timezone`, `avatar_url`, per the API design's `UpdateUserRequest`) — none of this project's sensitive-data categories (password, token, MFA secret). No redaction requirement beyond this project's existing blanket rule (NFR-001) that credential material never appears in any log, which these fields don't touch since `PATCH` never accepts `email`/`password`.
- No new PII beyond what `users` already stores; `invitation_tokens`/audit-log additions introduce no new personal-data category.

## Migration Note

Per `AGENTS.md` §4's migrations bullet and this project's Definition of Done: the migration itself (guards, `if_not_exists`, the `CREATE EXTENSION IF NOT EXISTS pg_trgm` statement, the `GIN` index creation — which needs `CONCURRENTLY` + `autocommit_block()` per `AGENTS.md` §4's PostgreSQL-hazards guidance, since `users` is a live table with existing rows — and the `upgrade`/`downgrade`/`upgrade` proof) belongs to the implementation stage (`migration-manager`), not this design.
