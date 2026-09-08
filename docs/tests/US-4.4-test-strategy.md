---
artifact_type: test_strategy
story: US-4.4
version: 2
status: DRAFT
created_at: "2026-09-07T17:07:56Z"
updated_at: "2026-09-07T19:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.4-plan-review.md
    version: 1
supersedes: null
---

# Test Strategy: Agent Ticket Queue & Assignment (US-4.4)

**Track:** backend. Tests were written directly into the two existing files
`AGENTS.md`'s "tests mirror app/" convention already names for this module
— no new test files, per `impact-analyzer`'s and `implementation_plan.md`'s
own confirmation that this story adds no new module:

- `tests/unit/modules/support/test_support_service.py`
- `tests/integration/modules/support/test_support_router.py`

This stage runs **before** `IMPLEMENTATION` (per `stage-map.yaml`'s
`TEST_WRITING -> IMPLEMENTATION` order). None of the symbols these tests
reference — `AgentTicketRead`/`AgentTicketListResponse`/`AgentTicketStateRead`/
`AssignTicketRequest` (schemas), `Ticket.assignee_id` (model),
`list_for_agent_queue`/`assign_ticket`/`unassign_ticket` (repository),
`TicketService.list_agent_queue`/`assign_ticket`/`unassign_ticket`,
`RoleServiceProtocol` (service), `AssignmentConflictError` (exceptions) —
exist yet. This is the same state US-4.3's own test-writing pass was in
(its unit tests referenced `EmailSender.send_ticket_resolved_email` before
that method existed) and is expected: these tests will fail to import/
collect until `IMPLEMENTATION`'s T1-T9 land, at which point they become the
executable proof the story asserts.

## Collaborator-shape assumptions (test-writer's own, not fixed by any design
## artifact — `IMPLEMENTATION` should match these, and any different real
## choice should update this file, not silently diverge from it)

No design artifact fixes these literal names/signatures; the plan and task
breakdown name some of them precisely and leave others open. Where a name is
explicit in `implementation_plan.md`/`task_breakdown.md`, it is used
verbatim; where it is not, the choice below is this stage's own and is
recorded here so a reviewer can see exactly what was assumed.

- **Repository** (`TicketRepositoryProtocol` growth — names fixed by the
  plan): `list_for_agent_queue(*, cursor, limit, status=None, category=None,
  assignee_id: uuid.UUID | Literal["none"] | None = None) -> TicketListPage
  | None`, `assign_ticket(ticket_id, *, new_assignee_id,
  expected_assignee_id) -> Ticket | None`, `unassign_ticket(ticket_id) ->
  Ticket | None`.
  - **Corrected at `QUALITY_GATE` loop-back (attempt 2):** this stage's
    original draft assumed a two-parameter `assignee_id`/`unassigned_only`
    shape (see below) instead of the single-sentinel shape the real
    implementation built. `gate-enforcer` confirmed `app/modules/support/
    repository.py`'s real `list_for_agent_queue` and `service.py`'s
    `TicketRepositoryProtocol` declaration both use the single-parameter
    shape recorded above, with no production defect — only
    `FakeTicketRepository` and five assertions in
    `test_support_service.py` needed to be brought into line with it. The
    superseded assumption, kept here for the record: `assignee_id`/
    `unassigned_only` as two independent parameters, not a single sentinel
    value — the *service*, not the repository, would resolve the query
    string `"me"`/`"none"`/a UUID into these two booleans-plus-value. The
    real shape instead has the service resolve `"me"`/`"none"`/a UUID into
    **one** value — a real `UUID`, the literal sentinel `"none"`
    (unassigned filter), or `None` (filter absent) — and pass that single
    value through.
  - `list_for_agent_queue` reuses the existing `TicketListPage` NamedTuple
    (`items: list[Ticket]`, `next_cursor: str | None`) verbatim rather than
    a new page type — the item shape (`Ticket` ORM rows) is identical to
    `list_for_requester`'s; only the filters/ordering differ.
  - `assign_ticket`/`unassign_ticket` follow `transition_status`'s existing
    `Ticket | None` idiom (`None` = zero rows affected by the conditional
    `UPDATE`) and both must include `updated_at=Ticket.updated_at` in their
    `.values()` per `implementation_plan.md` Architectural Change #9 (DR-3)
    — this is exercised at the integration layer only (see below).
- **Service** (names fixed by the plan): `TicketService.assign_ticket(*,
  ticket_id, actor_id, actor_scopes, assignee_id) -> AgentTicketStateRead`
  and `TicketService.unassign_ticket(*, ticket_id, actor_id, actor_scopes)
  -> AgentTicketStateRead`. The agent-queue listing method's name is *not*
  fixed by the plan ("a new TicketService method... parallel to
  list_own_tickets") — this stage names it `list_agent_queue(*, agent_id,
  status, category, assignee_id, cursor, limit) -> AgentTicketListResponse`.
  `actor_scopes: list[str]` (not `actor_kind: str`) is passed because FR-7's
  check is a genuine three-way split (no `tickets:*` -> 404; `tickets:read`
  only -> 403; `tickets:write` -> proceed) that `resolve_actor_kind`'s
  existing two-value vocabulary (`"customer"` / `"agent"`) cannot express.
- **New collaborator** `RoleServiceProtocol` (`support/service.py`,
  Architectural Change #4): `resolve_scopes_for_user(user_id: uuid.UUID) ->
  list[str]`, confirmed against the real
  `app.modules.roles.service.RoleService.resolve_scopes_for_user`
  (`app/modules/roles/service.py:94`). `TicketService.__init__` gains this
  as a new required parameter — this stage's own assumption places it
  immediately after `user_service` and before `email_sender` in the
  constructor's argument order; the unit-test fixture
  (`_make_service`) was updated accordingly, and pre-existing call sites
  that fully unpacked its return tuple by position were widened by one
  trailing placeholder rather than reordered, so every other existing
  US-4.1/US-4.2/US-4.3 unit test in the file keeps passing unmodified.
  **Corrected at `QUALITY_GATE` loop-back (attempt 2):** the original pass
  fixed two such call sites but missed two more —
  `test_create_ticket_happy_path_writes_audit_event_and_queues_email`
  (a fixed-name unpack of only 8 elements against the fixture's real
  9-element return, raising `ValueError: too many values to unpack`) and
  `test_create_ticket_no_email_on_file_skips_dispatch_without_failing`
  (a `*_, email_sender = _make_service(...)` unpack that, once
  `role_service` became the tuple's new trailing element, silently rebound
  `email_sender` to the fake `RoleService` instead). Both are now fixed the
  same way: a trailing `_` placeholder added for `role_service`.

## Unit tests (`tests/unit/modules/support/test_support_service.py`)

**New fakes:**
- `FakeRoleService` — `resolve_scopes_for_user` keyed by user id
  (`scopes_by_user` dict, default `[]`), mirroring the real
  `RoleService`'s own "no roles -> `[]`" fallthrough.
- `FakeTicketRepository` grows three methods (`list_for_agent_queue`,
  `assign_ticket`, `unassign_ticket`) with call-recording lists and
  configurable `assign_returns_none`/`unassign_returns_none` flags standing
  in for "the DB's own conditional `UPDATE` matched zero rows" — the same
  convention `transition_returns_none` already established for
  `transition_status`.
- `FakeUserService.get_account_status_for_user` gained call-recording
  (`status_calls`) and a per-user override map (`account_status_by_user`)
  — OD-4's check runs against the assign **target**'s id, not the caller's
  own, so the fake must be able to answer for an arbitrary id, not just
  return one fixed default.
- `_make_ticket` gained an `assignee_id` kwarg, initialized explicitly (not
  left unset) for every ticket the file builds — same "fail on an
  assertion, not an `AttributeError`, before `IMPLEMENTATION` lands"
  rationale the file already applies to `resolved_at`/`closed_at`/etc.

**Cases covered** (business-rule branches only — no DB, no HTTP):
- Agent-queue listing: filter/cursor/limit pass-through, `assignee_id`
  presence on returned items, `"me"`/`"none"`/UUID-string resolution,
  malformed `assignee_id`/cursor/out-of-range `limit` -> 422.
- `assign_ticket`: happy path + audit + commit, self-assign, re-assign
  (replaces + re-audits), 404-before-403 permission gate (parametrized
  across both `assign_ticket`/`unassign_ticket`), unknown-ticket 404,
  closed-ticket 409 (parametrized across both operations), target-lacks-
  scope 422, target-deactivated 422 (OD-4), concurrency-loss 409
  (`AssignmentConflictError`), commit-exactly-once.
- `unassign_ticket`: happy path + audit + commit, idempotent no-op success
  (audit-count is deliberately **not** asserted for the no-op case — API
  design's own Open Questions #5 leaves whether a repeat call writes a
  fresh audit entry undecided; asserting either way would invent scope no
  artifact states).

**What stays out of unit scope, deliberately:** the DR-3 `updated_at`-
preservation proof. A hand-written fake has no SQLAlchemy `onupdate`
mechanics — a fake-backed unit test would pass identically whether or not
the real repository method includes `updated_at=Ticket.updated_at` in its
`.values()`, per `implementation_plan.md`'s own explicit warning. That proof
is integration-only (below).

## Integration tests (`tests/integration/modules/support/test_support_router.py`)

**Seeder changes:**
- `_seed_ticket` gained `category`, `assignee_id`, and `updated_at` kwargs.
  `updated_at` is load-bearing beyond DR-3: `Ticket.updated_at` carries
  `server_default=func.now()`, frozen for the lifetime of one transaction
  (`AGENTS.md` §5) — AQ-AC1's "oldest-updated first" ordering assertion
  requires explicit, distinct values or it silently degrades to
  primary-key tiebreak.
- `_seed_agent_only` — a `support_agent`-role user with no session/token,
  for use purely as an assign **target** referenced by id in a request
  body (reuses `_seed_user` + `_assign_role`, mirrors `_seed_agent` minus
  the unneeded token).
- `_assign_path(ticket_id)` — the new `/{id}/assign` path helper, alongside
  the file's existing `_resolve_path`/`_close_path`/`_reopen_path`.

**Cases covered:**
- **AQ-AC1/AQ-AC2** (agent queue): ordering by explicit distinct
  `updated_at`, default exclusion of `closed`, `status=closed` explicit
  inclusion, `category` filter, `assignee_id=me`/`=none`/a specific UUID,
  malformed `assignee_id` -> 422, cursor pagination (two pages, disjoint
  item sets), every agent-branch item's field set is exactly
  `TicketRead`'s nine fields plus `assignee_id`.
- **AQ-AC5/AQ-AC6** (customer branch untouched): a customer's item field
  set is exactly `TicketRead`'s nine fields (never `assignee_id`) —
  byte-identical field-set assertion, not "no `assignee_id` key present"
  (`implementation_plan.md` Risk 1's own distinction) — and a customer's
  result set is unaffected by agent-only query params, with no `422` for a
  malformed agent-only `assignee_id` value on that branch.
- **`test_list_own_tickets_agent_scope_caller_returns_403`** (the sole
  existing test asserting the retired `403`) is **updated in place**, not
  deleted, to assert the new agent-branch `200` — per the spec's own NFR,
  `implementation_plan.md` Risk 7, and `task_breakdown.md` T9's explicit
  instruction that this diff be confirmed. Every other pre-existing
  customer-branch test in this file (newest-first ordering, malformed-
  cursor 422, the four `401` cases) is left unmodified — regression
  coverage by omission, not re-asserted here.
- **AQ-AC3/AQ-AC4** (assign/unassign happy paths): `200` + persisted
  `assignee_id` + audit row in the same request (asserted via a
  post-response `db_session` read, proving the write and the audit share
  one transaction), re-assign replaces the assignee and writes exactly one
  `ticket_assigned` audit row for that call, self-assign, unassign clears
  and audits, unassign-already-unassigned is idempotent `200`.
  **Corrected at `QUALITY_GATE` loop-back (attempt 2):** the re-assign test
  seeds its ticket with an assignee directly (no prior `assign_ticket`
  service call), so no audit row exists before the test's single `POST
  /assign` call — `gate-enforcer` confirmed `TicketService.assign_ticket`
  writes exactly one `ticket_assigned` row per call
  (`app/modules/support/service.py`'s `assign_ticket`, ~lines 561-568), so
  the test now asserts 1 row, not 2.
- **AQ-AC7** (permission split): a customer gets `404` for an existing
  ticket **and** an unknown one with an **identical response body**
  (the indistinguishability AQ-AC7 itself requires); a `tickets:read`-only
  agent gets `403 insufficient-permission`; both checked on `assign` and
  `unassign` independently.
- **AQ-AC8/OD-4** (target validation): a target with no `tickets:write` ->
  `422`, with the ticket's `assignee_id` confirmed still `None` afterward;
  a target holding `tickets:write` but a **deactivated** account -> `422`
  (OD-4's adopted default — flagged not-yet-human-confirmed, see Open
  Decisions below).
- **AQ-AC9 / OD-3** (closed-ticket `409`): `assign` on a closed ticket, and
  `unassign` on a closed ticket (OD-3's adopted default), each asserted
  independently with the ticket's `assignee_id` unchanged afterward.
- **AQ-AC10** (concurrency): `test_assign_ticket_repository_conditional_update_rejects_stale_expected_value`
  drives `TicketRepository.assign_ticket` directly, twice, both calls
  carrying `expected_assignee_id=None` — the exact condition FR-10
  describes (two agents who both read the ticket as unassigned before
  either wrote). The first call's conditional `UPDATE` matches and wins;
  the second's stale `expected_assignee_id` no longer matches the
  now-assigned row, so it returns `None` (zero rows affected). See the
  "Concurrency-test mechanism" note below for why this repository-direct
  approach was chosen over an HTTP-level `real_client`+`db_session` race.
  The `None` -> `409 assignment-conflict` mapping itself is proven at the
  unit layer (`test_assign_ticket_concurrency_loss_raises_409_assignment_conflict`).
- **DR-3** (`updated_at` preservation): a ticket seeded with an explicit,
  distinct **past** `updated_at`, asserted byte-identical after a
  successful `assign` and, in a second case, after a successful `unassign`
  — the concrete, determinate proof `design-reviewer` flagged as
  impossible to write before `implementation_plan.md`'s Architectural
  Change #9 resolved it.
- **Auth matrix** (`AGENTS.md` §5): a `2 (POST/DELETE) x 4
  (no-token/malformed/expired/revoked)` parametrized matrix on
  `/{id}/assign`, all asserting `401` — the file's existing
  `test_transition_endpoints_auth_matrix_returns_401` pattern, reused
  verbatim. The fifth §5-required case, "insufficient permissions", is
  covered by the dedicated `403` tests above rather than folded into this
  matrix (matching how this file already separates the two concerns for
  `resolve`/`close`/`reopen`).
- **Index coverage** (Enforcement Matrix `[gate]`, DR-1): an `EXPLAIN`
  assertion, under `SET LOCAL enable_seqscan = off`, that the default
  (filterless) agent-queue query's plan names
  `ix_tickets_queue_default_updated_at_id`. DR-1's actual claim is that the
  partial index is *usable* for the literal `status != 'closed'` predicate
  (survives PostgreSQL's predicate-implication check), not that it is the
  planner's cheapest choice on whatever data happens to exist when the
  test runs — on a near-empty `tickets` table a plain "no Seq Scan"
  assertion (the form `tests/integration/modules/audit/test_audit_router.py`'s
  `test_list_audit_logs_pagination_uses_indexed_scan_not_full_sort` uses)
  would fail against a perfectly correct implementation, since a sequential
  scan is genuinely cheaper on an empty heap. Disabling `enable_seqscan`
  removes that confound: if the index were not usable for this predicate,
  PostgreSQL would still fall back to a Seq Scan (disabling one plan never
  makes the planner error), so the index's name actually appearing in the
  plan is the real, discriminating proof.

### Concurrency-test mechanism (AQ-AC10)

An HTTP-level `real_client` + `db_session` race — this project's
established pattern for `test_refresh_concurrent_requests_exactly_one_succeeds`
and `test_password_reset_confirm_concurrent_same_token_exactly_one_succeeds`
(`tests/integration/modules/users/test_users_router.py`) — was considered
and rejected for `assign`. `db_session`'s fixture installs its session
override on `app.dependency_overrides` **process-wide** for the test's
duration, so `real_client`'s two requests share one session/transaction
and execute *serially*, not concurrently. That serialization is harmless
for the two existing precedents because their guard is a **consumed-state**
check (a second reader sees "already consumed" and is rejected outright).
`assign`'s guard is different: it is an **optimistic-expected-value** check
that the API design deliberately generalized to cover re-assignment
(`US-4.4-api-design.md`'s "Concurrency Design" — "scoped to whatever
`assignee_id` value was just read"). Under serialized execution, the second
call's own `get_by_id` read would see the *first* call's already-committed
`assignee_id`, adopt that as its own `expected` value, and its conditional
`UPDATE` would then also match and succeed — yielding `[200, 200]`, not
`[200, 409]`, against a perfectly correct implementation. An HTTP-level
version of this test would therefore be flaky-to-wrong, not merely
imprecise.

`test_assign_ticket_repository_conditional_update_rejects_stale_expected_value`
avoids this by driving `TicketRepository.assign_ticket` directly, real
PostgreSQL, no mocking: both calls pass `expected_assignee_id=None` (both
"read" the ticket as unassigned before either wrote), so the second call's
`expected` value is genuinely stale by the time it executes — the exact
race FR-10 describes, made deterministic rather than timing-dependent. The
`None` return -> `AssignmentConflictError` mapping is separately proven at
the unit layer. Together the two give complete, deterministic AQ-AC10
coverage without needing a second real PostgreSQL connection, which this
project's test harness (`tests/conftest.py`) has no fixture for.

## Coverage floor

`AGENTS.md` §5: 85% overall, 90%+ for `service.py`/`router.py` — a floor
`gate-enforcer` checks at `IMPLEMENTATION`'s close, not verified here since
no implementation exists yet to measure.

## Open Decisions carried into these tests (not resolved here)

Per `docs/decisions/US-4.4-open-decisions.md` (v1) and the spec's own Open
Questions, OD-1 through OD-4 are logged, not-yet-human-confirmed Open
Decisions whose **recommended defaults** were already adopted by every
upstream artifact this stage consumed (spec FR text, API design, DB design,
implementation plan, plan review — all PASS/APPROVED against the same
defaults). This stage follows suit rather than blocking on them, consistent
with `docs/workflow/artifact-lifecycle.md`'s definition of `BLOCKED`
("a mandatory input is missing or stale" — none is) and with
`stage-map.yaml`'s `invalid_*` loop-back keys being reserved for an
upstream artifact that is *untestable* as written (none of OD-1..OD-4 is:
each has a determinate adopted default a test can assert against). The
report below names the exact test functions that would need to change if a
default is reversed at `HUMAN_SPEC_APPROVAL`.
