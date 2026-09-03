# Implementation Plan: View Audit Information (US-3.3 / spec US-3.3)

**Spec:** docs/specifications/US-3.3-spec.md
**API design:** docs/designs/api/US-3.3-openapi.yaml, US-3.3-api-design.md
**DB design:** docs/designs/database/US-3.3-db-design.md, US-3.3-entity-model.md
**Impact analysis:** docs/impact-analysis/US-3.3-impact-analysis.md
**Open Decisions:** docs/decisions/US-3.3-open-decisions.md (14 items; OD-1/OD-2/OD-11/OD-12/OD-13/OD-14 resolved; OD-3–OD-10 carried forward, non-blocking — see Risks)

## Goal

Give administrators and auditors a filtered, cursor-paginated, tamper-evident query surface over security- and admin-relevant events (`GET /v1/admin/audit-logs`), backed by a new, daily-partitioned, hash-chained `audit_log` table that this story's own two new event types write into, unioned with the four already-shipped per-domain audit tables (which keep being written by their existing, unchanged call sites — OD-14 staged) for investigative continuity.

## Architectural Changes

1. **New module `app/modules/audit/`** — the first module owning `audit_log`, following the standard `router → dependencies → service → repository → models/schemas` layering (`AGENTS.md` §3).
2. **New physical table `audit_log`**, daily range-partitioned on `occurred_at`, with a `BEFORE INSERT` hash-chain trigger (AU-AC7/OD-11), plus a standalone chain-verification job (`scripts/verify_audit_chain.py`, AU-AC7's `[gate]`-marked "runs over any day's partition... reports the exact row" requirement). Partition creation ahead of need is an operational concern (see Risks), not new application code this story ships.
3. **New compatibility view `audit_log_history`** — `UNION ALL` of `audit_log` with the four existing per-domain tables, each column-mapped and NULL-padded per `US-3.3-entity-model.md`'s mapping table. This is `AuditLogRepository.list_filtered()`'s actual query target, not `audit_log` alone.
4. **Rename `email_verification.AuditLog`/`audit_log` → `unverified_account_purge_log`** (OD-1), freeing the name. Must run before `audit_log` is created in the same migration sequence.
5. **New `occurred_at` index on each of the four existing audit tables** (`auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`), `CREATE INDEX CONCURRENTLY` since all four are live (`AGENTS.md` §4 hazard).
6. **FR-3's denial-write, resolved (impact-analysis's flagged tension):** a new `require_audit_read` dependency in `app/modules/audit/dependencies.py` wraps `roles.dependencies.require_scope("audit:read")`, catching `InsufficientPermissionError`, writing the `audit_log` denial entry via `AuditLogService`, then re-raising. This is deliberately **endpoint-local**, not a change to the shared `require_scope` — widening `require_scope` itself would silently start auditing every other route that uses it (`users:read`, `users:write`, `roles:write`, `tickets:*`), which is out of this story's scope per the impact analysis.
7. **`migrations/env.py` model-registration import** — the new `app/modules/audit/models.py` needs the identical one-line model-registration import every prior new module has required (`AGENTS.md` §7.9-protected file). Flagged here per that section's own rule, not silently included — matches the precedent already used for `admin_users` (US-3.1) and `roles` (US-3.2), both explicitly user-approved at the time.

## Files To Create

| File | Purpose |
|---|---|
| `app/modules/audit/__init__.py` | New module. |
| `app/modules/audit/models.py` | `AuditLog` per `US-3.3-entity-model.md` (daily-partitioned, `previous_hash`/`row_hash` trigger-computed, never application-settable). |
| `app/modules/audit/schemas.py` | `AuditLogEntry`, `AuditLogListResponse` (outbound only, `from_attributes=True`, explicit field list per `AGENTS.md` §4) — no inbound schema; `audit_log` writes are internal, never router-exposed. |
| `app/modules/audit/repository.py` | `AuditLogRepository.list_filtered()` (queries `audit_log_history`, keyset-paginated on `(occurred_at DESC, actor_id, event)`, FR-1/FR-5's window enforcement applied as a `WHERE` clause) and `.create_entry()` (writes `audit_log`, FR-2/FR-3). |
| `app/modules/audit/service.py` | `AuditLogService.list_audit_logs()` (FR-1: validates the 90-day window per FR-5, applies `limit`/`cursor` bounds per the OD-5 `admin_users` precedent, then writes the FR-2 self-audit entry after a successful read) and `.record_access_denied()` (FR-3, called by `require_audit_read`). |
| `app/modules/audit/router.py` | `GET /v1/admin/audit-logs` per `US-3.3-openapi.yaml`, `response_model`/`status_code` declared (`AGENTS.md` §6.7). No `PATCH`/`PUT`/`DELETE` handler registered — Starlette's default `405` applies (verified against `app/main.py`'s actual exception handlers in impact-analysis; none intercept it). |
| `app/modules/audit/dependencies.py` | `AuditLogServiceDep`; `require_audit_read` (the FR-3-resolving wrapper described above). |
| `app/modules/audit/exceptions.py` | `RangeTooWideError` (FR-5, → `422`). `InsufficientPermissionError` is reused as-is from `app.modules.roles.exceptions`, not redefined here. |
| `migrations/versions/<rev>_rename_email_verification_audit_log.py` | OD-1's rename, must precede the next migration. |
| `migrations/versions/<rev>_add_audit_log_and_history_view.py` | `audit_log` table + partitions + hash-chain trigger + `audit_log_history` view, per `US-3.3-db-design.md`. |
| `migrations/versions/<rev>_add_occurred_at_indexes.py` (or four, `implementation-planner`'s call) | The four new `CONCURRENTLY` indexes. |
| `scripts/verify_audit_chain.py` | AU-AC7's chain-verification job — reports "intact" for an untouched day's partition, or the exact row at which the chain breaks. Follows this project's one existing job precedent (`scripts/purge_unverified_accounts.py`): a standalone script, externally triggered, not an in-app scheduler. `[gate]`-marked by the story's own Enforcement Matrix. Built by `service-and-router-builder` (OD-15, resolved by user 2026-09-02 — no execution skill's stated contract literally covers `scripts/`; closest fit chosen). |
| `scripts/anonymize_erased_user.py` | **Added 2026-09-02 (OD-19)** — OD-2's committed provisional erasure script (a minimal version of the still-unbuilt US-1.4 DA-AC9 job), never carried into this plan when first resolved at CLARIFICATION. Anonymizes the target `users` row and redacts `auth_audit_log.ip` for that user's rows. **Does NOT redact `profile_audit_log` (OD-20, superseding OD-13)** — that table's `BEFORE UPDATE OR DELETE` trigger from an earlier story unconditionally denies mutation, discovered by actually running the redaction SQL; disabling it was explicitly rejected by the user, deferred to a separate architectural review. Deliberately never touches `audit_log` itself — mutating any of that table's hashed fields would break AU-AC7's chain, and this story's own two event types carry no PII to redact there anyway. `[gate]`-marked (AU-AC8). Owner: `service-and-router-builder`, same OD-15 precedent as `verify_audit_chain.py`. |
| `tests/unit/scripts/test_verify_audit_chain.py` | Unit test for the verifier's break-detection logic, hand-written fakes for the DB read. |
| `tests/unit/modules/audit/test_audit_service.py` | Unit tests, hand-written fakes, no `MagicMock`. |
| `tests/integration/modules/audit/test_audit_router.py` | Integration tests against real PostgreSQL + Valkey, no `unittest.mock`. |
| `tests/integration/scripts/test_anonymize_erased_user.py` | **Added 2026-09-02 (OD-19)** — integration test for the erasure script, against real Postgres. |

## Files To Modify

| File | Change |
|---|---|
| `app/modules/email_verification/models.py` | `AuditLog` model's `__tablename__` updated to `unverified_account_purge_log` (OD-1). Class rename optional, left to `implementation-planner`. |
| `app/modules/email_verification/repository.py` | No logic change — only affected if the model class itself is renamed. |
| `app/modules/users/models.py`, `app/modules/roles/models.py`, `app/modules/profile/models.py`, `app/modules/account/models.py` | Each's respective audit table (`AuthAuditLog`, `AdminAuditLog`, `ProfileAuditLog`, `AccountLifecycleAuditLog`) gets no column change — only a new index declaration, matching the migration in Files To Create. |
| `app/api/v1/router.py` | Register the new `audit` router. |
| `migrations/env.py` | **§7.9-protected — flag for explicit user sign-off, not silent inclusion.** One model-registration import line for `app.modules.audit.models`, matching every prior new module's identical, already-approved pattern. |
| `tests/unit/modules/email_verification/*`, `tests/integration/modules/email_verification/test_purge_service.py` | Update table/model references for the OD-1 rename; behavior unchanged (confirmed by impact-analysis — exhaustive grep for `AuditLog`/`audit_log` references within this module's tests is `implementation-planner`'s task, not assumed complete here). |

No other file under `AGENTS.md` §7.9 protection (`pyproject.toml` contracts, `.pre-commit-config.yaml`) is touched by this plan.

## Risks

- **Migration ordering.** The OD-1 rename must land before `audit_log` is created in the same deploy — reversed order leaves the name collision unresolved mid-migration. Sequence, not just presence, matters here.
- **Partition maintenance (OD-16, resolved 2026-09-02):** `PARTITION BY RANGE` with no `DEFAULT` partition would mean the *first* `INSERT` past the migration-created partition's end date fails outright — including this story's own FR-2 self-audit write. Resolved: the migration also creates a `DEFAULT` partition as a safety net (rows land there, ungrouped, until a real partition exists — degraded but not a `500`). No ongoing partition-creation job ships with this story; that automation remains future work, now safely deferrable since the `DEFAULT` partition prevents the hard-failure case.
- **Hash-chain genesis rule (OD-17, resolved 2026-09-02):** first-ever row seeds `previous_hash` from a fixed sentinel; each subsequent day's first row seeds from the most recent non-empty prior partition's final `row_hash`, skipping empty days (trigger looks back across partitions, not just the immediately-prior one — see db-design.md's `audit_log` section for the exact query shape). No longer blocks `migration-manager`'s trigger authoring (T3b).
- **`audit_log_history`'s keyset pagination reads a union of moving targets** (impact-analysis finding) — four of five branches are live, actively-written tables. The p95 ≤ 500 ms NFR (NFR-011) needs to be validated against realistic concurrent-write conditions, not just a static fixture dataset.
- **FR-6's "fields marked sensitive" enumeration is still undefined** (carried-forward spec ambiguity) — `AuditLogEntry`'s field-level redaction logic cannot be fully implemented/tested without it; this story's own two event types (`audit_log_viewed`, denial) carry no known sensitive fields today, so the gap is real but not blocking for THIS story's own writes.
- **Non-blocking carried-forward Open Decisions** (OD-3, OD-4, OD-6–OD-10, `docs/decisions/US-3.3-open-decisions.md`): existing tables' inconsistent shapes (OD-3, addressed by this plan's NULL-padded view mapping, not a blocker), `ticket_audit_log` not yet existing (OD-4, view scoped to 4 sources per db-design), single-missing-bound behavior for `from`/`to` (OD-10), hash-chain concurrent-insert correctness (OD-6), `payload` JSONB redaction scope for a future OD-14 follow-up (not this story's), and AU-AC9's cold-storage target (OD-9/legal-DPO, unresolved — **OD-18, resolved 2026-09-02: AU-AC9's retention job is explicitly out of this story's build scope**, no file/task/test ships against it). None blocks this story's own implementation; `implementation-planner`/`plan-reviewer` should confirm each is either explicitly deferred in code comments or genuinely out of scope, consistent with this project's established pattern for non-blocking findings.

## Validation Strategy

- `pre-commit run --all-files` green (7/7 hooks), mypy strict clean on every new/changed file, `lint-imports` clean — the new `audit` module's own layering is checked automatically.
- Both new migrations (rename, then `audit_log`+view+trigger) and the index migration(s): `upgrade → downgrade → upgrade` proven against real PostgreSQL, per `AGENTS.md` §4/§6, including the hash-chain trigger's behavior and the view's `SELECT` returning correctly across all five sources both directions of the cycle.
- Coverage floor 85% overall, 90%+ on `audit/service.py` and `audit/router.py`, per `AGENTS.md` §6/NFR-009.
- A dedicated test proves AU-AC4's `[gate]` requirement: `PATCH`/`PUT`/`DELETE /v1/admin/audit-logs` all return `405` with no custom handler intervening.

## Testing Strategy

- **Unit (hand-written fakes, no `MagicMock`):** `AuditLogService.list_audit_logs()` — window validation (FR-5, both-omitted and over-90-days cases), `limit`/`cursor` bound enforcement (OD-5 precedent), self-audit write after a successful read (FR-2). `AuditLogService.record_access_denied()` (FR-3).
- **Integration (real PostgreSQL + Valkey, no `unittest.mock`):** AU-AC1 (filtered query, full field list against `audit_log`'s own rows only — historical rows from the four other tables are NULL-padded, not fabricated, per db-design), AU-AC2 (self-audit write, event/actor/filters asserted in the DB), AU-AC3 (403 + the resulting denial entry — both the security-case set per `AGENTS.md` §5 and the new `require_audit_read` wrapper's write path), AU-AC5 (window bound `422`s), AU-AC7 (mutate a row through the ordinary application session — per OD-12, there is no separate privileged connection to distinguish, since the app itself connects as the Postgres superuser — then run `scripts/verify_audit_chain.py` and assert it names that exact row as the break point; the story's Enforcement Matrix wording ("as the application role") predates OD-12 and should be read as this, not as requiring a second DB role, per the Enforcement Matrix's `[gate]` marker), AU-AC4 (405 on all three disallowed methods).
- **Regression:** the four existing per-domain audit tables' own existing test suites (`users`, `roles`, `profile`, `account`/`admin_users`) must stay green — this story adds an index to each but changes no column or write path they depend on.
