---
artifact_type: test_strategy
story: US-4.3
version: 2
status: ARCHIVED
created_at: "2026-09-06T23:00:00Z"
updated_at: "2026-09-07T03:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/impact-analysis/US-4.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.3-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.3-plan-review.md
    version: 1
supersedes: 1
---

# Test Strategy: Ticket Resolution (US-4.3)

## Rework (v2, attempt 2 — `IMPLEMENTATION` → `TEST_WRITING` via `changes_required_tests`)

`IMPLEMENTATION` (T1-T6 complete, 773/774 passing) found the two exact-7-day
boundary tests non-deterministically flaky: both seeded `resolved_at` from
Python's wall clock (`datetime.now(UTC) - timedelta(days=7)`), then compared
against Postgres's transaction-frozen `now()` at Act time — an outcome that
depends on real elapsed wall-clock time between Arrange and Act, not on the
implementation. Fixed by seeding `resolved_at` **server-side**, in the same
transaction, via `UPDATE ... SET resolved_at = func.now() -
func.make_interval(0, 0, 0, literal(7))` (a new `_seed_resolved_ticket_at_
exact_window_boundary` / `_seed_ticket_resolved_at_exact_window_boundary`
helper in each affected test file) instead of a Python-computed literal. Since
`db_session` runs each test's whole body in one transaction with
`transaction_timestamp()` frozen for its lifetime, the seed and the guard's
own predicate now read the identical frozen `now()` — the comparison is
deterministic in both directions, and the exact-boundary property being
proven (not just "comfortably inside/outside the window") is preserved. No
margin was widened. Verified: both named tests pass 5/5 in isolation and the
full 774-test repository suite passes (up from 773/774). No application code
changed. See "Window-guard testing split" below for the updated detail.

## Scope

Written **before** `IMPLEMENTATION` (T1-T6 have not run: `app/modules/support/
{models,repository,service,router,schemas,exceptions}.py` do not yet carry any
resolution-related symbol; `scripts/auto_close_resolved_tickets.py` does not
exist). Every test added this pass is written against the approved contract
(`US-4.3-openapi.yaml` v2, `US-4.3-entity-model.md` v3,
`US-4.3-implementation-plan.md` v1, `US-4.3-task-breakdown.md` v1) and is
expected to fail at collection/import time until `IMPLEMENTATION`'s T1-T6 land
— the intended TDD-red state, not a defect in this pass. Per this skill's own
Result Envelope contract, `PASS` requires only that every acceptance criterion
have a test function that exists and asserts its stated behavior — not that
application code exists yet.

## Unit vs. Integration split (`AGENTS.md` §5)

- **Unit** (`tests/unit/modules/support/test_support_service.py`, extended;
  `tests/unit/modules/support/test_support_schemas.py`, extended) —
  `TicketService.resolve_ticket`/`close_ticket`/`reopen_ticket`'s full
  check-order (lookup/ownership `404` → transition validity `409` →
  permission `403` → the conditional-update call → audit write → best-effort
  email), the `_ALLOWED_EVENTS_BY_STATUS` table asserted verbatim
  (implementation-plan Risk 2), the concurrency-loss path (a fake conditional
  update returning `None` → `409`, FR-9), each method's audit write, and the
  new `*TicketRequest`/`TicketStateRead` schemas' `extra="forbid"`/
  length-cap/data-minimization behavior. `TicketReplyService.create_reply`'s
  existing FR-4 branch is extended for DR-4's new `ticket_reopened` audit
  write and the new window-guarded conditional update.
- **Integration**
  (`tests/integration/modules/support/test_support_router.py`, extended) —
  `/resolve` (FR-1, FR-6, FR-7, FR-9, FR-10), `/close` (FR-2), `/reopen`
  (FR-5, FR-6), FR-4's now-modified `POST .../replies` behavior (both the
  audit write and the window-guard no-op case), the four-case authentication
  matrix (no token, malformed, expired, revoked) across all three new routes,
  and the dedicated exact-7-day boundary pairing (OD-4: the reopen guard's
  inclusive `<=` succeeds at exactly 7 days; the auto-close job's strict `<`,
  proven separately in the script test file, does not fire at that same
  instant) — no existing test in this codebase exercises this pairing.
- **New test surface**
  (`tests/integration/scripts/test_auto_close_resolved_tickets.py`, new) —
  `TicketRepository.auto_close_resolved_past_window`'s status/window
  predicates and idempotency (a DB-conditional-UPDATE concern, not
  unit-testable per `AGENTS.md` §5), plus one full-loop composition test
  proving the sentinel actor's empty role-grant list is a harmless path
  through `AuditLogService`/`RoleService` (DESIGN_REVIEW v3's own
  confirmation). The script's own `main()` (its own Postgres-engine and
  Valkey-client construction from `get_settings()`) is not separately
  exercised — consistent with `purge_unbound_attachments.py`'s own test file,
  which tests the repository method the script calls, not `main()` itself;
  `main()`'s wiring would need the test's ephemeral container URLs threaded
  through `get_settings()`, which no fixture in this codebase does today.

## Fixtures / fakes needed

- Unit: `FakeTicketRepository.transition_status(...)` (new — implements the
  real status-set check so tests can assert `expected_statuses`/`new_status`/
  window-guard kwargs; a `transition_returns_none` flag simulates "the DB's
  own WHERE clause matched zero rows," standing in for a real conditional
  UPDATE the fake cannot itself evaluate, mirroring
  `FakeAttachmentRepository.bind_returns_none`'s existing convention).
  `FakeEmailSender.send_ticket_resolved_email(...)` (new). `FakeAuditService`
  reused unchanged. All mutate/return real `app.modules.support.models.Ticket`
  ORM instances, matching this file's existing `mypy --strict`
  Protocol-covariance convention.
- Integration: existing `client`/`db_session` fixtures; `_seed_ticket`
  extended with optional `resolved_at`/`resolution_note`/`closed_at`/
  `closed_by` kwargs; new local path helpers `_resolve_path`/`_close_path`/
  `_reopen_path`; reuses `_seed_agent`/`_seed_session_and_token`/
  `_expired_token`/`_revoked_session_token`/`_auth_headers` verbatim.
- Script test: `AuditRepository`, `AuditLogService`, `RoleRepository`,
  `UserRoleRepository`, `RoleService`, `PermissionEpochCache` constructed
  directly against the test's own `db_session`/`app.state.valkey_client`
  (implementation-plan Decision 6's own class list), not the script's
  from-settings construction.

## Test-writer's own collaborator-shape assumptions (no design doc fixes these)

- `TicketService.resolve_ticket(*, ticket_id, actor_id, actor_kind,
  resolution_note) -> TicketStateRead`, `close_ticket(*, ticket_id, actor_id,
  actor_kind) -> TicketStateRead`, `reopen_ticket(*, ticket_id, actor_id,
  actor_kind) -> TicketStateRead` — keyword-only, matching `create_reply`'s
  established call shape.
- `TicketRepository.transition_status(...)` — the exact keyword signature
  implementation-plan.md Decision 2 states verbatim (`expected_statuses`,
  `new_status`, `resolved_at`, `clear_resolved_at`, `resolution_note`,
  `closed_at`, `closed_by`, `require_resolved_within_window`).
- **`TicketReplyService.create_reply`'s FR-4 branch splits into two
  sub-cases, not one.** The plan's own language describes a single
  `elif ticket.status in ("waiting_on_customer", "resolved"):` branch moving
  to `transition_status(..., require_resolved_within_window=True)` in its
  entirety. Applying the inclusive window guard
  (`resolved_at >= now() - interval '7 days'`) to the **`waiting_on_customer`**
  sub-case as well would attach that predicate to a row whose `resolved_at`
  is `NULL` — `NULL >= x` is `NULL`/false in SQL, so the row would never
  match and FR-2's ordinary customer-reply case would silently stop working.
  This suite therefore assumes the branch splits: `"waiting_on_customer"`
  keeps using plain `update()` (unaffected, no audit write); only the
  `"resolved"` sub-case moves to `transition_status(expected_statuses=
  ["resolved"], require_resolved_within_window=True, clear_resolved_at=True)`
  and gains the `ticket_reopened` audit write. Flagged for
  `reconciliation-reviewer` as a place the shipped code's actual branch shape
  must be checked against this assumption, not silently trusted.
- `TicketReplyService.__init__`'s new required `audit_service:
  AuditServiceProtocol` parameter (implementation-plan Decision 3) is
  positioned right after `rate_limit_cache` and before `email_sender` —
  mirroring `TicketService.__init__`'s own repos/caches-then-audit_service-
  then-optional-collaborators ordering. No design doc fixes this literal
  position.
- `EmailSender.send_ticket_resolved_email(*, to, ticket_number,
  resolution_note) -> None` — **a new `EmailSender` Protocol method FR-1's
  "the requester is emailed the resolution note plus a link" requires, but
  which `implementation_plan.md`'s Files To Modify table does not list**
  (`app/core/email.py` is absent from that table entirely). This is a plan
  gap, not an invented requirement — flagged in
  `US-4.3-test-generation-report.md`, matching US-4.1's own
  `get_email_for_user` precedent
  (`docs/catalog/US-4.1-pipeline-status.md`).
- `InvalidStateTransitionError(allowed_events: list[str])` — carries
  `.allowed_events` as a public attribute the test suite reads directly via
  `exc_info.value.allowed_events`, matching `TicketCreationRateLimitError`'s
  existing `.headers` attribute-exposure convention.

## `_ALLOWED_EVENTS_BY_STATUS` — one explicit table, tested per status (Risk 2)

`test_allowed_events_by_status_matches_the_plan_s_stated_table` asserts the
whole dict literal from `implementation_plan.md` Decision 4 in one test, and
every status value is additionally exercised through at least one
`InvalidStateTransitionError.allowed_events` assertion in the
transition-endpoint tests (`resolved`, `closed`, `open`,
`waiting_on_support`, `waiting_on_customer` all appear as a `status_before`
parametrization value across the resolve/close/reopen test groups).

## Window-guard testing split (AGENTS.md §5)

The 7-day window predicate is DB-evaluated interval arithmetic
(`implementation_plan.md` Decision 7) — a pure business-rule branch can only
be unit-tested by *simulating* the DB's answer, not by computing the real
comparison. This suite splits accordingly:

- **Unit** (`transition_returns_none=True`) — proves the *service's* reaction
  to a lost window/race (still `409`, with the pre-check `allowed_events`,
  not a re-fetched one — Risk 1's own documented fallthrough), without
  claiming to prove the SQL itself is correct.
- **Integration** — proves the *real* SQL predicate, including the one pairing
  no existing test in this codebase exercises: a ticket resolved at *exactly*
  the 7-day mark reopens successfully (inclusive `<=`,
  `test_reopen_ticket_at_exactly_7_days_boundary_succeeds`), while the
  auto-close job's own strict `<` predicate does *not* fire on that identical
  row (`test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_
  untouched`, in the script test file) — together proving OD-4's "the two
  predicates never both match the same row at the exact boundary instant."
  Both tests seed `resolved_at` server-side (v2 rework, above) so the
  comparison is deterministic rather than wall-clock-dependent.

## Known gaps — not tested here, and why

- **Two undefined-response gaps carried forward from `implementation_plan.md`
  Risk 1 / API_DESIGN Open Questions #1 / DESIGN_REVIEW DR-5** — a
  `"resolved"` ticket outside the 7-day window but not yet auto-closed
  produces the same `409` a genuine concurrency-race loser gets. This suite
  tests that this *is* the documented behavior
  (`test_reopen_ticket_outside_window_returns_409`,
  `test_create_reply_customer_on_resolved_outside_window_makes_no_status_
  change`) rather than treating it as an open question to resolve — consistent
  with `implementation_plan.md`'s own framing ("a defensible default", not
  something this pass may silently redecide).
- **`_ALLOWED_EVENTS_BY_STATUS`'s `"reason"` field on `/close`/`/reopen`**
  (`US-4.3-api-design.md` Open Questions #4) — accepted but unconstrained,
  with no stated purpose, persistence, or audit-log visibility. This suite
  tests only that the field is *accepted* (`CloseTicketRequest`/
  `ReopenTicketRequest` schema tests, and one integration case passing
  `reason` through `/close`); it does not assert the value is persisted or
  audited anywhere, since no FR states either.
- **`scripts/auto_close_resolved_tickets.py`'s own `main()` function** — not
  directly exercised (see Scope above); its only logic beyond wiring
  (`TicketRepository.auto_close_resolved_past_window` + one
  `AuditLogService.record_event` per id + one commit) is proven by
  `test_auto_close_job_writes_one_ticket_auto_closed_audit_row_per_ticket`
  against the same real collaborators the script itself constructs.
- **`migrations/env.py`'s expected zero-diff** (implementation-plan Risk 4) —
  `migration-manager`'s own confirmation, not a test-writer concern.
- **`CREATE INDEX CONCURRENTLY` mechanics for the new partial index** (DR-6,
  carried non-blocking) — `migration-manager`'s own concern against
  `AGENTS.md` §4, not duplicated here.

## Coverage floor

85% minimum overall, 90%+ on `support/service.py` and `support/router.py`, per
`AGENTS.md` §5/§6 and the implementation plan's own Validation Strategy — no
exclusion for the new audit-write branch or the script's Valkey-wiring path
(Risk 6) — enforced by `gate-enforcer`, not measured by this stage.
