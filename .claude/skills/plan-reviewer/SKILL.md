---
name: plan-reviewer
description: Reviews planner's implementation plan (docs/plans/<StoryId>-implementation-plan.md) and implementation-planner's task breakdown (docs/plans/<StoryId>-task-breakdown.md) against the approved spec, impact analysis, and API/DB designs before implementation starts — checking completeness, correct layering order, realistic risk and test strategy, and no scope creep beyond the approved spec. Use when the user asks to "review the plan for US-xxx," "check this plan before we build," or wants sign-off before implementation begins. Mirrors story-spec-reviewer's audit-only pattern: this skill produces a findings report and a verdict, it never rewrites the plan or task breakdown itself — a Fail sends the user back to planner/implementation-planner, not to this skill.
---

# Plan Reviewer

## Purpose & Role

This skill is the quality gate between "a plan exists" and "implementation starts." It reads `planner`'s architectural plan and `implementation-planner`'s task breakdown side by side with the spec, impact analysis, and API/DB designs they were built from, and produces a structured, evidence-based review report. The role is strictly auditor, not author — findings are reported, never silently fixed.

## Operational Contract

```
Precondition: planner's implementation plan and implementation-planner's task breakdown both exist for the story.
Input Artifacts: docs/plans/<StoryId>-implementation-plan.md; docs/plans/<StoryId>-task-breakdown.md; docs/impact-analysis/<StoryId>-impact-analysis.md; docs/specifications/<StoryId>-*-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md.
Output Artifacts: docs/reviews/plans/<StoryId>-plan-review.md.
```

## When To Use / When Not To Use

**Use this skill when:** a plan and task breakdown already exist and need validation before implementation starts; the user wants to know whether the plan fully covers the impact analysis, respects layering order, or has realistic risk/test coverage.

**Do not use this skill when:** no plan exists yet (that's `planner`/`implementation-planner`'s job); the user wants a code review (that's `implementation-verifier`/`gate-enforcer`, which review code, not plan documents); the user asks to just "fix" the plan — flag that this skill reports findings, it doesn't rewrite them.

## Inputs & Preconditions

Both `docs/plans/<StoryId>-implementation-plan.md` and `docs/plans/<StoryId>-task-breakdown.md` must exist, alongside the spec, impact analysis, and API/DB designs they derive from. If any is missing, say so and stop rather than reviewing an incomplete set.

## Step-by-Step Review Workflow

1. **Extract ground truth.** Read the spec, impact analysis, and API/DB designs first — these are what the plan and task breakdown must be measured against, not each other.
2. **Read both plan-stage artifacts once through**, then go back through each for the checks below.
3. **Check plan completeness against the impact analysis.** Every affected file `impact-analyzer` named should appear in `planner`'s Files To Create/Modify, and every plan item should trace to something the impact analysis or spec actually identified.
4. **Check layering order in the task breakdown.** `implementation-planner`'s sequence must respect `AGENTS.md` §3's downward-only direction and this project's migration-before-model-use rule — flag any task that depends on a layer built after it.
5. **Check risk realism.** Does `planner`'s Risks section actually cover migration hazards (`AGENTS.md` §4 "Migrations"), concurrency, and contract-breaking changes where the impact analysis or DB design implies they're relevant — not just a generic "testing will catch issues" placeholder?
6. **Check test-strategy realism** against `AGENTS.md` §5's unit-fake vs. integration-on-real-infrastructure split — does the plan's Testing Strategy actually name which parts are unit vs. integration, or is it vague?
7. **Check for scope creep.** Flag any planned file change or task with no traceable origin in the impact analysis or spec.
8. **Form the verdict:** **Pass** (complete, correctly ordered, realistic risk/test strategy, no scope creep) / **Pass with Issues** (no missing coverage or ordering violation, but risk/test-strategy gaps or minor scope creep) / **Fail** (any impact-analysis item missing from the plan, or a layering-order violation in the task breakdown — these block implementation).
9. **Write and save the report** using `assets/template.md`, to `docs/reviews/plans/<StoryId>-plan-review.md`. If a review already exists at that path, treat this run as the canonical update and tell the user you replaced it.

## Constraints

- Do not rewrite the plan or task breakdown — report findings only; a Fail sends the user back to `planner`/`implementation-planner`.
- Every finding cites the specific plan/task-breakdown line or impact-analysis item it's based on — no unsupported assertions.
- Always write the durable artifact to `docs/reviews/plans/` — a review that only exists in chat can't be referenced by other contributors or by `story-orchestrator`.

## Validation Checklist

- [ ] Spec, impact analysis, and API/DB designs were read in full before judging the plan.
- [ ] Every impact-analysis item is checked against the plan's Files To Create/Modify.
- [ ] The task breakdown's ordering is checked against AGENTS.md §3's layering direction.
- [ ] Risk and test-strategy realism are checked against AGENTS.md §4/§5, not just their presence.
- [ ] Every finding cites specific evidence (file, section, or line) from the plan/task-breakdown/impact-analysis.
- [ ] The verdict is consistent with the findings (any missing coverage or ordering violation forces Fail).
- [ ] The report was saved to `docs/reviews/plans/<StoryId>-plan-review.md`.

## Outputs

- `docs/reviews/plans/<StoryId>-plan-review.md`.

## Completion Criteria

Complete only when every impact-analysis item has a coverage status in the plan, the task breakdown's ordering has been checked against AGENTS.md §3, and the verdict is consistent with all findings.
