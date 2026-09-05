---
artifact_type: implementation_report
story: US-4.2
version: 1
status: DRAFT
created_at: "2026-09-06T00:15:00Z"
updated_at: "2026-09-06T00:15:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
supersedes: null
---

# Implementation Report — US-4.2 (Ticket Replies)

Aggregates all four `IMPLEMENTATION` builder sub-steps
(`docs/catalog/US-4.2-pipeline-status.md` v6) against `task_breakdown` v2's
T1–T6. `QUALITY_GATE`'s own gate results are in the paired
`docs/evidence/US-4.2-quality-gate-report.md`, not repeated here.

## What was built

**New endpoints** (`app/modules/support/router.py`):
- `POST /api/v1/support/tickets/{id}/replies` — `response_model=ReplyRead`, `status_code=201`.
- `GET /api/v1/support/tickets/{id}` — `response_model=TicketDetailRead`, `status_code=200`, keyset-paginated reply thread (`limit: 1..100, default 50`).

**Schemas** (`app/modules/support/schemas.py`): `CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead` — new; existing `TicketRead`/`TicketListResponse`/`CreateTicketRequest` unchanged.

**Data layer** (`app/modules/support/models.py`, `repository.py`, `cache.py`, `app/core/cache_keys.py`):
- `TicketReply` model (new table `ticket_replies`, `CheckConstraint ck_ticket_replies_visibility_agent_only`, composite index `(ticket_id, created_at, id)`), `Ticket.first_response_at` (additive), `Attachment.ticket_reply_id` (additive, indexed FK).
- `TicketReplyRepository.create()`/`list_for_ticket()`, `TicketRepository.update()`, `AttachmentRepository.bind_to_reply()`.
- `TicketReplyRateLimitCache` (30/user/hour, INCR+EXPIRE), `ticket_reply_rate_key()`.
- No `relationship()` added to any model — direct repository queries, matching this module's existing precedent (documented in `TicketReply`'s own docstring).

**Migration** (`migrations/versions/9132a68b73c8_add_ticket_replies.py`): `CREATE TABLE ticket_replies` with the check constraint and composite index; additive `tickets.first_response_at` and `attachments.ticket_reply_id` + index; hand-written `ENABLE`/`FORCE ROW LEVEL SECURITY` and two `CREATE POLICY` statements (read: hide `internal` replies from customers; write: only `agent` may insert `internal`), each guarded by `sa.inspect(op.get_bind())`; real `downgrade()`. Proven via `upgrade → downgrade → upgrade` twice — once by `migration-manager` during T3, re-proven fresh during `QUALITY_GATE` (see quality-gate report §5).

**Runtime role provisioning** (`scripts/db/provision_runtime_role.sql`, `tests/conftest.py`): new idempotent script creating a non-superuser `app_runtime` role (`NOSUPERUSER NOBYPASSRLS`) with `GRANT`s on existing and future tables/sequences, added because the deployment role (`postgres`) is a PostgreSQL superuser and unconditionally bypasses `FORCE ROW LEVEL SECURITY` — discovered as a `BLOCKED` finding at T3, resolved by `HUMAN_REDIRECTED` routing to `ARCHITECTURE_PLANNING` (Architectural Change #12). `tests/conftest.py`'s `_database` fixture now provisions the role once per session and serves all test requests through an `app_runtime`-credentialed engine. `app/main.py`'s `lifespan()` and `app/core/config.py`'s new `runtime_database_url` setting wire the same role into real deployments; `migrations/env.py` is untouched and still runs as the owner role.

**Service layer** (`app/modules/support/service.py`, `exceptions.py`, `app/core/email.py`, `app/core/config.py`, `.env.example`): `TicketReplyService.create_reply()`/`get_ticket_detail()` — actor-kind branch (customer/agent), ownership/scope checks, status-gating (open ticket rejects reply on `"closed"`; a customer reply on `"resolved"` reopens it to `"waiting_on_support"` per Resolution OD-8; an agent reply on `"resolved"` leaves status unchanged per OD-5), visibility check (`internal` agent-only, `public` default per OD-6), attachment reply-binding, 30/hour rate limit, `first_response_at` stamp on the first public agent reply, two post-commit best-effort email notifications (requester on agent reply; configured `support_queue_email` mailbox on customer reply, per OD-2). New exceptions: `TicketNotFoundError`, `InsufficientPermissionError`, `TicketClosedError`, `TicketReplyRateLimitError`. `EmailSender` Protocol gained two methods with matching `LoggingEmailSender` implementations.

**Dependencies** (`app/modules/support/dependencies.py`): `get_rls_session` — wraps `get_db_session`, issues `SET LOCAL app.actor_kind`/`SET LOCAL app.actor_id` per request so PostgreSQL RLS policies see the caller's identity.

## Task Breakdown status (task_breakdown v2)

| Task | Skill | Status | Notes |
|---|---|---|---|
| T1 | schema-builder | PASS | Carried forward from first pass, no re-run needed. |
| T2 | data-layer-builder | PASS | Carried forward from first pass, no re-run needed. |
| T3 | migration-manager | PASS (re-verified) | DDL proven at first pass; two direct-RLS integration tests re-verified passing once T4's role existed. |
| T4 | migration-manager | PASS | `provision_runtime_role.sql` idempotent (run twice, zero errors); full non-support integration suite (261 tests) + 26 support non-reply tests passed unchanged against `app_runtime`, proving the `GRANT` list is complete. |
| T5 | service-and-router-builder (service) | PASS | 61/61 support unit tests; `app/main.py` diff confirmed to be exactly the one `runtime_database_url` substitution. |
| T6 | service-and-router-builder (router) | PASS | OpenAPI render matches `US-4.2-openapi.yaml` v3 (path parameter `{id}`); `lint-imports` clean. |
| T7 | gate-enforcer | PASS | See `docs/evidence/US-4.2-quality-gate-report.md`. |

Two test-file-only defects were found and fixed mid-`IMPLEMENTATION` via the `changes_required_tests`/`HUMAN_REDIRECTED` loop-back to `TEST_WRITING` (RLS-context seeding gaps and a non-deterministic timestamp tie in `_seed_reply()`) — full detail in `workflow-state.yaml`'s `TEST_WRITING` re-entry notes and `docs/catalog/US-4.2-pipeline-status.md` v3–v6. No application code was changed by either fix.

## Final verification snapshot (captured fresh at QUALITY_GATE)

- 688/688 tests passed (full repository suite); 96.30% combined coverage (`support/service.py` 95%, `support/router.py` 100%).
- `pre-commit run --all-files`, `mypy app tests`, `lint-imports` (6/6 contracts kept) all clean.
- Migration `upgrade → downgrade → upgrade` re-proven.
- OpenAPI renders: 28 paths, including both new routes.

Full command output: `docs/evidence/US-4.2-quality-gate-report.md`.
