---
name: implementation-planner
description: Breaks an approved plan and impact analysis into small, ordered, independently-verifiable implementation tasks — which of this project's execution skills (schema-builder, data-layer-builder, migration-manager, service-and-router-builder) to invoke and in what sequence, respecting AGENTS.md §3 layering (models/migration before repository, repository before service, service before router) and this project's "migration before model use" rule. Use when a plan and impact analysis are approved and work needs to be sequenced into discrete steps ("break this into tasks," "what order do I build this in," "task list for US-xxx"). Similar in spirit to agent-skills:planning-and-task-breakdown but scoped to this project's five execution skills and layering order; it does not decide what changes (that's planner/impact-analyzer) and does not itself write schema/model/service/router code or run the gate (that's the execution skills and gate-enforcer).
---

# Implementation Planner

## Purpose

Turn "what needs to change" (`planner`'s plan, `impact-analyzer`'s survey) into "in what order, by which skill" — a task list concrete enough that `story-orchestrator` (or a human) can invoke each execution skill in sequence without re-deriving the dependency order each time.

## Operational Contract

```
Precondition: planner's implementation plan and impact-analyzer's impact analysis both exist for the story.
Input Artifacts: docs/plans/<StoryId>-implementation-plan.md; docs/impact-analysis/<StoryId>-impact-analysis.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md.
Output Artifacts: docs/plans/<StoryId>-task-breakdown.md (using assets/task-template.md).
```

## Required Context

Read, in order:

1. `docs/plans/<StoryId>-implementation-plan.md` — the architectural plan (what changes, files to create/modify, risks).
2. `docs/impact-analysis/<StoryId>-impact-analysis.md` — the affected-file/cross-module/migration survey.
3. `docs/designs/database/...` and `docs/designs/api/...` — to attribute each task to the right layer/skill.
4. `AGENTS.md` §3 — the layering direction this skill's ordering rule is derived from.

## Preconditions

Both `planner`'s plan and `impact-analyzer`'s impact analysis exist for the story. If either is missing, stop and name it rather than guessing at scope.

## Workflow

1. For every affected file/layer named in the impact analysis, emit one task naming:
   - which execution skill is responsible (`schema-builder`, `data-layer-builder`, `migration-manager`, `service-and-router-builder`),
   - its `AGENTS.md` §3 layer,
   - its depends-on tasks (by Task ID),
   - a concrete verification step (e.g. "mypy clean on this file," "alembic upgrade head succeeds," "grep confirms zero sqlalchemy imports in router.py").
2. **Ordering rule, derived from AGENTS.md §3 and this project's own migration/model relationship:** `data-layer-builder` (models.py) before `migration-manager`; `migration-manager` before any task that depends on the new schema being live; `data-layer-builder`/`schema-builder` before `service-and-router-builder` (a service needs the repository/schemas to exist); `service-and-router-builder`'s service-layer tasks before its router-layer tasks within the same module. `schema-builder` and `data-layer-builder` may run in parallel (neither depends on the other).
3. `gate-enforcer` is the final task in the sequence — a single task, not embedded per-file-change-task.
4. Do not decide *what* changes — every task must trace to something the plan or impact analysis already named. If a gap surfaces (an affected file with no clear owning skill), flag it as an open question rather than inventing scope.

## Constraints

- Never write code itself — this skill only sequences work for the execution skills to do.
- Never re-derive *what* changes from the spec directly — that's `planner`/`impact-analyzer`'s job; this skill only orders what they already identified.
- No task is scoped larger than one execution skill's own job (e.g. don't bundle "write models and service" into one task).

## Verification Checklist

- [ ] Every task has an explicit skill assignment, layer, and verification method.
- [ ] The sequence respects §3's downward-only import direction and the migration-before-model-use rule.
- [ ] `gate-enforcer` appears exactly once, as the final task.
- [ ] Every task traces to a specific item in the plan or impact analysis — nothing invented.
- [ ] No task's scope spans more than one execution skill's responsibility.

## Outputs

- `docs/plans/<StoryId>-task-breakdown.md`, built from `assets/task-template.md`.

## Completion Criteria

Complete only when every task has a named skill, layer, dependency list, and verification method, and the full sequence — read top to bottom — respects AGENTS.md §3's layering direction without gaps.

---

# Harness Contract

This skill owns the `IMPLEMENTATION_PLANNING` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`IMPLEMENTATION_PLANNING`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `api_design`, `openapi`, `database_design`, `entity_model`, `impact_analysis`, `implementation_plan`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `impact_analysis`
- `implementation_plan`

## Preconditions (harness)

- Every consumed artifact is current: `status` is not `SUPERSEDED` or
  `ARCHIVED`, and the `version` this skill records in its own `inputs` is the
  version actually on disk. A stale input is `BLOCKED`, not a caveat.
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` input that this stage depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active.

## Result Envelope

Return exactly this. `story-orchestrator` records the transition; this skill
never writes `docs/workflow/workflow-state.yaml`.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: IMPLEMENTATION_PLANNING
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/plans/<StoryId>-task-breakdown.md
  next_stage: PLAN_REVIEW
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required_plan` | `ARCHITECTURE_PLANNING` |

- `PASS` - tasks are ordered, independently verifiable, and each names the
  execution skill that runs it, respecting AGENTS.md section 3 layering and
  the migration-before-model-use rule.
- `CHANGES_REQUIRED` - the architectural plan cannot be sequenced as written.
- `BLOCKED` - a mandatory input is missing or stale.

## Prohibited (harness)

- Do not update workflow state (`workflow-state.yaml`, `active-story.yaml`,
  `history.jsonl`) - `story-orchestrator` owns those.
- Do not produce an artifact this skill does not own in
  `docs/workflow/artifact-paths.yaml`.
- Do not resolve Open Decisions.
- Do not emit a retired verdict (`Pass`, `Fail`, `Pass with Issues`,
  `APPROVED`, ...) - see `artifact-lifecycle.md` section 2.
- Do not use the retired sequential story ids (`US-0NN`) or retired stage
  identifiers (`DESIGN`, `PLANNING`, `TESTS`, `VERIFICATION`, `PR`).
- Do not create commits, branches, or Pull Requests.
