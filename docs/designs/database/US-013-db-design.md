# DB Design: View Audit Information (US-3.3 / spec US-013)

**Spec:** `docs/specifications/US-013-view-audit-information-spec.md` (Pass with Issues, third run, 2026-09-02)
**API:** `docs/designs/api/US-013-openapi.yaml`, `US-013-api-design.md`

## The central design decision, and why it revises what SPECIFICATION assumed

The spec's Data Model Notes (carried from the story's Assumption #1) describe `audit_log` as a union **view** over the four existing per-domain tables, and left "whether `audit_log` is itself a writable table or a read-only view" as an explicit Open Question (FR-2/FR-3's write target). Working through AU-AC7's mechanics forces a resolution PostgreSQL itself makes non-negotiable:

- **A view cannot be partitioned.** Partitioning is physical table storage; `PARTITION BY RANGE` only applies to a table.
- **AU-AC7 requires one coherent chain "over any day's partition"** — singular partition, singular chain per day. A `BEFORE INSERT` trigger fires per physical table on an actual `INSERT`; it cannot transparently interleave rows being inserted into four *separate* tables into one ordered chain without cross-table coordination this project has no precedent for.

The only design consistent with both AU-AC7's literal wording and PostgreSQL's actual capabilities is the one Assumption #1 already states in full, read as a whole rather than as two competing options: **`audit_log` is a new, single, physical, daily-partitioned table; the four existing per-domain tables are exposed through a union-compatibility view for query continuity.** This much is a technical conclusion, not a judgment call, and this design commits to it. It resolves the spec's FR-2/FR-3 write-target Open Question for whatever writes do land in `audit_log` (see immediately below).

**Whether the four existing modules' write call sites get repointed to `audit_log` was a separate, genuinely undecided scope question — logged as OD-14 and resolved by the user 2026-09-02: staged.** `audit_log` + the hash chain + this story's own two new events (`audit_log_viewed`, the `audit:read`-denial event) ship in this story; repointing each existing module's audit-write call site (auth, profile, roles/admin, account) is a separate, future follow-up story, one module at a time (matches this project's own expand → migrate → contract convention, `AGENTS.md` §4).

**Under staged OD-14, the four existing tables are not frozen — they stay live, actively written by their existing, unchanged call sites**, exactly as they are today. Only *new* audit-relevant events this story itself introduces (`audit_log_viewed`, the denial event) land in `audit_log`. This is why the earlier concern about adding `previous_hash`/`row_hash`/`category`/`outcome`/`payload` columns to all four is still moot — not because they stop changing, but because this design never routes new writes through them at all, so their shape is untouched regardless of write volume. AU-AC7's tamper-evidence guarantee covers only the events `audit_log` itself receives — the four existing tables' ongoing, live events remain outside the hash chain until their own follow-up ships. This is a disclosed scope boundary, not an oversight.

## New table: `audit_log`

The write target for this story's own two new event types (`audit_log_viewed`, the `audit:read`-denial event) only, per staged OD-14. Daily range-partitioned on `occurred_at` (OD-11).

- `id`, `occurred_at`, `category`, `event`, `previous_hash`, `row_hash` — never nullable, server/trigger-computed where noted.
- `actor_id`, `actor_role`, `target_id`, `outcome`, `request_id`, `ip`, `user_agent`, `payload` — nullable, because not every event type populates every field (e.g. AU-AC9's own retention-job-execution record has no HTTP `request_id`/`ip`, and a system-initiated event has no `actor_role`).
- No FK on `actor_id`/`target_id` — matches every existing audit table's own established precedent (must survive account erasure, BR-007/AU-AC8).
- `previous_hash`/`row_hash` are set exclusively by a `BEFORE INSERT` trigger over `(previous row's hash, occurred_at, actor_id, event, target_id, payload)`, scoped to the current day's partition, seeded from the prior day's partition's final `row_hash`. **Genesis rule (OD-17, resolved 2026-09-02):** the very first row ever inserted into `audit_log` seeds `previous_hash` from a fixed sentinel (hash of the empty string). Every subsequent day's first row seeds `previous_hash` from the most recent **non-empty** prior partition's final `row_hash`, skipping any wholly empty day — the trigger must look back across partitions (not just the immediately-prior one) to find that value, e.g. `SELECT row_hash FROM audit_log WHERE occurred_at < <this partition's start> ORDER BY occurred_at DESC, id DESC LIMIT 1`. A day that appears empty at verification time (genuinely quiet, or tampered-empty) is treated identically by this seeding rule; tampering still surfaces as a hash mismatch at the next real row, which is what AU-AC7's break-detection needs — no per-day placeholder row is required.
- The application-facing schema layer (`schema-builder`'s eventual `AuditLogCreate`, if one exists) MUST NOT accept `previous_hash`/`row_hash` as input fields — mirrors this project's `extra="forbid"`/mass-assignment discipline (AGENTS.md §4) applied to server-computed columns.
- Partition maintenance (creating each new day's partition ahead of time) is an operational job, not a schema decision — follows this project's `scripts/`-directory precedent (`scripts/purge_unverified_accounts.py`), not designed further here. **OD-16 (resolved 2026-09-02):** the migration also creates a `DEFAULT` partition as a safety net, so a day passing with no provisioned partition degrades to ungrouped rows rather than a hard `INSERT` failure.

## Renamed table: `unverified_account_purge_log` (was `email_verification.AuditLog`/`audit_log`)

Pure rename via migration (OD-1) — frees the `audit_log` name, no column or behavior change. `EmailVerificationRepository.create_audit_log`/`find_purge_candidates` continue to work unchanged against the renamed table (repository/service code updates the table reference, not this design's concern).

## Existing tables: `auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log` — stay live, no schema change

Under staged OD-14, these four keep being written by their existing, unchanged call sites indefinitely (or until a future follow-up story repoints one) — they are not frozen, not deprecated, and continue to be the primary record of logins, role changes, profile edits, and deactivations. No column change to any of them (this **reverses** the SPECIFICATION-stage assumption that all four needed new columns — that assumption depended on the now-superseded view-only interpretation); each gains only a new `occurred_at` index (see Indexes, below).

## New compatibility view: `audit_log_history`

`UNION ALL` of `audit_log` (this story's two new event types) with the four existing tables' rows — which, under staged OD-14, are not a static historical archive but an ongoing, live stream — each column-mapped and NULL-padded where a source table lacks that column. This is what `GET /v1/admin/audit-logs` (FR-1) actually queries, and it is the **primary** query surface for investigative purposes (most of what an auditor searches for — logins, role changes, deactivations — still lives in the four existing tables under this story's scope), not a compatibility shim for old data.

| Column | `audit_log` | `auth_audit_log` | `admin_audit_log` | `profile_audit_log` | `account_lifecycle_audit_log` |
|---|---|---|---|---|---|
| `category` | stored | literal `'auth'` | literal `'admin'` | literal `'profile'` | literal `'account_lifecycle'` |
| `actor_id` | stored | `actor_id` | `actor_id` | `actor_id` | `NULL` — `.actor` is free text, not a UUID; not parsed (would be invented logic) |
| `actor_role` | stored | `NULL` — not stored | `NULL` | `NULL` | `NULL` |
| `target_id` | stored | `NULL` — not stored | `target_id` | `NULL` | `user_id` — semantically the account the lifecycle event happened *to*, i.e. the target, not an actor |
| `outcome` | stored | `NULL` — not stored | `NULL` | `NULL` | `NULL` |
| `request_id` | stored | `request_id` | `request_id` | `request_id` | `NULL` — column doesn't exist |
| `ip` | stored | `ip` | `NULL` — not stored | `NULL` | `NULL` |
| `user_agent` | stored | `user_agent` | `NULL` | `NULL` | `NULL` |
| `payload` | stored | `NULL` | `NULL` (`old_roles`/`new_roles` not folded in — different shape) | `NULL` (`field`/`old_value`/`new_value` not folded in — see below) | `NULL` (`reason` not folded in) |
| `previous_hash`, `row_hash` | stored | `NULL` — predates tamper-evidence | `NULL` | `NULL` | `NULL` |

**This resolves the spec's "historical-row field availability" Ambiguity honestly, not by synthesis:** a field genuinely not captured on a row from one of the four existing tables is `NULL`, not fabricated — true for both their pre-existing rows and every new row they keep writing under staged OD-14, since their shape doesn't change. AU-AC1's per-entry field list (`FR-1`) is fully populated only for `audit_log`'s own two event types, and partially `NULL` for every event still recorded via the four existing tables — which is disclosed here rather than left as the spec's prior "not decided" framing.

**AU-AC7's hash chain covers only rows in `audit_log`** — the four existing tables' events, past and ongoing, were never designed for tamper-evidence and are not chained (no `previous_hash`/`row_hash` to compute one from without a separate, out-of-scope backfill-hashing effort, and no trigger fires on them under this story). This is a real, disclosed scope boundary, not an oversight: "every audit entry" in AU-AC7 is read as every entry *within `audit_log`*, the only table AU-AC7's trigger and verification job can mechanically apply to under staged OD-14.

## OD-13's redaction resolution is unaffected by staged OD-14 — the payload-JSONB concern is now deferred, not urgent

OD-13 (field-aware redaction on `profile_audit_log.old_value`/`new_value`) resolved AU-AC8 for exactly the rows that continue to be written there under staged OD-14 — `profile_audit_log` stays live, unchanged, indefinitely. The earlier concern (raised while this design still assumed a full write-path cutover) — that a profile field-change event would instead land in `audit_log.payload` JSONB with no redaction mechanism reaching into it — does not apply to this story's actual scope. It becomes relevant only if and when a future OD-14 follow-up repoints the `profile` module specifically; noted here so that follow-up's own design doesn't have to rediscover it.

## Indexes

- `audit_log`: covering index on `(occurred_at DESC, actor_id, event)` per the story's own Data Model Notes, local to each daily partition (standard PostgreSQL partitioned-index behavior — one physical index per partition, one logical index definition).
- **Each of the four existing tables needs a new index leading with `occurred_at`, regardless of how OD-14 resolves.** None of their existing indexes support it: `auth_audit_log` indexes `actor_id` only, `admin_audit_log` indexes `actor_id`/`target_id`, `account_lifecycle_audit_log` indexes `user_id`, and `profile_audit_log` has no index at all beyond its PK (confirmed against the live models, not assumed). `audit_log_history` is a five-branch `UNION ALL` keyset-paginated on `occurred_at DESC` (FR-1) — without a matching sort order on every branch, PostgreSQL can't produce a merge-append and instead sorts the full union, which risks the p95 ≤ 500 ms NFR at realistic row counts. Add `ix_<table>_occurred_at` on each of the four (a small, additive index migration — notably *not* the hash/category column changes this design otherwise rules out for these tables, since an index carries no data-shape implication). All four are live, actively-written tables under staged OD-14, so each index migration should use `CREATE INDEX CONCURRENTLY` (`AGENTS.md` §4's own hazard for exactly this case) — flagged for `implementation-planner`, not decided as one migration or four here.
- **The five `audit_log_history` branches are not static once combined.** Under staged OD-14, four of its five sources keep receiving writes in real time from their existing call sites while a query is paginating through them — `planner`'s validation strategy for the p95 ≤ 500 ms NFR should account for keyset pagination over a union of moving targets, not a frozen dataset.

## Relationships / loading strategy

No ORM `relationship()` — `audit_log_history` is a raw SQL view/union queried directly by the repository (`select().select_from(text("audit_log_history"))` or an unmapped `Table` reflection), not an ORM entity graph. This mirrors the US-2.6 precedent (FR-1's session listing is also a raw aggregate query, not a relationship load) — no eager-loading strategy applies because there is no relationship to eager-load.

## Sensitive columns

- `audit_log.payload` (JSONB) can contain PII depending on event type (profile field changes, per the finding above) — no encryption requirement stated by the spec (none invented here), but redaction-before-write is the responsibility of each write call site per FR-6, not this design.
- `ip`/`user_agent` on both `audit_log` and the four existing tables are read for the first time by this story (previously write-only, same pattern as US-2.6's `refresh_tokens.ip`/`.user_agent`) — FR-1 exposes them directly in the response; no minimization beyond what the spec states (full IP, unlike US-2.6's session-listing precedent, which deliberately narrowed to geo-IP-derived location — this story's spec states no such narrowing, so none is invented here).

## Explicitly deferred / not decided here

1. ~~**Hash-chain genesis rule**~~ — **resolved as OD-17** (2026-09-02, TESTS stage); see the `audit_log` section above.
2. **Post-cutover `payload` JSONB redaction mechanism** — new finding above; deferred until OD-14's follow-up story (if any) actually repoints a module whose events carry free-text identifier fields — not relevant to this story's own two new event types, which carry no PII.
3. **AU-AC9's cold-storage target and DA-AC9's anonymize-vs-hard-delete policy** — both explicitly deferred to legal/DPO sign-off in the story/spec; no mechanism modeled here beyond "moved out of the live partitioned table," which needs no schema decision this design can make. **OD-18 (resolved 2026-09-02):** AU-AC9's retention job itself is out of this story's build scope entirely — no code/task/test ships for it.
4. **OD-14's follow-up stories** (which module first, sequencing) — not scoped here; OD-14 itself is resolved (staged), but the follow-ups' own scope is future work, not this design's.
