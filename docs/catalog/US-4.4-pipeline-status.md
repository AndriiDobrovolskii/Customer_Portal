---
artifact_type: pipeline_status
story: US-4.4
version: 2
status: DRAFT
created_at: "2026-09-07T17:30:00Z"
updated_at: "2026-09-07T19:10:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/tests/US-4.4-test-strategy.md
    version: 2
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
supersedes: docs/catalog/US-4.4-pipeline-status.md (v1)
---

# IMPLEMENTATION Pipeline Status — US-4.4 (Agent Ticket Queue & Assignment)

Tracks the four `IMPLEMENTATION` sub-steps (`docs/workflow/stage-map.yaml`
`skills_by_track.backend`), dispatched one sub-agent per builder skill, each
covering the tasks `docs/plans/US-4.4-task-breakdown.md` assigns it:

| Skill | Tasks covered | Verdict | Artifacts |
|---|---|---|---|
| schema-builder | T1 | **PASS** | `app/modules/support/schemas.py` (`AssignTicketRequest`, `AgentTicketRead`, `AgentTicketListResponse`, `AgentTicketStateRead`) |
| data-layer-builder | T2, T3, T4 | **PASS** | `app/modules/support/models.py`, `app/modules/support/repository.py` |
| migration-manager | T5 | **PASS** | `migrations/versions/55d8d34a9753_add_ticket_assignee_column.py` |
| service-and-router-builder | T6, T7, T8, T9 | **PASS** | `app/modules/support/service.py`, `router.py`, `dependencies.py`, `exceptions.py` |

T10 (`gate-enforcer`, `QUALITY_GATE`) is the next workflow stage, not part of
this composite skill.

## T6/T7/T8/T9 — service-and-router-builder (in progress)

`RoleServiceProtocol` (Protocol-only, no direct `roles.service` import) added
and wired via `RoleServiceDep` in `dependencies.py`; `TicketService` gained
`list_agent_queue`, `assign_ticket`, `unassign_ticket` per the API design's
check order; `exceptions.py` swapped `AgentQueueNotAvailableError` for
`AssignmentConflictError` (409); `router.py`'s `list_own_tickets` branches on
`tickets:read`, gained `POST`/`DELETE /{id}/assign`. `mypy --strict` clean on
all four files; `ruff` clean; `app.openapi()` matches `US-4.4-openapi.yaml`
v1 exactly; import-boundary rules verified via grep (`lint-imports` itself
can't run in this sandbox - Smart App Control blocks its compiled extension,
a pre-existing environment constraint). The already-updated
`test_list_own_tickets_agent_scope_caller_returns_403` test was confirmed to
now assert the new `200` behavior, not the retired `403`.

**Defect found (cross-file, not this sub-step's to fix):**
`repository.py`'s `TicketRepository.assign_ticket` (T4, `data-layer-builder`)
names its keyword-only target parameter `assignee_id`, but both independently
written test suites (`test_support_service.py`'s fake, and
`test_support_router.py:2868` calling the real repository directly) expect
`new_assignee_id`. Root cause of 1 integration + 5 unit test failures.
`service-and-router-builder` correctly declined to edit a file it doesn't own
and reported this as a blocking finding instead. Routed back to
`data-layer-builder` for a targeted rename (in progress).

**Other findings, informational (test-file issues, not production defects,
not this composite stage's to fix — belong to `test-writer`/`TEST_WRITING`
if revisited):**
- 6 unit-test failures: `test_support_service.py`'s `FakeTicketRepository.list_for_agent_queue`
  uses a `assignee_id: uuid.UUID | None` + `unassigned_only: bool` shape that
  diverges from the real, integration-proven `list_for_agent_queue`'s
  `assignee_id: uuid.UUID | Literal["none"] | None` sentinel design. The real
  endpoint is fully proven by 8 passing integration tests.
- 2 unit-test failures in `_make_service()`'s own fixture: a tuple-unpack
  arity bug now that the fixture returns 9 elements (`role_service` appended)
  and a stale `*_, email_sender` call-site claim that actually binds
  `email_sender` to the fake `RoleService`.
- 1 integration-test assertion bug: `test_assign_ticket_reassign_replaces_assignee_and_audits_the_change`
  asserts 2 `ticket_assigned` audit rows after a single `POST /assign` call
  against a ticket seeded with no audit row; only one HTTP call is made, so
  only one audit row is correct per the API design's NFR - reads as an
  off-by-one in the test's own assertion.

Test counts before the rename fix: unit 90 passed / 13 failed; integration
134 passed / 2 failed (224/239 combined).

**Cross-file defect fixed:** `repository.py`'s `assign_ticket` keyword-only
parameter renamed `assignee_id` -> `new_assignee_id` (data-layer-builder,
targeted re-dispatch on T4), and `service.py`'s one call site plus
`TicketRepositoryProtocol`'s matching signature updated to match
(service-and-router-builder, targeted re-dispatch on T8). Both fixes verified
scoped (git diff / grep) and `mypy --strict` clean. Re-run after both fixes:
**230 passed, 9 failed** (up from 224/239). All 9 remaining failures
independently confirmed as pre-existing test-file issues, not production
defects (see findings above: 6 `FakeTicketRepository.list_for_agent_queue`
shape-mismatch failures, 2 `_make_service()` fixture tuple-unpack bugs, 1
audit-count off-by-one assertion) — left for `QUALITY_GATE`/`gate-enforcer`
to formally gate and route, per this composite stage's scope (code
generation only, not the mechanical Definition-of-Done gate).

**All four IMPLEMENTATION sub-steps complete (v1). Composite stage advanced to
QUALITY_GATE.**

## v2 — QUALITY_GATE loop-back re-entry, no builder re-invoked

`QUALITY_GATE` (`gate-enforcer`) returned `CHANGES_REQUIRED` via
`changes_required_tests`: 9 pytest failures + 9 mypy errors, all independently
traced to four defects confined entirely to `tests/unit/modules/support/test_support_service.py`
and `tests/integration/modules/support/test_support_router.py` (stale
`FakeTicketRepository.list_for_agent_queue` shape, a `_make_service()` fixture
tuple-unpack arity bug, one audit-count assertion off-by-one, and 5
Optional-indexing mypy sites) — zero production-code defect in `app/modules/support/`,
confirmed by `gate-enforcer` reading the real code directly. `TEST_WRITING`
(attempt 2) fixed all four in the test files only; `test_strategy` bumped to
v2 (corrected the same disproven `unassigned_only` assumption both it and the
generation report carried). Per `stage-map.yaml`, `TEST_WRITING.next` is
`IMPLEMENTATION`, so this composite stage was re-entered — but since none of
T1-T9's owned files (`schemas.py`, `models.py`, `repository.py`, migration,
`service.py`, `router.py`, `dependencies.py`, `exceptions.py`) changed, no
builder sub-step was re-dispatched. Existing v1 output validated: `mypy app
tests` clean (147 files), the two US-4.4 test files 239/239 passed, full
repo suite 836/836, `git status`/`git diff` confirm zero changes under `app/`
or `migrations/` since v1. `IMPLEMENTATION` advances to `QUALITY_GATE`
(identical resolution to `US-4.3`'s own `changes_required_tests` loop-back
precedent).

## T5 — migration-manager (PASS)

`55d8d34a9753_add_ticket_assignee_column.py` (chains from `242e0dba5ba2`):
additive `tickets.assignee_id` nullable FK to `users.id`
(`tickets_assignee_id_fkey`, explicitly named) plus the three new indexes,
all guarded with `sa.inspect(op.get_bind())` checks (add_column/create_foreign_key
aren't reached by the Rewriter) and `if_not_exists=True`/`if_exists=True` on
the index create/drop calls. Real `upgrade -> downgrade -> upgrade` cycle run
against Docker Postgres; at the intermediate downgraded point `\d tickets`
confirmed the new column/FK/indexes genuinely absent while the pre-existing
`ix_tickets_resolved_at_pending_autoclose` stayed intact. Post-upgrade
`pg_indexes` confirmed both partial predicates render as literal comparisons
(`status <> 'closed'` / `status = 'resolved'`), not `IN`-lists. `migrations/env.py`
untouched.

## T2/T3/T4 — data-layer-builder (PASS)

`Ticket.assignee_id: Mapped[uuid.UUID | None]` (nullable FK to `users.id`, no
`ondelete`) plus three new indexes in `models.py`: `ix_tickets_queue_default_updated_at_id`
(partial, literal `postgresql_where=text("status != 'closed'")`),
`ix_tickets_status_updated_at_id`, `ix_tickets_assignee_id_updated_at_id`.
`repository.py` gained `list_for_agent_queue` (new method, ascending
`Ticket.updated_at > cursor_updated_at` keyset, `status`/`category`/`assignee_id`
filters) — `list_for_requester` confirmed byte-for-byte unchanged (still uses
its own descending `created_at <` comparison) — and `assign_ticket`/
`unassign_ticket`, both using `Ticket.assignee_id.is_not_distinct_from(...)`/
unconditional-WHERE and both including `updated_at=Ticket.updated_at` in
`.values()` (DR-3's fix, verified present in both methods, not half-applied).
`mypy --strict`, `ruff check`, `ruff format --check` all clean on both files.

## T1 — schema-builder (PASS)

Added `AssignTicketRequest` (`assignee_id: uuid.UUID`, `extra="forbid"`),
`AgentTicketRead` (every `TicketRead` field plus required `assignee_id:
uuid.UUID | None`, no default), `AgentTicketListResponse` (parallel to
`TicketListResponse`), `AgentTicketStateRead` (every `TicketStateRead` field
plus required `assignee_id: uuid.UUID | None`) to `app/modules/support/schemas.py`,
per OD-1's approved schema split. `TicketRead`/`TicketListResponse`/
`TicketStateRead` confirmed byte-for-byte unchanged (`git diff` shows zero
removed/modified lines, pure addition). `mypy --strict`, `ruff check`, `ruff
format --check` all clean.

OD-1..OD-4 (`docs/decisions/US-4.4-open-decisions.md`) were confirmed by the
human stakeholder (sbruhov@gmail.com, 2026-09-07T17:25:48Z) before this stage
began dispatching — T1 (OD-1's schema split), T4 (OD-3's unassign-on-closed
409), and T8 (OD-4's deactivated-target 422) build directly against these now
human-confirmed defaults.
