---
artifact_type: test_generation_report
story: US-4.4
version: 2
status: DRAFT
created_at: "2026-09-07T17:07:56Z"
updated_at: "2026-09-07T19:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/tests/US-4.4-test-strategy.md
    version: 1
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.4-plan-review.md
    version: 1
supersedes: null
---

# Test Generation Report: Agent Ticket Queue & Assignment (US-4.4)

## Files modified

- `tests/unit/modules/support/test_support_service.py` — 21 new test
  functions (one parametrized over 2 limit values, two parametrized over
  the two method names `assign_ticket`/`unassign_ticket` — see the AC
  matrix for the exact list), 3 new fakes/fake extensions
  (`FakeRoleService`; `FakeTicketRepository` gained
  `list_for_agent_queue`/`assign_ticket`/`unassign_ticket`; `FakeUserService`
  gained call-recording and a per-user status map on
  `get_account_status_for_user`), `_make_ticket` gained an `assignee_id`
  kwarg, `_make_service` gained a `role_service` parameter and its return
  tuple grew one element (`FakeRoleService`, appended last). Two pre-
  existing US-4.1/US-4.3 tests that fully unpacked `_make_service`'s
  return tuple by position
  (`test_create_ticket_deactivated_account_raises_before_any_write`,
  `test_resolve_ticket_agent_from_each_eligible_status_succeeds`) were
  updated to add one trailing placeholder for the new tuple element — no
  other change to either test's body or assertions.
- `tests/integration/modules/support/test_support_router.py` — 29 new test
  functions plus one existing test updated in place
  (`test_list_own_tickets_agent_scope_caller_returns_403`, per the spec's
  NFR: now asserts the new agent-branch `200`, not the retired `403`).
  `_seed_ticket` gained `category`/`assignee_id`/`updated_at` kwargs (all
  optional, backward compatible with every existing caller). New helpers:
  `_seed_agent_only` (a `support_agent`-role user with no session, for use
  as an assign target only) and `_assign_path`. New import:
  `app.modules.support.repository.TicketRepository` (used directly by the
  AQ-AC10 test — see below).

Both files pass `ruff check` and `ruff format --check` clean as written.
Neither file can be fully collected/run by `pytest` yet —
`AssignmentConflictError` (exceptions), `Ticket.assignee_id` (models),
`list_for_agent_queue`/`assign_ticket`/`unassign_ticket` on
`TicketRepository`/`TicketService` (repository/service),
`RoleServiceProtocol` (service), and `AgentTicketRead`/
`AgentTicketListResponse`/`AgentTicketStateRead`/`AssignTicketRequest`
(schemas) do not exist in `app/modules/support/` yet — this is expected
and matches this project's own established test-writer/
service-and-router-builder ordering (`US-4.3`'s own test-writing pass
referenced `EmailSender.send_ticket_resolved_email` before that method
existed). `IMPLEMENTATION` (T1-T9) is what makes these tests importable
and, subsequently, green.

## Test counts

| | Unit | Integration |
|---|---|---|
| New test functions | 21 | 29 |
| Updated (not new) | 0 | 1 |
| Existing US-4.1/US-4.3 tests touched only for the tuple-width fix (no assertion change) | 2 | 0 |

## Every AC has at least one test

Confirmed against `docs/tests/US-4.4-ac-test-matrix.md`: AQ-AC1 through
AQ-AC10 each have at least one unit or integration test (most have both).
The two ACs with integration-only coverage (AQ-AC5's byte-shape assertion,
AQ-AC6) are integration-only because they assert on the customer branch of
`list_own_tickets`, a method this story does not modify — there is no new
service-layer branch for a unit test to exercise.

## Security cases (AGENTS.md §5: no token / expired / malformed / insufficient
## permissions / revoked, on every protected route)

- `GET /v1/support/tickets` — already fully covered by US-4.1's existing
  four-case token matrix (`test_list_own_tickets_no_token_returns_401`,
  `..._malformed_token_returns_401`, `..._expired_token_returns_401`,
  `..._revoked_session_returns_401`), unmodified by this story; this story
  adds no new insufficient-permission case for `GET` itself since the
  retired `403` was the "insufficient permission" case and it is gone by
  design (In Scope: `reject_agent_queue_access` removed, no `403` remains
  on this route for any caller kind).
- `POST`/`DELETE /{id}/assign` — `test_assign_and_unassign_auth_matrix_returns_401`
  covers no-token/malformed/expired/revoked (parametrized 2x4 = 8 cases);
  `test_assign_ticket_read_only_agent_returns_403` /
  `test_unassign_ticket_read_only_agent_returns_403` cover insufficient
  permissions. All five §5-required cases are present across these tests
  for both new routes.

## Open Decisions: reversal blast radius (non-blocking findings)

`docs/decisions/US-4.4-open-decisions.md` (v1) logs OD-1 through OD-4, none
yet human-confirmed. Every upstream artifact (spec, API design, DB design,
implementation plan, plan review — all PASS/APPROVED) already adopted each
OD's recommended default, and this stage's tests were written against those
same defaults, consistent with `AGENTS.md` §11 and
`docs/workflow/artifact-lifecycle.md`'s definition of `BLOCKED` (a missing
or stale mandatory input — none here). If `HUMAN_SPEC_APPROVAL` reverses one,
the following tests name exactly what breaks:

- **OD-1 (Critical — response schema split).** If reversed (shared
  `TicketRead`/`TicketStateRead` extended in place instead of new
  `AgentTicketRead`/`AgentTicketStateRead` schemas), every test in both
  files that asserts `assignee_id` presence/absence on a specific schema
  shape is affected: `test_list_own_tickets_customer_branch_response_has_no_assignee_id_field`,
  every `test_list_own_tickets_agent_branch_*` test's field-set assertion,
  and every `assign_ticket`/`unassign_ticket` response-shape assertion. This
  is the largest blast radius of the four, matching `implementation_plan.md`'s
  own Risk 9 assessment.
- **OD-2 (`GET /{id}` not extended).** No test in this matrix touches
  `TicketDetailRead`'s `assignee_id` either way (see the AC matrix's
  "Explicitly not covered" section) — reversing OD-2 requires *new* tests,
  not a change to any test written here.
- **OD-3 (unassign-on-closed -> 409).** If reversed (unassign instead
  succeeds unconditionally, even on a closed ticket), exactly two tests
  need to flip their expected status code and body:
  `test_assign_and_unassign_closed_ticket_raises_409`'s `unassign_ticket`
  parametrization (unit) and `test_unassign_ticket_closed_ticket_returns_409`
  (integration). Nothing else in either file asserts on this branch.
- **OD-4 (deactivated assign-target also rejected).** If reversed (only the
  scope condition is checked, account status ignored), exactly two tests
  need to flip: `test_assign_ticket_target_deactivated_raises_422` (unit)
  and `test_assign_ticket_deactivated_target_returns_422` (integration).
  Both are self-contained — no other test in either file depends on this
  branch's outcome.

## `QUALITY_GATE` loop-back fix pass (attempt 2, `TEST_WRITING` re-entry)

`gate-enforcer` ran the full Definition-of-Done gate against real Docker
PostgreSQL/Valkey and confirmed there is **no production defect** anywhere
in `app/modules/support/` — the real `repository.py`/`service.py`/
`router.py` are correct. All 9 pytest failures and 9 mypy errors traced to
four defects entirely inside `tests/unit/modules/support/test_support_service.py`
and `tests/integration/modules/support/test_support_router.py`, all
stemming from this stage's own now-superseded collaborator-shape
assumptions and two missed tuple-unpack call sites:

1. **`FakeTicketRepository.list_for_agent_queue` had a stale signature**
   (`assignee_id: uuid.UUID | None, unassigned_only: bool` instead of the
   real `assignee_id: uuid.UUID | Literal["none"] | None` with no
   `unassigned_only` parameter). Fixed the fake and the four
   `test_list_agent_queue_*` assertions that read `call["unassigned_only"]`
   to instead assert the single resolved `assignee_id` value (a UUID, the
   literal `"none"`, or `None`). 6 test failures + 2 mypy errors resolved.
2. **`_make_service()`'s 9-element return tuple had two missed call sites**
   beyond the two the original pass fixed (see "Collaborator-shape
   assumptions" above): `test_create_ticket_happy_path_writes_audit_event_and_queues_email`
   (fixed 8-element unpack against the real 9-element tuple — `ValueError:
   too many values to unpack`) and
   `test_create_ticket_no_email_on_file_skips_dispatch_without_failing`
   (`*_, email_sender = _make_service(...)` silently rebound `email_sender`
   to the fake `RoleService` once `role_service` became the trailing
   element). Both gained a trailing `_` placeholder. 2 test failures
   resolved (one `ValueError`, one `AttributeError:
   'FakeRoleService' object has no attribute 'sent'`).
3. **`test_assign_ticket_reassign_replaces_assignee_and_audits_the_change`
   asserted 2 `ticket_assigned` audit rows after exactly 1 `POST /assign`
   call**, against a ticket seeded directly with an assignee (no prior
   service call, so no prior audit row). Corrected the assertion to expect
   1 row — `gate-enforcer` confirmed `TicketService.assign_ticket` writes
   exactly one audit row per call. 1 test failure resolved.
4. **Five sites indexed `exc_info.value.errors[0]` without narrowing
   `ProblemError.errors: list[FieldError] | None`.** Replaced each with
   `[error.field for error in exc_info.value.errors or []]` then indexing
   `[0]` — the same `... or []` idiom `test_users_service.py:2397/2419/2441`
   already uses for the sibling `PasswordPolicyError` subclass. Runtime
   behavior unchanged (these assertions already passed); 5 mypy errors
   resolved.

**Result:** `mypy app tests` — 0 errors (was 9). Both files' own test runs
— 239 passed (was 230 passed / 9 failed). Full repo suite — 836 passed (was
827 passed / 9 failed), confirming no regression elsewhere. `ruff check`
and `ruff format --check` remain clean on both files.

No AC-to-test mapping changed — `docs/tests/US-4.4-ac-test-matrix.md` is
unaffected by this pass; every test function this pass touched already
existed under the same name and traced to the same AC row.

## Known gaps / limitations (reported, not silently accepted)

- **AQ-AC10's concurrency proof is repository-direct, not HTTP-level.** An
  HTTP-level `real_client`+`db_session` race — this project's established
  pattern for the two precedents in
  `tests/integration/modules/users/test_users_router.py` — was tried first
  and rejected: `db_session`'s fixture installs a process-wide
  `get_db_session` override, so `real_client`'s two requests would
  actually execute *serially* against one shared session, not
  concurrently. That serialization is harmless for the two existing
  precedents (a consumed-state guard), but `assign`'s guard is an
  optimistic-*expected-value* check the API design deliberately
  generalized to cover re-assignment — under serialization, the second
  call's own read would see the first call's already-committed
  `assignee_id`, adopt it as its own `expected` value, and also succeed,
  yielding `[200, 200]` against a correct implementation, not `[200,
  409]`. `test_assign_ticket_repository_conditional_update_rejects_stale_expected_value`
  instead drives `TicketRepository.assign_ticket` directly with a
  deliberately stale `expected_assignee_id` on the second call — real
  PostgreSQL, no mocking, deterministic rather than timing-dependent. The
  `None` -> `AssignmentConflictError` mapping is separately proven at the
  unit layer. See `docs/tests/US-4.4-test-strategy.md`'s
  "Concurrency-test mechanism" section for the full reasoning; this is a
  design choice, not an unresolved limitation — no HTTP-level version of
  this test remains outstanding.
- **The Enforcement Matrix's EXPLAIN test runs under `SET LOCAL
  enable_seqscan = off`.** DR-1's claim is that the partial index is
  *usable* for the literal `status != 'closed'` predicate, not that it is
  the planner's cheapest choice on a near-empty seeded table (this test
  seeds no rows) — a plain "no Seq Scan" assertion would fail against a
  correct implementation on an empty heap. Disabling `enable_seqscan`
  makes the index's name appearing in the plan the discriminating proof
  instead. See `docs/tests/US-4.4-test-strategy.md`'s "Index coverage"
  paragraph.
- **`list_for_agent_queue`'s single-`assignee_id` repository parameter
  shape** and the agent-queue service method's name (`list_agent_queue`)
  were test-writer's own collaborator-shape assumptions, not fixed by any
  design or planning artifact — see `docs/tests/US-4.4-test-strategy.md`'s
  "Collaborator-shape assumptions" section. The `assignee_id`/
  `unassigned_only` two-parameter shape originally assumed here did *not*
  match what `IMPLEMENTATION` built (a single `assignee_id: uuid.UUID |
  Literal["none"] | None`); this was corrected at the `QUALITY_GATE`
  loop-back documented above rather than left to diverge silently.
- **`TicketService.__init__`'s new `role_service` parameter position**
  (immediately after `user_service`, before `email_sender`) is likewise
  this stage's own assumption. `data-layer-builder`/`service-and-router-builder`
  are not bound to this exact position — only the unit test's own
  `_make_service` factory needs to match whatever the real constructor
  ends up being.
- **No AC-driven test exercises `GET /v1/support/tickets/{id}`** (OD-2) —
  deliberate, not an oversight; see the AC matrix.
