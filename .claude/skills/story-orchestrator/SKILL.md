---
name: story-orchestrator
description: Sequences the full story pipeline end-to-end per docs/workflow/stage-map.yaml — us-clarifier, story-spec-writer, story-spec-reviewer, openapi-designer + db-designer, impact-analyzer + planner, plan-reviewer, implementation-planner, the execution skills (schema-builder, data-layer-builder, migration-manager, service-and-router-builder) in dependency order, test-writer, gate-enforcer, implementation-verifier, reconciliation-reviewer, security-reviewer, pr-preparer — tracking pipeline state via docs/workflow/workflow-state.yaml, docs/workflow/active-story.yaml, and a per-story docs/catalog/<StoryId>-pipeline-status.md checklist. Use when the user wants to "run the pipeline for US-xxx," "move this story through the whole workflow," or "drive this story end to end." Acts as a checklist/sequencer only — it invokes the other skills rather than doing their work itself, and it stops at any review gate that reports Fail rather than proceeding, never skipping a review stage even when the change looks obviously fine (mirrors AGENTS.md §1's "report conflicts, don't silently relax a rule" applied to pipeline stages). Does not itself write specs, designs, plans, code, or reports.
---

# Story Orchestrator

## Purpose

Drive one story through every stage in `docs/workflow/stage-map.yaml`, invoking each stage's owning skill, reading its actual verdict, and only advancing on a genuine Pass. This skill's entire value is refusing to skip a stage or fabricate a result — it does none of the substantive work itself.

## Operational Contract

```
Precondition: docs/workflow/active-story.yaml names the story in scope.
Input Artifacts: docs/workflow/stage-map.yaml (read-only reference); docs/workflow/active-story.yaml; docs/workflow/workflow-state.yaml.
Output Artifacts: updates to docs/workflow/workflow-state.yaml and append-only docs/workflow/history.jsonl; docs/catalog/<StoryId>-pipeline-status.md as a human-readable rollup.
```

## Required Context

Read, in order:

1. `docs/workflow/stage-map.yaml` — the 11-stage list (`CLARIFICATION, SPECIFICATION, SPEC_REVIEW, DESIGN, PLANNING, TESTS, IMPLEMENTATION, VERIFICATION, SECURITY_REVIEW, RECONCILIATION, PR`). Read-only — never edited by this skill.
2. `docs/workflow/active-story.yaml` — the `active_story` field naming which story is in scope. **This file has carried a stated assumption before** (e.g. a note flagging that the "next" story was inferred from backlog order rather than confirmed) — surface any such comment to the user rather than silently trusting the value if it looks uncertain.
3. `docs/workflow/workflow-state.yaml` — `story`, `current_stage`, `status` fields recording where the active story currently sits.

## Preconditions

`docs/workflow/active-story.yaml` names a story. If `workflow-state.yaml`'s `story` field doesn't match `active-story.yaml`'s `active_story`, stop and flag the mismatch rather than guessing which is authoritative.

## Stage → Skill Map

| Stage | Owning skill(s) |
|---|---|
| CLARIFICATION | `us-clarifier` |
| SPECIFICATION | `story-spec-writer` |
| SPEC_REVIEW | `story-spec-reviewer` |
| DESIGN | `openapi-designer`, `db-designer` |
| PLANNING | `impact-analyzer` → `planner` → `implementation-planner` → `plan-reviewer` |
| TESTS | `test-writer` |
| IMPLEMENTATION | `schema-builder`, `data-layer-builder` → `migration-manager`, then `service-and-router-builder`, per `implementation-planner`'s task breakdown ordering, then `gate-enforcer` |
| VERIFICATION | `implementation-verifier` |
| SECURITY_REVIEW | `security-reviewer` |
| RECONCILIATION | `reconciliation-reviewer` |
| PR | `pr-preparer` |

`PLANNING` and `IMPLEMENTATION` each span multiple skills — track their sub-steps in `docs/catalog/<StoryId>-pipeline-status.md` (see `assets/pipeline-checklist-template.md`) rather than adding fields to `workflow-state.yaml`; a schema change to that file needs its own explicit user sign-off, out of this skill's authority (`AGENTS.md` §1).

## Workflow

1. Read `workflow-state.yaml` to find the active story's `current_stage` and `status`.
2. Invoke the skill(s) that own that stage, per the map above. For `PLANNING`/`IMPLEMENTATION`, invoke their sub-skills in the stated order, updating `docs/catalog/<StoryId>-pipeline-status.md` after each sub-step.
3. Read that skill's actual verdict/output — never assume success from the fact that it ran without an error.
4. **On Pass:** update `workflow-state.yaml`'s `current_stage` to the next stage in `stage-map.yaml` and `status` accordingly; append an entry to `docs/workflow/history.jsonl` recording the stage, verdict, and timestamp.
5. **On Fail (or Pass with Issues where the user hasn't explicitly accepted the risk):** stop. Report which stage failed, the skill's stated reason, and do not advance `current_stage` or invoke any downstream skill.
6. Never skip a stage because the change "looks obviously fine" — every stage in `stage-map.yaml` must actually run and its result actually be read for this story, with no exceptions.
7. When every stage reaches Pass through `PR`, update `docs/catalog/<StoryId>-pipeline-status.md` to reflect the story reached PR, and report that `pr-preparer`'s draft is ready for the user's review.

## Constraints

- Never edit `docs/workflow/stage-map.yaml`.
- Never write specs, designs, plans, code, or reports directly — always invoke the owning skill.
- Never advance `current_stage` past a stage whose owning skill reported anything other than Pass (or a user-accepted Pass with Issues).
- Never add fields to `workflow-state.yaml`'s schema — track sub-steps in `docs/catalog/` instead.

## Verification Checklist

- [ ] `workflow-state.yaml` and `active-story.yaml` agree on which story is active, or the mismatch was flagged.
- [ ] Every stage's owning skill was actually invoked — none skipped.
- [ ] Every stage's actual verdict was read before advancing past it.
- [ ] `history.jsonl` has one appended entry per stage transition, never edited retroactively.
- [ ] A Fail at any stage stopped the pipeline and named the blocking stage — no downstream skill was invoked afterward.
- [ ] `docs/catalog/<StoryId>-pipeline-status.md` reflects sub-steps for `PLANNING` and `IMPLEMENTATION`, not just the top-level stage.

## Outputs

- Updated `docs/workflow/workflow-state.yaml`.
- Appended `docs/workflow/history.jsonl` entries.
- `docs/catalog/<StoryId>-pipeline-status.md`.

## Completion Criteria

Complete only when every stage in `stage-map.yaml` has a recorded outcome for the active story — either the story reached `PR` with every stage Pass, or the pipeline stopped at a named stage with the specific reason recorded, never silently abandoned mid-sequence.
