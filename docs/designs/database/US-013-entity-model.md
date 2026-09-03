# Entity Model: View Audit Information (US-3.3 / spec US-013)

## Entities

### `AuditLog` (`audit_log`) — new, daily range-partitioned on `occurred_at`

| Column | Type | Nullable | Default | Constraints |
|---|---|---|---|---|
| `id` | `Mapped[uuid.UUID]` | No | `default=uuid.uuid4` | PK (composite with `occurred_at` per PostgreSQL's partition-key-in-PK requirement) |
| `occurred_at` | `Mapped[datetime]` → `DateTime(timezone=True)` | No | `server_default=func.now()` | PK (composite), partition key |
| `category` | `Mapped[str]` → `String(32)` | No | — | e.g. `auth`, `profile`, `account_lifecycle`, `admin`; `ticket` once Epic 4 ships |
| `actor_id` | `Mapped[uuid.UUID \| None]` | Yes | — | No FK — must survive account erasure (BR-007/AU-AC8), matches every existing audit table's precedent |
| `actor_role` | `Mapped[str \| None]` → `String(32)` | Yes | — | Resolved by the write path at event time; `NULL` for system-initiated events |
| `event` | `Mapped[str]` → `String(64)` | No | — | Free-text, matches existing tables' convention |
| `target_id` | `Mapped[uuid.UUID \| None]` | Yes | — | No FK, same reasoning |
| `outcome` | `Mapped[str \| None]` → `String(32)` | Yes | — | e.g. `success`/`denied`/`failure`; not meaningful for every event type |
| `request_id` | `Mapped[str \| None]` → `String(64)` | Yes | — | `NULL` for non-HTTP-triggered events (e.g. AU-AC9's own job-execution record) |
| `ip` | `Mapped[str \| None]` → `String(45)` | Yes | — | `NULL` for non-HTTP-triggered events |
| `user_agent` | `Mapped[str \| None]` → `Text()` | Yes | — | — |
| `payload` | `Mapped[dict \| None]` → `JSONB` | Yes | — | Event-specific structured detail; may contain PII depending on event type (see db-design's redaction finding) |
| `previous_hash` | `Mapped[str]` → `String(64)` | No | trigger-computed | SHA-256 hex; set exclusively by the `BEFORE INSERT` trigger, never application-supplied |
| `row_hash` | `Mapped[str]` → `String(64)` | No | trigger-computed | Same trigger, computed after `previous_hash` |

### `UnverifiedAccountPurgeLog` (`unverified_account_purge_log`, renamed from `email_verification.AuditLog`/`audit_log`)

No column change — pure rename (OD-1). Retains its existing shape: `id` (PK), `event` (`String(64)`), `subject_user_id` (nullable, no FK), `detail` (`Text`, not null), `occurred_at` (`DateTime(timezone=True)`, not null, `server_default=func.now()`).

### `auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log` — no column changes, one new index each

No column changes — this design considered and rejected altering their shapes (see db-design.md's central decision); each stands exactly as originally designed by US-2.1/US-2.6 (`auth_audit_log`), US-3.2 (`admin_audit_log`), US-1.3 (`profile_audit_log`), and US-1.4/US-3.1 (`account_lifecycle_audit_log`). Each gains one new `ix_<table>_occurred_at` index (see Indexes Summary) — required for `audit_log_history`'s query pattern regardless of how OD-14 resolves.

## Relationships

None — `audit_log` has no ORM relationships (no FKs by design, per the erasure-survival requirement every audit table in this project already follows). `audit_log_history` (below) is a raw SQL view, not an ORM-mapped entity with a `relationship()`.

## `audit_log_history` — new compatibility view (not an ORM entity)

```sql
CREATE VIEW audit_log_history AS
SELECT id, occurred_at, category, actor_id, actor_role, event, target_id,
       outcome, request_id, ip, user_agent, payload, previous_hash, row_hash
FROM audit_log
UNION ALL
SELECT id, occurred_at, 'auth' AS category, actor_id, NULL AS actor_role, event,
       NULL AS target_id, NULL AS outcome, request_id, ip, user_agent,
       NULL AS payload, NULL AS previous_hash, NULL AS row_hash
FROM auth_audit_log
UNION ALL
SELECT id, occurred_at, 'admin' AS category, actor_id, NULL, event, target_id,
       NULL, request_id, NULL, NULL, NULL, NULL, NULL
FROM admin_audit_log
UNION ALL
SELECT id, "timestamp" AS occurred_at, 'profile' AS category, actor_id, NULL, 'field_changed' AS event,
       NULL, NULL, request_id, NULL, NULL, NULL, NULL, NULL
FROM profile_audit_log
UNION ALL
SELECT id, occurred_at, 'account_lifecycle' AS category, NULL AS actor_id, NULL, event,
       user_id AS target_id, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM account_lifecycle_audit_log;
```

Illustrative — the exact SQL (and whether `event` needs a per-table literal like `profile_audit_log`'s, which has no `event` column of its own and instead a `field`/`old_value`/`new_value` triple) is `migration-manager`'s concern when the migration is actually written, not fixed here. `implementation-planner` should note this view is what `GET /v1/admin/audit-logs`'s repository queries, keyset-paginated on `(occurred_at DESC, actor_id, event)` per the covering index — a `UNION ALL` view cannot itself carry an index, so keyset pagination across it relies on each member query being individually well-indexed (`audit_log`'s new covering index, plus the four new `occurred_at` indexes below — none of the four tables' *pre-existing* indexes support this ordering).

## Indexes Summary

| Table | Index | Purpose |
|---|---|---|
| `audit_log` | Composite PK (`id`, `occurred_at`) | Required by PostgreSQL for the partition key to be part of every unique constraint |
| `audit_log` | Covering index on `(occurred_at DESC, actor_id, event)`, per-partition | FR-1's filtered, newest-first query (story's own Data Model Notes) |
| `unverified_account_purge_log` | Unchanged from its pre-rename indexes | — |
| The four existing, still-live tables | New `ix_<table>_occurred_at` on each — **except `profile_audit_log`, whose timestamp column is actually named `timestamp`, not `occurred_at`** (found during T2/T3c, IMPLEMENTATION stage — this design's own column list at the top of this document was wrong for that one table); its index is `ix_profile_audit_log_timestamp` on `timestamp` | Required for `audit_log_history`'s `occurred_at DESC` keyset pagination (FR-1) to produce a merge-append instead of sorting the full union — none of their existing indexes lead with `occurred_at`/`timestamp` (verified against the live models). Additive, no data-shape change; `CREATE INDEX CONCURRENTLY` since these tables are actively written. |

## Traceability

| Entity/Relationship | Functional Requirement(s) |
|---|---|
| `audit_log` | FR-1 (query fields), FR-2/FR-3 (write target), FR-4 (immutability — DB-grant half explicitly out of this story per the amended story), FR-7 (hash chain + daily partitioning) |
| `unverified_account_purge_log` | Not itself an AC target — renamed only to resolve OD-1's naming collision, which blocked `audit_log`'s own name |
| `audit_log_history` | FR-1 (the actual, primary query surface — most investigative queries resolve against the four still-live tables, not `audit_log`'s own two event types), FR-8 (identifier redaction via OD-13, which continues to apply to `profile_audit_log`'s ongoing live rows, not just historical ones) |

## Known Gaps (not decided at this stage)

- ~~Hash-chain genesis rule~~ — resolved as OD-17 (2026-09-02); see db-design.md's `audit_log` section.
- Exact `audit_log_history` view SQL, and per-source-table `event`/`category` literal mapping for tables lacking a real `event` column (`profile_audit_log`) — illustrative only above, left to `migration-manager`.
- A future OD-14 follow-up story repointing any of the four modules would need to design the `payload` JSONB redaction mechanism OD-13 doesn't cover — not this story's concern, noted for that future design to find.
