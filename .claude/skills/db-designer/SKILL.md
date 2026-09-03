---
name: db-designer
description: Produces the persistence design (entities, columns, constraints, indexes, relationships) for a story from its approved specification and API design, expressed as SQLAlchemy 2.0 declarative models (Mapped[]/mapped_column()) consistent with this project's layering rules — never JPA/Hibernate. Use when a story's spec and OpenAPI design are approved and the database shape needs to be decided before an Alembic migration or repository is written ("design the schema for this story," "what tables does US-xxx need," "db design for..."). Does not write the migration itself or touch models.py — it produces the design artifact planner and the eventual implementation work from.
---

# DB Designer

## Purpose

Design the persistence model a story requires, as a reviewable artifact — before any `models.py` change or Alembic migration exists. This is design, not implementation: no code is written here, only the decisions a migration/repository author will need.

## Operational Contract

```
Precondition: story-spec-reviewer's verdict is Pass or Pass with Issues; an OpenAPI design exists if the story has endpoints.
Input Artifacts: docs/specifications/<StoryId>-spec.md, docs/reviews/specifications/<StoryId>-spec-review.md, docs/designs/api/<StoryId>-openapi.yaml (if it exists), docs/product/business-rules.md, docs/product/business-glossary.md.
Output Artifacts: docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — functional and validation requirements.
2. `docs/reviews/specifications/<StoryId>-spec-review.md` — must be **Pass** or **Pass with Issues**; do not design against a **Fail**.
3. `docs/designs/api/<StoryId>-openapi.yaml` (if it exists) — request/response shapes constrain what the persistence layer must hold and return.
4. `docs/product/business-rules.md` and `docs/product/business-glossary.md` — canonical terms and constraints (uniqueness, cardinality) already established elsewhere in the product.
5. `AGENTS.md` §3 (Architectural Constraints) and the "Migrations" bullet in §4 — this project's persistence conventions: explicit `Mapped[]`/`mapped_column()`, no reliance on ORM defaults, eager-loading discipline, no `create_all()`.

## Responsibilities

Identify, per entity touched by the story:

- Attributes, with explicit types, lengths, nullability, and default values — never left to SQLAlchemy/PostgreSQL defaults.
- Primary keys, foreign keys, and their `ondelete` behavior.
- Uniqueness constraints (state whether case-sensitive — this project has precedent for case-insensitive email uniqueness; check `business-rules.md` before assuming a new entity follows the same rule).
- Indexes needed for the query patterns the spec/API design imply (e.g. a lookup-by-token endpoint needs an index on that token column).
- Relationships and their cardinality, and which side will need eager loading (`joinedload`/`selectinload`) per `AGENTS.md` §3's "Eager loading is mandatory" rule — state this explicitly so the repository layer doesn't discover it via a `MissingGreenlet` in production.

## Security

Flag sensitive columns (password hashes, tokens, MFA secrets, PII) and state their storage requirement (e.g. "bcrypt hash only, never the raw value"; "encrypted at rest" only if a decision actually requires it — don't invent encryption requirements the spec doesn't state).

## Constraints

- Every column decision must be explicit — do not write "use sensible defaults" or leave a field's nullability unstated.
- Do not invent an entity, column, or constraint the spec doesn't support; if something is needed but undecided, log it as a gap referencing `docs/decisions/<StoryId>-open-decisions.md` rather than guessing.
- Migration mechanics (guards, `if_not_exists`, the upgrade/downgrade cycle) belong to the implementation stage, not this design — reference `AGENTS.md` §4's "Migrations" bullet in the output as the standard the eventual migration must follow, but do not draft the migration.

## Outputs

Create:

- `docs/designs/database/<StoryId>-db-design.md` — narrative design: what changed and why, per entity.
- `docs/designs/database/<StoryId>-entity-model.md` — the concrete model: entities, columns (name/type/length/nullable/default), constraints, indexes, and relationships with their loading strategy.

## Completion Criteria

Complete only when every entity the story touches has fully specified columns, constraints, and relationships, sensitive data is identified with its storage requirement, and every entity is traceable to a functional requirement or acceptance criterion in the spec.

---

# Harness Contract

This skill owns the `DB_DESIGN` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`DB_DESIGN`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `specification`, `api_design`, `openapi`, `open_decisions`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `specification`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `open_decisions`

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
  verdict: PASS | BLOCKED
  stage: DB_DESIGN
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/designs/database/<StoryId>-db-design.md
    - docs/designs/database/<StoryId>-entity-model.md
  next_stage: DESIGN_REVIEW
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

- `PASS` - the persistence design is complete: explicit types, nullability,
  uniqueness, indexes, and a named eager-loading strategy per relationship.
- `NOT_APPLICABLE` - the approved specification explicitly states the story
  changes no persistence behavior. Record the decision and the citation.
- `BLOCKED` - the specification or API design is missing or stale, or a
  blocking Open Decision affects the schema.

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
