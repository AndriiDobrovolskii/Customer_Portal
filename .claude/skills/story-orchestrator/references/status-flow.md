# Status Flow

Report the current workflow state. **Read-only.** No skill invocation, no state
change, no artifact generation, no write-capable GitHub calls.

## Inputs

- `docs/workflow/active-story.yaml`, `docs/workflow/workflow-state.yaml`
- `docs/workflow/stage-map.yaml`, `docs/workflow/artifact-paths.yaml`
- `docs/workflow/artifact-lifecycle.md`
- `docs/catalog/stories.yaml`, `docs/catalog/{story_id}-pipeline-status.md`
- the current stage's output and the relevant review artifact (read only)
- `docs/workflow/history.jsonl` (tail)
- `git status`

## Report

- active Story id and its catalog `state`;
- workflow `status`;
- `current_stage`, `previous_stage`, `last_completed_stage`, `attempt`, and
  `implementation_substep` when inside `IMPLEMENTATION`;
- `last_invoked_skill`, `last_result`;
- for `current_stage`: resolved input paths with versions and output paths;
  whether each exists and its `status`;
- stale inputs — a downstream artifact recording an older upstream version;
- pending Open Decisions, and any blocking `TODO` / `TBD` / `FIXME` marker in an
  `APPROVED` artifact;
- `pending_human_gate`: stage, status, required artifacts, and the exact command;
- blocking issue count; carried non-blocking findings;
- current branch; working-tree changes unrelated to the active Story;
- the next stage from `stage-map.yaml` and the recommended command.

## Health value

One of: `HEALTHY`, `WAITING_FOR_HUMAN`, `BLOCKED`, `INCONSISTENT`, `IDLE`,
`COMPLETED`, `ARCHIVED`.

Report `INCONSISTENT` when: the two state files disagree; `current_stage` is not
in `stage_order` (including when it is a retired identifier such as `PR` or
`VERIFICATION`); more than one current artifact exists for a type; a downstream
artifact references a stale upstream version; or the recorded state contradicts
the artifacts on disk.

## Result

A concise console report. Write no durable file unless explicitly asked. Suggest
exactly one of `/so:next`, `/so:start <StoryId>`, `/so:approve`, `/so:reject`,
`/so:archive`, or a specific blocker resolution.
