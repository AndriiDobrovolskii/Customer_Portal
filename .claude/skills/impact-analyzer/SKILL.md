---
name: impact-analyzer
description: Surveys the blast radius of a proposed change — a new story once its spec/designs are approved, or a proposed modification to existing behavior — identifying every affected file/module/layer, cross-module ripple (service→service calls per AGENTS.md §3), migration/schema impact, and test-surface impact, before an implementation plan is drafted. Use when the user asks "what does this change touch," "impact analysis for US-xxx," or wants the affected-file survey before planning starts. This is a narrower split-out of what planner used to survey on its own — planner now consumes this skill's output rather than re-deriving it, and this skill does not sequence work, estimate risk narrative, or decide execution order (that's planner/implementation-planner). Design-only: produces a report, writes no code.
---

# Impact Analyzer

## Purpose

Answer one question precisely before anyone plans or codes anything: what does this change actually touch? A plan built on an incomplete blast-radius survey under-scopes the work; a plan built on an over-broad one invites drive-by changes AGENTS.md §7.8 forbids. This skill's only job is the survey — sequencing and risk narrative belong to `planner`/`implementation-planner`.

## Operational Contract

```
Precondition: the story's spec review is Pass or Pass with Issues; API and DB designs are approved, or explicitly not applicable for a read-only/no-schema-change story.
Input Artifacts: docs/specifications/<StoryId>-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; the existing app/modules/ layout.
Output Artifacts: docs/impact-analysis/<StoryId>-impact-analysis.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — what the story actually requires.
2. `docs/designs/api/<StoryId>-openapi.yaml` and `-api-design.md` — the endpoints being added/changed.
3. `docs/designs/database/<StoryId>-db-design.md` and `-entity-model.md` — the schema being added/changed.
4. The existing `app/modules/` layout — which modules exist today, and which files within them already exist vs. would be new.
5. `AGENTS.md` §3 — the layer table and the "cross-module calls go service → service" discipline, which §3 itself flags as "not enforced, so it is on you."

## Preconditions

Spec review Pass/Pass with Issues; API/DB designs approved (or explicitly stated N/A for a story with no schema/endpoint change).

## Workflow

1. **Affected files/modules/layers.** For each entity/endpoint the spec+designs introduce or change, list the specific files that will need to change, grouped by `AGENTS.md` §3 layer (`models.py`/`schemas.py`/`repository.py`/`cache.py`/`service.py`/`router.py`/`dependencies.py`/`exceptions.py`). Every listed file needs a stated reason — "touched because X" — never a bare path.
2. **Cross-module ripple.** Trace every place this story's service(s) will need to call another module's service (or be called by one). List caller and callee explicitly. If the story introduces a new cross-module dependency that doesn't exist today, flag it — that's a bigger architectural fact than an in-module change.
3. **Migration/schema impact.** State explicitly whether this story requires a migration. If yes, name which tables/columns/indexes are affected and which existing repository queries might be affected by the schema change (e.g. a new NOT NULL column touches every existing `INSERT`). If no migration is needed, say "none" explicitly — never omit this section silently.
4. **Test-surface impact.** List which existing test files must change (because behavior they cover shifted) versus which are wholly new. This tells `implementation-planner` where the new/updated test tasks belong without re-deriving it from scratch.

## Constraints

- This is a survey, not a plan — do not propose implementation order, risk mitigation narrative, or a validation strategy; that's `planner`.
- Do not decide the sequence execution skills run in — that's `implementation-planner`.
- Do not invent an affected file with no traceable reason from the spec/designs.

## Verification Checklist

- [ ] Every affected file has a named reason.
- [ ] Every cross-module call is listed with its caller and callee service explicitly.
- [ ] Migration/schema impact is explicitly stated — "none" or itemized, never silently omitted.
- [ ] Test-surface impact distinguishes existing-file changes from new files.
- [ ] No sequencing, risk narrative, or execution order appears in the output — those are out of scope.

## Outputs

- `docs/impact-analysis/<StoryId>-impact-analysis.md`.

## Completion Criteria

Complete only when every affected file, cross-module call, and migration/test impact is stated with a specific reason — nothing left as an unstated assumption for `planner` to rediscover.

---

# Harness Contract

This skill owns the `IMPACT_ANALYSIS` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`IMPACT_ANALYSIS`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `specification_review`, `api_design`, `openapi`, `database_design`, `entity_model`, `design_review`, `open_decisions`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `specification_review`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `design_review`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
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
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: IMPACT_ANALYSIS
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/impact-analysis/<StoryId>-impact-analysis.md
  next_stage: ARCHITECTURE_PLANNING
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required_specification` | `SPECIFICATION` |
| `changes_required_api` | `API_DESIGN` |
| `changes_required_database` | `DB_DESIGN` |

- `PASS` - the blast radius is surveyed: affected files, cross-module reach,
  and migration risk are all recorded.
- `CHANGES_REQUIRED` - the survey found that an upstream artifact is wrong,
  not merely incomplete. Route to the artifact that must change.
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
