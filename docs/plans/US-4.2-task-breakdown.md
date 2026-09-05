---
artifact_type: task_breakdown
story: US-4.2
version: 2
status: DRAFT
created_at: "2026-09-05T15:00:00Z"
updated_at: "2026-09-05T20:00:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
supersedes: docs/plans/US-4.2-task-breakdown.md (v1)
---

# Task Breakdown — US-4.2 (Ticket Replies)

## Revision Note (v2)

v1 (2026-09-05T15:00:00Z) was sequenced against `implementation_plan` v1 and
predates Architectural Change #12 (`implementation_plan` v2, added
2026-09-05T19:00:00Z per the `HUMAN_REDIRECTED` transition routing
`IMPLEMENTATION` → `ARCHITECTURE_PLANNING`): a dedicated non-superuser
`app_runtime` PostgreSQL role, so `FORCE ROW LEVEL SECURITY` actually forces
anything. v1 did not sequence `scripts/db/provision_runtime_role.sql`,
`app/main.py`, or `tests/conftest.py` — files `implementation_plan` v2 itself
flags as falling outside all four execution skills' usual footprint and
explicitly defers to this stage ("`IMPLEMENTATION_PLANNING` schedules the
script's creation ... as an explicit task, not an afterthought"; "flagged for
`IMPLEMENTATION_PLANNING` to assign explicitly"). This revision adds T4
(new) for that work and folds the remaining new files
(`app/core/config.py`'s `runtime_database_url` field, `app/main.py`,
`.env.example`) into T5, mirroring v1's own precedent of bundling
`support_queue_email` (OD-2) into the service task rather than inventing a
sixth execution skill. T1–T3's rows are carried forward verbatim — T1/T2 are
already `PASS`, T3's migration DDL is already proven and needs no re-run,
only re-verification once T4 lands (`docs/catalog/US-4.2-pipeline-status.md`
v2). See "Assignment note" below both new rows for why no loop-back to
`ARCHITECTURE_PLANNING` was used to resolve this instead.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | schema-builder | schemas | — | `app/modules/support/schemas.py` (new `CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead`; existing `TicketRead`/`TicketListResponse`/`CreateTicketRequest` unchanged) | mypy `strict` clean on the file; grep confirms `extra="forbid"` on `CreateReplyRequest`; `TicketDetailRead`/`ReplyRead` declare `from_attributes=True` with an explicit field list. **Already PASS** (`docs/catalog/US-4.2-pipeline-status.md` v2, T1) — carried forward unchanged, no re-run. |
| T2 | data-layer-builder | models / repository / cache | — | `app/modules/support/models.py` (new `TicketReply` class + `CheckConstraint` + composite `(ticket_id, created_at, id)` index; additive `Ticket.first_response_at`; additive `Attachment.ticket_reply_id` with `index=True`; no `relationship()` on any of the three), `app/modules/support/repository.py` (new `TicketReplyRepository.create()`/`list_for_ticket()`; new `TicketRepository.update()`; new `AttachmentRepository.bind_to_reply()`), `app/modules/support/cache.py` (new `TicketReplyRateLimitCache`), `app/core/cache_keys.py` (new `ticket_reply_rate_key(user_id)`) | mypy `strict` clean; grep confirms zero `session.query()`/`relationship()` additions; grep confirms `Mapped[]`/`mapped_column()` only on the new columns. **Already PASS** (`docs/catalog/US-4.2-pipeline-status.md` v2, T2) — carried forward unchanged, no re-run. |
| T3 | migration-manager | migration | T2 | `migrations/versions/9132a68b73c8_add_ticket_replies.py` (`CREATE TABLE ticket_replies` incl. `CHECK` constraint and composite index; additive `tickets.first_response_at`/`attachments.ticket_reply_id` + plain, non-`CONCURRENTLY` index per DR-2 resolved; hand-written `ENABLE`/`FORCE ROW LEVEL SECURITY` + two `CREATE POLICY` statements, each guarded by `sa.inspect(op.get_bind())`, with a real `downgrade()`) | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` — **already executed and passed** (`docs/catalog/US-4.2-pipeline-status.md` v2, T3). The DDL itself needs no re-run; T3's status is **re-verifiable, not re-runnable** once T4 lands — re-run only `tests/integration/modules/support/test_support_router.py::test_internal_reply_hidden_from_customer_context_by_rls_alone` and `::test_no_actor_kind_set_defaults_to_hiding_internal_reply` (per `implementation_plan` v2 §12) to confirm the already-proven policy predicates now hold end-to-end. |
| T4 (NEW, v2) | migration-manager | database role provisioning + test infrastructure (cross-cutting — no single AGENTS.md §3 layer; see assignment note below) | T3 | `scripts/db/provision_runtime_role.sql` (new — idempotent `CREATE ROLE app_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`, `GRANT CONNECT`/`USAGE`/`SELECT,INSERT,UPDATE,DELETE ON ALL TABLES`/sequence `USAGE,SELECT`, `ALTER DEFAULT PRIVILEGES`, per `implementation_plan` v2 §12), `tests/conftest.py` (`_database` fixture: after `command.upgrade(alembic_cfg, "head")`, execute the provisioning script against the owner-role engine, then build a second `app_runtime`-credentialed engine/session_factory and assign it — not the owner-role one — to `app.state.db_engine`/`db_session_factory`) | `scripts/db/provision_runtime_role.sql` runs twice against the same database without error (idempotency); `test_internal_reply_hidden_from_customer_context_by_rls_alone` and `test_no_actor_kind_set_defaults_to_hiding_internal_reply` pass against the `app_runtime`-connected fixture; **the full existing integration suite** (`tests/integration/modules/{users,roles,admin_users,audit,profile,support}/...`, not `support`'s alone) passes against the new role — the actual proof the `GRANT` list is complete (`implementation_plan` v2 Risk 7), not a review of the SQL by inspection. |
| T5 | service-and-router-builder (service) | service | T1, T3 | `app/modules/support/service.py` (new reply-handling method(s): actor-kind branch, FR-4 ownership/scope check, status-gating switch, FR-5 visibility check, `body` length validation, attachment reply-binding via `bind_to_reply`, 30/hour rate-limit check, `first_response_at` stamp, two post-commit best-effort email dispatches; new/extended Protocols), `app/modules/support/exceptions.py` (new `TicketNotFoundError`, module-owned `InsufficientPermissionError`, `TicketClosedError`, `TicketReplyRateLimitError`), `app/core/email.py` (`EmailSender` Protocol: two new methods; `LoggingEmailSender`: matching log-only implementations), `app/core/config.py` (new `support_queue_email: str` field; **NEW (v2)** new `runtime_database_url: str` field, dev-only default mirroring `jwt_secret_key`), `.env.example` (new `SUPPORT_QUEUE_EMAIL` entry; **NEW (v2)** new `RUNTIME_DATABASE_URL` entry), **`app/main.py`** (NEW, v2 — the one-line `lifespan()` change: `create_engine_and_sessionmaker(settings.database_url)` → `create_engine_and_sessionmaker(settings.runtime_database_url)`; see assignment note below) | grep confirms zero `fastapi`/`starlette`/`HTTPException` imports in `service.py`; mypy `strict` clean with explicit `-> *Read` annotations on every new service method; unit tests for the new methods pass against hand-written fakes; grep confirms `app/main.py`'s diff is exactly the one `settings.database_url` → `settings.runtime_database_url` substitution in `lifespan()`, nothing else changed. |
| T6 | service-and-router-builder (router) | router | T5 | `app/modules/support/router.py` (new `POST /support/tickets/{id}/replies` and `GET /support/tickets/{id}` routes, both using the `get_rls_session`-backed dependency chain, `response_model`/`status_code` declared on each, `limit: Annotated[int, Query(ge=1, le=100)] = 50` on the `GET` route, agent-branch authorization via `require_scope("tickets:write")`/`require_scope("tickets:read")`), `app/modules/support/dependencies.py` (new `get_rls_session` dependency wrapping `get_db_session` with `SET LOCAL app.actor_kind`/`SET LOCAL app.actor_id`; new/extended service-provider wiring) | grep confirms zero `sqlalchemy`/`models`/`repository`/`AsyncSession`/Valkey imports in `router.py`; OpenAPI schema render matches `US-4.2-openapi.yaml` v3 endpoint/schema shapes; `lint-imports` passes (`router → dependencies` only, `exhaustive=true`). |
| T7 | gate-enforcer | — | T1–T6 (+ test-writer, already run at TEST_WRITING) | — | `pre-commit run --all-files`; `mypy app tests`; `lint-imports`; `pytest --cov` against the 85%/90% floors in `AGENTS.md` §5/§6, run against the `app_runtime`-connected fixture (T4). |

**Parallel-eligible:** T1 and T2 have no dependency on each other and may run
in parallel. T4 and T5/T6 are also mutually parallel-eligible in principle —
neither's *code* depends on the other's output (T4 touches no
`app/modules/support/` file; T5/T6's code only needs T1/T3's schema and
repository/migration to exist, not `app_runtime` itself) — but T4 must
complete before `gate-enforcer` (T7) runs, since T7's full-suite regression
pass is the proof T4's `GRANT` list is complete, and before the two direct-RLS
integration tests can be asserted as genuinely passing rather than
accidentally passing against a still-superuser fixture.

## Assignment note — T4 and the `app/main.py` line in T5 (non-blocking, carried to `plan-reviewer`)

`implementation_plan` v2 names three files
(`scripts/db/provision_runtime_role.sql`, `app/main.py`, `tests/conftest.py`)
that do not fit any of the four execution skills' usual file footprint and
explicitly defers the assignment to this stage (§12, and the Files-To-Modify
table's `tests/conftest.py` row). No loop-back to `ARCHITECTURE_PLANNING` was
used: the plan already decided *what* changes and *why* in full — nothing is
being invented here, only *which skill runs it*, which is this stage's own
charter, and `ARCHITECTURE_PLANNING` has already run twice on this story.

- `scripts/db/provision_runtime_role.sql` + `tests/conftest.py`'s fixture
  change are assigned to **migration-manager** as T4: both are PostgreSQL
  role/connection provisioning, the same domain (idempotency guards,
  `AGENTS.md` §4 PostgreSQL hazards) migration-manager already owns for T3,
  and T4's own verification is exactly the re-verification of T3's RLS proof
  that `implementation_plan` v2 §12 says must happen once the role exists.
  This is wider than migration-manager's usual "Alembic revision" footprint
  (the SQL script is explicitly *not* a migration, and `tests/conftest.py` is
  shared test infrastructure, not `app/modules/support/`) — flagged here so
  `plan-reviewer` and the `HUMAN_PLAN_APPROVAL` gate can weigh in before
  `IMPLEMENTATION` invokes it.
- `app/main.py`'s one-line `lifespan()` change is folded into **T5**
  (service-and-router-builder's service task), following this story's own v1
  precedent of bundling adjacent `app/core/config.py`/`.env.example` settings
  additions into the service task rather than inventing a task for a
  single-line, non-module file. Also wider than the skill's usual
  `app/modules/<module>/` + `app/core/` footprint — same flag as above.

If `plan-reviewer` or the human gate judges either assignment wrong, the
correct loop-back is `changes_required_sequencing` (stays within
`IMPLEMENTATION_PLANNING`/`PLAN_REVIEW`, per `stage-map.yaml`
`PLAN_REVIEW.loop_back`), not another `ARCHITECTURE_PLANNING` pass — the
*what* is settled; only the *who* was in question.

## Notes

- Ordering follows `AGENTS.md` §3 (`router → dependencies → service →
  repository/cache → models/schemas`, read bottom-up for build order) and
  this project's migration-before-model-use rule: T3 (migration) must
  complete and be proven before T5/T6 (service/router) run against the live
  schema, even though T5/T6's *code* only imports the repository (T2), not
  the migration file itself — the dependency is on the schema being live in
  the database the service's integration tests hit.
- T4's dependency on T3 (not T2) is deliberate: T4 provisions a role and
  grants it privileges on tables T3 already created; running T4 before T3
  would still be idempotently correct (the `ALTER DEFAULT PRIVILEGES`
  statement covers future tables) but the plan's own ordering
  (`implementation_plan` v2 §12: "after migrations have been applied at least
  once") is followed here for traceability.
