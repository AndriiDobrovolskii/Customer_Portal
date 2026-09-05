---
artifact_type: pipeline_status
story: US-4.2
version: 6
status: DRAFT
created_at: "2026-09-05T18:00:00Z"
updated_at: "2026-09-05T23:55:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
supersedes: docs/catalog/US-4.2-pipeline-status.md (v5)
---

## Revision Note (v6)

T5/T6's blocker is resolved. Per the user's `HUMAN_REDIRECTED` direction
(`docs/workflow/history.jsonl`, 2026-09-05T23:45:00Z), `test-writer` fixed
both named defects in `tests/integration/modules/support/test_support_router.py`:
(1) added `SET LOCAL app.actor_kind = 'agent'` before the internal-visibility
`_seed_reply()` call in
`test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`;
(2) added an optional `created_at` parameter to `_seed_reply()` and updated
`test_get_ticket_detail_paginates_reply_thread_oldest_first` to seed three
distinct, sequential `created_at` values, removing the transaction-frozen-
`now()`/random-UUID-tiebreak flakiness. Both tests verified deterministic
across 3 repeated runs. Full support suite (unit+integration): 125/125
passed, 93.90% coverage. Full repository suite: **688/688 passed.**
`ruff`/`ruff format`/`mypy --strict`/`lint-imports` all clean. **T5 and T6
are both now fully PASS.** `IMPLEMENTATION`'s four sub-steps (T1-T4 already
PASS, T5/T6 now PASS) are complete; the stage advances to `QUALITY_GATE`
(`stage-map.yaml` `IMPLEMENTATION.next`) per `docs/workflow/workflow-state.yaml`.

## Revision Note (v5)

`service-and-router-builder` ran T5/T6 per `task_breakdown` v2. Both are code-
complete and independently verified: `ruff`/`ruff format`/`mypy --strict`/
`lint-imports` all clean; OpenAPI render matches `US-4.2-openapi.yaml` v3
exactly (path parameter renamed `{ticket_id}` → `{id}` to match the contract
literally); all 61 support unit tests plus 63 of 64 support integration tests
pass; the full non-support integration suite (261 tests) passes unchanged
(Risk 7 still holds under `app_runtime`); combined unit+integration coverage
for `app/modules/support/` is 93.90% (service.py 95%, router.py 100%,
dependencies.py 100%), clear of the 85%/90% floors.

**BLOCKED**, not on a T5/T6 defect — mirrors the T3/T4 precedent exactly (a
test-file gap, no `IMPLEMENTATION.loop_back` key fits it): two independent,
pre-existing defects in `tests/integration/modules/support/test_support_router.py`,
both owned by `TEST_WRITING`, not `service-and-router-builder`:

1. `test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`
   fails with `InsufficientPrivilegeError` on the internal-visibility
   `_seed_reply()` insert — the exact same `SET LOCAL app.actor_kind = 'agent'`
   gap already fixed in three *other* tests by the 2026-09-05T22:30:00Z
   `HUMAN_REDIRECTED` transition, but this fourth occurrence was missed by
   that pass. Positive evidence the new `get_rls_session`/`TicketReplyService`
   wiring is itself correct: every other test exercising the same
   internal-visibility insert path through the real HTTP route (e.g.
   `test_create_reply_agent_internal_note_is_created_visible_to_agent`)
   passes, which is only possible if `app.actor_kind` is genuinely being set
   to `'agent'` before that insert.
2. `test_get_ticket_detail_paginates_reply_thread_oldest_first` is flaky
   (observed both pass and fail across repeated runs of this session).
   Confirmed root cause via a direct query of the three seeded replies'
   `created_at` values: all three are byte-identical (PostgreSQL's `now()` is
   frozen for the lifetime of one transaction, and this test's `db_session`
   fixture runs the whole test body in one transaction), so
   `list_for_ticket`'s `ORDER BY created_at ASC, id ASC` — correct per
   `US-4.2-db-design.md`'s composite index — ties-break on `id`, a random
   UUID uncorrelated with seed order. `_seed_reply()` takes no `created_at`
   override to force distinct values, unlike US-4.1's own
   `test_list_own_tickets_returns_only_callers_tickets_newest_first`, which
   does. Violates `AGENTS.md` §5 ("no unseeded randomness").

**Decision needed (human):** no `IMPLEMENTATION.loop_back` key
(`partial`/`blocked_by_plan`/`blocked_by_architecture`) fits "a test file
needs a fix." Recommended, mirroring the T4 resolution exactly: route
`IMPLEMENTATION` → `TEST_WRITING` via `HUMAN_REDIRECTED` so `test-writer` can
(1) add `SET LOCAL app.actor_kind = 'agent'` before finding #1's
internal-visibility `_seed_reply()` call, and (2) give `_seed_reply()` (or
this specific test) explicit, distinct `created_at` values for finding #2 —
then re-enter `IMPLEMENTATION` at T5/T6 re-verification (expected to need no
code changes, only a re-run of the two named tests, exactly as T4's
re-verification needed no new migration).

See T5/T6 section below for full detail, file list, and non-blocking
findings.

## Revision Note (v4)

T4's blocker is resolved. Per the user's `HUMAN_REDIRECTED` direction
(`docs/workflow/history.jsonl`, 2026-09-05T22:30:00Z), `test-writer` fixed
`test_support_router.py`'s `_seed_reply()` gap in the three named RLS tests
(`SET LOCAL app.actor_kind = 'agent'` before each internal-visibility seed;
`test_no_actor_kind_set_defaults_to_hiding_internal_reply` additionally
`RESET`s it before its Act phase, since `SET LOCAL` persists for the rest of
the transaction otherwise). All three now pass — verified individually,
together, against the full `support` suite (35 failed/29 passed, exactly the
three moved from fail to pass, no other regression), and against the full
non-`support` integration suite (261/261 unchanged). **T3 and T4 are both
now fully resolved: RLS is proven genuinely enforced under the non-superuser
`app_runtime` role, end to end.** `IMPLEMENTATION` resumes at **T5**
(`service-and-router-builder`) per `task_breakdown` v2.

## Revision Note (v3)

T4 (migration-manager) ran per `task_breakdown` v2: `scripts/db/provision_runtime_role.sql`
written and `tests/conftest.py`'s `_database` fixture rewired to serve requests
through the new non-superuser `app_runtime` role, matching `implementation_plan`
v2 Architectural Change #12. Both artifacts are complete and independently
verified — idempotency (ran the provisioning script twice against a fresh DB,
zero errors) and GRANT completeness (Risk 7: the full existing integration
suite outside `support`, 261 tests, plus 26 of `support`'s own non-reply
tests, pass unchanged against `app_runtime`). **BLOCKED**, not on a T4 defect:
the two named re-verification tests
(`test_internal_reply_hidden_from_customer_context_by_rls_alone`,
`test_no_actor_kind_set_defaults_to_hiding_internal_reply`) — and a third,
previously-"passing" one (`test_agent_context_sees_internal_reply_via_rls`) —
now fail because `tests/integration/modules/support/test_support_router.py`'s
`_seed_reply()` helper (a `test-writer`/`TEST_WRITING`-owned artifact, outside
T4's file scope) inserts internal-visibility replies through the shared
`db_session` with no `SET LOCAL app.actor_kind = 'agent'` first. Under the
previous superuser `db_session` this was silently masked (RLS bypass covers
`INSERT`'s `WITH CHECK` too, not just `SELECT`); under `app_runtime` it is
correctly rejected by `ticket_replies_write`'s `WITH CHECK` clause — direct
proof RLS is now genuinely enforced, and direct proof of `implementation_plan`
v2 Risk 1's warning that the prior "pass" was an artifact of the bypass, not
real policy enforcement. See T4 section below for full detail.

## Revision Note (v2)

Corrects v1's Decision-needed framing. `stage-map.yaml`
`IMPLEMENTATION.loop_back.blocked_by_architecture` **does** mechanically reach
`ARCHITECTURE_PLANNING` — v1's claim that "neither [DB_DESIGN nor
ARCHITECTURE_PLANNING] is a valid loop_back key" was wrong about the
ARCHITECTURE_PLANNING half; only `DB_DESIGN` has no loop_back key from
`IMPLEMENTATION`. Presented with the corrected framing, the human
(`sbruhov@gmail.com`, 2026-09-05T18:30:00Z) chose to route via
`blocked_by_architecture` to `ARCHITECTURE_PLANNING` rather than revise
`db_design`/`entity_model` in place — see
`docs/workflow/workflow-state.yaml`'s `HUMAN_REDIRECTED` note and
`docs/workflow/history.jsonl` for the recorded transition. T1/T2 remain PASS;
T3's migration file stays on disk pending re-verification once the RLS
mechanism decision (non-superuser runtime role) is designed.

# IMPLEMENTATION Pipeline Status — US-4.2 (Ticket Replies)

Tracks the four `IMPLEMENTATION` sub-steps (`docs/workflow/stage-map.yaml`,
`docs/plans/US-4.2-task-breakdown.md`), run in the order fixed by `AGENTS.md`
section 3 and refined by the task breakdown: T1/T2 parallel-eligible, T3 after
T2, T4/T5 after T1 and T3.

| Task | Skill | Verdict | Artifacts |
|---|---|---|---|
| T1 | schema-builder | **PASS** | `app/modules/support/schemas.py` (`CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead`) |
| T2 | data-layer-builder | **PASS** | `app/modules/support/models.py` (`TicketReply`, `Ticket.first_response_at`, `Attachment.ticket_reply_id`), `app/modules/support/repository.py` (`TicketRepository.update`, `AttachmentRepository.bind_to_reply`, `TicketReplyRepository`), `app/modules/support/cache.py` (`TicketReplyRateLimitCache`), `app/core/cache_keys.py` (`ticket_reply_rate_key`) |
| T3 | migration-manager | **PASS** | `migrations/versions/9132a68b73c8_add_ticket_replies.py` (written, proven, and RLS enforcement now re-verified genuine end to end via T4) |
| T4 | migration-manager | **PASS** | `scripts/db/provision_runtime_role.sql` (new), `tests/conftest.py` (`_database` fixture) — resolved via `TEST_WRITING` HUMAN_REDIRECTED fix, see below |
| T5 | service-and-router-builder (service) | **PASS** | `app/modules/support/service.py` (`TicketReplyService`), `app/modules/support/exceptions.py` (`TicketNotFoundError`, `InsufficientPermissionError`, `TicketClosedError`, `TicketReplyRateLimitError`), `app/core/email.py`, `app/core/config.py`, `.env.example`, `app/main.py` |
| T6 | service-and-router-builder (router) | **PASS** | `app/modules/support/router.py` (two new routes), `app/modules/support/dependencies.py` (`get_rls_session`, `resolve_actor_kind`, `TicketReplyServiceDep`) — resolved via `TEST_WRITING` `HUMAN_REDIRECTED` fix, see below |
| T7 | gate-enforcer (QUALITY_GATE, not part of this composite skill) | not started | — |

## T1 — schema-builder (PASS)

`CreateReplyRequest`/`ReplyRead`/`ReplyThreadPage`/`TicketDetailRead` added to
`app/modules/support/schemas.py`, matching `docs/designs/api/US-4.2-openapi.yaml`
v3 exactly. `ruff check`/`format` clean, `mypy --strict` clean. All 13 tests in
`tests/unit/modules/support/test_support_schemas.py` pass.

## T2 — data-layer-builder (PASS)

`TicketReply` model (CHECK constraint, composite `(ticket_id, created_at, id)`
index), additive `Ticket.first_response_at`, additive
`Attachment.ticket_reply_id` (indexed); `TicketRepository.update()`,
`AttachmentRepository.bind_to_reply()`, new `TicketReplyRepository`
(`create`/`list_for_ticket`/`commit`); `TicketReplyRateLimitCache` (mirrors
`TicketCreationRateLimitCache`'s pipelined `INCR`+`EXPIRE` shape) and
`ticket_reply_rate_key` in `app/core/cache_keys.py`. `ruff`/`mypy --strict`
clean on all four files. No `session.query()`, no `relationship()`. Confirmed
`migrations/env.py` already imports `app.modules.support.models` wholesale —
zero-diff registration, as `docs/plans/US-4.2-task-breakdown.md` T3 predicted.

## T3 — migration-manager (PASS — see Resolution at the end of the T4 section below)

Revision `9132a68b73c8_add_ticket_replies.py` generated, hand-edited to strip
autogenerate's unrelated audit-log/trgm-index noise (same precedent as
`37c89e98a86f`/`2c77dd65027b`), guarded (`sa.inspect(op.get_bind())`) on every
`add_column`/`create_foreign_key`/`drop_constraint`/`drop_column`, and the
hand-written RLS DDL (`ENABLE`/`FORCE ROW LEVEL SECURITY` + two `CREATE
POLICY` statements) guarded via a `pg_policies` existence check. DR-2 (carried
finding) resolved: plain `CREATE INDEX` for `attachments.ticket_reply_id`, not
`CONCURRENTLY` — no production write path populates `attachments` yet (US-4.1
shipped binding without an upload endpoint).

**Real `upgrade → downgrade → upgrade` cycle executed and passed** (captured
output: three clean `alembic` runs, no errors). The migration DDL itself is
correct and requires no further changes.

**Blocker — not a migration defect:** TR-AC3's RLS guarantee ("holds even if
the application layer forgets to filter") does not hold in this deployment.
The single configured database role (`postgres`, from `DATABASE_URL` in
`.env.example` / `app/core/config.py`) has `rolsuper=True`, `rolbypassrls=True`
(confirmed via `SELECT rolname, rolsuper, rolbypassrls FROM pg_roles`).
PostgreSQL superusers unconditionally bypass row security — `FORCE ROW LEVEL
SECURITY` only closes the table-owner exemption, never the superuser one, and
no table-level setting can override it.

Proven two ways:
1. The story's own already-written integration tests fail against this role:
   `tests/integration/modules/support/test_support_router.py::test_internal_reply_hidden_from_customer_context_by_rls_alone`
   and `::test_no_actor_kind_set_defaults_to_hiding_internal_reply` both FAIL
   (a customer/no-GUC session sees the internal-visibility row). Only
   `::test_agent_context_sees_internal_reply_via_rls` passes, and it can't
   distinguish "policy worked" from "RLS bypassed" since an agent is
   supposed to see everything anyway.
2. A scratch `NOSUPERUSER`/`NOBYPASSRLS` role (created, exercised, and
   dropped within this session — no trace left in the database) proves the
   `CREATE POLICY` predicates themselves are correct: under a real
   non-superuser role, customer-context sees only `'public'`, agent-context
   sees both, and a session with no `app.actor_kind` GUC set correctly
   fails closed to `'public'` only.

`docs/designs/database/US-4.2-db-design.md` v3 and `-entity-model.md` v3 are
wrong on disk about this: their RLS reasoning analyzes the table-owner
exemption in detail but never considers that the single configured role might
also be a superuser — a claim now falsified for this codebase's actual
`DATABASE_URL`.

**Not attempted:** `ALTER ROLE postgres NOSUPERUSER` (destructive to shared
cluster state, breaks every other migration/service running as that role);
provisioning a dedicated non-superuser runtime role (a second role,
`.env.example`, `app/core/config.py`, `app/db/session.py`, docker/CI
provisioning — an architectural change outside this skill's scope per
`AGENTS.md` section 7.8, and outside `DB_DESIGN`'s scope too).

**State left behind:** revision `9132a68b73c8` is applied to the local
database and present in the working tree, uncommitted. The local dev database
is currently at this head. Suite red-state character changed: before T3, the
support test files failed at collection (`ImportError`, the expected
pre-`IMPLEMENTATION` TDD state `test-writer` documented); the two RLS tests
above now fail on assertion instead — a later `QUALITY_GATE` run would see
these as implementation bugs without this note.

**Decision needed (human) — RESOLVED (2026-09-05T18:30:00Z, `sbruhov@gmail.com`):**
routed to `ARCHITECTURE_PLANNING` via the existing
`IMPLEMENTATION.loop_back.blocked_by_architecture` key in
`docs/workflow/stage-map.yaml` — `docs/plans/US-4.2-implementation-plan.md`
Architectural Change #1 already owns the RLS mechanism decision, and
provisioning a dedicated non-superuser runtime role is itself an
architectural change. `DB_DESIGN` (the alternative of revising v3's RLS claim
in place) was not chosen; it also has no `loop_back` key from
`IMPLEMENTATION` in `docs/workflow/stage-map.yaml` (only `partial` /
`blocked_by_plan` / `blocked_by_architecture` exist). See
`docs/workflow/history.jsonl` (`HUMAN_REDIRECTED`, attempt 2) and
`docs/workflow/workflow-state.yaml` for the recorded transition.

## T4 — migration-manager (PASS — Resolution at the end of this section)

Per `task_breakdown` v2 T4 row, following `ARCHITECTURE_PLANNING`'s attempt-2
Architectural Change #12.

**Delivered and verified:**

- `scripts/db/provision_runtime_role.sql` (new): idempotent `CREATE ROLE
  app_runtime WITH LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE`
  (guarded via `DO $$ ... EXCEPTION WHEN duplicate_object THEN NULL; END $$;`,
  Postgres has no `CREATE ROLE IF NOT EXISTS`); `GRANT CONNECT` (dynamic, via
  `current_database()` — no hard-coded database name, so the same script runs
  unchanged in production and against `tests/conftest.py`'s ephemeral
  `testcontainers` database) and `USAGE ON SCHEMA public`; blanket
  `SELECT, INSERT, UPDATE, DELETE ON ALL TABLES`/`USAGE, SELECT ON ALL
  SEQUENCES`; `ALTER DEFAULT PRIVILEGES` (no `FOR ROLE` clause — defaults to
  "objects created by the executing role," i.e. the owner role that also runs
  every migration, so future migration-created tables are covered without
  hard-coding an owner-role name that differs per environment). Password is
  the obvious placeholder `CHANGE_ME_IN_PRODUCTION` (same "dev-only, real
  deployments must override" discipline as `Settings.jwt_secret_key`) — flagged
  by `detect-secrets`' Secret Keyword plugin as expected, audited and added to
  `.secrets.baseline` (same handling this repo already uses for
  `DATABASE_URL`'s `postgres:postgres` default and `Settings.database_url`).
- `tests/conftest.py`'s `_database` fixture: after `command.upgrade(alembic_cfg,
  "head")`, runs the provisioning script once (own statement splitter,
  `_split_sql_statements`, that treats `$$ ... $$` blocks as atomic so
  semicolons inside `DO` blocks aren't mistaken for statement boundaries)
  against the owner-role engine, disposes it, then builds a second engine from
  `_runtime_database_url()` (the same connection substituting `app_runtime`'s
  credentials via `sqlalchemy.engine.make_url(...).set(...)`) and assigns
  *that* — not the owner-role one — to `app.state.db_engine`/`db_session_factory`,
  matching what `app/main.py`'s `lifespan` will do in a real deployment.
  `cleanup_users` needed no change (`app_runtime` has `DELETE` too, as the
  plan anticipated).
- **Idempotency** (task_breakdown T4 verification #1): ran the provisioning
  script twice against the same fresh database — zero errors both times,
  confirmed connecting as `app_runtime` afterward.
- **GRANT completeness / Risk 7** (task_breakdown T4 verification #3): the
  full existing integration suite outside `support` — 261 tests across
  `users`/`roles`/`admin_users`/`audit`/`profile`/`account`/
  `email_verification` — passes unchanged against `app_runtime`, plus 26 of
  `support`'s own non-reply/non-RLS tests (ticket creation/listing, unaffected
  by this change). This is the actual proof the `GRANT` list is complete, not
  a review of the SQL by inspection, exactly as Risk 7 required.

**Blocker (task_breakdown T4 verification #2 — not a T4 defect):**
`test_internal_reply_hidden_from_customer_context_by_rls_alone` and
`test_no_actor_kind_set_defaults_to_hiding_internal_reply` still fail — and so
now does the previously-"passing" `test_agent_context_sees_internal_reply_via_rls`.
Root cause, confirmed by reading both the failing traceback and
`migrations/versions/9132a68b73c8_add_ticket_replies.py`'s own policy SQL: the
`ticket_replies_write` policy's `WITH CHECK (visibility = 'public' OR
current_setting('app.actor_kind', true) = 'agent')` now genuinely fires.
`test_support_router.py`'s `_seed_reply()` helper (owned by `test-writer` /
`TEST_WRITING`, not in T4's file scope — `task_breakdown` v2 T4 row lists only
`scripts/db/provision_runtime_role.sql` and `tests/conftest.py`) inserts
internal-visibility replies through the shared `db_session` fixture with no
`SET LOCAL app.actor_kind = 'agent'` first. Under the previous superuser
`db_session` this insert silently succeeded (RLS bypass covers `INSERT`'s
`WITH CHECK`, not only `SELECT`'s `USING`) — the prior "pass" on
`test_agent_context_sees_internal_reply_via_rls` was an artifact of that
bypass, not genuine policy enforcement, exactly what `implementation_plan` v2
Risk 1 warned about. This is now direct, positive proof RLS is genuinely
enforced under `app_runtime` — the same INSERT that used to slip through is
now correctly rejected.

**Fix is mechanical and narrowly scoped**, but outside migration-manager's
file ownership: in each of the three RLS tests' Arrange blocks, run
`await db_session.execute(text("SET LOCAL app.actor_kind = 'agent'"))` before
the `_seed_reply(..., author_kind="agent", visibility="internal", ...)`
call(s), before the Act phase's own `SET LOCAL`. This is `test-writer`
content, not migration-manager's.

**Not in T4's blocker:** the other 38 `support` test failures observed in a
full-file run are the expected pre-`T5`/`T6` red state (`POST
.../replies`/`GET /support/tickets/{id}` routes don't exist until
`service-and-router-builder` runs — 404s, not RLS-related).

**Decision needed (human):** no `IMPLEMENTATION.loop_back` key in
`docs/workflow/stage-map.yaml` fits "a test file needs a fix" — mirrors T3's
own precedent above exactly (`BLOCKED`, no loop_back key, human routing
decision required). No new Alembic revision created; `migrations/env.py`
untouched; no existing revision file edited.

**Decision needed (human) — RESOLVED (2026-09-05T22:30:00Z, `sbruhov@gmail.com`):**
routed to `TEST_WRITING` via `HUMAN_REDIRECTED` (no `IMPLEMENTATION.loop_back`
key fits a test-file fix). `test-writer` added `SET LOCAL app.actor_kind =
'agent'` before each internal-visibility `_seed_reply()` call in the three
named tests, plus a `RESET app.actor_kind` after seeding in
`test_no_actor_kind_set_defaults_to_hiding_internal_reply` (its Act phase
requires no GUC set at all, and `SET LOCAL` otherwise persists for the rest
of the transaction). Verified: all three tests pass; full `support` suite
35 failed/29 passed (was 38/26 — exactly these three moved to passing, no
other regression, remaining 35 are the expected pre-`T5`/`T6` red state);
full non-`support` integration suite 261/261 unchanged; `ruff`/`mypy --strict`
clean. **T4 is PASS.** `IMPLEMENTATION` resumes at T5.

## T5/T6 — service-and-router-builder (PASS — resolution at the end of this section)

Per `task_breakdown` v2 T5 (service) and T6 (router) rows, both invoked in one
`service-and-router-builder` pass since they are the same skill/one code
review pass end to end.

**Delivered:**

- `app/modules/support/service.py`: new `TicketReplyService` (`create_reply`,
  `get_ticket_detail`), `TicketReplyRepositoryProtocol`,
  `TicketReplyRateLimitCacheProtocol`; extended `TicketRepositoryProtocol`
  (`update`) and `AttachmentRepositoryProtocol` (`bind_to_reply`). Status-
  gating and `first_response_at` stamping implement `implementation_plan` v2
  §4's table exactly, including the deliberate no-op branch (API_DESIGN Open
  Question #1). FR-5's `403` is raised from the service's own check, never a
  caught `IntegrityError` (verified: `test_create_reply_customer_internal_
  raises_from_service_not_integrity` asserts `reply_repo.created == []`).
- `app/modules/support/exceptions.py`: new `TicketNotFoundError` (404),
  module-owned `InsufficientPermissionError` (403, same slug/shape as
  `roles.exceptions.InsufficientPermissionError` but not imported from there —
  `AccountDeactivatedError`'s precedent), `TicketClosedError` (409,
  `ticket-closed` — new slug), `TicketReplyRateLimitError` (429 +
  `Retry-After`).
- `app/core/email.py`: `EmailSender` Protocol gained
  `send_ticket_reply_notification`/`send_ticket_reply_queue_notification`;
  `LoggingEmailSender` implements both (log-only, never logging the
  requester's `to` address, consistent with every other method on this
  class; the queue address is not PII so it is logged).
- `app/core/config.py`: new `support_queue_email` (OD-2's example default) and
  `runtime_database_url` (Architectural Change #12, dev-only default
  mirroring `jwt_secret_key`) fields. `.env.example` gained the matching
  `SUPPORT_QUEUE_EMAIL`/`RUNTIME_DATABASE_URL` entries.
- `app/main.py`: the single Architectural Change #12 line —
  `create_engine_and_sessionmaker(settings.database_url)` →
  `create_engine_and_sessionmaker(settings.runtime_database_url)` in
  `lifespan()`. Nothing else in the file changed (grep-confirmed).
- `app/modules/support/dependencies.py`: new `get_rls_session` (module-scoped
  wrapper around `get_db_session`, per Architectural Change #2 — `SET LOCAL`-
  equivalent `set_config(..., true)` calls with bound parameters, never
  string-interpolated); `resolve_actor_kind` (the single derivation point,
  reused by both `get_rls_session` and `router.py`, per Architectural Change
  #2's explicit "reuse `reject_agent_queue_access`'s existing check" note);
  `get_ticket_reply_service`/`TicketReplyServiceDep`.
- `app/modules/support/router.py`: `POST /support/tickets/{id}/replies` and
  `GET /support/tickets/{id}`, both declaring `response_model`/`status_code`;
  `limit: Annotated[int, Query(ge=1, le=100)] = 50` on the `GET` route. Path
  parameter named `id` (not `ticket_id`) to match `US-4.2-openapi.yaml` v3's
  declared parameter name exactly — verified via `app.openapi()`, which
  renders `/api/v1/support/tickets/{id}/replies` and
  `/api/v1/support/tickets/{id}` character-for-character.
- **Deliberate deviation from `task_breakdown`'s literal text (non-blocking,
  see finding below):** `require_scope("tickets:write")`/
  `require_scope("tickets:read")` are NOT used to gate these two routes —
  `require_scope`'s `403` would violate FR-4's explicit "never `403`, always
  `404`" enumeration-prevention rule. `resolve_actor_kind` (the actual
  mechanism `implementation_plan` v2 §2 describes) is wired instead.

**Verified:**

- `ruff check .` / `ruff format --check .`: clean across the whole repo.
- `mypy app tests`: `Success: no issues found in 146 source files`.
- `lint-imports`: `Contracts: 6 kept, 0 broken` (router → dependencies only;
  service → no `fastapi`/`starlette`/`HTTPException`).
- `pre-commit run detect-secrets`: the new `RUNTIME_DATABASE_URL`/
  `runtime_database_url` credentialed placeholder is flagged as expected
  (Basic Auth Credentials) — audited into `.secrets.baseline`, same handling
  T4 already established for `provision_runtime_role.sql`'s password.
- Unit: `tests/unit/` full suite, 363 passed (support module: 61/61).
- Integration: `tests/integration/` full suite, 324 passed / 1 failed
  (support module: 63/64 passed) — the one failure is TEST_WRITING-owned,
  see Decision needed below, not a T5/T6 defect. Full non-support suite
  (261 tests) passes unchanged — Risk 7 still holds under `app_runtime`.
- Coverage (`app/modules/support/`, unit+integration combined): 93.90% total;
  `service.py` 95%, `router.py` 100%, `dependencies.py` 100% — clear of
  `AGENTS.md` §5/§6's 85%/90% floors.

**BLOCKED — two TEST_WRITING-owned defects in
`tests/integration/modules/support/test_support_router.py`, not a T5/T6
defect (mirrors the T3/T4 precedent — no `IMPLEMENTATION.loop_back` key fits
"a test file needs a fix"):**

1. `test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`
   fails with `InsufficientPrivilegeError` — its internal-visibility
   `_seed_reply()` call never sets `SET LOCAL app.actor_kind = 'agent'`
   first, the identical gap already fixed in three *other* tests by the
   2026-09-05T22:30:00Z `HUMAN_REDIRECTED` transition; this fourth
   occurrence was missed by that pass. Positive evidence the new
   `get_rls_session`/`TicketReplyService` wiring is itself correct: every
   *other* test exercising the same internal-visibility insert through the
   real HTTP route (e.g.
   `test_create_reply_agent_internal_note_is_created_visible_to_agent`)
   passes — only possible if `app.actor_kind` is genuinely `'agent'` before
   that insert.
2. `test_get_ticket_detail_paginates_reply_thread_oldest_first` is flaky
   (observed both passing and failing across repeated runs this session).
   Root cause confirmed directly (queried the three seeded replies'
   `created_at` mid-test): all three are byte-identical — PostgreSQL's
   `now()` is frozen for the lifetime of one transaction, and this test's
   whole body runs in one transaction (`db_session`'s savepoint fixture) —
   so `list_for_ticket`'s `ORDER BY created_at ASC, id ASC` (correct per
   `US-4.2-db-design.md`'s composite index) ties-break on `id`, a random
   UUID uncorrelated with seed order. `_seed_reply()` takes no `created_at`
   override to force distinct values, unlike US-4.1's own
   `test_list_own_tickets_returns_only_callers_tickets_newest_first`, which
   does. Violates `AGENTS.md` §5's determinism requirement.

**Decision needed (human) — RESOLVED (2026-09-05T23:45:00Z, `sbruhov@gmail.com`):**
routed to `TEST_WRITING` via `HUMAN_REDIRECTED`. `test-writer` applied both
named fixes exactly: (1) `SET LOCAL app.actor_kind = 'agent'` added before
the internal-visibility `_seed_reply()` call in
`test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent`
(no `RESET` needed — the test's Act phase runs through real HTTP requests,
and `get_rls_session` sets its own fresh `app.actor_kind` per request from
the caller's own token, overwriting whatever the seed left); (2) `_seed_reply()`
gained an optional `created_at` parameter, and
`test_get_ticket_detail_paginates_reply_thread_oldest_first` now seeds three
replies with `base_time + timedelta(seconds=i)`, removing the tie on
PostgreSQL's transaction-frozen `now()`. Verified: both tests pass
individually and together, deterministic across 3 repeated runs; full
support suite (unit+integration) 125/125 passed, 93.90% coverage;
**full repository suite 688/688 passed**; `ruff`/`ruff format`/
`mypy --strict`/`lint-imports` all clean. **T5 and T6 are both PASS.**
`IMPLEMENTATION`'s four sub-steps are now all complete — advances to
`QUALITY_GATE`.

## Non-blocking findings (T5/T6)

- `TicketReplyService.__init__`'s `user_service` argument is optional
  (default `None`, unlike `TicketService`'s required collaborator of the same
  shape) with a `str(requester_id)` fallback in `_resolve_requester_email` —
  diverges from `TicketService`'s "no email on file → skip dispatch"
  precedent. Forced by `test-writer`'s own fixed `TicketReplyService`
  constructor shape (`_make_reply_service`, 5 positional args, no
  `user_service`) combined with `test_create_reply_agent_notifies_requester`
  asserting the notification fires unconditionally. `dependencies.py` always
  wires the real `UserServiceDep` in production, so the fallback is
  unreached there (`requester_id` is a real FK). Flagged for
  reconciliation-reviewer awareness, not requesting a change.
- Shared `app/core/email.py` `EmailSender` Protocol gaining two new abstract
  methods broke `mypy --strict` conformance for four *other* modules'
  hand-written fake email senders (structural `Protocol` typing requires
  every member). Patched
  `tests/unit/modules/{profile,email_verification,admin_users,users}/
  test_*_service.py` with two matching no-op stub methods each — the exact
  same mechanical ripple this codebase's own precedent required when
  `send_ticket_created_email` was added for US-4.1. No test logic or
  assertion changed in any of the four files.
