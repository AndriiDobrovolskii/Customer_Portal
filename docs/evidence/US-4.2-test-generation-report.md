---
artifact_type: test_generation_report
story: US-4.2
version: 3
status: ARCHIVED
created_at: "2026-09-05T17:00:00Z"
updated_at: "2026-09-05T22:45:00Z"
produced_by: test-writer
inputs:
  - path: docs/tests/US-4.2-test-strategy.md
    version: 3
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
supersedes: docs/evidence/US-4.2-test-generation-report.md (v2)
---

# Test Generation Report: Ticket Replies (US-4.2)

## Why this pass ran (TEST_WRITING, HUMAN_REDIRECTED re-entry, attempt 2)

`story-orchestrator` routed `IMPLEMENTATION` → `TEST_WRITING` via
`HUMAN_REDIRECTED` (`docs/workflow/history.jsonl`, 2026-09-05T22:30:00Z),
resolving `migration-manager`'s T4 `BLOCKED` verdict
(`docs/catalog/US-4.2-pipeline-status.md` v3, T4 section): once
`tests/conftest.py` began serving requests through the new non-superuser
`app_runtime` role, `test_support_router.py`'s `_seed_reply()` helper's
internal-visibility inserts started genuinely violating
`ticket_replies_write`'s `WITH CHECK` policy (previously silently bypassed
by the superuser role) in three tests: `test_internal_reply_hidden_from_
customer_context_by_rls_alone`, `test_agent_context_sees_internal_reply_
via_rls`, `test_no_actor_kind_set_defaults_to_hiding_internal_reply`.

## Files changed this pass (v3)

`tests/integration/modules/support/test_support_router.py` only — the three
named tests' Arrange blocks. Each now runs `await db_session.execute(text(
"SET LOCAL app.actor_kind = 'agent'"))` before seeding its internal-
visibility reply; `test_no_actor_kind_set_defaults_to_hiding_internal_reply`
additionally runs `await db_session.execute(text("RESET app.actor_kind"))`
immediately after seeding, before its Act phase, so the seeding GUC does not
persist forward into the Act SELECT (`SET LOCAL` lasts for the rest of the
transaction, not just the statement — this fixture's test body is one
savepoint-based transaction never rolled back mid-test). No test function
was added, removed, or renamed; no other file changed.

**Verification (actually run, this pass):**
- The three named tests, run together: `3 passed`.
- Full `tests/integration/modules/support` suite: `35 failed, 29 passed`
  (was `38 failed, 26 passed` before this fix) — exactly the three RLS tests
  moved from failed to passed; the other 35 failures are the pre-existing,
  expected `T5`/`T6`-pending red state (routes not yet built), unchanged.
- Full non-`support` integration suite: `261 passed` — unchanged, zero
  regression from this file's edit.
- `ruff check`/`format` and `mypy --strict` on the changed file: clean.

## Why this pass ran (TEST_WRITING, re-entry)

`story-orchestrator` advanced from `HUMAN_PLAN_APPROVAL` (attempt 2 —
human-approved `implementation_plan` v2 / `task_breakdown` v2 / `plan_review`
v2, `docs/workflow/history.jsonl` 2026-09-05T21:15:00Z) back to
`TEST_WRITING`. v1 of this report (2026-09-05T17:00:00Z) ran against
`implementation_plan` v1/`task_breakdown` v1/`plan_review` v1, before the
`IMPLEMENTATION` → `HUMAN_REDIRECTED` → `ARCHITECTURE_PLANNING` loop
(2026-09-05T18:30:00Z) added Architectural Change #12 (dedicated
non-superuser `app_runtime` role). This pass re-verifies the existing suite
against the current plan chain rather than regenerating it — see "Files
changed this pass" below.

## Files changed this pass

None. `implementation_plan` v2's own Testing Strategy section states the
unit suite is "unaffected by v2" and the integration suite needs "no test
rewrite" — the runtime-role change is infrastructure (which role serves a
DB connection), not AC-observable behavior. Verified directly: grepping
`^(async )?def test_` against the three files this story owns returns 60
(`tests/integration/modules/support/test_support_router.py`), 42
(`tests/unit/modules/support/test_support_service.py`), and 12
(`tests/unit/modules/support/test_support_schemas.py`) — identical to v1's
reported 22+38=60 / 12+30=42 / 12 counts. The three direct-RLS tests
(`test_internal_reply_hidden_from_customer_context_by_rls_alone`,
`test_agent_context_sees_internal_reply_via_rls`,
`test_no_actor_kind_set_defaults_to_hiding_internal_reply`) are confirmed
still present at their v1 line locations. `docs/tests/US-4.2-test-strategy.md`
and `docs/tests/US-4.2-ac-test-matrix.md` are re-stamped to v2 (provenance
refresh plus a Revision Note each); this file becomes v2 for the same
reason.

## v1 record (unchanged content, retained below)

### Why the v1 pass ran (TEST_WRITING, attempt 1)

`story-orchestrator` advanced from `HUMAN_PLAN_APPROVAL` (human-approved
`implementation_plan` v1 / `task_breakdown` v1 / `plan_review` v1,
`docs/workflow/history.jsonl` `2026-09-05T16:30:00Z`) to `TEST_WRITING`.
`IMPLEMENTATION` (T1-T5: `schema-builder`, `data-layer-builder`,
`migration-manager`, `service-and-router-builder`) has not yet run — no
reply-related symbol exists anywhere in `app/modules/support/` or
`app/core/{email,config,cache_keys}.py` yet.

### Files changed this pass (v1)

- `tests/unit/modules/support/test_support_schemas.py` (new) — 12 test
  functions covering `CreateReplyRequest`'s `extra="forbid"`/length-cap/
  defaulting behavior and `ReplyRead`/`ReplyThreadPage`/`TicketDetailRead`'s
  `from_attributes=True` and explicit-construction shape.
- `tests/unit/modules/support/test_support_service.py` (extended) — added
  `FakeTicketReplyRepository`, `FakeTicketReplyRateLimitCache`, a
  `_make_reply_service` builder, and 30 new test functions (2 parametrized:
  ×2, ×3) covering `TicketReplyService.create_reply`/`.get_ticket_detail`.
  Additive-only changes to the existing fakes (`FakeTicketRepository.update`,
  `FakeAttachmentRepository.bind_to_reply`,
  `FakeEmailSender.send_ticket_reply_notification`/
  `.send_ticket_reply_queue_notification`) — the 12 pre-existing
  `TicketService`/`create_ticket`/`list_own_tickets` tests are unchanged and
  do not call any of the new members.
- `tests/integration/modules/support/test_support_router.py` (extended) —
  added `_seed_ticket`, `_seed_reply`, `_reply_payload`, `_seed_agent` helpers
  and 38 new test functions (3 parametrized) covering both new routes
  end-to-end: TR-AC1 through TR-AC7, the four-case authentication matrix on
  both routes, the reply rate limit and its independence from ticket
  creation's, all attachment-IDOR cases, GET pagination, three direct RLS
  tests, and a statement-count-independence test for the reply thread.
- `docs/tests/US-4.2-test-strategy.md`, `docs/tests/US-4.2-ac-test-matrix.md`,
  this file — new, v1.

No application code changed — test files and this stage's own three
artifacts only, per this skill's own scope constraint.

### Design choice this pass made (not fixed by any upstream artifact)

`docs/plans/US-4.2-implementation-plan.md` Architectural Change #4 explicitly
leaves the service's file-internal split open ("new method(s) on
`TicketService` ... or a new `TicketReplyService` ... final split is
`service-and-router-builder`'s call"). This pass writes against a **new
`TicketReplyService` class** with its own five-argument constructor
(`ticket_repository, reply_repository, attachment_repository,
rate_limit_cache, email_sender`), and a single `actor_kind:
Literal["customer", "agent"]` parameter reused for both the RLS-derivation
purpose (implementation-plan §2's `tickets:write` check) and each route's own
authorization branch. This choice was made specifically so this pass adds
**zero** risk to the 12 already-shipped `TicketService` unit tests — no shared
constructor, no touched fake. Full detail and the exact assumed method
signatures are recorded in `US-4.2-test-strategy.md`'s "Shipped-contract
assumption" section. If `service-and-router-builder` ships a different shape,
a reconciliation `TEST_WRITING` pass updates this suite the same way
US-4.1's v2 pass reconciled `test_support_service.py` against its own shipped
collaborator shapes (`docs/tests/US-4.1-test-strategy.md` "Scope (v2)") — this
is expected, not a defect in this pass.

### Verified this pass (pre-`IMPLEMENTATION` — the expected red state, v1)

```
uv run --no-sync ruff check tests/unit/modules/support/test_support_schemas.py \
  tests/unit/modules/support/test_support_service.py \
  tests/integration/modules/support/test_support_router.py
  → All checks passed!

uv run --no-sync ruff format --check <same three files>
  → 3 files already formatted

python -m py_compile <same three files>
  → OK (no syntax errors)

uv run --no-sync python -m pytest --collect-only <same three files> -q
  → 3 errors during collection, all ImportError against not-yet-built
    application symbols:
    - test_support_schemas.py: cannot import name 'TicketReply' from
      app.modules.support.models
    - test_support_service.py: cannot import name
      'InsufficientPermissionError' from app.modules.support.exceptions
    - test_support_router.py: cannot import name 'TicketReply' from
      app.modules.support.models
```

**Important for whoever runs `pytest`/`QUALITY_GATE` before `IMPLEMENTATION`
completes:** because `test_support_service.py` and `test_support_router.py`
are single Python modules, adding an import for a not-yet-built symbol at
module scope breaks collection of the **entire file**, including the 12
pre-existing, currently-shipped `TicketService` tests in
`test_support_service.py` and the 22 pre-existing `test_support_router.py`
tests — not only the new US-4.2 cases. This is inherent to Python's
all-or-nothing module import, not a regression introduced by this pass, and
resolves itself automatically once `IMPLEMENTATION` T1 (`schemas.py`), T2
(`models.py`/`repository.py`/`cache.py`), and T4
(`service.py`/`exceptions.py`) land the missing symbols. `gate-enforcer`
(T6) runs only after all of T1-T5 are complete, by which point every import
in both files resolves — the task breakdown's own ordering already accounts
for this.

### Coverage against the ac-test-matrix (v1)

Every row in `docs/tests/US-4.2-ac-test-matrix.md` names a test function that
exists in the working tree at the path given, verified by the collection run
above (the ImportErrors are at module-import time, after Python has already
parsed and located every function definition — a typo'd or missing function
name would instead surface as a `pytest` collection warning/error naming that
specific function, which did not occur). TR-AC1 through TR-AC7 each have both
a unit-level and an integration-level test; the two flagged
`non_blocking_findings` carried in `docs/workflow/workflow-state.yaml` (API_
DESIGN OQ-1's no-op branch, the NFR's RLS-bypass test) and Risk 6 (rate-limit
key independence) are each covered by name — see the ac-test-matrix's own
rows for API_DESIGN OQ-1, the RLS tests, and
`test_ticket_reply_rate_key_never_collides_with_ticket_create_rate_key`.

### Gaps carried forward (see ac-test-matrix's own "Gaps Not Covered" section, v1)

1. API_DESIGN OQ-2's exact `POST`-side "agent-shaped but missing
   `tickets:write`" combination has no integration-level test — genuinely
   unreachable under the shipped role seed. Unit-covered only.
2. The RLS DDL's own `upgrade → downgrade → upgrade` reversibility is
   `migration-manager`'s (T3) responsibility, not this suite's.
3. `migrations/env.py`'s expected zero-diff (implementation-plan Risk 4) is
   `migration-manager`'s own confirmation.

All three gaps are unchanged in v2 — none is affected by Architectural
Change #12.

## Result (v2)

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.2
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.2-test-strategy.md
    - docs/tests/US-4.2-ac-test-matrix.md
    - docs/evidence/US-4.2-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "Re-entry pass, no test file changed: implementation_plan/task_breakdown/plan_review advanced v1->v2 (Architectural Change #12, app_runtime role) while this story sat at TEST_WRITING through an IMPLEMENTATION->ARCHITECTURE_PLANNING->...->HUMAN_PLAN_APPROVAL loop. implementation_plan v2's own Testing Strategy section states the change is infrastructure-only (unaffected unit suite, no integration rewrite) - verified this pass by grep count match (60/42/12) against v1's reported figures. test_strategy/ac_test_matrix/test_generation_report bumped to v2 for provenance only."
    - "implementation_plan v2 Risk 7 / Testing Strategy adds a full-suite regression re-run requirement (every other module's existing integration tests, once tests/conftest.py serves app_runtime) as proof the new role's GRANT list is complete. This is task_breakdown v2 T4/T7's (migration-manager / gate-enforcer) responsibility to execute and evidence, not new test-writer content - flagged here for traceability only."
    - "Test-writer's own collaborator-shape assumption (carried from v1): a new TicketReplyService class (not new methods on TicketService), with actor_kind: Literal['customer','agent'] reused across both create_reply and get_ticket_detail, derived per implementation-plan Architectural Change #2's tickets:write check for both routes. implementation-plan Architectural Change #4 explicitly leaves this split open - service-and-router-builder may ship a different shape, which would need a reconciliation TEST_WRITING pass exactly like US-4.1's v2 pass. Full assumption detail in US-4.2-test-strategy.md."
    - "API_DESIGN OQ-2's POST-side 'agent-shaped but missing tickets:write' combination is unit-tested only - unreachable via real HTTP under the shipped role seed (tickets:read/tickets:write always travel together for support_agent/admin)."
    - "The RLS policy DDL's own upgrade/downgrade/upgrade reversibility is migration-manager's (T3) proof, not this suite's - already executed and passed (docs/catalog/US-4.2-pipeline-status.md v2); this suite's 3 RLS tests assume the migration has already been applied and currently fail on assertion (superuser bypass), not at the database level, pending T4."
    - "Adding imports for not-yet-built symbols to test_support_service.py and test_support_router.py breaks collection of those entire files, including the 12/22 pre-existing US-4.1 tests, until IMPLEMENTATION T1/T2/T5 land the missing symbols - expected, self-resolving, and accounted for by the task breakdown's own T1-T6-before-T7 ordering, not a regression."
```

### Result (v1, for reference)

```yaml
result:
  verdict: PASS
  stage: TEST_WRITING
  story: US-4.2
  artifact_status: DRAFT
  artifacts:
    - docs/tests/US-4.2-test-strategy.md
    - docs/tests/US-4.2-ac-test-matrix.md
    - docs/evidence/US-4.2-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "Test-writer's own collaborator-shape assumption: a new TicketReplyService class (not new methods on TicketService), with actor_kind: Literal['customer','agent'] reused across both create_reply and get_ticket_detail, derived per implementation-plan Architectural Change #2's tickets:write check for both routes. implementation-plan Architectural Change #4 explicitly leaves this split open — service-and-router-builder may ship a different shape, which would need a reconciliation TEST_WRITING pass exactly like US-4.1's v2 pass. Full assumption detail in US-4.2-test-strategy.md."
    - "API_DESIGN OQ-2's POST-side 'agent-shaped but missing tickets:write' combination is unit-tested only — unreachable via real HTTP under the shipped role seed (tickets:read/tickets:write always travel together for support_agent/admin)."
    - "The RLS policy DDL's own upgrade/downgrade/upgrade reversibility is migration-manager's (T3) proof, not this suite's — this suite's 3 RLS tests assume the migration has already been applied and will fail at the database level (missing table/policy) until T3 lands, distinct from the ImportError failures the rest of the suite hits."
    - "Adding imports for not-yet-built symbols to test_support_service.py and test_support_router.py breaks collection of those entire files, including the 12/22 pre-existing US-4.1 tests, until IMPLEMENTATION T1/T2/T4 land the missing symbols — expected, self-resolving, and accounted for by the task breakdown's own T1-T5-before-T6 ordering, not a regression."
```
