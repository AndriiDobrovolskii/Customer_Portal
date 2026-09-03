# Entity Model: US-2.6 Active Session Management

Traceability: every column below cites the FR it exists for.

## `refresh_tokens` (existing — `app/modules/users/models.py`) — no new columns

Every column FR-1 through FR-7 read or write already exists (added by US-2.1/US-2.2/US-2.3):

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `id` *(existing)* | UUID | No | app-side `uuid4()` | — |
| `family_id` *(existing)* | UUID | No | app-side `uuid4()` | FR-1 (grouping key), FR-2/FR-4/FR-7 (bulk revoke target) |
| `user_id` *(existing)* | UUID (FK `users.id`, `ondelete=CASCADE`) | No | — | FR-1 (own-account scoping), FR-3 (ownership check), FR-7 (cap scoping) |
| `issued_at` *(existing)* | `DateTime(timezone=True)` | No | `func.now()` | FR-1 (`created_at` = `MIN(issued_at)` per family), FR-7 (oldest-family ordering) |
| `expires_at` *(existing)* | `DateTime(timezone=True)` | No | — | FR-1/FR-4 ("live" = not yet expired) |
| `revoked_at` *(existing)* | `DateTime(timezone=True)` | Yes | none | FR-2/FR-7 (set on revoke/evict), FR-4 (already-set → idempotent) |
| `consumed_at` *(existing)* | `DateTime(timezone=True)` | Yes | none | FR-1 (distinguishes the family's current live row from prior rotations) |
| `last_used_at` *(existing)* | `DateTime(timezone=True)` | Yes | none | FR-1 (per-family metadata, from the `MAX(issued_at)` row) |
| `ip` *(existing)* | `String(45)` | Yes | none | FR-1 (geo-IP input, never returned raw) |
| `user_agent` *(existing)* | `Text` | Yes | none | FR-1 (device/browser label input) |

**No columns added.** This story's only schema change is a new index (below) and one column on a different table (`auth_audit_log.target_family`).

**Query pattern (not a column, documented here for traceability):**
```sql
-- (1) current-state row per live family, for a user:
SELECT DISTINCT ON (family_id) *
FROM refresh_tokens
WHERE user_id = :user_id AND revoked_at IS NULL AND expires_at > now()
ORDER BY family_id, issued_at DESC;

-- (2) each family's created_at, for the same user:
SELECT family_id, MIN(issued_at) AS created_at
FROM refresh_tokens
WHERE user_id = :user_id AND revoked_at IS NULL AND expires_at > now()
GROUP BY family_id;
```
FR-7's oldest-family lookup is (2) ordered by `created_at ASC LIMIT 1`, executed under `SELECT ... FOR UPDATE` scoped to the user's rows (spec-review resolution).

## `auth_audit_log` (modify existing — `app/modules/users/models.py`)

| Column | Type | Nullable | Default | FR |
|---|---|---|---|---|
| `target_family` *(new)* | UUID | Yes | none | FR-2 (`event=session_revoked`), FR-7 (`event=session_evicted`) |
| `event` *(existing, new values used)* | `String(32)` | No | none (existing) | FR-2 (`"session_revoked"`), FR-7 (`"session_evicted"`) |

No other `auth_audit_log` columns change. `target_family` is `NULL` on every event type this table already records.

## Indexes

- **`ix_refresh_tokens_user_id_family_id_issued_at`** *(new)* on `refresh_tokens(user_id, family_id, issued_at)` — supports both aggregate query shapes above as an ordered/index-only scan. See `US-2.6-db-design.md` for the p95-budget rationale.
- No new index on `auth_audit_log.target_family`: this story only writes it, per `US-2.6-db-design.md`'s Indexes section.

**Relationships:** none new. No `relationship()` is added to either model; both query patterns above are raw aggregate `SELECT`s (or existing bulk `UPDATE`s for revoke/evict), not ORM collection loads — no eager-loading strategy applies.

## Not modeled here (explicitly out of scope for this design)

- The GeoLite2 database file and `user-agents` library (OD-4, OD-3) — application-level, read-only lookups, not persisted state.
- A first-class `refresh_token_families` table — considered and rejected, see `US-2.6-db-design.md`.
- Any purge job/scheduled task for the 90-day metadata retention NFR — marked `[manual]` enforcement by the story, not modeled as a migration or column here.
