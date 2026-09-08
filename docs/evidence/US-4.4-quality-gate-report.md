---
artifact_type: quality_gate_report
story: US-4.4
version: 2
status: DRAFT
created_at: "2026-09-07T18:27:18Z"
updated_at: "2026-09-07T21:05:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
supersedes: docs/evidence/US-4.4-quality-gate-report.md (v1)
---

# Quality Gate Report — US-4.4 (Agent Ticket Queue & Assignment) — v2

**Full gate re-run from scratch**, not a partial recheck. Track: backend.
Branch: `docs/epic5-frontend-followup-stories`. Docker `customer_portal_pg` /
`customer_portal_valkey` confirmed running (`docker ps`); integration tests
and the migration cycle ran against real PostgreSQL, not mocked.

**Context:** v1 of this report (superseded) returned `CHANGES_REQUIRED`
(`changes_required_tests`) for 9 pytest failures + 9 mypy errors, all traced
to four defects confined to `tests/unit/modules/support/test_support_service.py`
and `tests/integration/modules/support/test_support_router.py`, with zero
production-code defect in `app/modules/support/`. `TEST_WRITING` (attempt 2)
fixed all four in the test files only; `git status` confirms no `app/` or
`migrations/` file changed since. This run independently re-verifies that
fix and re-checks the entire gate, not just the four named defects.

**Harness preconditions confirmed:** `docs/plans/US-4.4-implementation-plan.md`
and `docs/plans/US-4.4-task-breakdown.md` are both `version: 1, status: APPROVED`
(matches the versions recorded in this report's `inputs`); `docs/tests/US-4.4-ac-test-matrix.md`
is `version: 1, status: DRAFT` (matches recorded input; not `SUPERSEDED`/
`ARCHIVED`). `docs/workflow/active-story.yaml` (`active_story: US-4.4`) and
`docs/workflow/workflow-state.yaml` (`story: US-4.4`, `current_stage: QUALITY_GATE`)
agree on the active story and stage.

`git status --porcelain` confirms the diff scope for this story: 9 files
under `app/modules/support/` unchanged from v1 (`dependencies.py`,
`exceptions.py`, `models.py`, `repository.py`, `router.py`, `schemas.py`,
`service.py`), 2 test files (`tests/unit/modules/support/test_support_service.py`,
`tests/integration/modules/support/test_support_router.py`), and one new
migration (`migrations/versions/55d8d34a9753_add_ticket_assignee_column.py`).

## Part A — Mechanical

### 1. `pre-commit run --all-files`
**Result:** PASS (all 11 hooks)
```
ruff (lint).............................................................................Passed
ruff (format)...........................................................................Passed
mypy (strict)...........................................................................Passed
import-linter (layering contracts)......................................................Passed
unit tests..............................................................................Passed
no unittest.mock in integration tests...................................................Passed
eslint (frontend).......................................................................Passed
prettier --check (frontend).............................................................Passed
tsc --noEmit (frontend).................................................................Passed
no vi.mock() of the unit under test in frontend integration tests.......................Passed
Detect secrets..........................................................................Passed
```
(Frontend hooks ran as no-ops — no `frontend/` files in this diff.)

### 2. `mypy app tests`
**Result:** PASS
```
Success: no issues found in 147 source files
```
All 9 previously-reported errors (all in `test_support_service.py`) are gone;
zero errors anywhere in `app/` or `tests/`.

### 3. `lint-imports`
**Result:** PASS
```
=============
Import Linter
=============


---------
Contracts
---------

Analyzed 124 files, 436 dependencies.
-------------------------------------

Module layers: router -> dependencies -> service -> repository|cache ->
models|schemas KEPT
Top-level layers: main -> api -> modules -> db -> core KEPT
Routers must not touch persistence infrastructure KEPT
Services must not import the web framework or raw infrastructure clients KEPT
Repository stays free of web framework KEPT
Only core.config may read the environment KEPT

Contracts: 6 kept, 0 broken.
```
`git diff HEAD -- pyproject.toml` produced no output — no new `ignore_imports`
or `exhaustive = false` since the last commit.

### 4. `pytest --cov=app --cov-report=term-missing --cov-fail-under=85`
**Result:** PASS (run twice for reproducibility)

First run:
```
FAILED tests/integration/modules/audit/test_audit_router.py::test_list_audit_logs_historical_rows_null_pad_unavailable_fields
1 failed, 835 passed in 103.22s (0:01:43)
Required test coverage of 85% reached. Total coverage: 96.39%
```
Second, immediate re-run (no code changes in between):
```
836 passed in 106.42s (0:01:46)
Required test coverage of 85% reached. Total coverage: 96.39%
```
The single failure in the first run
(`test_list_audit_logs_historical_rows_null_pad_unavailable_fields`) is in
`tests/integration/modules/audit/`, a file not part of this story's diff
(`git diff HEAD -- tests/integration/modules/audit/test_audit_router.py`
produces no output; last commit touching it is `6af00401` dated
2026-09-03, before this story existed). It passed standalone
(`pytest tests/integration/modules/audit/test_audit_router.py::<name>` — 1
passed in 5.88s) and passed together with the rest of its own file
(`pytest tests/integration/modules/audit` — 26 passed in 6.75s), and passed
on the full-suite re-run. Both full runs used the identical file set and
pytest collection order with near-identical wall time (103.22s vs 106.42s;
run 1 failed, run 2 passed) — that rules out ordering/isolation as the
cause, so this is intermittent, non-reproducible timing nondeterminism in
the `audit` module's own test, not order-dependence and not a US-4.4 defect.
Reported as a non-blocking finding (also recorded in the Result Envelope's
`non_blocking_findings`), not silently ignored, and not used to justify
skipping or excluding anything.

Isolated confirming run of just the two US-4.4 test files (real captured
output — all 9 previously-failing tests are in here):
```
$ uv run --no-sync pytest tests/unit/modules/support/test_support_service.py tests/integration/modules/support/test_support_router.py -q
239 passed in 28.40s
```
Also confirmed via the pre-commit `unit-tests` hook re-run standalone:
```
$ uv run --no-sync python -m pytest tests/unit -m unit -q
431 passed in 25.61s
```

Per-module coverage for touched files, compared against v1's own numbers (no
touched module lost coverage — AGENTS.md §6 item 4's second half):
| Module | v1 | v2 |
|---|---|---|
| `app/modules/support/models.py` | 100% | 100% |
| `repository.py` | 93% | 93% |
| `service.py` | 94% | 95% |
| `router.py` | 100% | 100% |
| `schemas.py` | 100% | 100% |
| `dependencies.py` | 100% | 100% |
| `exceptions.py` | 100% | 100% |
| `cache.py` (unchanged in this diff) | 93% | 93% |
| **Total repo coverage** | 96.34% | 96.39% |

Every touched module held or gained coverage; total repo coverage rose
0.05pp. Floor is 85%; actual is 96.39%.

### 5. Migration cycle (`upgrade → downgrade → upgrade`)
**Result:** PASS — independently re-run this stage
```
$ alembic current
55d8d34a9753 (head)

$ alembic downgrade -1
INFO  [alembic.runtime.migration] Running downgrade 55d8d34a9753 -> 242e0dba5ba2, add_ticket_assignee_column

$ docker exec customer_portal_pg psql -U postgres -d customer_portal -c "\d tickets" | grep -i assignee
(no output — assignee_id column, FK, and all three new indexes genuinely absent)

$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 242e0dba5ba2 -> 55d8d34a9753, add_ticket_assignee_column

$ docker exec customer_portal_pg psql -U postgres -d customer_portal -c "\d tickets" | grep -i "assignee\|ix_tickets"
 assignee_id       | uuid                     |           |          |
    "ix_tickets_assignee_id_updated_at_id" btree (assignee_id, updated_at, id)
    "ix_tickets_queue_default_updated_at_id" btree (updated_at, id) WHERE status::text <> 'closed'::text
    "ix_tickets_requester_id" btree (requester_id)
    "ix_tickets_requester_id_created_at_id" btree (requester_id, created_at, id)
    "ix_tickets_resolved_at_pending_autoclose" btree (resolved_at) WHERE status::text = 'resolved'::text
    "ix_tickets_status_updated_at_id" btree (status, updated_at, id)
    "tickets_assignee_id_fkey" FOREIGN KEY (assignee_id) REFERENCES users(id)

$ alembic current
55d8d34a9753 (head)
```
Column/FK/all three indexes cleanly removed on downgrade and cleanly restored
on upgrade; pre-existing indexes (`ix_tickets_requester_id*`,
`ix_tickets_resolved_at_pending_autoclose`) untouched throughout; database
left at head afterward. `migrations/env.py` untouched
(`git diff HEAD -- migrations/env.py` — no output). Migration file
(`55d8d34a9753_add_ticket_assignee_column.py`) read directly: `add_column`/
`create_foreign_key` guarded via `sa.inspect(op.get_bind())` checks (the
Rewriter in `env.py` cannot reach these), index create/drop use
`if_not_exists=True`/`if_exists=True`, the partial-index predicate is the
literal `status != 'closed'` (not an `.in_([...])`) per the DB design's
requirement that PostgreSQL's predicate-implication check must be able to
prove it, and the FK is explicitly named (`tickets_assignee_id_fkey`) so
`downgrade()` can find and drop it deterministically.

## Part B — Runtime rules (AGENTS.md §6.6)

### 6. ORM containment
**Result:** PASS. `router.py` imports only `uuid`, `typing`, `fastapi`,
`app.modules.support.dependencies`, `app.modules.support.schemas`,
`app.modules.users.dependencies` — no `models`/`repository`/`sqlalchemy`.
Public service methods return domain DTOs only:
`list_agent_queue(...) -> AgentTicketListResponse`,
`assign_ticket(...) -> AgentTicketStateRead`,
`unassign_ticket(...) -> AgentTicketStateRead`. The `Ticket | None`/
`TicketListPage | None` return types visible in `service.py` belong to the
internal `TicketRepositoryProtocol` describing the service's repository
dependency, never returned across the router boundary.

### 7. Eager loading
**Result:** N/A. `assignee_id` is a plain scalar FK column
(`Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))`), not a
`relationship()`. `git diff HEAD -- app/modules/support/models.py` confirms
no relationship was added.

### 8. Cache TTL
**Result:** N/A. `git diff --stat HEAD -- app/modules/support/cache.py`
produces no output — zero changes to the module's cache gateway in this diff.

### 9. Cross-module discipline
**Result:** PASS. `service.py`'s only cross-module import is
`app.core.email.EmailSender`/`app.core.exceptions.FieldError`; all
support-domain imports are within-module
(`app.modules.support.{cache,exceptions,models,repository,schemas}`). The new
`support -> roles` wiring (T6) is Protocol-only in `service.py`
(`class RoleServiceProtocol(Protocol)`, with an explicit docstring: "never a
direct `from app.modules.roles.service import RoleService`"); the concrete
`RoleServiceDep` is resolved via DI only in `dependencies.py`
(`from app.modules.roles.dependencies import RoleServiceDep`). Zero
`from app.modules.<other>.router import` anywhere in the diff.

### 10. Banned idioms
**Result:** PASS
```
$ git diff HEAD -- app/modules/support/ | grep -n "^\+" | grep -E "typing\.Any|: Any\b|# type: ignore|cast\(|os\.getenv|os\.environ"
(no output)
```

### 11. Contract & security spot-check (§6.7)
**Result:** PASS
- **Scope-branch isolation (this story's highest-consequence security
  property, NFR "a missing scope must fall through to the customer branch,
  never to an unfiltered list", AQ-AC5/AQ-AC6):** read directly, not
  inferred. `router.py::list_own_tickets` (lines 65-98) branches purely on
  `"tickets:read" in current_user.scopes`: the `True` branch calls
  `service.list_agent_queue(...)` (agent shape, `category`/`assignee_id`
  passed through); the `else` branch calls
  `service.list_own_tickets(requester_id=current_user.user_id, status=status, cursor=cursor, limit=limit)`
  — `category` and `assignee_id` are never passed to the customer branch at
  all, confirming the router itself drops them rather than the service
  silently ignoring them. `service.py::list_own_tickets` (lines 399-429)
  filters exclusively by `requester_id` via `repository.list_for_requester`
  and returns `TicketListResponse(items=[TicketRead.model_validate(...)])`
  — the customer DTO, never `AgentTicketRead`/`AgentTicketListResponse`, so
  the union `response_model=TicketListResponse | AgentTicketListResponse`
  serializes the customer branch strictly as the customer shape (no
  `assignee_id` can leak through it).
- Every changed route declares both `response_model` and `status_code`:
  `GET /tickets` now `response_model=TicketListResponse | AgentTicketListResponse`,
  `POST /{id}/assign` and `DELETE /{id}/assign` both
  `response_model=AgentTicketStateRead, status_code=status.HTTP_200_OK`.
- The one new inbound schema, `AssignTicketRequest`, sets
  `model_config = ConfigDict(extra="forbid")`; its single field
  (`assignee_id: uuid.UUID`) is the action target, not a privilege field.
- No sensitive field was added to any `*Read` schema. Read directly:
  `TicketRead`/`TicketListResponse`/`TicketStateRead` (customer-facing) are
  byte-for-byte unchanged and carry no `assignee_id`; the new
  `AgentTicketRead`/`AgentTicketListResponse`/`AgentTicketStateRead`
  (agent-only) each add only `assignee_id: uuid.UUID | None` to their
  customer-facing counterpart's field list.
- `.env.example`: `git diff --stat HEAD -- .env.example` — no output; correct,
  no new setting was introduced.
- OpenAPI renders: `app.openapi()` succeeds, 32 paths, including
  `/api/v1/support/tickets/{id}/assign` (confirmed via direct
  `app.openapi()['paths']` inspection).

## Verdict

**PASS.**

Every Part A check that runs locally in this environment was actually run
and captured, and all passed: `pre-commit run --all-files` (11/11 hooks),
`mypy app tests` (0 errors, 147 files), `lint-imports` (6/6 contracts kept),
and `pytest --cov=app --cov-fail-under=85` (836/836 passing on the
confirming re-run, 96.39% coverage). The migration
`upgrade → downgrade → upgrade` cycle was independently re-run and proven.
Every Part B runtime-rule item is confirmed-compliant or explicitly N/A with
evidence.

**Non-blocking finding:** one full-suite run hit a single intermittent
failure in
`tests/integration/modules/audit/test_audit_router.py::test_list_audit_logs_historical_rows_null_pad_unavailable_fields`
— a file untouched by this story, last modified 2026-09-03. It passed
standalone, passed with its sibling tests in the same file, and passed on an
immediate full-suite re-run (identical file set and collection order,
near-identical wall time) with no code changes in between — ruling out
ordering/isolation as the cause. This is intermittent, non-reproducible
timing nondeterminism in the `audit` module's own test, not a US-4.4 defect,
and not something `changes_required` (the only loop-back key this stage
defines, routing to `IMPLEMENTATION`) could meaningfully address for a
module this story never touches. Recorded here and in the Result Envelope's
`non_blocking_findings`; not a blocker, and no bypass
(skip/exclude/rerun-only-to-hide) was applied to make it disappear — it is
reported exactly as observed.

No bypass was proposed or used for any check (no `--no-verify`, `SKIP=`,
narrowed mypy/pytest scope, coverage exclude, or lowered
`--cov-fail-under`) — AGENTS.md §7.9.

**loop_back_stage:** null (not applicable — verdict is PASS)

**blocking_issues:** none.
