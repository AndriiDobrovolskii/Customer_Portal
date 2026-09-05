---
artifact_type: implementation_verification
story: US-4.2
version: 1
status: DRAFT
created_at: "2026-09-06T00:45:00Z"
updated_at: "2026-09-06T00:45:00Z"
produced_by: implementation-verifier
supersedes: null
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-4.2-plan-review.md
    version: 2
  - path: docs/evidence/US-4.2-implementation-report.md
    version: 1
  - path: docs/evidence/US-4.2-quality-gate-report.md
    version: 1
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: "3"
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/tests/US-4.2-test-strategy.md
    version: 3
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
---

# Verification Report: Ticket Replies

**Story ID:** US-4.2
**gate-enforcer Result Relied On:** PASS (v1) — `docs/evidence/US-4.2-quality-gate-report.md`: all 7 pre-commit hooks green, `mypy app tests` clean (146 files), `lint-imports` 6/6 contracts kept with zero `pyproject.toml` diff, `pytest --cov=app --cov-fail-under=85` 688/688 passed, 96.30% coverage (`support/service.py` 95%, `support/router.py` 100%), migration `upgrade → downgrade → upgrade` re-proven fresh against `9132a68b73c8`.
**Reviewed:** 2026-09-06
**Overall Verdict:** PASS

## Summary

Independently re-verified every AGENTS.md §6.5/§6.6/§6.7 item and the §5 security-case matrix for both new routes (`POST /support/tickets/{id}/replies`, `GET /support/tickets/{id}`) by reading `migrations/versions/9132a68b73c8_add_ticket_replies.py`, `app/modules/support/{models,repository,cache,schemas,service,router,dependencies}.py`, and the relevant test file directly — not inferred from `gate-enforcer`'s summary. All items are Pass or an explicitly justified N/A; no Critical or Major finding.

## §6.5 — Migration Human Half

- Generated file read: Yes — full read of `migrations/versions/9132a68b73c8_add_ticket_replies.py` this pass.
- Rewriter-unreachable statements guarded: Pass — evidence: `9132a68b73c8_add_ticket_replies.py:102-108` guards both `add_column` calls (`tickets.first_response_at`, `attachments.ticket_reply_id`) with an `sa.inspect(op.get_bind())` column-existence check; lines 121-129 guard `create_foreign_key` (`_ATTACHMENTS_TICKET_REPLY_ID_FK`) with a foreign-key-existence check via the same inspector; lines 131-142 guard both `CREATE POLICY` statements (`ticket_replies_read`/`ticket_replies_write`) with a `pg_policies` existence query, since `sa.inspect()` has no policy introspection — documented rationale at lines 39-45. `ENABLE`/`FORCE ROW LEVEL SECURITY` (lines 46-48, 131-132) are correctly left unguarded per the file's own comment (idempotent at the SQL level).
- `downgrade()` real, not `pass`: Pass — evidence: `9132a68b73c8_add_ticket_replies.py:145-166` drops both policies, disables RLS, drops the `attachments.ticket_reply_id` FK/index/column, drops `tickets.first_response_at`, drops the `ticket_replies` index and table — in reverse dependency order, each guarded (`if_exists=True` or an inspector check). Independently re-proven fresh by `gate-enforcer` v1's `upgrade → downgrade → upgrade` run (`US-4.2-quality-gate-report.md` §5), not only trusted from `migration-manager`'s earlier T3 proof.

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | Pass | `app/modules/support/service.py:439,553` — `TicketReplyService.create_reply(...) -> ReplyRead` returns `ReplyRead.model_validate(reply)` (line 543); `get_ticket_detail(...) -> TicketDetailRead` constructs `TicketDetailRead(...)` directly from scalar `ticket`/`page` fields (lines 574-589), never returning the `Ticket`/`TicketReply` ORM objects themselves. `app/modules/support/router.py` imports only `app.modules.support.{dependencies,schemas}` and `app.modules.users.dependencies.CurrentUserDep` — no `models`/`sqlalchemy`/`AsyncSession` import (confirmed by reading the full 140-line file). |
| All nested data eager-loaded | N/A | `app/modules/support/models.py` declares no `relationship()` anywhere (`TicketReply`'s own docstring, lines 69-76, states this is deliberate module precedent — direct repository queries over ORM graph traversal). `TicketDetailRead` is composed in the service (`service.py:574-589`) from two independent repository calls (`_ticket_repository.get_by_id`, `_reply_repository.list_for_ticket`), not a single eager-loaded graph fetch — nothing to eager-load. |
| Every cache write has a TTL | Pass | `app/modules/support/cache.py:120-126` `TicketReplyRateLimitCache.record_and_check` — pipelined `INCR`+`EXPIRE(window_seconds)` (line 124), same shape as the existing `TicketCreationRateLimitCache`. No other cache write is introduced by this story. |
| Cross-module calls go service→service | Pass | `app/modules/support/service.py` has no `from app.modules.*.router import` (confirmed by direct read of the file's imports, lines 1-31); `TicketReplyService`'s only cross-module collaborator is `UserServiceProtocol` (structural Protocol, lines 123-133), satisfied by `dependencies.py:104,117` injecting `UserServiceDep` (`app.modules.users.dependencies`), which resolves to the concrete `UserService` class, never a router. |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | Pass | `app/modules/support/router.py:84-88` `POST /{id}/replies` — `response_model=ReplyRead`, `status_code=status.HTTP_201_CREATED`; lines 115-119 `GET /{id}` — `response_model=TicketDetailRead`, `status_code=status.HTTP_200_OK`. Both pre-existing US-4.1 routes (lines 27-31, 54-59) unchanged and still compliant. |
| `extra="forbid"` + privilege exclusion on inbound schemas | Pass | `app/modules/support/schemas.py:55` `CreateReplyRequest.model_config = ConfigDict(extra="forbid")`; fields are `body`/`visibility`/`attachment_ids` only (lines 57-59) — no `id`/`ticket_id`/`author_id`/`author_kind`/`created_at` accepted client-side, checked against `TicketReply`'s actual column list (`models.py:100-112`), not just AGENTS.md's example list. |
| `.env.example` updated (if applicable) | Pass | `git diff HEAD -- .env.example` (re-run this pass) shows `SUPPORT_QUEUE_EMAIL` and `RUNTIME_DATABASE_URL` added — both new `Settings` fields this story introduces (`app/core/config.py`, per `implementation_report` v1). |
| No sensitive field in any `*Read` | Pass | `app/modules/support/schemas.py:70-76` `ReplyRead` exposes `id`, `ticket_id`, `author_id`, `author_kind`, `visibility`, `body`, `created_at` — matches `US-4.2-openapi.yaml` v3 `ReplyRead` verbatim, no attachment references (API_DESIGN Open Questions #5). `TicketDetailRead` (lines 97-107) adds only `first_response_at` and `replies` beyond `TicketRead`'s existing field set — no internal-only column exposed (`models.py` declares no field beyond what's listed). |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| `POST /support/tickets/{id}/replies` | `test_create_reply_no_token_returns_401` (line 1175) | `test_create_reply_expired_token_returns_401` (line 1205) | `test_create_reply_malformed_token_returns_401` (line 1189) | `test_create_reply_customer_visibility_internal_returns_403` (line 866) — a customer requesting `visibility="internal"` is rejected by `InsufficientPermissionError` (`service.py:462-466`), this route's actual permission gate | `test_create_reply_revoked_session_returns_401` (line 1222) |
| `GET /support/tickets/{id}` | `test_get_ticket_detail_no_token_returns_401` (line 1239) | `test_get_ticket_detail_expired_token_returns_401` (line 1269) | `test_get_ticket_detail_malformed_token_returns_401` (line 1253) | `test_get_ticket_detail_agent_lacking_tickets_read_returns_404` (line 1134) — an agent-scoped caller without `tickets:read`/ownership is rejected (404, not 403, by deliberate API_DESIGN choice not to confirm ticket existence to an unauthorized caller — `router.py:97-104` docstring) | `test_get_ticket_detail_revoked_session_returns_401` (line 1284) |

All ten cell functions confirmed present this pass by direct grep of `tests/integration/modules/support/test_support_router.py` at the cited line numbers. Both routes carry every applicable §5 case. The "insufficient permissions" outcome is `404` rather than `403` for both routes' ownership branch (`test_create_reply_different_customer_returns_404` line 1098, `test_get_ticket_detail_different_customer_returns_404` line 1117) — a deliberate, documented design decision (`API_DESIGN Open Question #2`, `router.py:100-103`) so the route never confirms a ticket id exists to a caller who is neither the requester nor an agent; the cells above cite each route's actual enforced-permission case (visibility gate for `POST`, scope/ownership gate for `GET`) rather than the ownership-404 case, consistent with `US-4.1`'s own precedent of citing the route's real permission gate in this matrix.

## Verdict Rationale

Every §6.5/§6.6/§6.7 item is Pass or an explicitly justified N/A, independently confirmed against the current code with file:line evidence rather than taken from the implementation or quality-gate reports. Both new protected routes carry full §5 security-case coverage. No ORM leak, missing eager-load, TTL-less cache write, service→router cross-module call, or missing `response_model`/`status_code` was found. Verdict: **PASS**.

**Carried forward, not this stage's to resolve:** the runtime-role provisioning script's per-environment documentation (`scripts/db/provision_runtime_role.sql`, flagged for `documentation-and-adrs` at `ARCHITECTURE_PLANNING` v2); `impact_analysis` v2's staleness against Architectural Change #12's four files (non-blocking finding, `PLAN_REVIEW` v2); the emergent `SUPPORT_QUEUE_EMAIL`/`RUNTIME_DATABASE_URL` settings' downstream deployment/secrets-rotation implications — all carried for `SECURITY_REVIEW`/`RECONCILIATION`/`HUMAN_PR_APPROVAL`.
