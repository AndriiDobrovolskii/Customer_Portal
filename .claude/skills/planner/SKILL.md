---
name: planner
description: Produces the architectural implementation plan for a story from its approved spec, designs, and impact-analyzer's blast-radius survey — architectural changes, files to create/modify, risks, and validation/testing strategy. Use when the user asks to "plan the implementation for US-XXX" or wants the architectural plan before touching code. Reads docs/specifications, docs/designs/api, docs/designs/database, docs/impact-analysis, docs/product/non-functional-requirements.md; writes docs/plans. Does not write code, does not survey the affected-file/cross-module blast radius (that's impact-analyzer, which this skill now consumes rather than re-deriving), and does not decide execution order or which execution skill runs each task (that's implementation-planner).
---

# Purpose

Create a detailed architectural implementation plan before code generation begins. The plan defines what will change and how it will be validated — so implementation stays scoped to the story (`AGENTS.md` §7.8: no opportunistic refactors, no unrelated files touched).

# Operational Contract

```
Precondition: spec review is Pass/Pass with Issues; API design exists; database design exists (unless the story is genuinely read-only, stated explicitly); impact-analyzer has produced the affected-file/cross-module survey.
Input Artifacts: docs/specifications/<StoryId>-*-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; docs/impact-analysis/<StoryId>-impact-analysis.md; docs/product/non-functional-requirements.md.
Output Artifacts: docs/plans/<StoryId>-implementation-plan.md.
```

# Required Context

Read:

- `docs/specifications/<StoryId>-*-spec.md`
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
