---
artifact_type: implementation_verification
story: US-4.1
version: 3
status: DRAFT
created_at: "2026-09-04T07:00:00Z"
updated_at: "2026-09-04T07:00:00Z"
produced_by: implementation-verifier
supersedes: docs/verification/US-4.1-implementation-verification.md (v2)
inputs:
  - path: docs/evidence/US-4.1-implementation-report.md
    version: 5
  - path: docs/evidence/US-4.1-quality-gate-report.md
    version: 5
  - path: docs/tests/US-4.1-test-strategy.md
    version: 5
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
---

# Verification Report: Create Support Ticket

**Story ID:** US-4.1
**gate-enforcer Result Relied On:** PASS (v5) — `docs/evidence/US-4.1-quality-gate-report.md`: all 7 pre-commit hooks green, `mypy app tests` 0 errors/145 files, `lint-imports` 6/6 kept, `pytest --cov=app --cov-fail-under=85` 603/603 passed (318 unit + 285 integration, including `tests/integration/modules/support/` and the new `tests/integration/scripts/test_purge_unbound_attachments.py` against real PostgreSQL/Valkey), 96.18% coverage, migration `upgrade → downgrade → upgrade` re-proven fresh against `customer_portal_pg`.
**Reviewed:** 2026-09-04
**Overall Verdict:** PASS

## Summary

Re-run against `implementation_report`/`quality_gate_report` v5 and `test_strategy`/`ac_test_matrix` v5 — v2 (recorded against v4/v4) is now superseded: `RECONCILIATION` v1's `test_gap` finding (ST-AC7's 24h purge clause untested) routed to `TEST_WRITING` attempt 5, which added `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests). This is a test-only addition exercising `AttachmentRepository.find_unbound_older_than`/`.purge` — no application code changed since v4 (confirmed by direct re-read of every file cited below; all evidence lines are identical to v2's). All AGENTS.md §6.5/§6.6/§6.7 items are independently re-verified Pass or justified N/A against the current code. The §5 security-case matrix is unchanged and still fully covered per v2's finding-resolution. No Critical or Major finding.

## §6.5 — Migration Human Half

- Generated file read: Yes — full re-read of `migrations/versions/37c89e98a86f_add_support_tickets.py` this pass; unchanged since v2 (no model/migration file touched by `TEST_WRITING` attempt 5, which added a test file only).
- Rewriter-unreachable statements guarded: Pass — evidence: the migration's only Rewriter-unreachable statements are two hand-written `op.execute()` calls (`37c89e98a86f_add_support_tickets.py:99-100`, `_CREATE_SEQUENCE`/`_SET_TICKET_NUMBER_DEFAULT`), both SQL-level idempotent (`CREATE SEQUENCE IF NOT EXISTS`; `SET DEFAULT` is naturally idempotent), documented at lines 34-41 citing `57a978462b74`'s established precedent for a SQL-level guard instead of a separate `sa.inspect(op.get_bind())` check. All `op.create_table`/`op.create_index` calls carry `if_not_exists=True` (lines 83, 90, 97, 121, 129, 136, 143).
- `downgrade()` real, not `pass`: Pass — evidence: `37c89e98a86f_add_support_tickets.py:147-163` drops both attachment indexes, the `attachments` table, the `ticket_number` default and sequence, both ticket indexes, and the `tickets` table, in reverse dependency order, each with `if_exists=True`. Independently re-proven this pass by `gate-enforcer` v5's fresh `upgrade → downgrade → upgrade` run against `customer_portal_pg` (`US-4.1-quality-gate-report.md` §5), not only trusted from `migration-manager`'s earlier proof.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/support/service.py:199,277` — `create_ticket(...) -> TicketRead` returns `TicketRead.model_validate(ticket)` on both the replay and success paths; `list_own_tickets(...) -> TicketListResponse` (line 333-336) builds `TicketRead.model_validate(ticket)` per item. `app/modules/support/router.py` imports only `app.modules.support.{dependencies,schemas}` and `app.modules.users.dependencies.CurrentUserDep` — no `models`/`sqlalchemy`/`AsyncSession` import (confirmed by reading the full file, 64 lines). |
| All nested data eager-loaded | N/A | `app/modules/support/models.py` declares no `relationship()` on `Ticket` or `Attachment` (only `mapped_column()` scalar/FK columns) — nothing to eager-load in this story's data model. |
| Every cache write has a TTL | Pass | `app/modules/support/cache.py:37-40` `TicketIdempotencyCache.claim` — `SET ... nx=True, ex=ttl_seconds`; lines 69-70 `.resolve` — `SET ... ex=ttl_seconds`; lines 99-101 `TicketCreationRateLimitCache.record_and_check` — pipelined `INCR`+`EXPIRE(window_seconds)`. `.release` (lines 72-83) is a `DELETE`, not a write, and needs no TTL. |
| Cross-module calls go service→service | Pass | `app/modules/support/dependencies.py:9,14` injects `AuditLogServiceDep` (`app.modules.audit.dependencies`) and `UserServiceDep` (`app.modules.users.dependencies`) — both resolve to concrete service classes (`UserServiceDep = Annotated[UserService, Depends(get_user_service)]`, `app/modules/users/dependencies.py:68`), never a router. `service.py`'s `AuditServiceProtocol`/`UserServiceProtocol` are structural Protocols satisfied by those injected instances, not direct repository/router access. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/support/router.py:14-18` `POST` — `response_model=TicketRead`, `status_code=status.HTTP_201_CREATED`; lines 41-45 `GET` — `response_model=TicketListResponse`, `status_code=status.HTTP_200_OK`. |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/support/schemas.py:15` `CreateTicketRequest.model_config = ConfigDict(extra="forbid")`; fields are `subject`/`body`/`category`/`attachment_ids` only — no `id`/`ticket_number`/`status`/`requester_id`/`created_at`/`updated_at` accepted client-side (checked against the actual `Ticket` model's column list, `app/modules/support/models.py`, not just AGENTS.md's example list). |
| `.env.example` updated (if applicable) | N/A | No new `Settings` field introduced by this story — confirmed via `gate-enforcer` v5's captured `git diff -- .env.example` / `git status --porcelain -- .env.example` (both empty) and independently: no `os.getenv`/`core.config` reference appears anywhere under `app/modules/support/` (`US-4.1-quality-gate-report.md` item 10's banned-idiom grep, re-confirmed by direct read of `service.py`/`router.py`/`cache.py`/`schemas.py` this pass). |
| No sensitive field in any `*Read` | Pass | `app/modules/support/schemas.py:23-39` `TicketRead` exposes `id`, `ticket_number`, `status`, `requester_id`, `subject`, `body`, `category`, `created_at`, `updated_at` — matches `US-4.1-openapi.yaml`'s `TicketRead` field list verbatim; no internal-only column (there are none beyond the ones listed — `models.py` declares no additional field). |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /v1/support/tickets` | `test_create_ticket_no_token_returns_401` | `test_create_ticket_expired_token_returns_401` | `test_create_ticket_malformed_token_returns_401` | N/A — route authorizes by identity/ownership only, no `tickets:*` scope gate exists to test against (`US-4.1-api-design.md` DR-4 fix, `router.py:25-30` docstring, `dependencies.py` has no scope check on the `POST` path); `ac_test_matrix.md` v5 records the same design decision. | `test_create_ticket_revoked_session_returns_401` |
| `GET /v1/support/tickets` | `test_list_own_tickets_no_token_returns_401` | `test_list_own_tickets_expired_token_returns_401` | `test_list_own_tickets_malformed_token_returns_401` | `test_list_own_tickets_agent_scope_caller_returns_403` — a caller holding `tickets:read`/`tickets:write` is rejected (`dependencies.py:42-53` `reject_agent_queue_access`), GET's actual permission gate | `test_list_own_tickets_revoked_session_returns_401` |

All ten cell functions were re-confirmed present this pass by direct grep of `tests/integration/modules/support/test_support_router.py` (lines 314, 324, 336, 354, 372, 391, 399, 407, 421, 568) — no test removed or renamed since v2. Both routes carry every applicable case from AGENTS.md §5; `POST`'s "insufficient permissions" cell is an explicit, previously-reviewed N/A (`DESIGN_REVIEW` v3 DR-4), not an unflagged gap.

FR-5's account-deactivated `403` (`test_create_ticket_deactivated_account_returns_403`, integration; `test_create_ticket_deactivated_account_raises_before_any_write`/`test_create_ticket_active_account_proceeds`, unit) is a business-rule case, not part of the §5 security matrix, but independently re-confirmed correct by code read this pass: `app/modules/support/service.py:172-174` checks `get_account_status_for_user` first, before the idempotency claim or any cache/DB write.

The new test file this pass, `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests against `AttachmentRepository.find_unbound_older_than`/`.purge`, closing ST-AC7's purge clause per `RECONCILIATION` v1), exercises an unauthenticated maintenance script with no HTTP route and no protected-route surface — out of scope for the §5 matrix, and confirmed by `gate-enforcer` v5 to contain no `unittest.mock`/`AsyncMock`/`MagicMock`.

## Verdict Rationale

Every §6.5/§6.6/§6.7 item is Pass or an explicitly justified N/A against the current code (all evidence independently re-confirmed this pass, not carried from v2 without re-reading), and both protected routes carry their full applicable §5 security-case coverage, unchanged since v2's finding-resolution. The only change since v2 — a new test file for a non-route maintenance script — introduces no new §6.5/§6.6/§6.7/§5 surface. Verdict: **PASS**.

**Carried forward, not this stage's to resolve:** OD-3 (category enum, no DB-level `CHECK`/`ENUM` constraint), BR-007 FK `ondelete` mechanics (pending legal/DPO sign-off), the idempotency poll-exhaustion path's undocumented 500 (confirmed implementation behavior, not a further gap), the two Spec Drift items from `RECONCILIATION` v1 (`ticket_number` guessable format; `ticket_audit_log` vs. `audit_log` wording), and the FR-1 email-collaborator emergent scope (`EmailSender.send_ticket_created_email`, `UserService.get_email_for_user`, not named in any approved design/plan artifact) — all carried for `SECURITY_REVIEW`/`RECONCILIATION`/`HUMAN_PR_APPROVAL`. `scripts/purge_unbound_attachments.py`'s missing test is resolved as of `TEST_WRITING` v5 — no longer carried.
