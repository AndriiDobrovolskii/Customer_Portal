# Plan Review: View Audit Information (US-3.3 / spec US-013)

**Story ID:** US-3.3
**Plan Reviewed:** docs/plans/US-013-implementation-plan.md
**Task Breakdown Reviewed:** docs/plans/US-013-task-breakdown.md
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass with Issues

## Summary

The plan covers every file `impact-analyzer` identified, the task breakdown's ordering respects `AGENTS.md` §3's layering direction and this project's migration-before-model-use rule with no violations, and both the Risks and Testing Strategy sections are concrete rather than placeholder text. The verdict is Pass with Issues rather than a clean Pass for two reasons, neither a defect in the plan itself: (1) `scripts/verify_audit_chain.py` — a file the plan correctly includes (AU-AC7's `[gate]` marker) — was never listed in `docs/impact-analysis/US-013-impact-analysis.md`'s own survey, a gap in that upstream document rather than this plan; (2) two genuinely open "who builds this" questions (T6's unowned script, and the partition-maintenance job) are honestly disclosed as unresolved rather than silently decided, which is correct process but means the plan isn't yet fully actionable without the user's input.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/audit/__init__.py` | Covered | Files To Create | — |
| `app/modules/audit/models.py` | Covered | Files To Create; task breakdown T2 | — |
| `app/modules/audit/schemas.py` | Covered | Files To Create; T1 | — |
| `app/modules/audit/repository.py` | Covered | Files To Create; T2 | — |
| `app/modules/audit/service.py` | Covered | Files To Create; T4 | — |
| `app/modules/audit/router.py` | Covered | Files To Create; T5 | — |
| `app/modules/audit/dependencies.py` | Covered | Files To Create; T5 | Includes the `require_audit_read` FR-3 resolution, an elaboration of the impact analysis's flagged architectural tension, not new scope. |
| `app/modules/audit/exceptions.py` | Covered | Files To Create; T4 | — |
| `app/modules/email_verification/models.py` (rename) | Covered | Files To Modify; T2b | — |
| `app/modules/email_verification/repository.py` | Covered | Files To Modify (states "no logic change unless class renamed") | — |
| `app/modules/users/models.py` (new index) | Covered | Files To Modify; T3c | — |
| `app/modules/roles/models.py` (new index) | Covered | Files To Modify; T3c | — |
| `app/modules/profile/models.py` (new index) | Covered | Files To Modify; T3c | — |
| `app/modules/account/models.py` (new index) | Covered | Files To Modify; T3c | — |
| `app/api/v1/router.py` | Covered | Files To Modify; T5 | — |
| Migration(s) (rename, `audit_log`+view+trigger, 4 indexes) | Covered | Files To Create; T3/T3b/T3c | Plan correctly sequences the rename before `audit_log` creation, matching impact-analysis's own explicit ordering note. |
| New test files (`tests/unit/modules/audit`, `tests/integration/modules/audit`) | Covered | Files To Create; T7, T8 | — |
| `tests/unit/modules/email_verification/*`, `tests/integration/modules/email_verification/test_purge_service.py` | Covered | Files To Modify; T8 | — |
| **`scripts/verify_audit_chain.py`** | **Not in impact-analysis.md at all** | Plan's Files To Create (added after the plan's own advisor pass); T6 | This file is required by the spec (AU-AC7's `[gate]` marker was already knowable at impact-analysis time) but `docs/impact-analysis/US-013-impact-analysis.md`'s survey never lists it under any layer. The plan and task breakdown both correctly include it — this is a completeness gap in the upstream impact-analysis document, not a plan defect. Recommend `impact-analyzer`'s output be amended in place (this project's established pattern for upstream-doc gaps found downstream) rather than leaving future readers of `US-013-impact-analysis.md` to rediscover it. |

## Layering Order (Task Breakdown)

No violation found. T1 (schemas)/T2 (models/repository)/T2b (rename) run in parallel with no interdependency, correctly preceding T3/T3b (migrations, which need T2's models and T2b/T3's freed name respectively) and T4 (service, which needs T1's schemas, T2's repository, and T3b's live table). T5 (router) correctly depends only on T4. T7 (unit tests) correctly depends on T4 alone (no live database needed for fake-driven unit tests) rather than the migration tasks; T8 (integration tests) correctly depends on T5 plus every migration task (T2b, T3, T3b, T3c) since integration tests need the real, fully-migrated schema. T9 (gate-enforcer) depends on the full set including T7b. The T3/T3b sequencing (rename must commit before `audit_log` creation) is stated as a hard dependency, not just a suggestion — correctly reflects the name-collision constraint from `docs/decisions/US-3.3-open-decisions.md` OD-1.

## Risk Realism

No finding requiring a fix — the Risks section is concrete, not placeholder text: migration ordering (specific, not generic "test the migration"), partition maintenance (the exact failure mechanism — no `DEFAULT` partition means the first post-window `INSERT` including this story's own FR-2 write returns `500` — with two named resolution options), the hash-chain genesis gap's blocking effect on T3b specifically, and the moving-target pagination risk against the p95 NFR. One process note, not a risk-content defect: the partition-maintenance decision and T6's script-ownership question are both real open decisions the plan/task-breakdown correctly refuse to silently resolve, but neither is closed — `story-orchestrator` should treat both as blocking implementation start, not just informational, before `schema-builder`/`data-layer-builder` are invoked for T1/T2.

## Test-Strategy Realism

No finding. The Testing Strategy names specific ACs against specific test types (e.g. "AU-AC7 (mutate a row through the ordinary application session... then run `scripts/verify_audit_chain.py`...)" is concrete and directly reflects the OD-12 no-privileged-connection reality rather than the story's now-superseded Enforcement Matrix wording), and the task breakdown's T7/T7b/T8 split cleanly separates hand-written-fake unit coverage from real-Postgres/Valkey integration coverage per `AGENTS.md` §5.

## Scope Creep

No findings. Every file in the plan traces to the spec, the DB/API designs, or the impact analysis (with the one exception already noted under Impact-Analysis Coverage, which is the reverse problem — an under-surveyed item, not an invented one). The `require_audit_read` wrapper (T5) is a resolution of an architectural tension impact-analyzer itself flagged, not new scope.

## Verdict Rationale

Pass with Issues: full impact-analysis coverage (with one upstream-document completeness gap noted, not a plan defect), no layering-order violations, and realistic risk/test strategies. The verdict is not a clean Pass because two genuinely open ownership/design decisions (T6's script, and the partition-maintenance mechanism) remain unresolved by design — correctly disclosed rather than guessed, but still blocking for `story-orchestrator` before execution-skill invocation begins.
