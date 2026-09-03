---
name: story-orchestrator
description: >
  Sequences a story through the delivery workflow defined in
  docs/workflow/stage-map.yaml, invoking each stage's owning skill, reading its
  Result Envelope, and recording the transition in
  docs/workflow/workflow-state.yaml plus docs/workflow/history.jsonl. Use when
  the user wants to "run the pipeline for US-x.y", "advance this story", "start
  US-x.y", or asks where a story stands. Four modes, one per /so command: start
  (activate a story), continue (advance exactly one stage), status (read-only
  report), archive (consolidate a completed delivery). Acts as a sequencer
  only - it invokes the owning skills rather than doing their work, stops at any
  stage whose skill reports anything other than PASS or NOT_APPLICABLE, and
  never treats a review skill's PASS as human approval. Does not itself write
  specs, designs, plans, code, or reports, and never pushes, opens, or merges a
  Pull Request.
---

# Story Orchestrator

## Purpose

Drive one story through the stages in `docs/workflow/stage-map.yaml`, invoking
each stage's owning skill, reading its actual Result Envelope, and advancing
only on a genuine `PASS`. This skill's entire value is refusing to skip a stage
or fabricate a result — it does none of the substantive work itself.

## The stage map is the authority

**This skill carries no stage list of its own.** The canonical stage order,
each stage's owning skill, its inputs and outputs, its `next` target, its
`loop_back` keys, and which stages are human gates all live in
`docs/workflow/stage-map.yaml`. Read it at the start of every run. If this
document and the stage map ever disagree, the stage map wins and this document
is the bug.

Likewise, never hard-code an artifact path. Resolve every one from
`docs/workflow/artifact-paths.yaml`.

A stage identifier that is not in `stage_order` — including any entry in
`retired_identifiers` — is an `INCONSISTENT` state. Report it and the canonical
replacement; never silently translate it and carry on.

## Operational Contract

```
Precondition: docs/workflow/active-story.yaml names the story in scope, and docs/workflow/workflow-state.yaml agrees with it.
Input Artifacts: docs/workflow/stage-map.yaml, artifact-paths.yaml, artifact-lifecycle.md, artifact-schema.md, state-schema.md (all read-only); docs/workflow/active-story.yaml; docs/workflow/workflow-state.yaml; docs/catalog/stories.yaml.
Output Artifacts: docs/workflow/workflow-state.yaml; append-only docs/workflow/history.jsonl; docs/catalog/<StoryId>-pipeline-status.md; docs/evidence/<StoryId>-delivery-summary.md and docs/knowledge/project-state.md (archive mode only).
```

## Canonical sources

- Workflow, routing, ownership, gates: `docs/workflow/stage-map.yaml`.
- Artifact paths and owners: `docs/workflow/artifact-paths.yaml`.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- State and history event schemas: `docs/workflow/state-schema.md`.
- Story lifecycle status: `docs/catalog/stories.yaml`.
- Non-normative overview: `docs/workflow/stages.md`.

## Modes

One per `/so` command. Each has its own reference file; read the one for the
mode you are in.

| Mode | Command | Reference |
|---|---|---|
| start | `/so:start <StoryId>` | `references/start-flow.md` |
| continue | `/so:next` | `references/continue-flow.md` |
| status | `/so:status` | `references/status-flow.md` |
| archive | `/so:archive` | `references/archive-flow.md` |

`/so:approve` and `/so:reject` are handled inside continue mode's human-gate
branch — see `references/continue-flow.md` step 3.

## Resolving a stage to its skill

Do not consult a table in this file. For the current stage:

1. `stage := workflow-state.yaml.current_stage`; confirm it is in
   `stage-map.yaml` `stage_order`.
2. If `stages.<stage>.type` is `human_gate` — invoke no skill. Follow the
   human-gate branch of continue mode.
3. If `type` is `terminal` — only archive mode reaches it.
4. If `type` is `automated_skill` — invoke `stages.<stage>.skill`.
5. If `type` is `composite_skill` — invoke `stages.<stage>.skills` in the order
   given, which is fixed by `AGENTS.md` §3 layering and refined per story by
   `task_breakdown`. Record each sub-step in `pipeline_status` and set
   `implementation_substep` in `workflow-state.yaml`. Only `IMPLEMENTATION` is
   composite today.

Some stages are `optional: true` with an `optional_when` condition. A skill may
return `NOT_APPLICABLE` only when that condition holds and it records why.

## Reading a result

Every stage skill returns the Result Envelope defined in
`artifact-lifecycle.md`. Read the actual envelope, then inspect the artifacts it
claims to have produced at their registry paths. **Never infer success from the
fact that a skill ran without erroring.**

- `PASS` / `NOT_APPLICABLE` → advance to `stages.<stage>.next`, `attempt := 1`.
- `CHANGES_REQUIRED` → the skill names a `loop_back` key. It must exist under
  `stages.<stage>.loop_back`; an unknown key is rejected and the stage holds as
  `BLOCKED` pending a human decision.
- `BLOCKED` → the stage does not move; `status := BLOCKED`; surface
  `blocking_issues`.

A retired verdict (`Pass`, `Fail`, `Pass with Issues`, `APPROVED`, …) from a
skill is a defect — map it via `artifact-lifecycle.md` §2 and report that the
skill needs updating, rather than guessing what it meant.

## Human gates

A gate stage stops the workflow for a person. Build `pending_human_gate` per
`state-schema.md`, set `status: WAITING_FOR_HUMAN`, list the required artifacts
with their versions and the automated verdict that fed the gate, and stop.

**A review skill returning `PASS` is not human approval.** Only `/so:approve`
records one. Never infer approval, and never pass a gate automatically —
including when running several stages at the user's request.

## Workflow invariants

Check before invoking anything. On failure: hold, report, and name the earliest
stage responsible. Do not route.

- `active-story.yaml.active_story` equals `workflow-state.yaml.story`.
- `current_stage` is in `stage_order`.
- No input artifact for the current stage is `SUPERSEDED` or `ARCHIVED`.
- No downstream artifact records an older `version` of an upstream artifact
  than the one on disk (`artifact-schema.md` staleness contract).
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` artifact this stage depends on.
- Exactly one story is active.

## Constraints

- Never edit `docs/workflow/stage-map.yaml`, `artifact-paths.yaml`, or any of
  the schema documents.
- Never write specs, designs, plans, code, or reports directly — always invoke
  the owning skill named in the stage map.
- Never advance past a stage whose skill reported anything other than `PASS` or
  `NOT_APPLICABLE`.
- Never skip a stage because the change "looks obviously fine".
- Never add a field to `workflow-state.yaml`'s schema; a schema change needs
  explicit user sign-off (`AGENTS.md` §7.8). Track sub-steps in
  `pipeline_status` instead.
- Never rewrite `history.jsonl`. It is append-only, one event per transition.
- Never create, push, or merge a Pull Request (`AGENTS.md` §1).

## Verification Checklist

- [ ] The stage list came from `stage-map.yaml` this run, not from memory.
- [ ] `workflow-state.yaml` and `active-story.yaml` agree, or the mismatch was
      flagged and nothing advanced.
- [ ] The stage's owning skill was actually invoked and its Result Envelope
      actually read.
- [ ] Any `loop_back` key named by a skill exists under that stage in the map.
- [ ] Exactly one `history.jsonl` event was appended per transition.
- [ ] A non-`PASS` verdict stopped the pipeline and named the blocking stage —
      no downstream skill ran afterward.
- [ ] No human gate was passed without `/so:approve`.
- [ ] `pipeline_status` reflects `IMPLEMENTATION`'s sub-steps, not just the
      top-level stage.

## Completion Criteria

Continue mode is complete when exactly one transition has been recorded, or the
workflow is holding at a named stage with a specific reason — never silently
abandoned mid-sequence.
