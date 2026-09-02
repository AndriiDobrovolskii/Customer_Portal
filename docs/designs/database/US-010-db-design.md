# DB Design: US-2.6 Active Session Management

**Spec:** `docs/specifications/US-010-active-session-management-spec.md` (Pass with Issues, resolved 2026-09-02)
**API:** `docs/designs/api/US-010-openapi.yaml`, `US-010-api-design.md`

## What changes, per entity

### `refresh_tokens` (existing table) — no new columns, one new composite index

Every column FR-1 through FR-7 needs already exists: `family_id`, `user_id`, `issued_at`, `expires_at`, `revoked_at`, `consumed_at`, `last_used_at`, `ip`, `user_agent` were all added by US-2.1/US-2.2/US-2.3 (confirmed against the live `app/modules/users/models.py:RefreshToken`, not just the story's own Data Model Notes, which predate that implementation). This story adds **no migration for new columns**, only a supporting index (below) — matching the story's own stated intent ("this story adds columns, not a new store") more literally than even the story author expected, since the columns turned out to already be there.

**Query pattern this story introduces** (new — nothing before US-2.6 ever needed to group rows by `family_id` for a *listing*, only for a bulk revoke): a "session" as FR-1/FR-2 use the term is not one row — it's a rotation chain of rows sharing one `family_id`. Listing live sessions (FR-1) and evicting the oldest one (FR-7) both require:

1. **The family's `created_at`** = `MIN(issued_at)` across every row in that `family_id` (the *first* token ever issued in the chain, i.e., the original login/rotation start) — not the current row's own `issued_at`, which only reflects the most recent rotation.
2. **The family's current-state metadata** (`last_used_at`, `ip`, `user_agent`) = the row with `MAX(issued_at)` in that `family_id` — the most recently issued token, which is the one currently valid for that family (per US-2.3's single-use-then-rotate invariant, at most one row per family is un-consumed and un-revoked at a time).
3. **"Live"** = filtered to families having at least one row with `revoked_at IS NULL AND expires_at > now()`.

Both (1) and (2) are computed per `user_id`, scoped to that user's own families only (FR-1's own-account listing; FR-7's own-account cap). PostgreSQL's `DISTINCT ON (family_id) ... ORDER BY family_id, issued_at DESC` is the natural expression for (2); `GROUP BY family_id` with `MIN(issued_at)` for (1). Both need the same supporting index.

- **`ix_refresh_tokens_user_id_family_id_issued_at`** on `(user_id, family_id, issued_at)` — new composite index. The existing single-column `ix_refresh_tokens_user_id` and `ix_refresh_tokens_family_id` (added by US-2.1/US-2.2) each serve their own original query (bulk-revoke-by-family, look-up-by-user) but neither supports an efficient per-user `GROUP BY family_id` / `DISTINCT ON (family_id)` scan without a sort — this composite index lets PostgreSQL satisfy both (1) and (2) as an index-only scan ordered correctly, which matters for NFR's stated p95 ≤ 200 ms budget with up to 20 live families × their historical rotation rows per user.

**FR-7's row lock (spec-review resolution — concurrent cap eviction):** the count-and-evict check runs as `SELECT ... FOR UPDATE` scoped to the acting user's rows in `refresh_tokens` before the new family's row is inserted and before any eviction `UPDATE`, so two concurrent logins for the same user serialize on this lock rather than both observing a stale count. This is a query-time locking strategy, not a schema change — no new column or constraint models it.

**No new table for "family" as a first-class entity.** Considered and rejected: a dedicated `refresh_token_families` table (with its own `created_at`/`last_used_at`/`ip`/`user_agent`/`revoked_at`, `refresh_tokens.family_id` becoming a real FK into it) would remove the need for the aggregate queries above and make "family" a queryable row in its own right. Rejected because it requires a backfill migration for every existing family across US-2.1–US-2.5's already-shipped data, is a materially larger change than the story's own explicit scope note anticipates, and the aggregate-query approach meets the stated p95 budget with the new index. Flagged here, not decided silently: if a future story needs to query families independently of their token rows (e.g., an admin-facing session view), this rejection should be revisited.

### `auth_audit_log` (existing table) — add `target_family`

FR-2's `event=session_revoked` and FR-7's `event=session_evicted` both use the table's existing free-text `event: Mapped[str]` column (confirmed in `app/modules/users/models.py`) — the same plain-string convention every other story in this codebase already uses (no enum, no CHECK constraint on `event`'s values). But `target_family` itself has nowhere to go on the existing row shape: `reason` and `scope` are both `String(32)`, too short for a UUID's 36-character canonical form, and both already carry an established, different meaning elsewhere in this table (`reason` = "why did the attempt fail," per US-2.2's own design note; `scope` = `session`/`all_sessions` on logout rows) — overloading either would make those columns ambiguous for any row that isn't this story's, the same reasoning US-2.2's design already applied when it added `scope` instead of reusing `reason`. No other audit table in this codebase has a "target entity" reference column to follow as precedent either.

- **`target_family`** *(new)* — nullable `Mapped[uuid.UUID | None]`, no default, set only on `session_revoked` (FR-2) and `session_evicted` (FR-7) rows; `NULL` on every other existing event type (nullable column, no migration needed for existing rows).

### Indexes

- `ix_refresh_tokens_user_id_family_id_issued_at` on `refresh_tokens(user_id, family_id, issued_at)` — new, per above.
- No new index on `auth_audit_log`: `event=session_revoked`/`session_evicted` rows are written, not queried, by this story; the existing `actor_id`/`user_id` index this table already has (per US-2.1's original design) serves any future per-account audit-history read, same reasoning US-2.2's design applied.

## Relationships / loading strategy

No new relationships and no ORM `relationship()` involved. FR-1's listing query is a raw aggregate `SELECT`/`DISTINCT ON`, not an ORM collection load. FR-2/FR-4's revoke is the existing bulk `UPDATE ... WHERE family_id = :family_id` (US-2.2's established pattern). FR-7's eviction is the identical bulk `UPDATE`, targeted at the oldest family's rows instead of a caller-specified one.

## Sensitive columns

No new sensitive columns. `refresh_tokens.ip` and `.user_agent` (already present, unchanged) are read for the first time by this story (previously write-only) — FR-1 explicitly narrows what's exposed: no full IP address (only a geo-IP-derived city/country) and no raw token/hash ever leaves the response, per the spec's own NFR and this project's `NFR-012` (PII & Data Minimization).

## Explicitly deferred / not decided here

1. **The 90-day session-metadata purge job** — the spec's NFR states the retention window but the story marks its enforcement `[manual]` (scheduled execution verified in staging), not `[gate]`. No column, scheduled task, or migration for a purge mechanism is modeled here; this design only ensures the data being purged (`ip`, `user_agent`, timestamps) is already scoped correctly.
2. **The GeoLite2 database file and the `user-agents` library** (OD-4, OD-3) are application-level dependencies, not persistence — no table stores them; they're read-only, in-process lookups at request time. Out of this design's scope.
3. **A first-class `refresh_token_families` table** — considered and rejected above; not modeled here.
