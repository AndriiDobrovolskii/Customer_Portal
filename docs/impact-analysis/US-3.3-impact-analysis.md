# Impact Analysis: View Audit Information (US-3.3 / spec US-3.3)

**Spec:** docs/specifications/US-3.3-spec.md
**API design:** docs/designs/api/US-3.3-openapi.yaml, US-3.3-api-design.md
**DB design:** docs/designs/database/US-3.3-db-design.md, US-3.3-entity-model.md
**Scope basis:** OD-14 resolved staged (`docs/decisions/US-3.3-open-decisions.md`) — this story ships `audit_log` + the hash chain + its own two new event types only; no existing module's write call site is repointed.

## 1. Affected Files, by Layer

No existing module owns audit querying — a new module, `app/modules/audit/`, is created (mirrors the `roles` module's precedent of being the first-of-its-kind for its concern).

### New — `app/modules/audit/`

| File | Layer | Reason |
|---|---|---|
| `__init__.py` | — | New module. |
| `models.py` | models | `AuditLog` (`audit_log` table, daily-partitioned) per `US-3.3-entity-model.md`. `UnverifiedAccountPurgeLog` (rename target, OD-1) stays in `app/modules/email_verification/models.py` — a rename, not a move; see §3. |
| `schemas.py` | schemas | `AuditLogEntry`, `AuditLogListResponse` (outbound, per `US-3.3-openapi.yaml`). No inbound `*Create`/`*Update` schema — writes are internal (service-to-repository), never a router-exposed request body, matching FR-4's immutability requirement structurally (there is no schema an API caller could use to write one even if a route existed). |
| `repository.py` | repository | `AuditLogRepository`: `list_filtered()` querying the `audit_log_history` view (keyset-paginated per FR-1/Data Model Notes), `create_entry()` writing into `audit_log` for FR-2/FR-3. |
| `service.py` | service | `AuditLogService.list_audit_logs()` (FR-1, FR-5 window validation, FR-2 self-audit write after a successful read), `AuditLogService.record_access_denied()` (FR-3). |
| `router.py` | router | `GET /v1/admin/audit-logs` per `US-3.3-openapi.yaml`. `PATCH`/`PUT`/`DELETE` register **no explicit handler** — Starlette returns `405` automatically for a method not registered on an already-matched path. Verified against `app/main.py`'s actual registered exception handlers (`RegistrationValidationError`, `ProblemError`, `DuplicateEmailError`, `RequestValidationError` — no `StarletteHTTPException`/generic `405` handler exists), so nothing in this app reshapes or intercepts the default response; it satisfies FR-4 without new route code. No existing route in this codebase relies on this path as precedent (it's a new pattern for this project), but it needs none — this is Starlette's own default behavior. |
| `dependencies.py` | dependencies | `AuditLogServiceDep`. Reuses `require_scope("audit:read")` from `app.modules.roles.dependencies` — an existing cross-module import pattern already used by `admin_users/router.py` (`from app.modules.roles.dependencies import require_scope`), not new to this story. |
| `exceptions.py` | exceptions | `RangeTooWideError` (FR-5, →`422`). `InsufficientPermissionError` (FR-3's `403`) is **not** a new exception — reused as-is from `app.modules.roles.exceptions`. |

**Amended 2026-09-02 (found by `plan-reviewer`, docs/reviews/plans/US-3.3-plan-review.md):** this survey originally omitted the AU-AC7 `[gate]`-marked chain-verification job, even though it was derivable from the spec at this stage. Added below.

| File | Layer | Reason |
|---|---|---|
| `scripts/verify_audit_chain.py` | — (standalone script, no execution skill in this project's roster owns this class of file — flagged as an open question in `docs/plans/US-3.3-task-breakdown.md`'s T6) | AU-AC7: "When the chain verification job runs over any day's partition... reports the exact row at which the chain breaks." Follows this project's one existing job precedent, `scripts/purge_unverified_accounts.py`. |

### Modified — existing modules

| File | Reason |
|---|---|
| `app/modules/email_verification/models.py` | `AuditLog` class renamed (table `audit_log` → `unverified_account_purge_log`, OD-1). Class name may also need renaming for clarity (e.g. `PurgeLog`) — left to `planner`; not a behavior change either way. |
| `app/modules/email_verification/repository.py` | `create_audit_log()`'s `self._session.add(AuditLog(...))` call references the renamed model — no logic change, but the model import/class name changes if `planner` renames the class too. |
| `app/modules/users/models.py`, `app/modules/roles/models.py`, `app/modules/profile/models.py`, `app/modules/account/models.py` | **New `ix_<table>_occurred_at` index** on `AuthAuditLog`, `AdminAuditLog`, `ProfileAuditLog`, `AccountLifecycleAuditLog` respectively (db-design's index finding) — additive, no column change. |
| `app/api/v1/router.py` | Register the new `audit` router (`app.include_router(audit.router, prefix="/v1/admin")` or equivalent), matching this file's existing aggregation pattern (same as US-3.2's `roles` router registration). |

## 2. Cross-Module Ripple

- **`audit.service` → `roles.dependencies.require_scope`.** Reused as-is (no new dependency direction — `admin_users` already imports from `roles.dependencies`, this story follows the same established pattern, not a new architectural fact).
- **FR-3's denial-write is NOT free.** Checked `app/modules/roles/dependencies.py::require_scope` directly: it raises `InsufficientPermissionError` and writes nothing — no central exception handler audits every `403` project-wide either (confirmed by grepping for `InsufficientPermissionError`/`authz_denied` call sites: the only existing `authz_denied` writes are hand-written inside `roles/service.py`'s own privilege-escalation/self-target checks, not a shared mechanism `require_scope` triggers). **This is a genuine architectural tension, not decided here:** either (a) `audit.router`'s route wraps `require_scope("audit:read")` with an audit-specific dependency that catches the denial and writes before re-raising, scoped to this one endpoint, or (b) `require_scope` itself gains a generic denial-audit write, which would then also start auditing every other route that already uses it (`users:read`, `users:write`, `roles:write`, `tickets:*`) — a cross-cutting behavior change well beyond this story's stated scope. Flagged for `planner` to choose; (a) is the narrower option and does not touch shared code other endpoints depend on.
- **No new dependency from any existing module onto `audit`.** Nothing in `users`/`roles`/`profile`/`account` needs to call `audit.service` for this story (OD-14 staged means no write-path repointing happens here).

## 3. Migration/Schema Impact

**Yes, a migration is required.** Per `US-3.3-entity-model.md`:

- **New:** `audit_log` table (daily range-partitioned on `occurred_at`), its `BEFORE INSERT` hash-chain trigger, and the `audit_log_history` view.
- **Renamed:** `email_verification.audit_log` → `unverified_account_purge_log` (no column change) — must run **before** the new `audit_log` table is created in the same migration sequence, since the name must be freed first (OD-1).
- **New indexes only, no column change:** `ix_auth_audit_log_occurred_at`, `ix_admin_audit_log_occurred_at`, `ix_profile_audit_log_occurred_at`, `ix_account_lifecycle_audit_log_occurred_at` on the four existing tables (db-design's index finding).

**Note for `planner`'s validation strategy:** under staged OD-14, four of `audit_log_history`'s five source tables stay live and actively written by their existing call sites — the view's `occurred_at DESC` keyset pagination (FR-1) reads a union of moving targets, not a static/historical dataset, when validating the p95 ≤ 500 ms NFR.

**No existing repository query is affected by a column change** — every schema change to an existing table in this story is either a pure rename (one table) or a pure additive index (four tables); no existing `INSERT`/`SELECT` on those tables needs updating. Per `AGENTS.md` §4's PostgreSQL hazards: the four new indexes should use `CREATE INDEX CONCURRENTLY` (each its own migration inside `autocommit_block()` with `if_not_exists=True`) since these are live, already-written-to tables — `planner`'s call, not decided here whether all four ship in one migration or four.

## 4. Test-Surface Impact

### New test files

- `tests/unit/modules/audit/test_audit_service.py`
- `tests/integration/modules/audit/test_audit_router.py`

### Existing test files that must change

- `tests/unit/modules/email_verification/test_*` (whichever unit test constructs or asserts against `email_verification.models.AuditLog` by name/table) — must be updated for the rename; a grep for `AuditLog`/`audit_log` within `tests/**/email_verification/` is needed at IMPLEMENTATION time to find every reference, not assumed exhaustively here.
- `tests/integration/modules/email_verification/test_purge_service.py` (confirmed to exist, per this module's own file listing) — asserts against the purge job's audit-writing behavior; needs its table/model reference updated for the rename, behavior unchanged.
- No other existing test file needs a behavior-level change — the four new `occurred_at` indexes and the `audit_log`/`audit_log_history` additions are purely additive and don't alter any existing endpoint's observable behavior.
