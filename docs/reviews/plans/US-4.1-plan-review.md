---
artifact_type: plan_review
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-03T02:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-4.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.1-task-breakdown.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
supersedes: null
---

# Plan Review: Support Tickets — Create (US-4.1)

**Story ID:** US-4.1
**Plan Reviewed:** docs/plans/US-4.1-implementation-plan.md (v1)
**Task Breakdown Reviewed:** docs/plans/US-4.1-task-breakdown.md (v1)
**Reviewed:** 2026-09-03
**Overall Verdict:** Pass with Issues

## Summary

The plan covers every file `impact-analyzer` identified, including the two cross-module ripple files (`app/modules/audit/service.py`, `app/modules/audit/repository.py`) and the flagged transaction-boundary tension, which it resolves explicitly rather than deferring further. The task breakdown's ordering respects `AGENTS.md` §3's layering direction and the migration-before-model-use rule with no violations. The verdict is Pass with Issues rather than a clean Pass for two minor reasons, neither blocking: (1) `app/modules/support/__init__.py` appears in the plan's Files To Create table but no task in the breakdown explicitly owns creating it; (2) the plan's numbered Risks section omits the hand-written `ticket_number_seq` sequence/default as its own risk item, even though the plan's own Validation Strategy section correctly identifies that this hazard needs a Rewriter-blind-spot guard per `AGENTS.md` §4.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/support/__init__.py` | Covered | Files To Create | No task in the task breakdown explicitly creates this file; see Layering/Completeness note below. |
| `app/modules/support/models.py` | Covered | Files To Create; task breakdown T2 | — |
| `app/modules/support/schemas.py` | Covered | Files To Create; T1 | — |
| `app/modules/support/repository.py` | Covered | Files To Create; T2 | — |
| `app/modules/support/cache.py` | Covered | Files To Create; T2 | — |
| `app/modules/support/service.py` | Covered | Files To Create; T6 | — |
| `app/modules/support/router.py` | Covered | Files To Create; T7 | — |
| `app/modules/support/dependencies.py` | Covered | Files To Create; T7 | — |
| `app/modules/support/exceptions.py` | Covered | Files To Create; T6 | Plan explicitly defers the `AccountDeactivatedError` reuse-vs-new decision to `service-and-router-builder` at IMPLEMENTATION time rather than deciding silently — disclosed, not a gap. |
| `scripts/purge_unbound_attachments.py` | Covered | Files To Create; T6 | — |
| `app/core/cache_keys.py` | Covered | Files To Modify; T2 | — |
| `app/modules/audit/service.py` (`record_event`) | Covered | Files To Modify; T5 | Resolves impact-analysis §2's flagged transaction-boundary tension explicitly (no self-commit). |
| `app/modules/audit/repository.py` (`record_event`) | Covered | Files To Modify; T3 | — |
| `app/api/v1/router.py` | Covered | Files To Modify; T7 | — |
| `migrations/env.py` (model-registration import) | Covered | Files To Modify; T4 | — |
| Migration (`tickets`, `attachments`, `ticket_number_seq`) | Covered | Files To Create (Migration); T4 | — |
| New test files (§4: unit + integration, support + purge script) | Covered | Testing Strategy section | Correctly not assigned a task-breakdown task — test-file authorship belongs to `TEST_WRITING` (`test-writer`), which runs before `IMPLEMENTATION` but after this stage; the plan restates the file list only for traceability. |
| `tests/unit/modules/audit/test_audit_service.py` (existing, must change) | Covered | Testing Strategy section; plan Risk 1 | Plan states the new assertion needed (`record_event` does not call `commit()`). |
| `tests/unit/test_audit_write_call_site_scan.py` (confirmed no change) | Covered | Files To Modify note (audit/repository.py row) | Matches impact-analysis's own confirmation — AST-walk scan needs no edit. |
| `tests/conftest.py` (confirmed no change) | Covered | "No other existing file changes" statement | Matches impact-analysis's own confirmation. |

## Layering Order (Task Breakdown)

No violation found. T1 (`schemas.py`) and T2 (`models.py`/`repository.py`/`cache.py`/`cache_keys.py`) have no interdependency and are parallel-eligible, both correctly preceding T4 (migration, which needs T2's models) and T6 (service, which needs T1's schemas). T3 (`audit/repository.py`) is independent of T1/T2 and correctly precedes T5 (`audit/service.py`, which needs T3's new repository method) — repository before service is respected. T4 (migration) correctly depends only on T2, matching the migration-before-model-use rule (the model must exist before the migration is authored, and the migration must land before T6's service code exercises the table). T6 (service) correctly depends on T1 (schemas), T4 (migration — table must exist before the service is verified against it), and T5 (audit service, the new cross-module collaborator it calls) — service after repository/migration is respected. T7 (router) correctly depends only on T6 — router after service is respected. T8 (`gate-enforcer`) correctly runs last, after T1–T7 plus `test-writer`'s TEST_WRITING output.

**Minor completeness note (not a layering violation):** `app/modules/support/__init__.py` is not explicitly assigned to any task. It is a zero-content package marker that whichever of T1/T2 runs first would trivially need to create; this is very likely to happen in practice without incident, but the task breakdown does not say so, unlike `US-3.3-task-breakdown.md`'s equivalent module, where the `__init__.py` was at least implicitly bundled into an explicit "Files To Create" task row. Recommend `implementation-planner` add a one-line note to T1 or T2 naming this file, but it does not block IMPLEMENTATION.

## Risk Realism

- **[Low] Hand-written sequence/default guard omitted from the numbered Risks list** — Plan's Risks section (5 numbered items: transaction-boundary regression, idempotency poll latency, `migrations/env.py` edit, OD-3, BR-007) never lists the hand-written `ticket_number_seq` `SEQUENCE` and its `server_default=FetchedValue()` expression as a risk, even though the same document's own Validation Strategy section states: "the hand-written `ticket_number_seq` sequence/default, which the Rewriter cannot reach and `migration-manager` must guard per `AGENTS.md` §4." `AGENTS.md` §4 is explicit that hand-written migration content (`op.execute()`, non-autogenerated defaults) needs an `sa.inspect(op.get_bind())` guard distinct from the Rewriter's `if_exists`/`if_not_exists` injection — this is a materially different hazard from the `migrations/env.py` edit risk already listed (Risk 3), and a reader scanning only the Risks section for migration hazards would miss it. Not blocking since the hazard is stated elsewhere in the same document and `migration-manager`'s own skill contract already requires this guard independent of this plan.

## Test-Strategy Realism

No issues found. The Testing Strategy section names the unit/integration split concretely (fakes vs. real PostgreSQL/Valkey per `AGENTS.md` §5), lists exact file paths, states the specific branches each unit test must cover (idempotency claim/replay/reuse/mid-flight-poll, rate-limit-vs-idempotency ordering, attachment-ownership indistinguishable-cause paths), and states the 85%/90% coverage floor.

## Scope Creep

None found. Every file in the plan's Files To Create/Modify tables traces to an impact-analysis item or the plan's own explicit resolution of impact-analysis's flagged transaction-boundary tension (§2) — no invented scope.

## Verdict Rationale

Full impact-analysis coverage and correct task-breakdown layering order both hold, which rules out Fail. Two minor, non-blocking issues — an unassigned trivial file in the task breakdown and one migration hazard stated in Validation Strategy but not cross-listed in the Risks section — keep this from a clean Pass, yielding Pass with Issues.
