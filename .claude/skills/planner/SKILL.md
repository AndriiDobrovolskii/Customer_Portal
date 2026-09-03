---
name: planner
description: Produces the architectural implementation plan for a story from its approved spec, designs, and impact-analyzer's blast-radius survey — architectural changes, files to create/modify, risks, and validation/testing strategy. Use when the user asks to "plan the implementation for US-XXX" or wants the architectural plan before touching code. Reads docs/specifications, docs/designs/api, docs/designs/database, docs/impact-analysis, docs/product/non-functional-requirements.md; writes docs/plans. Does not write code, does not survey the affected-file/cross-module blast radius (that's impact-analyzer, which this skill now consumes rather than re-deriving), and does not decide execution order or which execution skill runs each task (that's implementation-planner).
---

# Purpose

Create a detailed architectural implementation plan before code generation begins. The plan defines what will change and how it will be validated — so implementation stays scoped to the story (`AGENTS.md` §7.8: no opportunistic refactors, no unrelated files touched).

# Operational Contract

```
Precondition: spec review is Pass/Pass with Issues; API design exists; database design exists (unless the story is genuinely read-only, stated explicitly); impact-analyzer has produced the affected-file/cross-module survey.
Input Artifacts: docs/specifications/<StoryId>-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; docs/impact-analysis/<StoryId>-impact-analysis.md; docs/product/non-functional-requirements.md.
Output Artifacts: docs/plans/<StoryId>-implementation-plan.md.
```

# Required Context

Read:

- `docs/specifications/<StoryId>-spec.md`
- `docs/designs/api/<StoryId>-openapi.yaml`, `docs/designs/api/<StoryId>-api-design.md`
- `docs/designs/database/<StoryId>-db-design.md`, `docs/designs/database/<StoryId>-entity-model.md`
- `docs/impact-analysis/<StoryId>-impact-analysis.md` — the affected-file/cross-module/migration survey; this skill builds the plan from it rather than re-surveying the blast radius itself.
- `docs/product/non-functional-requirements.md`
- The existing module under `app/modules/` this story extends (or the nearest sibling module, if this is a new one) — mirror its actual file layout rather than assuming one.

# Preconditions

Spec review is Pass/Pass with Issues, an API design exists, a database design exists (unless the story is genuinely read-only with no schema change — state that explicitly if so, don't silently skip the design docs), and `impact-analyzer` has produced the blast-radius survey this plan builds on.

# Responsibilities

Determine, following `AGENTS.md` §3 layering (`router → dependencies → service → repository/cache → models/schemas`) and building on `impact-analyzer`'s survey rather than re-deriving it:

- architectural changes the story requires
- new files required, and which existing files are modified (per `impact-analyzer`'s survey)
- risks (concurrency, migration hazards per `AGENTS.md` §4 "Migrations", breaking an existing contract)
- dependencies on other stories or Open Decisions still unresolved

# Planning Rules

- Minimize unrelated changes; list only files the story's own scope touches.
- Every planned file change traces back to a requirement in the spec or design docs — no speculative additions.
- Call out anywhere the plan would need to touch a file `AGENTS.md` §7.9 protects (`pyproject.toml` contracts, `migrations/env.py`, `.pre-commit-config.yaml`) — those require explicit user sign-off, not silent inclusion.

# Plan Structure

Write `docs/plans/<StoryId>-implementation-plan.md` with these sections: Goal · Architectural Changes · Files To Create · Files To Modify · Risks · Validation Strategy (how `pre-commit run --all-files`/mypy/import-linter stay green) · Testing Strategy (unit fakes vs. integration-on-real-PG-and-Valkey split, per `AGENTS.md` §5). Execution order and which execution skill runs each task belong to `implementation-planner`'s task breakdown, not this plan.

# Outputs

Create:

- `docs/plans/<StoryId>-implementation-plan.md` — the plan, per the structure above.

# Completion Criteria

- Every architectural change traces to a specific requirement and to an item already identified in `impact-analyzer`'s survey.
- Validation strategy and testing strategy are both stated, not left implicit.
- Any protected-file touch or unresolved Open Decision is flagged, not buried.

---

# Harness Contract

This skill owns the `ARCHITECTURE_PLANNING` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`ARCHITECTURE_PLANNING`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `open_decisions`, `specification`, `specification_review`, `api_design`, `openapi`, `database_design`, `entity_model`, `design_review`, `impact_analysis`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `open_decisions`
- `specification`
- `specification_review`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `design_review`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `impact_analysis`

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
  stage: ARCHITECTURE_PLANNING
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/plans/<StoryId>-implementation-plan.md
  next_stage: IMPLEMENTATION_PLANNING
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required_impact` | `IMPACT_ANALYSIS` |
| `changes_required_specification` | `SPECIFICATION` |

- `PASS` - the architectural plan names every file to create or modify, the
  risks, and how the change is validated.
- `CHANGES_REQUIRED` - planning revealed a gap in the impact survey or the
  specification that must be closed first.
- `BLOCKED` - a mandatory input is missing or stale, or a blocking Open
  Decision prevents committing to an approach.

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
