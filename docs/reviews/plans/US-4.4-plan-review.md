---
artifact_type: plan_review
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T23:59:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.4-task-breakdown.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Plan Review: Agent Ticket Queue & Assignment

**Story ID:** US-4.4
**Plan Reviewed:** docs/plans/US-4.4-implementation-plan.md (v1, DRAFT)
**Task Breakdown Reviewed:** docs/plans/US-4.4-task-breakdown.md (v1, DRAFT)
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

Both plan-stage artifacts were checked against the spec, impact analysis, and API/DB designs. Every file the impact analysis named appears in the plan's Files To Create/Modify with matching detail, the task breakdown's ten-task sequence respects AGENTS.md §3's downward-only layering and migration-before-service-use, and the two targeted architectural calls (DR-3's `updated_at` suppression, DR-5's new repository method) are carried through consistently from plan into task breakdown with correctly scoped verification commands. One Low, non-blocking gap is noted in Test-Strategy Realism (T8's verification command has no explicit grep check tying OD-4's deactivated-target branch to the same `ValidationFailedError`/422 the plan's Files-To-Modify section specifies). No missing impact-analysis coverage and no layering-order violation were found.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `models.py`: `Ticket.assignee_id` column + 3 new indexes | Covered | Files To Modify → `models.py`; task_breakdown T2 | Partial-index literalism (DR-1) carried into T2's verification (grep for literal `!= "closed"`). |
| `schemas.py`: `AgentTicketRead`, `AgentTicketListResponse`, `AgentTicketStateRead`, `AssignTicketRequest`; `TicketRead`/`TicketListResponse`/`TicketStateRead` unchanged | Covered | Architectural Change #2; Files To Modify → `schemas.py`; task_breakdown T1 | T1's verification explicitly diffs to confirm the three existing schemas are byte-for-byte unchanged (OD-1's whole point). |
| `repository.py`: new `list_for_agent_queue` (DR-5) + own cursor decode/`WHERE` logic | Covered | Architectural Change #5; Files To Modify → `repository.py`; task_breakdown T3 | T3 verification confirms `list_for_requester` is untouched and the new method's comparison operator is `>` (ascending), matching DR-5's stated direction. |
| `repository.py`: new conditional `assign_ticket`/`unassign_ticket` writes (FR-3/FR-4/FR-10, DR-3) | Covered | Architectural Change #6/#9; Files To Modify → `repository.py`; task_breakdown T4 | See Test-Strategy Realism — the DR-3 proof requirement is correctly escalated to an integration test in T4's own verification cell. |
| `service.py`: `TicketRepositoryProtocol` growth; new `RoleServiceProtocol`; agent-queue listing method; `assign_ticket`/`unassign_ticket` | Covered | Architectural Change #3/#4; Files To Modify → `service.py`; task_breakdown T6, T7, T8 | Cross-module dependency correctly scoped as its own task (T6) rather than inlined — see Layering Order below. |
| `router.py`: `list_own_tickets` branch + Union response model; new `POST`/`DELETE /{id}/assign` | Covered | Architectural Change #1; Files To Modify → `router.py`; task_breakdown T9 | T9 verification includes an explicit `app.openapi()` render check against the openapi.yaml v1 contract. |
| `dependencies.py`: remove `reject_agent_queue_access`; wire `RoleServiceDep`; 404-vs-403 gate placement (API design Open Questions #1) | Covered | Files To Modify → `dependencies.py`; task_breakdown T6, T9; "Routed open item closed at this stage" | The open dependency-vs-inline question is explicitly resolved (inline in service) in the task breakdown, not left ambiguous. |
| `exceptions.py`: remove `AgentQueueNotAvailableError`; add `AssignmentConflictError`; reuse `InvalidStateTransitionError`/`InsufficientPermissionError`/`TicketNotFoundError`/`ValidationFailedError` | Covered | Files To Modify → `exceptions.py`; task_breakdown T8 | T8 verification greps for `AssignmentConflictError` vs. `InvalidStateTransitionError` on the two distinct 409 cases — see Test-Strategy Realism for one gap on the `ValidationFailedError`/OD-4 side. |
| `cache.py`: no change | Covered | Files To Modify → `cache.py` ("no change, confirmed by impact-analyzer") | Explicit no-op, matches impact analysis. |
| `scripts/auto_close_resolved_tickets.py`: no change | Covered | Files To Modify → "Not modified, confirmed no impact" | Explicit no-op, matches impact analysis. |
| Migration: additive column + 3 indexes, chains from `242e0dba5ba2`, Rewriter guard on both partial indexes | Covered | Files To Create (migration); Risk 6; task_breakdown T5 | T5 verification explicitly calls out confirming the guard on **both** partial indexes now on `tickets`, not assuming precedent generalizes. |
| Cross-module ripple: `support→roles.RoleService.resolve_scopes_for_user` (new) | Covered | Architectural Change #4; task_breakdown T6 | See Layering Order — correctly sequenced ahead of the task that actually calls it (T8). |
| Cross-module ripple: `support→users.UserService.get_account_status_for_user` (existing, reused for OD-4 target) | Covered | Files To Modify → `service.py` (`assign_ticket` flow); task_breakdown T8 | Testing Strategy flags confirming the existing `FakeUserService` fake supports an arbitrary target id, not only the caller's own. |
| Cross-module ripple: `support→audit.record_event` (existing) | Covered | Files To Modify → `service.py`; task_breakdown T8 | No signature change, reused verbatim. |
| Test-surface: update (not delete) `test_list_own_tickets_agent_scope_caller_returns_403` | Covered | Risk 7; Testing Strategy; task_breakdown T9 verification | T9's verification cell explicitly names the file/line and requires confirming the diff, not just relying on router-level checks. |
| Test-surface: customer-branch regression tests must still pass unmodified | Covered | Testing Strategy ("Regression" bullet) | |
| Test-surface: new unit fakes (`FakeRoleService`, `FakeTicketRepository` growth, `FakeUserService` reuse) | Covered | Testing Strategy (Unit section) | |
| Test-surface: new integration tests (agent queue, assign/unassign HTTP paths, concurrency, DR-3, `EXPLAIN`-based index selection) | Covered | Testing Strategy (Integration section) | |
| Test-surface: migration `upgrade → downgrade → upgrade` proof | Covered | Validation Strategy; task_breakdown T5 | |
| Test-surface: OpenAPI-render check (no checked-in test exists) | Covered | Validation Strategy ("OpenAPI renders" note); task_breakdown T9 | Correctly identified as a `QUALITY_GATE`-time check, not a file this plan modifies. |
| DR-3 finding (updated_at queue-reset) | Covered | Architectural Change #9 (full resolution); task_breakdown T4 | See dedicated discussion below — resolution is reasoned, not asserted, and correctly documented as superseding db-design.md/entity-model.md text. |
| DR-5 finding (new repository method) | Covered | Architectural Change #5; task_breakdown T3 | |
| OD-3 finding (unassign-on-closed symmetry) | Covered | Architectural Change #6; Risk 8; task_breakdown T4, T8, Notes | See dedicated discussion below. |
| OD-4 finding (deactivated-target check) | Covered | Files To Modify → `service.py`; Risk 8; task_breakdown T8, Notes | See dedicated discussion below. |

No impact-analysis item was found Missing or Partially Covered.

### DR-3 verification requirement (targeted check)

Confirmed: task_breakdown T4's Verification Command cell does **not** stop at a generic "test passes" note. It states explicitly: *"the load-bearing proof for this task is an integration test that seeds a ticket with an explicit, distinct **past** `updated_at` and asserts it is unchanged after `assign`/`unassign` — a same-transaction `func.now()`-seeded unit/fake test would pass identically whether or not this fix is present ... and proves nothing; this task's own mypy/grep checks are necessary but not sufficient proof."* This matches AGENTS.md §5's frozen-`func.now()`-per-transaction rule verbatim and is repeated consistently in implementation_plan's Risk 5 / Testing Strategy and task_breakdown's own "Notes carried forward" section. The plan's supersession of db-design.md/entity-model.md's "no suppression mechanism" text was independently verified against `docs/designs/database/US-4.4-db-design.md` lines 171-184 ("This design does not add a mechanism to suppress it ... Flagged as a real, observable consequence ... for `service-and-router-builder`") — the plan's Architectural Change #9 correctly frames this as the design stage properly declining to invent unrequested behavior, and the architecture stage now making that call with a reasoned rationale (queue-starvation prevention, cursor-stability), not a silent contradiction.

### OD-3 / OD-4 cross-artifact consistency (targeted check)

- **OD-3** (open_decisions.md recommends: `DELETE .../assign` on `"closed"` → `409 invalid-state-transition`, mirroring FR-9): spec FR-4 adopts this default → implementation_plan Architectural Change #6 (`unassign_ticket`'s conditional `WHERE status != 'closed'`, reusing `InvalidStateTransitionError`) → task_breakdown T4 (repository `WHERE` clause) and T8 (service closed-ticket check, "OD-3's adopted default"). Consistent end-to-end; the same error type (`InvalidStateTransitionError`, `allowed_events=[]`) is named at every layer, not a different slug at any stage.
- **OD-4** (open_decisions.md recommends: extend FR-8's target check to also reject a deactivated target account with the same `422 validation-failed`): spec FR-8 adopts this default → implementation_plan's `service.py` entry names both checks (`RoleServiceProtocol.resolve_scopes_for_user` for the scope condition, `UserServiceProtocol.get_account_status_for_user` against the target id for the account-status condition) and its exceptions section states `ValidationFailedError` is reused for "the target-validation case" (both FR-8 and OD-4) → task_breakdown T8 names both checks against T6/existing collaborators. Content-level consistency confirmed. One verification-completeness gap noted below (Test-Strategy Realism).

### T6 sequencing ahead of T7/T8 (targeted check)

Confirmed and more precisely scoped than the review brief assumed: only **T8** (`assign_ticket`) actually calls `RoleServiceProtocol.resolve_scopes_for_user` — T7 is the agent-queue listing method (FR-1/FR-2), which performs no target-validation and has no runtime need for the roles collaborator. The task_breakdown's dependency edges reflect this correctly: T8's `Depends On` column lists `T4, T6, T7` (T6 precedes it), while T7's `Depends On` column lists `T1, T3, T5` (no T6 edge). The task_breakdown's own "Parallel-eligible" note makes this explicit: T6 is kept as a dependency of T8 for rule-conformance/traceability even though T6's content "touches no `Ticket` column/index and calls no repository method," and states plainly that "T8 (which consumes the Protocol inside `assign_ticket`) must run after it regardless." No sequencing defect found; the artifacts correctly identify T8, not T7, as the consumer.

## Layering Order (Task Breakdown)

No ordering issue found. T1 (schemas) / T2 (models) run in parallel with no cross-dependency; T3/T4 (repository) both depend only on T2; T5 (migration) depends on T2+T3+T4 (settled `models.py`/`repository.py` before autogenerate, consistent with the migration-before-model-use rule and the precedent cited from US-4.3's task breakdown); T6/T7/T8 (service) depend on T5 plus their own upstream schema/repository tasks, with T6 correctly preceding T8 (see above) and T7 correctly not depending on T6; T9 (router) depends on T7+T8; T10 (gate-enforcer) depends on all preceding tasks. This is a clean downward traversal of AGENTS.md §3's `router → dependencies → service → repository → models/schemas` stack (read in build order: schemas/models → repository → migration → service → router → gate), with no task consuming a layer built after it.

## Risk Realism

None found beyond what the plan already covers. Risks 1-9 in implementation_plan concretely name: the new `Union` `response_model` leak risk (mitigated by asserting byte-identical customer-branch output, not just "no `assignee_id` key"), the new cross-module coupling's Protocol-bypass risk (mitigated by naming T6 as its own task), the `IS NOT DISTINCT FROM` vs. `=` SQL-null-semantics trap (FR-10), the partial-index predicate-literalism trap (DR-1), the DR-3 half-applied-fix risk across both new write methods, the Rewriter guard-injection risk repeating across two partial indexes on the same table, the `403`→`200` contract-change risk for the retired `reject_agent_queue_access` caller, and the OD-3/OD-4 reversal-rework risk (correctly bounded to `service.py`/`repository.py`, never a schema element, per db-design.md's own analysis). These map directly to AGENTS.md §4's migration hazards (partial-index guards) and this story's own concurrency/contract-breaking exposure — not generic placeholders.

## Test-Strategy Realism

- **[Low] T8's verification command omits an explicit check for OD-4's exception path.** T4's Verification Command cell explicitly greps for both `IS NOT DISTINCT FROM` and `updated_at=Ticket.updated_at` on each of its two hazards (Risk 3, Risk 5). T8's Verification Command cell, by contrast, greps for the `AssignmentConflictError`-vs-`InvalidStateTransitionError` distinction on the two 409 cases, but has no equivalent grep confirming the OD-4 deactivated-target branch raises the same `ValidationFailedError`/422 that implementation_plan's exceptions section says is "reused" for "the target-validation case" (covering both FR-8's scope check and OD-4's account-status check). This is a verification-completeness gap, not a design gap — the intended behavior is clearly and consistently stated in prose at every artifact layer (see OD-4 discussion above), and implementation_plan's own Testing Strategy already names the OD-4 unit-test variant explicitly ("target-validation 422 including the OD-4 deactivated-account variant (FR-8)"). Recommend `test-writer`/`gate-enforcer` add a grep or test assertion confirming both target-validation failure paths raise `ValidationFailedError` (not a distinct exception type) when task_breakdown next revises, but this does not block implementation: the unit-test-level assertion already named in implementation_plan's Testing Strategy is sufficient coverage even without a corresponding grep in T8's own cell.

Everything else in the Testing Strategy concretely names the AGENTS.md §5 unit/integration split per test case (which fakes, which file, which HTTP path, which concurrency pattern) rather than a vague "tests will be written" placeholder, and correctly escalates the one determinism-sensitive assertion (DR-3) to integration with an explicit rationale for why a unit/fake test cannot prove it.

## Scope Creep

None found. Every file change, new method, new schema, new exception, and new task traces to a spec FR, an Open Decision's adopted default, or a design-review/impact-analysis finding (DR-1, DR-3, DR-5). The one item that could look like scope creep — Architectural Change #9's full DR-3 resolution — is explicitly the impact analysis's own routing instruction ("that decision belongs to `ARCHITECTURE_PLANNING`"), not an invented requirement.

## Verdict Rationale

Full impact-analysis coverage confirmed with no Missing/Partially Covered items, no layering-order violation in the ten-task sequence, and risk/test-strategy sections are concrete and traceable to AGENTS.md §4/§5 rather than generic. The single Low finding (T8's verification cell lacking an explicit OD-4 exception-type grep) is a verification-completeness gap only — the underlying design and test-strategy intent are already unambiguous and consistent across every artifact — so it does not block implementation. Verdict: **PASS**.
