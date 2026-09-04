---
artifact_type: impact_analysis
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-03T00:15:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.1-design-review.md
    version: 3
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
supersedes: null
---

# Impact Analysis: Support Tickets (Create) (US-4.1 / spec US-4.1)

**Spec:** docs/specifications/US-4.1-spec.md (v1)
**API design:** docs/designs/api/US-4.1-api-design.md, US-4.1-openapi.yaml (v3)
**DB design:** docs/designs/database/US-4.1-db-design.md, US-4.1-entity-model.md (v3)
**Design review:** docs/reviews/designs/US-4.1-design-review.md (v3, PASS)

This story has no existing module to extend — no `support`/`tickets` directory
exists under `app/modules/` today (confirmed by directory listing: `account`,
`admin_users`, `audit`, `email_verification`, `profile`, `roles`, `users`
only). A new module, `app/modules/support/`, is created, matching the naming
`US-4.1-db-design.md`'s own "Cross-module layering note" already uses
(`this story's support/tickets module`).

## 1. Affected Files, by Layer

### New — `app/modules/support/`

| File | Layer | Reason |
|---|---|---|
| `__init__.py` | — | New module. |
| `models.py` | models | `Ticket` (`tickets`) and `Attachment` (`attachments`) per `US-4.1-entity-model.md`; no `relationship()` on either (design states no response nests a collection). |
| `schemas.py` | schemas | `CreateTicketRequest` (`extra="forbid"`), `TicketRead`, `TicketListResponse` per `US-4.1-openapi.yaml`'s component schemas. |
| `repository.py` | repository | `TicketRepository` (`create`, `get_by_id`, keyset-paginated `list_for_requester` using the `(requester_id, created_at DESC, id DESC)` index) and `AttachmentRepository` (`get_by_id` for the ownership check, `bind_to_ticket`, `find_unbound_older_than` for the purge job). |
| `cache.py` | cache | Idempotency gate (`SET NX EX` claim/overwrite/bounded-poll per `US-4.1-db-design.md`'s atomic create/replay mechanism) and the `ticket_create_rate:{user_id}` `INCR`+`EXPIRE` rate limiter, both Valkey-only per `AGENTS.md` §3. |
| `service.py` | service | `TicketService.create_ticket()` (FR-1, FR-3, FR-4, FR-6, FR-7 orchestration, in the order DB design states: idempotency gate → rate limit → validation → attachment binding → audit write, all in one transaction) and `TicketService.list_own_tickets()` (FR-2). |
| `router.py` | router | `POST /v1/support/tickets`, `GET /v1/support/tickets` per `US-4.1-openapi.yaml`. |
| `dependencies.py` | dependencies | `TicketServiceDep`; the `GET` staff-rejection branch's `require_scope("tickets:read")` / `require_scope("tickets:write")` wiring (reusing `app/modules/roles/dependencies.py`'s existing factory — no new authorization mechanism per the API design's DR-4 fix). |
| `exceptions.py` | exceptions | `IdempotencyKeyReuseError` (422, FR-4), `AttachmentNotOwnedError` (422, FR-7 — response never distinguishes the three causes per BR-016/IDOR), `TicketCreationRateLimitError` (429 + `Retry-After`, FR-6, mirroring `email_verification/exceptions.py`'s `TooManyAttemptsError` pattern of a dynamically-set `self.headers`), `AgentQueueNotAvailableError` (403, `GET`'s staff-rejection branch). `AccountDeactivatedError` (403, FR-5) if not already reachable from `app/modules/users`. |

### New — `scripts/`

| File | Reason |
|---|---|
| `scripts/purge_unbound_attachments.py` | FR-7's "unbound attachments older than 24 hours are purged by a scheduled job." This project's only existing precedent for a scheduled purge (`email_verification`'s `purge_unverified_accounts` service method) is invoked by a standalone CLI script, not an in-process scheduler — `scripts/purge_unverified_accounts.py` is the exact structural precedent. Calls a new `TicketService`/`AttachmentRepository` method (`purge_unbound_attachments` or equivalent) built on `find_unbound_older_than`. |

### Modified — cross-cutting (`app.core`)

| File | Reason |
|---|---|
| `app/core/cache_keys.py` | Add `idempotency_key(user_id, key)` → `idempotency:{user_id}:{key}` and `ticket_create_rate_key(user_id)` → `ticket_create_rate:{user_id}`, mirroring the existing per-user key builders (`revoke_before_key`, `login_fail_account_key`) already in this file — same file, same pattern, per `US-4.1-db-design.md`'s explicit statement that it reuses this codebase's existing per-user keying scheme rather than inventing one. |

### Modified — existing modules (cross-module ripple, not this story's own module)

| File | Reason |
|---|---|
| `app/modules/audit/service.py` | Neither existing public method (`list_audit_logs`, `record_access_denied`) fits a `ticket_created` write — both hard-code their own `event`/`category`/`payload` shape and neither accepts a `target_id` or a caller-supplied `event` name. Confirmed by direct read (`app/modules/audit/service.py:1-171`). A new method (e.g. `record_event`) is needed on `AuditLogService`, taking `category`, `event`, `actor_id`, `target_id`, `outcome`, `payload` as the `US-4.1-db-design.md` `audit_log` write-mapping table specifies, and internally reusing the existing `_resolve_actor_role` helper. |
| `app/modules/audit/repository.py` | The new `AuditLogService` method needs a matching `AuditRepository` method that constructs an `AuditLog(...)` row (a new `AuditLog(...)` call site in this file, alongside the two existing ones in `record_self_audit`/`record_access_denied`) and does **not** call `.commit()` itself, since the write must land in the *same transaction* as ticket creation (`US-4.1-db-design.md`'s "Cross-module layering note": tickets service calls audit service, audit service issues the insert, but the tickets service owns the commit for this one operation — a deviation from `record_self_audit`'s own self-committing shape that `planner`/`implementation-planner` must resolve explicitly, not silently copy). `tests/unit/test_audit_write_call_site_scan.py` already scans every `AuditLog(...)` call site in this exact file by AST walk and is *not* scoped to a fixed count, so the new call site is automatically covered by the existing scan with no test-file edit required. |
| `app/api/v1/router.py` | Register the new `support` router (`router.include_router(support_router)`), matching this file's existing flat aggregation pattern (7 existing `include_router` calls). |
| `migrations/env.py` | Add `from app.modules.support import models as support_models  # noqa: F401  # registers models`, matching the 6 existing per-module registration imports (`account`, `admin_users`, `audit`, `email_verification`, `profile`, `roles`, `users` — `email_verification`, `users` confirmed at lines 14-22). Without this, Alembic's `--autogenerate` will never see `Ticket`/`Attachment` and will produce an empty or destructive-looking diff. This file is a protected config per `AGENTS.md` §7.9 ("read, never edit") in the sense of not weakening what it enforces — adding one model-registration import line, following the exact established pattern, is the same class of change every prior story's `migration-manager`/`data-layer-builder` step has already made 6 times over, not a change to the file's Rewriter/guard logic itself. Flagged here as a required file, not a decision on who performs the edit. |

## 2. Cross-Module Ripple

- **`support.service` → `audit.service` (new cross-module dependency).** `TicketService.create_ticket()` must call a new `AuditLogService` method to write the `ticket_created` row (FR-1), inside the same DB transaction as the ticket insert and the attachment bind. This is a new direction of dependency — no existing module currently calls into `audit.service` for a write from outside `audit` itself (`audit.service`'s own `list_audit_logs`/`record_access_denied` write *audit's own* self-audit entries, they are not called by another module to record a foreign event). Per `AGENTS.md` §3 "cross-module calls go service → service," `support.repository` must not import `AuditRepository`/`AuditLog` directly.
- **`support.service` → `roles.service` (indirect, via `audit.service`).** The new `AuditLogService.record_event()` method's `actor_role` resolution reuses the existing `_resolve_actor_role(role_service, actor_id)` helper, which already calls `roles.service.get_role_grants_for_user` — no new direct `support` → `roles` edge, this ripple stays inside `audit.service` as it already does today for its own writes.
- **`support.router` → `roles.dependencies` (direct, not service-to-service — this is authorization wiring, not a business-logic call).** `GET`'s staff-rejection branch imports `require_scope(...)` from `app/modules/roles/dependencies.py`, the same pattern `app/modules/audit/dependencies.py`'s `require_audit_read` already uses. This is a `router`-layer dependency import, not a `service`-layer cross-module call, and is consistent with every other scope-gated route in this project.
- **Transaction-boundary tension (flagged, not resolved here).** `US-4.1-db-design.md`'s own "Cross-module layering note" states the audit write must happen inside ticket creation's transaction. `audit.service`'s existing two methods each call `self._repository.commit()` themselves (self-contained transactions). A `support.service`-owned transaction that also writes an audit row means either (a) the new `AuditLogService` method must NOT commit, leaving `support.service` to commit both writes together, or (b) accept two separate commits (ticket created, then audit write) with a documented small window where a ticket could exist without its audit entry if the second commit fails. This is the same class of tension `US-3.2-impact-analysis.md` flagged for its own FR-7 last-admin check and left unresolved for `planner` — flagged identically here, not decided.

## 3. Migration/Schema Impact

**Yes, a migration is required.** New tables only — no existing table's columns change:
- `tickets` (new) — plus a hand-written `ticket_number_seq` `SEQUENCE` and a `server_default=FetchedValue()` expression for `ticket_number`, since Alembic's autogenerate does not produce sequence-backed column defaults on its own (`US-4.1-db-design.md` states this mirrors `AuditLog.previous_hash`'s own hand-written-`DEFAULT` precedent).
- `attachments` (new)

No existing repository query is affected — no column is added to `users`, `audit_log`, or any other existing table, and `audit_log`'s existing `(occurred_at DESC, actor_id, event)` index already covers the new `ticket_created` event/category literal without a new index (per `US-4.1-db-design.md`'s own statement). No seed data is required (unlike `US-3.2`'s role/permission seed inserts) — `category`'s value set (OD-3) is deliberately left unenumerated pending a stakeholder decision, so no `CHECK`/enum migration step exists for this story.

## 4. Test-Surface Impact

### New test files
- `tests/unit/modules/support/__init__.py`
- `tests/unit/modules/support/test_support_schemas.py` — `CreateTicketRequest`/`TicketRead` validation (`extra="forbid"`, length caps, `attachment_ids` shape).
- `tests/unit/modules/support/test_support_service.py` — `TicketService` business logic against hand-written fakes: idempotency claim/replay/reuse/mid-flight-poll branches, rate-limit ordering relative to idempotency (FR-6 must never fire on a genuine replay), attachment ownership rejection paths (FR-7, indistinguishable causes), category validation stub pending OD-3.
- `tests/integration/modules/support/__init__.py`
- `tests/integration/modules/support/test_support_router.py` — end-to-end HTTP behavior against real PostgreSQL/Valkey per `AGENTS.md` §5: FR-1 through FR-7's status codes, the 401/403/422/429 cases, and the audit-row side effect of a successful `POST` (a genuine cross-module integration check, following `tests/integration/modules/roles/test_roles_router.py`'s own local-helper-per-file pattern — `tests/conftest.py`'s shared fixtures, `db_session`/`client`/`cleanup_users`, need no change).
- `tests/unit/scripts/test_purge_unbound_attachments.py` and/or `tests/integration/scripts/test_purge_unbound_attachments.py` — mirroring `tests/integration/scripts/test_anonymize_erased_user.py`'s existing pattern for a standalone purge/erasure script.

### Existing test files that must change
- `tests/unit/modules/audit/test_audit_service.py` — must gain coverage for the new `AuditLogService` method (`record_event` or equivalent) this story adds, including the no-self-commit variant if the transaction-boundary tension (§2) is resolved that way.
- `migrations/env.py`'s own model-registration list has no dedicated test, but `scripts/validate_harness.py` and the standard `alembic upgrade → downgrade → upgrade` proof (owned by `migration-manager`) will fail if the new import is missing — noted here as a verification dependency, not a new test file.

### Existing test files confirmed NOT requiring change
- `tests/unit/test_audit_write_call_site_scan.py` — scans every `AuditLog(...)` call site in `app/modules/audit/repository.py` by AST walk (not a fixed count), so the new call site this story adds is automatically covered with no edit to the scan itself.
- `tests/conftest.py` — no shared fixture is needed; every existing per-module router test (e.g. `test_roles_router.py`) seeds its own users/tokens/roles via local module-level helpers, and this story's tests follow the same local-helper pattern.
