# DB Design: US-2.3 Refresh Token

**Spec:** `docs/specifications/US-2.3-spec.md` (Pass with Issues, accepted 2026-09-01, all 3 same-day findings resolved)
**API:** `docs/designs/api/US-2.3-openapi.yaml`, `US-2.3-api-design.md`

## What changes, per entity

### `refresh_tokens` (existing table) — add `consumed_at`, `last_used_at`, `ip`, `user_agent`

Current columns (`id`, `token_hash`, `family_id`, `user_id`, `issued_at`, `expires_at`, `revoked_at`) come from US-2.1 (issuance) and US-2.2 (OD-3's minimal `revoked_at` for family-wide logout revocation). This story adds the four columns the source story's Data Model Notes list and haven't been built yet:

- **`consumed_at`** — nullable `DateTime(timezone=True)`, no default. Set exactly once, when a row is rotated (FR-1) or detected as reused (FR-2, where it's already set — reuse is *defined* as a second presentation of a row whose `consumed_at` is already non-`NULL`). Same nullable-timestamp-state-transition pattern as `revoked_at`, `users.deactivated_at`.
- **`last_used_at`** — nullable `DateTime(timezone=True)`, no default. Set to `now()` on the **new** row created by a successful rotation (FR-1); left `NULL` on a row created by initial login issuance (US-2.1) that has never itself been rotated forward. FR-4's idle-timeout check reads `COALESCE(last_used_at, issued_at)` on the *presented* token, so a family that has never been refreshed since login still has a valid reference point (the login moment itself). This design deliberately does not update `last_used_at` on the *old*, about-to-be-consumed row — for a single-use token, "last used" and "consumed" would be the identical instant, so tracking it on the new row (representing "the family's most recent successful refresh") avoids two columns racing to mean the same thing.
- **`ip`**, **`user_agent`** — nullable `String(45)` / `Text()`, no default, matching `AuthAuditLog`'s existing types for the same concepts. Populated on every row this story's rotation (FR-1) creates. **Deliberately nullable, not matching `AuthAuditLog.ip`'s `nullable=False`:** making them required would force a change to US-2.1's already-shipped `create_refresh_token` call site (which doesn't collect `ip`/`user_agent` today) as a side effect of this story's own migration — see the Open Question below rather than deciding that here.

**Not added:** a dedicated family-creation timestamp. Per the spec's FR-1/FR-5, the 30-day absolute cap is enforced via the existing `expires_at` — fixed once at family creation (already how US-2.1's login issuance sets it) and copied forward unchanged by every rotation. No new column needed for this; `expires_at` already carries the information.

### `refresh_tokens` — atomic check-and-consume mechanism (FR-7 / RT-AC6)

The spec's FR-7 permits either a Valkey Lua script or a conditional Postgres `UPDATE`. This design recommends the Postgres route:

```sql
UPDATE refresh_tokens
SET consumed_at = now()
WHERE token_hash = :hash AND consumed_at IS NULL
RETURNING *;
```

No new index needed — `token_hash`'s existing unique index already serves this `WHERE` clause. Rationale: `refresh_tokens` is already the single source of truth for this state (unlike login's throttle counters, which have no DB-backed equivalent); introducing a second system (Valkey) to arbitrate the same fact the row already holds would create exactly the kind of dual-source-of-truth risk `AGENTS.md` §3 already steers away from for the token denylist ("the cache is never the source of truth"). A losing concurrent request's `UPDATE` affects zero rows; the service then reads the row's `consumed_at` to decide whether it's inside the 10-second grace window (plain `401`, no revocation) or a genuine reuse (FR-2's family-wide revocation) — no new column needed for this distinction, `consumed_at`'s existing value is sufficient.

### `auth_audit_log` (existing table) — add `severity` (resolved OD-4)

- **`severity`** — nullable `String(16)`, no default. Set to `"high"` on `event=refresh_reuse_detected` rows only (FR-2); `NULL` on every other event type this table already records, same pattern as US-2.2's own `scope` column addition (OD-5 there).

### Indexes

- No new index on `refresh_tokens`. The existing unique index on `token_hash` serves both the lookup (lookup-then-consume) and the atomic `UPDATE ... WHERE token_hash = ... AND consumed_at IS NULL` above. The existing `ix_refresh_tokens_family_id` (added by US-2.2's OD-3) already serves FR-2's family-wide revocation `UPDATE`.
- No new index on `auth_audit_log.severity`. Same reasoning as US-2.2's `scope` column: no FR or NFR in this story states a query pattern filtering by `severity` alone; `ix_auth_audit_log_actor_id` already serves the anticipated "history for this account" pattern.

## Relationships / loading strategy

No new relationships. FR-1's rotation is an `INSERT` (new row) plus an `UPDATE` (the presented row, atomic per above) — no ORM collection load. FR-2's family-wide revocation is the existing bulk `UPDATE ... WHERE family_id = :id` (unchanged mechanism from US-2.2). No `relationship()`/eager-loading strategy is needed for any of this story's queries.

## Sensitive columns

- `refresh_tokens.token_hash` — unchanged, already SHA-256-hashed, never the raw token (per the story's own Token Design assumption and this project's existing `hash_refresh_token`).
- `refresh_tokens.ip` — coarse-grained PII (an IP address), same sensitivity class as `auth_audit_log.ip` (existing, unredacted at rest); no new redaction requirement stated by this story's spec, so none is invented here.
- No other new sensitive columns. `last_used_at`/`consumed_at` are timestamps; `severity` is a closed low-cardinality label (`"high"`/`NULL`), same non-sensitive class as `auth_audit_log.event`/`reason`/`scope`.

## Explicitly deferred / not decided here

1. **Whether US-2.1's login-issuance `create_refresh_token` call is also updated to populate `ip`/`user_agent`.** This story's own rotation path (FR-1) populates both on every row it creates; the original login-issued row (US-2.1, already shipped) does not collect these values today. Leaving them `NULL` on that first row is schema-safe (both are nullable) but means a family's very first row shows no origin metadata for US-2.6's eventual session listing until its first rotation. This touches already-shipped US-2.1 code, so it's flagged for `planner` rather than decided here.
2. **The `family_id`-keyed rate-limit counter (resolved OD-1) is a Valkey structure, not a Postgres entity — out of this design's scope.** Sizing/naming it (e.g. a `refresh_rate_limit:{family_id}` key, following the existing `login_fail:*` prefix convention in `app/core/cache_keys.py`) is `data-layer-builder`'s `cache.py` responsibility during IMPLEMENTATION, per `openapi-designer`'s own OQ-2 in `docs/designs/api/US-2.3-api-design.md`.
3. **CSRF-related schema** — out of scope for this story entirely (unrelated to refresh; carried as a standing follow-up from US-2.2's OD-4).
