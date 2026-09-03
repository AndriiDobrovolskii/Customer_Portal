# feat: view audit information (US-3.3)

## Summary

Adds `GET /v1/admin/audit-logs` — a scoped (`audit:read`), cursor-paginated, filterable view over a new tamper-evident `audit_log` table unioned with this app's 4 existing per-domain audit tables (`audit_log_history` view). Every successful query self-audits (`event=audit_log_viewed`); every denied attempt is recorded too. `audit_log` rows are chained by a server-side SHA-256 hash trigger (`previous_hash`/`row_hash`, never application-settable), verifiable end-to-end via `scripts/verify_audit_chain.py`. A minimal, provisional erasure script (`scripts/anonymize_erased_user.py`) anonymizes a deleted user's `users` row and redacts `auth_audit_log.ip`.

- Story: `docs/stories/US-3.3-view-audit-information.md`
- Spec: `docs/specifications/US-013-view-audit-information-spec.md`
- Implementation plan: `docs/plans/US-013-implementation-plan.md`

## What changed

- **New module** `app/modules/audit/` — schemas, models, repository (raw `text()` query against the `audit_log_history` view — deliberately not ORM-mapped, since a view has no single underlying table), service, router, dependencies, exceptions.
- **New table** `audit_log`, daily-range-partitioned (`DEFAULT` partition only — no partition-provisioning job in this story's scope), with a `BEFORE INSERT` hash-chain trigger serialized via `pg_advisory_xact_lock` (a plain `SELECT...FOR UPDATE` does not serialize concurrent inserts under PostgreSQL MVCC — proven against real overlapping transactions).
- **New view** `audit_log_history` — `UNION ALL` over `audit_log` + `auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`.
- **Renamed table**: `email_verification`'s pre-existing `audit_log`/`AuditLog` → `unverified_account_purge_log`/`UnverifiedAccountPurgeLog` (freed the name for this story's own table).
- **4 new `CONCURRENTLY` indexes** on the existing per-domain tables' `occurred_at`(-equivalent) columns, needed for `audit_log_history`'s keyset pagination to use a merge-append instead of a full sort (confirmed via `EXPLAIN`: `Index Scan` feeding `Merge Append`, no `Seq Scan`).
- **2 new scripts**: `scripts/verify_audit_chain.py` (AU-AC7's chain-verification job), `scripts/anonymize_erased_user.py` (AU-AC8's provisional erasure script).
- **3 migrations**, `upgrade → downgrade → upgrade` proven against real Postgres 16.

## Known, disclosed gaps (not silently missing — see `docs/decisions/US-3.3-open-decisions.md`)

- **AU-AC9** (400-day retention → cold storage) is explicitly out of scope for this story (OD-18), blocked on a still-pending legal/DPO decision (OD-9). No code/task/test delivered against it.
- **AU-AC8's `profile_audit_log` redaction** (OD-13's original mechanism) is technically impossible: that table's pre-existing `BEFORE UPDATE OR DELETE` trigger unconditionally denies mutation, confirmed by actually running the redaction SQL. The user explicitly rejected disabling the trigger as an architectural anti-pattern (OD-20). Deferred to a separate architectural review; `anonymize_erased_user.py` proves it does *not* attempt the mutation, rather than proving a redaction that doesn't exist.
- **AU-AC4's DB-grant clause** (immutability enforced at the database-role level, not just the API's 405) is deferred to a project-wide follow-up (OD-12) — this app's DB connection is the Postgres superuser role, which cannot be restricted by grants at all.
- **Low, disclosed advisory** (SECURITY_REVIEW, carried forward through RECONCILIATION, still open): the `event`/`cursor` query params have no `max_length` and reach the immutable `audit_log.payload` JSONB unbounded. Not a security violation (bound parameters throughout) and not AC-text drift — a real unbounded-growth gap in a table this story deliberately makes un-deletable/un-redactable, left for a future pass.

## Gate results (all four confirmed Pass from their own reports)

| Gate | Verdict | Detail |
|---|---|---|
| gate-enforcer (T9) | **Pass** | 7/7 pre-commit hooks (ruff lint+format, mypy strict on 131 files, import-linter 6/6, unit tests, no-mock-in-integration guard, detect-secrets — all green; an environment-only WDAC/Smart App Control block hit mid-story on mypy/detect-secrets was resolved by rebuilding the affected dependencies from source, not by weakening any check). `lint-imports` 6/6 contracts kept. `pytest --cov=app`: 557/557 tests, coverage well above the 85% floor (`audit/service.py`/`audit/router.py` both 100%, floor 90%). |
| implementation-verifier | **Pass** | `docs/verification/US-013-verification-report.md`. No ORM leak, no missing eager-load (N/A — no relationships), no TTL-less cache write (N/A — no `cache.py` in this module), no service→router cross-module call, no missing `response_model`/`status_code`. Both non-CONCURRENTLY-index migrations' `downgrade()` perform real inverse DDL. All 5 AGENTS.md §5 security cases exist by name for the one protected route; AU-AC4's 405 additionally runtime-verified. |
| security-reviewer | **Pass** | `docs/security/US-013-security-review.md`. 3/6 AGENTS.md §7 rows N/A (no credential/new-auth surface in this story's scope, each verified not assumed); 3/6 Pass directly (zero log/print calls in the module; all SQL bound-parameterized everywhere, including migrations and both scripts). 1 Low advisory (see above), does not force Fail. |
| reconciliation-reviewer | **Pass** (initial pass Fail, closed same-day) | `docs/reconciliation/US-013-reconciliation-report.md`. Every AC has a matrix row and an existing, behavior-asserting test. Initial pass found 3 partial-assertion gaps (AU-AC1's full field-list, AU-AC2's full filter-parameter payload, AU-AC5's message-content clause) — the shipped code was already correct in all 3 cases, only the assertions were short. `test-writer` closed all 3 same-day; re-verified with a full 557/557 suite run and mypy re-confirmed clean. No spec drift found in either pass. |

## Test plan

- **Unit** (`tests/unit/modules/audit/`, `tests/unit/scripts/`, `tests/unit/test_audit_write_call_site_scan.py`): service branch coverage against hand-written fakes (filter/window validation, self-audit/denial payload construction, actor-role resolution), chain-verifier break-detection logic, schema-level hash-field-immutability proof, AU-AC6's AST-based CI-grep over audit-write call sites.
- **Integration** (`tests/integration/modules/audit/test_audit_router.py`, real PostgreSQL + Valkey via testcontainers): filtered query/pagination/empty-result/limit/cursor validation, full 9-field response shape, self-audit + denial writes with full persisted-state assertions, all 5 AGENTS.md §5 security cases, AU-AC4's 405 on PATCH/PUT/DELETE, AU-AC5's 422 with message content, hash-chain genesis/gap/tamper/concurrency behavior (including a genuine concurrency proof against real overlapping transactions), `audit_log_history`'s query-plan shape via `EXPLAIN`.
- **Integration** (`tests/integration/scripts/test_anonymize_erased_user.py`): erasure script's 3 AU-AC8 clauses (anonymize + redact, entries remain queryable with `actor_id` retained, `profile_audit_log` proven untouched per OD-20).
- **Regression**: `tests/integration/modules/email_verification/test_purge_service.py` updated for the table rename, still green.
- Full traceability: `docs/tests/US-013-traceability-matrix.md`.

## `.env.example` / config

No new settings introduced by this story — confirmed via `git diff --stat main...HEAD -- app/core/config.py .env.example` (empty).

## Commit hygiene

Every changed/new file in this branch's 49-file diff traces to this story's scope (new `audit` module, the `email_verification` rename it depends on, migrations, scripts, tests, and the pipeline's own tracking docs). No drive-by refactor of untouched code.

---

**This is a draft only.** Pushing the branch or opening the PR on GitHub requires an explicit instruction from you (`git push` / `gh pr create`) — nothing has been pushed yet.
