---
artifact_type: task_breakdown
story: US-4.4
version: 1
status: APPROVED
created_at: "2026-09-08T01:30:00Z"
updated_at: "2026-09-07T15:54:29Z"
produced_by: implementation-planner
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
supersedes: null
---

# Task Breakdown — US-4.4 (Agent Ticket Queue & Assignment)

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | schema-builder | schemas | — (parallel with T2) | `app/modules/support/schemas.py` (new `AgentTicketRead` — every `TicketRead` field plus `assignee_id`; `AgentTicketListResponse` parallel to `TicketListResponse`; `AgentTicketStateRead` — every `TicketStateRead` field plus `assignee_id`; `AssignTicketRequest` — `{assignee_id: uuid.UUID}`, OD-1's adopted schema-split) | mypy `strict` clean; grep confirms `extra="forbid"` on `AssignTicketRequest`; diff confirms `TicketRead`/`TicketListResponse`/`TicketStateRead` are byte-for-byte unchanged (OD-1's whole point — the customer-reachable contract must stay identical). |
| T2 | data-layer-builder | models | — (parallel with T1) | `app/modules/support/models.py` (`Ticket.assignee_id: Mapped[uuid.UUID \| None] = mapped_column(ForeignKey("users.id"), nullable=True)`, no `ondelete` override; three new `Index(...)` entries in `__table_args__` — `ix_tickets_queue_default_updated_at_id` partial `(updated_at, id)`, `ix_tickets_status_updated_at_id` `(status, updated_at, id)`, `ix_tickets_assignee_id_updated_at_id` `(assignee_id, updated_at, id)`; no new `CHECK` constraint) | mypy `strict` clean; grep confirms the partial index's predicate is written as the literal `Ticket.status != "closed"` — never `.in_([...])` — per DR-1/Architectural Change #10 (a `.in_()` predicate silently fails PostgreSQL's partial-index predicate-implication check and is invisible until `EXPLAIN`, T5's/T8's gate). |
| T3 | data-layer-builder | repository | T2 | `app/modules/support/repository.py` — new `list_for_agent_queue(...)` method (DR-5): its own ascending `(updated_at, id)` `WHERE`-building routine plus its own decode-to-`WHERE` comparison (`Ticket.updated_at > cursor_updated_at`, mirroring `TicketReplyRepository.list_for_ticket`'s ascending pattern, not `list_for_requester`'s descending one), the three new filter predicates (`status`, `category`, `assignee_id` incl. `me`/`none`); may reuse the existing generic `_encode_cursor`/`_decode_cursor` helpers verbatim for the encode/decode step itself | mypy `strict` clean; grep/diff confirms `list_for_requester` (existing method) is byte-for-byte unchanged — DR-5 is a **new** method, not an extension; grep confirms `list_for_agent_queue`'s comparison operator is `>` (ascending), not `<`; grep confirms the default (filterless) branch emits the literal `Ticket.status != "closed"` predicate consumed by T2's partial index. |
| T4 | data-layer-builder | repository | T2 | `app/modules/support/repository.py` — new `assign_ticket(...)`: conditional `UPDATE tickets SET assignee_id = :new WHERE id = :id AND status != 'closed' AND assignee_id IS NOT DISTINCT FROM :expected RETURNING *`; new `unassign_ticket(...)`: unconditional `UPDATE tickets SET assignee_id = NULL WHERE id = :id AND status != 'closed' RETURNING *`; **both statements' `.values()` must explicitly include `updated_at=Ticket.updated_at`** (DR-3's resolved mechanism — a self-referential `SET updated_at = tickets.updated_at`, server-side, overriding the column's `onupdate=func.now()` default so FR-1 queue ordering survives an assign/unassign cycle) | mypy `strict` clean; grep confirms `IS NOT DISTINCT FROM` (not `=`) in `assign_ticket`'s `WHERE` clause (Risk 3 — `NULL = NULL` is `NULL`, not `true`, in SQL, which would silently break every first assignment as a `409`); grep confirms **both** `assign_ticket` and `unassign_ticket` include `updated_at=Ticket.updated_at` in `.values()` (Risk 5 — a half-applied fix is worse than no fix). **Flag for `TEST_WRITING`/downstream test verification:** the load-bearing proof for this task is an **integration** test that seeds a ticket with an explicit, distinct **past** `updated_at` and asserts it is unchanged after `assign`/`unassign` — a same-transaction `func.now()`-seeded unit/fake test would pass identically whether or not this fix is present (per `AGENTS.md` §5's frozen-`func.now()`-per-transaction rule) and proves nothing; this task's own mypy/grep checks are necessary but not sufficient proof. |
| T5 | migration-manager | migration | T2, T3, T4 | `migrations/versions/<hash>_*.py` (autogenerated; additive only — one nullable FK column, three indexes; chains from current head `242e0dba5ba2`) | `alembic revision --autogenerate -m "add_ticket_assignee_column"` (or equivalent snake_case description); read the generated file before trusting it; confirm the `Rewriter`-injected `if_not_exists`/`if_exists` guard is present on **both** partial indexes now on `tickets` (the new `ix_tickets_queue_default_updated_at_id` and the pre-existing `ix_tickets_resolved_at_pending_autoclose` from US-4.3 — Risk 6, do not assume the existing precedent generalizes untested); `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` against real PostgreSQL. |
| T6 | service-and-router-builder (service) | service | T1, T5 | `app/modules/support/service.py` (new `RoleServiceProtocol` — mirroring the existing `AuditServiceProtocol`/`UserServiceProtocol` shape, exposing `resolve_scopes_for_user(user_id: uuid.UUID) -> list[str]`; **never** a direct `from app.modules.roles.service import RoleService` in this file), `app/modules/support/dependencies.py` (wire `app.modules.roles.dependencies.RoleServiceDep` into whichever factory constructs the service owning `assign_ticket`/`unassign_ticket`, the same pattern already used for `app.modules.audit.dependencies`/`app.modules.users.dependencies`) | **Named as its own task deliberately (implementation-plan Risk 2 mitigation) so this first-ever `support`→`roles` cross-module wiring isn't done ad hoc inline inside T8.** `lint-imports` passes with zero new broken contracts (Contract 1 is wildcarded per-module and already permits this per `impact-analyzer`'s confirmation; re-run the gate here rather than citing the prior analysis); grep confirms `service.py` contains no direct `import` of `app.modules.roles.service` (Protocol-only, DI resolved at `dependencies.py`); mypy `strict` clean on the new Protocol's signature. |
| T7 | service-and-router-builder (service) | service | T1, T3, T5 | `app/modules/support/service.py` — `TicketRepositoryProtocol` grows `list_for_agent_queue`'s signature; new `TicketService` method for the agent-queue listing (parallel to `list_own_tickets`): `assignee_id=me`/`=none` resolution, filter pass-through, `AgentTicketListResponse` construction | mypy `strict` clean, explicit `-> AgentTicketListResponse` annotation (no `Any`); grep confirms zero `fastapi`/`starlette`/`HTTPException` imports in `service.py`. |
| T8 | service-and-router-builder (service) | service | T4, T6, T7 | `app/modules/support/service.py` — `TicketRepositoryProtocol` grows `assign_ticket`/`unassign_ticket` signatures; new `TicketService.assign_ticket(...)`: permission gate first (no lookup, inlined in the service per the plan's own Files-To-Modify description of the check order — the reusable-`Depends`-vs-inline choice API design left open is resolved here as **inline in the service**, since the gate is one of several ordered checks inside one business method, not a standalone route guard) → ticket lookup `404` → closed-ticket `409` (FR-9) → target-validation via T6's `RoleServiceProtocol.resolve_scopes_for_user` (`422` if `tickets:write` absent, FR-8) and via the already-held `UserServiceProtocol.get_account_status_for_user` against the *target* id (OD-4's adopted default) → conditional update (`409 assignment-conflict` on race loss, FR-10) → `AuditServiceProtocol.record_event(event="ticket_assigned", ...)` → one commit; new `TicketService.unassign_ticket(...)`: permission gate → lookup `404` → closed-ticket `409` (OD-3's adopted default) → unconditional clear → `record_event(event="ticket_unassigned", ...)` → one commit; `app/modules/support/exceptions.py` — remove `AgentQueueNotAvailableError`, add `AssignmentConflictError` (409, `assignment-conflict`, first use in this project) | mypy `strict` clean, explicit `-> AgentTicketStateRead`/`-> None` annotations; grep confirms the permission check precedes the ticket-lookup call in both methods (FR-7's 404-before-403 ordering, the deliberate departure from `resolve_ticket`/`close_ticket`/`reopen_ticket`'s existing lookup-first order); grep confirms `AssignmentConflictError` (not `InvalidStateTransitionError`) is raised on optimistic-concurrency loss and `InvalidStateTransitionError` with `allowed_events=[]` is reused for the closed-ticket case in both methods; grep confirms zero `fastapi`/`starlette`/`HTTPException` imports. |
| T9 | service-and-router-builder (router) | router | T7, T8 | `app/modules/support/router.py` — `list_own_tickets`: drop `dependencies=[Depends(reject_agent_queue_access)]`, branch on `tickets:read` presence in `current_user.scopes` to call the existing customer-branch service method or T7's new agent-branch one, add `category`/`assignee_id` query params, change `response_model`/return annotation to `TicketListResponse \| AgentTicketListResponse`; new `POST /{id}/assign` → `AgentTicketStateRead`; new `DELETE /{id}/assign` → `AgentTicketStateRead`; `app/modules/support/dependencies.py` — remove `reject_agent_queue_access` and its `AgentQueueNotAvailableError` import (`resolve_actor_kind` is unaffected and stays) | grep confirms zero `sqlalchemy`/`models`/`repository`/`AsyncSession`/Valkey imports in `router.py`; explicit `-> TicketListResponse \| AgentTicketListResponse` return annotation present (mypy strict forbids `Any`); `lint-imports` passes; OpenAPI render (`app.openapi()`) matches `US-4.4-openapi.yaml` v1's endpoint and schema shapes; grep confirms `reject_agent_queue_access`/`AgentQueueNotAvailableError` no longer referenced anywhere in `app/modules/support/` **or `tests/`** — specifically, `tests/integration/modules/support/test_support_router.py::test_list_own_tickets_agent_scope_caller_returns_403` (line 697, the sole existing test asserting the retired `403`) must be **updated to assert the new agent-branch `200` behavior, not deleted** (spec NFR; implementation_plan Risk 7; impact-analysis §4's first named item) — this task's `app.openapi()`/router-level checks alone will not catch a stale or missing update to this test; confirm the diff explicitly. |
| T10 | gate-enforcer | — | T1–T9 (+ test-writer) | — | `pre-commit run --all-files` (Ruff format+lint, mypy strict, `lint-imports`, secret scan); `mypy app tests`; `lint-imports`; `pytest --cov` against the 85% overall / 90%+ `service.py`/`router.py` floors — including T4's DR-3 integration case, the new agent-branch/assign/unassign integration tests, the FR-10 concurrency test, and the `EXPLAIN`-based partial-index-selection check named in `implementation_plan`'s Testing Strategy. |

**Parallel-eligible:** T1 and T2 have no dependency on each other. T6 (the
`RoleServiceProtocol`/`RoleServiceDep` wiring) is listed depending on T1, T5
— following this skill's flat "`data-layer-builder`/`schema-builder` before
`service-and-router-builder`" ordering rule for every service-layer task on
this track, no exception carved out — but note for scheduling purposes that
T6's own content touches no `Ticket` column/index and calls no repository
method, so an implementer could in principle pull it forward without
correctness risk; the dependency edge is kept for rule-conformance and
traceability, not because T6 has a real runtime need for the live schema.
It is sequenced as its own row (not merged into T7/T8) per the
implementation plan's Risk 2 mitigation, and T8 (which consumes the
Protocol inside `assign_ticket`) must run after it regardless.

## Ordering rationale (AGENTS.md §3 + migration-before-model-use)

- `schema-builder` (T1) and `data-layer-builder`'s model change (T2) have no
  dependency on each other and may run in parallel, per the standard rule.
- `data-layer-builder`'s two repository tasks (T3 DR-5 queue listing, T4
  DR-3 assign/unassign writes) both depend only on T2 (`models.py`'s new
  `assignee_id` column existing at the Python level) — not on each other,
  since they touch disjoint methods in the same file. They are named as
  **separate tasks** per the orchestrator brief: DR-5 is "its own file/
  method-level task, not an extension task" (implementation_plan
  Architectural Change #5), and DR-3's fix is inseparable from the two new
  write methods it patches (Architectural Change #6/#9).
- `migration-manager` (T5) depends on **all three** `models.py`/
  `repository.py` tasks (T2, T3, T4) completing first, even though only
  T2's model diff drives `alembic revision --autogenerate` — this keeps a
  single migration-authoring pass against a settled `models.py` rather than
  re-running autogenerate mid-stream, consistent with this project's
  established sequencing (`US-4.3-task-breakdown.md`'s T3 waited on its
  single combined data-layer task the same way).
- Every `service-and-router-builder` task (T6, T7, T8) is sequenced after
  T5's migration per this skill's flat ordering rule, even though T6's own
  content (the `RoleServiceProtocol`/`RoleServiceDep` wiring) doesn't
  actually use the new column — see the parallel-eligibility note above.
  T7 and T8 do have a genuine runtime dependency on T5: both call
  repository methods that read/write `assignee_id`/`updated_at` under the
  new indexes.
- Within `service-and-router-builder`, service-layer tasks (T6, T7, T8)
  precede the router-layer task (T9), per the base ordering rule.
- `gate-enforcer` (T10) is the single final task, depending on every
  preceding task plus `test-writer`'s output (a separate workflow stage,
  not sequenced as an `IMPLEMENTATION` sub-step here — consistent with
  `US-4.3`/`US-4.2`'s identical omission).

## Routed open item closed at this stage

- **API design's own Open Questions #1 (second half): reusable `Depends`
  vs. inline service check for the `assign`/`unassign` 404-vs-403 permission
  gate.** `implementation_plan` explicitly left this as "a genuine
  `task_breakdown`-level choice for `implementation-planner`." Resolved
  here (T8): **inline in the service**, not a new reusable dependency —
  the plan's own Files-To-Modify description already places the permission
  gate as the first of several ordered checks inside `assign_ticket`'s/
  `unassign_ticket`'s own body (permission → lookup → closed-ticket →
  target-validation → conditional update → audit → commit), which is a
  business-method-internal check sequence, not a standalone FastAPI route
  guard reusable across unrelated routes. No new `Depends`-based dependency
  is added to `dependencies.py` for this purpose.

## Notes carried forward, non-blocking

- **OD-3 / OD-4 remain unconfirmed at the spec level.** T4 (repository:
  unassign's unconditional-clear-then-409-on-closed default) and T8
  (service: `assign_ticket`'s OD-4 deactivated-target `422` check) are
  already built against the spec's own adopted drafting defaults per
  `implementation_plan`'s Risk 8. This task breakdown does not block on
  either being reconfirmed, per the orchestrator brief, but both **must be
  confirmed before `IMPLEMENTATION` actually runs T4/T8's code** — if either
  is reversed, `db-design.md`'s own analysis (confirmed by `design-reviewer`
  and `impact-analyzer`) bounds the rework to a `service.py`/`repository.py`
  conditional-`WHERE`/branch change within these same two tasks, never a
  schema element, so T2/T5 (models/migration) are not at risk either way.
- **API design's own Open Questions #5** (whether an idempotent-no-op
  `unassign` still writes an audit row) is an implementation-time branch
  decision inside T8's `unassign_ticket` method, not fixed further by this
  breakdown.
- **T4's DR-3 proof is explicitly an integration-test concern**, not
  satisfiable by this task's own mypy/grep verification alone — flagged in
  T4's Verification Command column and repeated here so it is not lost when
  `TEST_WRITING`/`test-writer` scopes its own tasks off this breakdown.
