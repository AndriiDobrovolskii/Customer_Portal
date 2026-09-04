---
artifact_type: quality_gate_report
story: US-4.1
version: 5
status: ARCHIVED
created_at: "2026-09-04T00:10:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.1-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
supersedes: docs/evidence/US-4.1-quality-gate-report.md (v4)
---

# Gate Report — US-4.1 (attempt 5)

**Date:** 2026-09-04 · **Branch/commit:** chore/harness-sync-v2@d5c9ac5 (working tree)

Re-run against the now-complete test suite: `RECONCILIATION` v1
(`CHANGES_REQUIRED`, `test_gap`) routed to `TEST_WRITING` attempt 5
(test-writer, PASS, v5), which added
`tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests against
`AttachmentRepository.find_unbound_older_than`/`.purge`), closing ST-AC7's last
untested clause. No application code changed since v4's run — only a new test
file. `IMPLEMENTATION` (attempt 1) was re-validated by `story-orchestrator` (no
builder sub-step re-invoked) before routing here.

## Part A — Mechanical

### 1. `pre-commit run --all-files`
**Result:** Pass — all 7 hooks green, no auto-fix needed.

```
ruff (lint)..............................................................Passed
ruff (format)............................................................Passed
mypy (strict)............................................................Passed
import-linter (layering contracts).......................................Passed
unit tests...............................................................Passed
no unittest.mock in integration tests....................................Passed
Detect secrets...........................................................Passed
```

### 2. `mypy app tests`
**Result:** Pass — 0 errors.

```
Success: no issues found in 145 source files
```

### 3. `lint-imports`
**Result:** Pass — 6 contracts kept, 0 broken. `git diff -- pyproject.toml`
empty — no new `ignore_imports` or `exhaustive = false`.

```
Analyzed 124 files, 428 dependencies.
Module layers: router -> dependencies -> service -> repository|cache -> models|schemas KEPT
Top-level layers: main -> api -> modules -> db -> core KEPT
Routers must not touch persistence infrastructure KEPT
Services must not import the web framework or raw infrastructure clients KEPT
Repository stays free of web framework KEPT
Only core.config may read the environment KEPT
Contracts: 6 kept, 0 broken.
```

### 4. `pytest --cov=app --cov-report=term-missing --cov-fail-under=85`
**Result:** Pass — runnable in this environment this attempt.

```
603 passed in 76.78s (0:01:16)
=============================== tests coverage ================================
TOTAL                                             3275     97    442     39    96%
Required test coverage of 85% reached. Total coverage: 96.18%
```

`app/modules/support/` module coverage: `models.py` 100%, `schemas.py` 100%,
`dependencies.py` 100%, `exceptions.py` 100%, `router.py` 100%, `cache.py` 91%
(2 missed lines: 46, 48), `service.py` 92% (5 missed lines: 198, 235, 295, 314,
323), `repository.py` 86% (9 missed lines: 18-19, 25-26, 67-68, 81-83) — up
from v4's 74% now that `tests/integration/scripts/test_purge_unbound_attachments.py`
exercises `AttachmentRepository.find_unbound_older_than`/`.purge`. No touched
module fell below the 85% floor.

Broken out by suite for clarity (the combined run above already includes both):

```
$ pytest tests/unit -q
318 passed in 32.74s

$ pytest tests/integration -q
285 passed in 42.86s
```

`tests/integration/modules/support/test_support_router.py` and the new
`tests/integration/scripts/test_purge_unbound_attachments.py` (4/4 passed,
verified individually) are both included in the 285 and green — this run
exercises real PostgreSQL/Valkey via testcontainers, not a mock (confirmed:
`no unittest.mock in integration tests` hook Passed, and a direct grep of the
new file for `unittest.mock`/`mock.patch`/`patch.object`/`AsyncMock`/
`MagicMock` returns no matches).

### 5. Migration cycle (`upgrade → downgrade → upgrade`)
**Result:** Pass — re-proven fresh this attempt against the live database
(not only carried from v2/migration-manager's earlier proof):

```
$ alembic current
37c89e98a86f (head)

$ alembic downgrade -1
Running downgrade 37c89e98a86f -> 5dd6fff75016, add_support_tickets

$ alembic upgrade head
Running upgrade 5dd6fff75016 -> 37c89e98a86f, add_support_tickets

$ alembic current
37c89e98a86f (head)
```

No model or migration file changed since v2/T4; this is independent
re-confirmation, not first discovery.

## Part B — Runtime rules (AGENTS.md §6.6)

### 6. ORM containment
**Result:** Pass — `grep` for `from app.modules.support.models` /
`from app.modules.support import models` in `app/modules/support/router.py`:
no matches. `TicketService.create_ticket -> TicketRead`,
`TicketService.list_own_tickets -> TicketListResponse` — both public service
methods return `*Read`/domain response types, never an ORM model.

### 7. Eager loading
**Result:** N/A — `grep "relationship\("` on `app/modules/support/models.py`:
no matches. `Ticket`/`Attachment` declare no ORM relationships.

### 8. Cache TTL
**Result:** Pass — every write in `app/modules/support/cache.py` carries a
TTL: `TicketIdempotencyCache.claim` (`ex=ttl_seconds`, `nx=True`),
`.resolve` (`ex=ttl_seconds`), `TicketCreationRateLimitCache` (`pipe.expire`
INCR+EXPIRE shape mirroring `LoginThrottleCache._incr_with_ttl`).

### 9. Cross-module discipline
**Result:** Pass — `grep "from app\.modules\.[a-z_]+\.router import"` across
`app/modules/support/service.py`, `app/modules/audit/service.py`,
`app/modules/users/service.py`: no matches. Support's `UserServiceProtocol`
(structural, service.py-local) is satisfied by the concrete `UserService`
injected via `app/modules/support/dependencies.py`'s
`app.modules.users.dependencies.UserServiceDep` — service-to-service DI.

### 10. Banned idioms (`Any`, `# type: ignore`, `cast(`, `os.getenv`/`os.environ`)
**Result:** Pass — `grep -rn "typing\.Any|# type: ignore|cast\(|os\.getenv|os\.environ"`
across `app/modules/support/`, `app/modules/audit/`,
`app/modules/users/service.py`, and `scripts/purge_unbound_attachments.py`:
no matches.

### 11. Contract & security spot-check (§6.7)
**Result:** Pass —
- `POST /support/tickets`: `response_model=TicketRead`,
  `status_code=status.HTTP_201_CREATED`.
- `GET /support/tickets`: `response_model=TicketListResponse`,
  `status_code=status.HTTP_200_OK`.
- `CreateTicketRequest`: `model_config = ConfigDict(extra="forbid")`; no
  privilege field (`id`/`ticket_number`/`status`/`requester_id`/
  `created_at`/`updated_at`) client-writable.
- `TicketRead`/`TicketListResponse`: `model_config = ConfigDict(from_attributes=True)`
  with an explicit field list; no sensitive field exposed.
- `.env.example`: no diff — `git diff -- .env.example` empty; `git status
  --porcelain -- .env.example` empty. No new setting introduced.
- OpenAPI: `pytest`'s app-startup fixtures build the FastAPI app (including
  `app.main.app.openapi()`) on every integration-test run above with no
  exception; `/api/v1/support/tickets` present in the router registration
  (`app/api/v1/router.py`).

## Verdict

**PASS**

Every Part A check that was runnable was run with real captured output and
passed: `pre-commit` (7/7 hooks), `mypy app tests` (0 errors/145 files),
`lint-imports` (6/6 kept), `pytest --cov=app --cov-fail-under=85` (603 passed,
96.18% coverage), and a freshly re-proven `upgrade → downgrade → upgrade`
migration cycle. All Part B runtime rules are confirmed-compliant or
explicitly N/A. No bypass was proposed or needed for any check.

**Resolved by this pass:** `scripts/purge_unbound_attachments.py`'s missing
test — `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests,
added by `TEST_WRITING` v5) now covers `AttachmentRepository
.find_unbound_older_than`/`.purge`, the code path the script's own `main()`
composes. No longer carried forward.

**Carried forward, unchanged by this stage:** OD-3 (category enum, no
DB-level `CHECK`/`ENUM` constraint), BR-007 FK `ondelete` mechanics (pending
legal/DPO sign-off), the idempotency poll-exhaustion path's undocumented 500
(confirmed implementation behavior, not a further gap), the two Spec Drift
items from `RECONCILIATION` v1 (`ticket_number` guessable format;
`ticket_audit_log` vs. `audit_log` wording), and the `ticket_number`
guessability security advisory from `SECURITY_REVIEW` v1 — none newly
affected by this stage. Carried for `RECONCILIATION`'s re-run and
`HUMAN_PR_APPROVAL`.
