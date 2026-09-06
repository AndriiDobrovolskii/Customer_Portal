---
artifact_type: test_generation_report
story: US-4.3
version: 2
status: ARCHIVED
created_at: "2026-09-06T23:00:00Z"
updated_at: "2026-09-07T03:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/tests/US-4.3-test-strategy.md
    version: 2
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
supersedes: 1
---

# Test Generation Report: Ticket Resolution (US-4.3)

## Why this pass ran (TEST_WRITING, attempt 2 — supersedes v1)

`story-orchestrator` routed `IMPLEMENTATION` → `TEST_WRITING` via
`stage-map.yaml` `IMPLEMENTATION.loop_back.changes_required_tests`
(`docs/workflow/workflow-state.yaml` `last_result.verdict: CHANGES_REQUIRED`,
`recorded_at: "2026-09-07T02:00:00Z"`). All six `IMPLEMENTATION` sub-steps
(T1-T6) were complete and independently verified — 773/774 repository tests
passing (`docs/catalog/US-4.3-pipeline-status.md` v1) — but two tests were
found non-deterministically flaky, a test-file defect, not an implementation
defect:

1. `tests/integration/scripts/test_auto_close_resolved_tickets.py::
   test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_
   untouched` seeded `resolved_at` from Python's wall clock
   (`datetime.now(UTC) - timedelta(days=7)`) at Arrange time, then the
   auto-close job's strict predicate (`resolved_at < now() - interval
   '7 days'`, evaluated via Postgres's transaction-frozen `now()`) was
   compared at Act time. The outcome depended on real elapsed wall-clock time
   between Arrange and Act — system-load-dependent, not deterministic.
   Confirmed 5/5 passes in isolation vs. 1 failure under full-suite load.
2. Its twin, `tests/integration/modules/support/test_support_router.py::
   test_reopen_ticket_at_exactly_7_days_boundary_succeeds`, was the identical
   zero-margin construction against the inclusive `>=` guard — it passed the
   `IMPLEMENTATION` run only by chance of scheduling and would fail
   unpredictably under different timing.

## What changed this pass (attempt 2)

Fixed both tests by seeding `resolved_at` **server-side**, in the same
transaction, instead of from a Python-computed literal:

- `tests/integration/scripts/test_auto_close_resolved_tickets.py` — new
  helper `_seed_resolved_ticket_at_exact_window_boundary` seeds a resolved
  ticket, then issues `UPDATE tickets SET resolved_at = func.now() -
  func.make_interval(0, 0, 0, literal(7)) WHERE id = :id` on the same
  `db_session` before flush/refresh.
- `tests/integration/modules/support/test_support_router.py` — new helper
  `_seed_ticket_resolved_at_exact_window_boundary`, identical pattern, built
  on the existing `_seed_ticket`.

`db_session`'s fixture runs each test's whole body in one connection-level
transaction, and `transaction_timestamp()` (`func.now()`) is frozen for that
transaction's lifetime — the same fact the pre-existing 5-minute-margin
boundary tests already rely on. The seed and the guard's own predicate
(`repository.py`'s identical `func.now() - func.make_interval(0, 0, 0,
literal(_RESOLUTION_WINDOW_DAYS))` expression) therefore read the *identical*
frozen `now()`: `resolved_at < now() - 7d` is now deterministically false and
the inclusive `>=` sibling deterministically true, with no wall-clock race in
either direction. The margin was **not** widened — both tests still assert
the exact boundary, preserving the property being proven.

No other test was touched. No application code was touched — T1-T6 remain
exactly as `IMPLEMENTATION` (attempt 1) left them.

## Verified this pass

```
uv run --no-sync ruff check <2 edited files>       → All checks passed! (after
  fixing 2 E501 line-length findings from the new UPDATE call's line length)
uv run --no-sync ruff format --check <2 edited files> → both formatted
uv run --no-sync mypy <2 edited files> --strict    → Success: no issues found
  in 2 source files

uv run --no-sync pytest <the 2 fixed tests> -q  (5 consecutive runs)
  → 2 passed, ×5 (deterministic; no flake observed)

uv run --no-sync pytest tests/integration/modules/support/
  tests/integration/scripts/test_auto_close_resolved_tickets.py
  tests/unit/modules/support/ -q
  → 211 passed

uv run --no-sync pytest -q  (full repository suite)
  → 774 passed  (up from 773/774 at IMPLEMENTATION attempt 1 — the flaky
    test is now green under full-suite load, not merely not-yet-triggered)
```

## Result

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.3
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.3-test-strategy.md (v2)
    - docs/tests/US-4.3-ac-test-matrix.md (v2)
    - docs/evidence/US-4.3-test-generation-report.md (v2)
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "Rework only: fixed the two non-deterministic exact-7-day-boundary tests IMPLEMENTATION (attempt 1) flagged via changes_required_tests, by seeding resolved_at server-side (func.now() - func.make_interval(...)) instead of from Python's wall clock. No margin was widened - both tests still assert the literal boundary. No application code changed; all v1 non_blocking_findings (collaborator-shape assumptions, plan gaps, etc.) stand unchanged and are not repeated here - see test_generation_report.md v1 (superseded) for their full text."
    - "Full repository suite now 774/774 (was 773/774 at IMPLEMENTATION attempt 1) - the previously-flaky test is confirmed fixed under full-suite load, not just individually. Ready to re-enter IMPLEMENTATION; T1-T6 are not expected to need further change."
```

---

## Appendix: v1 report (attempt 1 — superseded, retained verbatim for history)

## Why this pass ran (TEST_WRITING, attempt 1)

`story-orchestrator` advanced from `HUMAN_PLAN_APPROVAL` (human approved
`implementation_plan` v1, `task_breakdown` v1, `plan_review` v1;
`docs/workflow/workflow-state.yaml` `updated_at: "2026-09-06T22:00:00Z"`) to
`TEST_WRITING`. `IMPLEMENTATION` (T1-T6: `schema-builder`,
`data-layer-builder`, `migration-manager`, `service-and-router-builder` ×2,
and the `scripts/auto_close_resolved_tickets.py` script) has not yet run — no
resolution-related symbol exists anywhere in `app/modules/support/` and
`scripts/auto_close_resolved_tickets.py` does not exist.

## Files changed this pass

- `tests/unit/modules/support/test_support_schemas.py` (extended) — 13 new
  test functions covering `ResolveTicketRequest`'s `extra="forbid"`/
  length-cap/mandatory-field behavior, `CloseTicketRequest`/
  `ReopenTicketRequest`'s optional unconstrained `reason`, and
  `TicketStateRead`'s data-minimization scope (`closed_by`/`resolution_note`
  excluded). 12 pre-existing US-4.2 test functions unchanged (25 total, was
  12).
- `tests/unit/modules/support/test_support_service.py` (extended) — 21 new
  test functions (several parametrized: ×2, ×3, ×4) covering
  `TicketService.resolve_ticket`/`close_ticket`/`reopen_ticket` and the
  `_ALLOWED_EVENTS_BY_STATUS` table, plus 2 test functions extending/
  reconciling `TicketReplyService.create_reply`'s existing FR-4 test for
  DR-4's new audit write and window guard. New members: `FakeTicketRepository
  .transition_status(...)` (additive), `FakeEmailSender
  .send_ticket_resolved_email(...)` (additive), `_resolved_ticket(...)`
  helper, `_RESOLUTION_NOTE` constant. `_make_ticket` now explicitly
  initializes `resolved_at`/`resolution_note`/`closed_at`/`closed_by` to
  `None` on every constructed ticket (additive — the 42 pre-existing US-4.1/
  US-4.2 test functions are unaffected, since none reads these fields). 63
  total (was 42).
- `tests/integration/modules/support/test_support_router.py` (extended) — 17
  new test functions (several parametrized: ×3, ×4, ×12) covering `/resolve`,
  `/close`, `/reopen` end-to-end, the four-case authentication matrix across
  all three routes, the concurrent-resolution race (FR-9), and FR-4's now-
  modified reply-reopen audit write plus its window-guard no-op case. `_seed_
  ticket` gains optional `resolved_at`/`resolution_note`/`closed_at`/
  `closed_by` kwargs (additive — every existing call site omits them). New
  path helpers `_resolve_path`/`_close_path`/`_reopen_path`. 77 total (was
  60).
- `tests/integration/scripts/test_auto_close_resolved_tickets.py` (new) — 8
  test functions covering `TicketRepository.auto_close_resolved_past_window`
  (status/window predicates, idempotency, batch id-list return shape,
  survival of a since-reopened ticket) and one full-loop composition test
  (`AuditRepository`/`AuditLogService`/`RoleRepository`/`UserRoleRepository`/
  `RoleService`/`PermissionEpochCache`, mirroring the script's own Decision 6
  wiring against the test's already-provisioned Postgres/Valkey rather than
  the script's own from-`get_settings()` construction).
- `docs/tests/US-4.3-test-strategy.md`, `docs/tests/US-4.3-ac-test-matrix.md`,
  this file — new, v1.

No application code changed — test files and this stage's own three
artifacts only, per this skill's own scope constraint.

## Test-writer's own collaborator-shape assumptions made this pass

Recorded in full in `US-4.3-test-strategy.md`'s own section of the same name;
summarized here for the Result Envelope's `non_blocking_findings`:

1. `TicketService.resolve_ticket`/`close_ticket`/`reopen_ticket`'s keyword-only
   signatures and `TicketRepository.transition_status`'s exact keyword shape
   (both directly stated by `implementation_plan.md` Decision 2 — low risk).
2. **`TicketReplyService.create_reply`'s FR-4 branch splits into two
   sub-cases**, not the single branch the plan's prose describes literally —
   necessary to avoid a real defect (the inclusive window guard would attach
   `resolved_at >= now() - interval '7 days'` to a `NULL` `resolved_at` on the
   ordinary `waiting_on_customer` case, silently breaking FR-2). Flagged for
   `reconciliation-reviewer` to confirm against the actual shipped branch
   shape.
3. `TicketReplyService.__init__`'s new `audit_service` parameter position
   (right after `rate_limit_cache`, before `email_sender`) — no design doc
   fixes this; chosen to mirror `TicketService.__init__`'s own ordering.
4. **`EmailSender.send_ticket_resolved_email(...)` is a new Protocol method
   FR-1 requires that `implementation_plan.md`'s Files To Modify table does
   not list** (`app/core/email.py` is absent from that table). This is a
   genuine plan gap, not an invented requirement — matches US-4.1's own
   `get_email_for_user` precedent. `service-and-router-builder` must add this
   method to `EmailSender`/`LoggingEmailSender`.

## Self-review fixes (before declaring PASS)

Caught during this pass's own review, before recording the result:

1. **`_seed_ticket`'s `status="closed"`/`status="resolved"` seeds would
   violate `US-4.3-entity-model.md` v3's two `CHECK` constraints once T3's
   migration lands.** `ck_tickets_closed_requires_closed_fields` is a full
   biconditional (`closed_at`/`closed_by` must be set together with, and
   only with, `status='closed'`); `ck_tickets_resolved_requires_resolution_
   fields` requires `resolved_at` and `resolution_note` together whenever
   `status='resolved'`. Several new integration tests, and three
   **pre-existing US-4.2 tests** (`test_create_reply_on_closed_ticket_
   returns_409`, `test_create_reply_agent_public_on_resolved_ticket_status_
   stays_resolved`, `test_create_reply_customer_on_resolved_ticket_reopens_
   it`) seed `status="closed"`/`"resolved"` without the fields the new CHECKs
   require — a regression this story's own migration would have introduced
   into US-4.2's already-shipped suite, which `impact-analyzer` did not catch
   (it checked production code paths, not test seeders). Fixed once, in
   `_seed_ticket` itself: when `status="resolved"` and no explicit
   `resolved_at`/`resolution_note` is given, both default (`datetime.now(UTC)`
   / `"Seeded resolution."`); symmetrically for `status="closed"`
   (`closed_at`/`closed_by=requester_id`). An explicit kwarg always wins, so
   `test_reopen_ticket_outside_window_returns_409`'s deliberately-old
   `resolved_at` is unaffected, and no test gains a false-passing assertion
   (nothing asserts `closed_by` on a ticket seeded via the bare default).
2. **`docs/tests/US-4.3-ac-test-matrix.md`'s first draft mislabeled or
   dropped three source AC ids** — TC-AC3 (auto-close) was labeled
   `TC-AC1 / FR-3`; TC-AC4 (reply reopens) and TC-AC9 (missing
   `resolution_note`) rows existed but carried only the FR label, not the AC
   id. Corrected — see the current matrix.
3. **This report's own "Coverage against the ac-test-matrix" section
   overstated what the collection run proves** for the three files that fail
   at `import` time — an `ImportError` happens before the module body
   executes, so no function object is ever created to "not find." Replaced
   with an actual name diff (`comm -23` against `grep`-extracted defined
   function names) — see below. The same paragraph also mis-added the
   per-file new-test counts (39 instead of 59); corrected.
4. **Three window-boundary integration tests seeded `resolved_at` only 1
   second past the 7-day cutoff, timed against the wrong clock.** The window
   predicates are evaluated by Postgres via `func.now()`
   (`transaction_timestamp()`, frozen at the enclosing transaction's start —
   `_seed_reply`'s own docstring already documents this). The `db_session`
   fixture opens that transaction *before* the test body runs, so Postgres's
   `now()` is always earlier than any `datetime.now(UTC)` the Arrange block
   computes later — by however long fixture setup (including `_seed_user`'s
   password hashing) took. A 1-second margin is narrower than that setup gap
   can plausibly be, making `test_reopen_ticket_outside_window_returns_409`,
   `test_create_reply_customer_on_resolved_outside_window_makes_no_status_
   change`, and `test_auto_close_resolved_past_window_closes_ticket_older_
   than_7_days` flaky against a *correct* implementation — the same
   wrong-clock-reference risk as the CHECK-constraint seeding gap above, not
   a design flaw in the guard itself. Fixed by widening each to a 5-minute
   margin past the 7-day boundary (`timedelta(days=7, minutes=5)`) — still
   unambiguously "outside the window," now with headroom no realistic setup
   latency can close. The two *exact*-boundary tests
   (`test_reopen_ticket_at_exactly_7_days_boundary_succeeds`,
   `test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_
   untouched`) are unaffected — they assert the boundary itself
   (`timedelta(days=7)`, no margin), and the same clock skew runs in the
   direction that keeps them correct (Postgres's `now()` being earlier than
   the seed's reference time only makes a `resolved_at` computed from
   `python_now - 7d` look *more* recent from the DB's perspective, not less).

## Verified this pass (pre-`IMPLEMENTATION` — the expected red state)

```
uv run --no-sync ruff check tests/unit/modules/support/test_support_schemas.py \
  tests/unit/modules/support/test_support_service.py \
  tests/integration/modules/support/test_support_router.py \
  tests/integration/scripts/test_auto_close_resolved_tickets.py
  → All checks passed! (after fixing 2 RUF059 unused-unpacked-variable and
    2 E501 line-length findings raised by this pass's own first draft)

uv run --no-sync ruff format --check <same four files>
  → 4 files already formatted (after running ruff format on the 2 files it
    flagged)

python -m py_compile <same four files>
  → OK (no syntax errors), all four files

uv run --no-sync mypy <same four files>
  → 73 errors, all in the two expected categories below - zero errors of any
    other kind:
    (a) attr-defined: a not-yet-existing symbol/column (`InvalidStateTransitionError`,
        `_ALLOWED_EVENTS_BY_STATUS`, `SYSTEM_ACTOR_ID`, `TicketService.resolve_ticket`/
        `close_ticket`/`reopen_ticket`, `TicketRepository.auto_close_resolved_past_window`,
        `Ticket.resolved_at`/`resolution_note`/`closed_at`/`closed_by`,
        `*TicketRequest`/`TicketStateRead` schemas) — resolves once IMPLEMENTATION
        T1/T2/T4/T6 land the corresponding code.
    (b) arg-type on the `TicketReplyService(...)` fixture call (2 errors,
        test_support_service.py:589-590) — mypy correctly checks the fixture's new
        6-positional-argument call against the *current, not-yet-updated*
        5-argument constructor; resolves once T4 adds the `audit_service`
        parameter per Decision 3.
    (c) unused-ignore (4 errors, test_support_schemas.py) — the new schema
        classes resolve to `Any` via the unresolved import above, so the
        deliberately-invalid `ResolveTicketRequest(..., extra_field=...)`
        calls' `# type: ignore[call-arg]` currently suppress no real error;
        these become genuinely needed once T1 lands the real Pydantic classes
        with `extra="forbid"`.

uv run --no-sync python -m pytest --collect-only <same four files> -q
  → 3 collection ImportErrors (test_support_schemas.py: `CloseTicketRequest`;
    test_support_service.py: `InvalidStateTransitionError`;
    test_auto_close_resolved_tickets.py: `SYSTEM_ACTOR_ID`) — each names the
    first not-yet-existing symbol Python's import machinery reaches, exactly
    the expected TDD-red state. test_support_router.py collects successfully
    (100 tests) since it imports no new symbol at module scope — its new
    `/resolve`/`/close`/`/reopen` calls only fail at runtime (currently `404
    Not Found`, no such route), not at collection.
```

**Important for whoever runs `pytest`/`QUALITY_GATE` before `IMPLEMENTATION`
completes:** because `test_support_schemas.py`, `test_support_service.py`, and
`test_auto_close_resolved_tickets.py` are single Python modules, each ImportError
breaks collection of that **entire file**, including every pre-existing,
currently-shipped test in it (12 in schemas, 42 in service) — not only this
story's new cases. `test_support_router.py` is unaffected (collects in full;
its new tests fail at runtime instead). This is inherent to Python's
all-or-nothing module import, not a regression introduced by this pass, and
resolves automatically once `IMPLEMENTATION` T1 (`schemas.py`), T2
(`models.py`/`repository.py`), T4 (`service.py`/`exceptions.py`), and T6
(the new script) land the missing symbols. `gate-enforcer` (T7) runs only
after T1-T6 are all complete, by which point every import resolves.

## Coverage against the ac-test-matrix

Every row in `docs/tests/US-4.3-ac-test-matrix.md` names a test function that
actually exists in the working tree at the path given. `pytest --collect-only`
proves this directly only for `test_support_router.py` (its 100-test
collection lists every named function by name with no "not found" warning);
for the three files that fail at `import` time (`test_support_schemas.py`,
`test_support_service.py`, `test_auto_close_resolved_tickets.py`), the
`ImportError` happens before the module body executes, so collection itself
proves nothing about function names in those files. Verified instead by a
direct name diff:

```
grep -oE 'test_[a-z0-9_]+' docs/tests/US-4.3-ac-test-matrix.md | sort -u > named.txt
grep -hoE '^(async )?def test_[a-z0-9_]+' tests/unit/modules/support/test_support_schemas.py \
  tests/unit/modules/support/test_support_service.py \
  tests/integration/modules/support/test_support_router.py \
  tests/integration/scripts/test_auto_close_resolved_tickets.py \
  | grep -oE 'test_[a-z0-9_]+' | sort -u > defined.txt
comm -23 named.txt defined.txt
  → test_auto_close_resolved_tickets / test_matrix / test_support_router /
    test_support_schemas / test_support_service (all five are filename
    fragments the loose `test_[a-z0-9_]+` pattern also matched from the
    "File" column's paths, not real function-name mismatches)
```

Every actual `test_*` function name the matrix cites is present in `defined.txt`.
This pass added 59 new test functions (13 schemas + 21 service + 17 router +
8 script, matching the per-file deltas in "Files changed this pass" above),
not the 39 an earlier draft of this report miscounted. Every FR (FR-1 through
FR-10) and every source-native TC-AC the spec's own Traceability Matrix
carries forward (TC-AC1 through TC-AC9) has at least one correctly-labeled
test row — an earlier draft of the matrix mislabeled TC-AC3 as `TC-AC1 / FR-3`
and left TC-AC4/TC-AC9 unlabeled (`FR-4`/`FR-10` only); both are corrected in
the current `US-4.3-ac-test-matrix.md`. FR-5 (which the spec itself notes has
no covering source Acceptance Criterion) is covered the same way the spec
derives it — from the normative API Contract/State Machine table plus OD-3.

## Gaps carried forward (see ac-test-matrix's own "Gaps Not Covered" section)

1. API_DESIGN Open Questions #1 / DESIGN_REVIEW DR-5's undefined
   resolved-but-expired-not-yet-auto-closed response is tested as the
   documented `409`-fallthrough default, not as an open gap to resolve.
2. DR-6 (partial index `CREATE INDEX CONCURRENTLY`), DR-7 (`reason` field
   maxLength), and API_DESIGN Open Questions #4 (`reason`'s undefined
   purpose/persistence) remain carried, non-blocking, not test-writer's to
   resolve.
3. `scripts/auto_close_resolved_tickets.py`'s own `main()` wiring (its
   from-settings Postgres engine and Valkey client construction) is not
   directly exercised — see `US-4.3-test-strategy.md` Scope for why, matching
   `purge_unbound_attachments.py`'s own established test-file precedent.
4. `migrations/env.py`'s expected zero-diff and the new partial index's
   `CREATE INDEX CONCURRENTLY` reversibility are `migration-manager`'s (T3)
   concern, not duplicated here.

## Result

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.3
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.3-test-strategy.md
    - docs/tests/US-4.3-ac-test-matrix.md
    - docs/evidence/US-4.3-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "Test-writer's own collaborator-shape assumption: TicketReplyService.create_reply's FR-4 branch splits into two sub-cases (the ordinary 'waiting_on_customer' case stays on plain update(); only the 'resolved' reopening sub-case moves to transition_status(require_resolved_within_window=True)), diverging from implementation_plan.md's literal single-branch description. Necessary to avoid a real defect: applying the inclusive window guard to a NULL resolved_at (the waiting_on_customer case) would silently break FR-2, since NULL >= x is not true in SQL. Flagged for reconciliation-reviewer to confirm against the actual shipped branch shape. Full detail in US-4.3-test-strategy.md."
    - "EmailSender.send_ticket_resolved_email(*, to, ticket_number, resolution_note) is a new Protocol method FR-1 requires ('the requester is emailed the resolution note plus a link') that implementation_plan.md's Files To Modify table does not list - app/core/email.py is absent from that table entirely. This is a plan gap, not an invented requirement, matching US-4.1's own get_email_for_user precedent (docs/catalog/US-4.1-pipeline-status.md). service-and-router-builder must add this method to EmailSender/LoggingEmailSender."
    - "TicketReplyService.__init__'s new required audit_service parameter is assumed positioned right after rate_limit_cache, before email_sender, mirroring TicketService.__init__'s own ordering - no design doc fixes this literal position; a shipped different order needs only a fixture-call update, not a test-logic change."
    - "The 7-day window guard is DB-evaluated interval arithmetic and cannot be unit-tested directly (AGENTS.md §5) - unit tests simulate a lost window via FakeTicketRepository.transition_returns_none (standing in for 'the DB's own WHERE clause matched zero rows'); the real SQL predicate, including the exact-7-day boundary pairing (reopen's inclusive <= succeeds; auto-close's strict < does not fire on the identical row), is proven only at integration/script-test level."
    - "scripts/auto_close_resolved_tickets.py's own main() function (its from-get_settings() Postgres engine and Valkey client construction) is not directly exercised - TicketRepository.auto_close_resolved_past_window and the AuditLogService/RoleService composition it calls are tested directly instead, matching purge_unbound_attachments.py's own established test-file precedent (no fixture in this codebase threads the test container's ephemeral URLs through get_settings())."
    - "Adding imports for not-yet-built symbols to test_support_schemas.py, test_support_service.py, and test_auto_close_resolved_tickets.py breaks collection of those entire files, including the 12/42 pre-existing US-4.1/US-4.2 test functions, until IMPLEMENTATION T1/T2/T4/T6 land the missing symbols - expected, self-resolving, and accounted for by the task breakdown's own T1-T6-before-T7 ordering, not a regression. test_support_router.py is unaffected (collects in full; its new tests fail at runtime with 404 instead)."
    - "mypy --strict reports 2 arg-type errors on the TicketReplyService(...) fixture call (test_support_service.py:589-590) because it correctly checks against the CURRENT, not-yet-updated 5-argument constructor - resolves once IMPLEMENTATION T4 adds the audit_service parameter per Decision 3. Also reports 4 unused-ignore findings in test_support_schemas.py where the new schema classes currently resolve to Any via the unresolved import, making the deliberately-invalid extra_field type:ignore comments currently suppress no real error - these become genuinely needed once T1 lands the real extra='forbid' Pydantic classes."
    - "Self-caught before declaring PASS: _seed_ticket's status='closed'/'resolved' seeds would violate US-4.3-entity-model.md v3's two CHECK constraints once T3's migration lands (ck_tickets_closed_requires_closed_fields is a full biconditional; ck_tickets_resolved_requires_resolution_fields requires both fields together). This would have broken three pre-existing US-4.2 tests as an unintended regression from this story's own migration, not just new US-4.3 tests - impact-analyzer's blast-radius survey checked production code paths, not test seeders. Fixed once in _seed_ticket itself (defaults applied only when the caller omits the field explicitly)."
    - "Self-caught before declaring PASS: the first draft of US-4.3-ac-test-matrix.md mislabeled TC-AC3 as 'TC-AC1 / FR-3' and omitted the TC-AC4/TC-AC9 source AC ids from their rows (FR-4/FR-10 label only) - corrected. Also corrected this report's own 'Coverage against the ac-test-matrix' section, which had claimed the collection run 'located every function definition' in the three ImportError files - an ImportError fires before the module body executes, so it proves nothing about function names there; replaced with an actual name diff, and the miscounted 39-new-tests figure corrected to the actual 59."
    - "Observed, not corrected here: every upstream US-4.3 artifact this stage consumed (specification, api_design, database_design, design_review, impact_analysis, implementation_plan, task_breakdown, plan_review) carries front-matter status: DRAFT despite having passed its review and (for spec/plan) human-approval gate - artifact-lifecycle.md defines APPROVED as 'passed its review gate (and human gate where one exists)'. Does not violate any workflow invariant this stage checks (DRAFT is neither SUPERSEDED nor ARCHIVED, and the TODO/TBD/FIXME rule is scoped to APPROVED artifacts) and is project-wide, not specific to this story or this stage's own output - each artifact's status field is its producing skill's responsibility, not test-writer's or story-orchestrator's to correct in a /so:next."
    - "Self-caught before declaring PASS: three window-boundary integration tests (test_reopen_ticket_outside_window_returns_409, test_create_reply_customer_on_resolved_outside_window_makes_no_status_change, test_auto_close_resolved_past_window_closes_ticket_older_than_7_days) originally seeded resolved_at only 1 second past the 7-day cutoff, timed against datetime.now(UTC) rather than the DB's own frozen-per-transaction now() the real predicate is evaluated against - a margin narrower than fixture setup latency (password hashing) can plausibly be, risking a flaky failure against a correct implementation. Widened to a 5-minute margin; the two exact-boundary tests are unaffected (the clock-skew direction there is safe, per the report's own Self-review fixes section)."
```
