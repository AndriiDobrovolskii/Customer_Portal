# DB Design: US-2.2 Logout

**Spec:** `docs/specifications/US-2.2-spec.md` (Pass with Issues, accepted 2026-08-31)
**API:** `docs/designs/api/US-2.2-openapi.yaml`, `US-2.2-api-design.md`

## What changes, per entity

### `user_sessions` (existing table) — no schema change

FR-1's access-token revocation reuses the `revoked_at` column US-2.1 already added and already checks on every authenticated request (resolved OD-1 — this story does not introduce a Valkey `jti_denylist`, contrary to the story's original literal design). The write is a single-row `UPDATE user_sessions SET revoked_at = now() WHERE jti = :jti` against the existing primary key — no new index needed, the PK lookup already exists.

FR-4's idempotent repeat call (resolved OD-2) re-issues the identical `UPDATE` against a row whose `revoked_at` is already set — a no-op in effect (setting an already-set timestamp to a new `now()` value is harmless; nothing reads `revoked_at`'s *exact* value, only whether it's `NULL`). No schema accommodation needed for idempotency; it falls out of the existing column's semantics.

### `refresh_tokens` (existing table, resolved OD-3) — add `revoked_at`, index `family_id`

The table (added by US-2.1 for OD-9, ahead of US-2.3) has no revocation column and no index on `family_id` today, since nothing before this story ever needed to look up or update by family. This story adds the minimal pair FR-1 needs:

- **`revoked_at`** — nullable `DateTime(timezone=True)`, no default, set explicitly on every row in a family when that family is revoked. Matches this project's established nullable-timestamp-state-transition pattern (`user_sessions.revoked_at`, `users.deactivated_at`, `EmailChangeToken.consumed_at`).
- **`ix_refresh_tokens_family_id`** on `family_id` — the lookup path for FR-1's "revoke every row sharing this family_id," which is a new query pattern this story introduces (US-2.1 only ever wrote one row per family; it never queried by `family_id`).

**Lookup-by-cookie mechanics (spec-review finding, resolved 2026-08-31):** FR-1 first resolves the presented refresh cookie to its row via the existing unique `token_hash` index (`SELECT * FROM refresh_tokens WHERE token_hash = :hash`), then updates every row sharing that row's `family_id`. If the `SELECT` finds no row (stale/tampered/deleted cookie), the `UPDATE` step is skipped entirely — no schema accommodation needed, this is a service-layer branch on an empty query result, not a persistence concern.

**Not added:** `consumed_at` or any single-use/rotation columns — remains US-2.3's own migration, per resolved OD-3's explicit scope boundary.

### `auth_audit_log` (existing table, resolved OD-5) — add `scope`

The table (added by US-2.1) has `event`/`reason` but no way to record which blast radius a logout event covered. This story adds:

- **`scope`** — nullable `String(32)`, no default. Values `session` (FR-1) or `all_sessions` (FR-2) on logout rows; `NULL` on every other event type this table already records (`login_succeeded`, `login_failed`, etc. — unaffected, no migration needed for existing rows since the new column is nullable).

Rejected alternative: reusing the existing `reason` column for `scope`'s values. Not used — `reason`'s established meaning across every other row in this table is "why did the attempt fail" (`bad_password`, `unknown_email`, etc.); overloading it with a "which blast radius, on a *successful* logout" concept would make the column's semantics ambiguous for anyone reading the table without first checking `event`. A dedicated column keeps each field single-purpose, matching the project's existing audit-table style (one column, one meaning, per US-2.1's own `auth_audit_log` design).

### Indexes

- `ix_refresh_tokens_family_id` on `refresh_tokens(family_id)` — new, per above.
- No new index on `auth_audit_log.scope`: no FR or NFR in this story states a query pattern filtering by `scope` alone; the existing `actor_id` index already serves the anticipated "audit history for this account" pattern (US-3.3's eventual audit-view query is not this story's concern to pre-guess, same reasoning US-2.1's design applied).
- No new index on `user_sessions`: FR-1/FR-4/FR-5 all key off the existing primary key (`jti`).

## Relationships / loading strategy

No new relationships. `refresh_tokens`'s family-wide `UPDATE` is a bulk statement (`sqlalchemy.update()`, matching the existing `revoke_sessions_except` pattern in `UserRepository`), not an ORM collection load — no `relationship()`/eager-loading strategy is needed for it. Same for `user_sessions`'s single-row `UPDATE`.

## Sensitive columns

No new sensitive columns. `refresh_tokens.token_hash` and `user_sessions.jti` (both already sensitive-adjacent, unchanged) are read, not newly exposed; `auth_audit_log.scope` is a closed two-value label (`session`/`all_sessions`), the same non-sensitive class as `event`/`reason`.

## Explicitly deferred / not decided here

1. **`refresh_tokens.family_id`'s existing `nullable=False, default=uuid.uuid4` stays unchanged.** This story only adds `revoked_at` and an index; it does not touch `family_id`'s existing definition.
2. **CSRF-related schema** — resolved OD-4, descoped from this story entirely; no table or column is modeled here for it.
3. **`refresh_tokens.consumed_at`** — remains US-2.3's own migration when single-use rotation is implemented; this story's `revoked_at` addition is deliberately scoped to family-wide revocation only, not per-token consumption state.
