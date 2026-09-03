# Continue Flow

Advance the active Story by **at most one** workflow stage. Primary mode, also
invoked as `/so:next`.

## Inputs

- `docs/workflow/active-story.yaml`
- `docs/workflow/workflow-state.yaml`
- `docs/workflow/stage-map.yaml` (workflow + routing authority)
- `docs/workflow/artifact-paths.yaml` (path authority)
- `docs/workflow/artifact-lifecycle.md`, `docs/workflow/state-schema.md`
- `AGENTS.md`

## Algorithm

### 1. Resolve the active Story

Read `active-story.yaml`. Confirm exactly one `active_story` and that
`workflow-state.yaml.story` matches. If none: stop with
`BLOCKED — run /so:start <StoryId>`. If they disagree: stop `INCONSISTENT`. Do
not guess which file is authoritative.

### 2. Resolve the current stage

Read `current_stage`, `status`, `attempt`, `pending_human_gate`. `current_stage`
must be a member of `stage-map.yaml` `stage_order`. If it is a
`retired_identifiers` key instead, report the canonical replacement and stop
`INCONSISTENT` — do not silently translate it.

### 3. If the current stage is a human gate (`type: human_gate`)

Invoke no skill. Depending on `pending_human_gate.status`:

- `PENDING` → re-report the gate (required artifacts with versions, the
  automated verdict, blocking findings, and the exact `/so:approve` |
  `/so:reject` command) and stop.
- `APPROVED` → advance `current_stage` to the gate's `on_approve`, clear
  `pending_human_gate`, set `status`, append history, stop.
- `REJECTED` → route to the gate's `on_reject`, clear `pending_human_gate`,
  append history, stop.

If `pending_human_gate` is `null`, build it per `state-schema.md` and stop
`WAITING_FOR_HUMAN`.

**A review skill's `PASS` is never human approval.** Never infer one from the
other.

### 4. Validate workflow invariants

State files agree; no artifact for this story is `SUPERSEDED` while a downstream
artifact still records its old version; no blocking Open Decision affects the
stage about to run; no `TODO` / `TBD` / `FIXME` in an `APPROVED` artifact the
stage depends on. On failure: hold, report, and recommend the earliest
responsible stage. Do not route.

### 5. Check for existing stage output

Resolve `stages.<current>.outputs` through `artifact-paths.yaml`. If a current,
valid output already exists — right `story`, `status` not `SUPERSEDED` or
`ARCHIVED`, inputs not stale, no open `CHANGES_REQUIRED` / `BLOCKED` record —
do not regenerate. Validate it and go to step 7 using its recorded verdict.
Otherwise continue.

### 6. Invoke the one responsible skill

`skill := stages.<current>.skill`. Confirm it exists under `.claude/skills/`.
Invoke it with the Story id, the canonical stage, and the resolved input paths.
Wait. Read the Result Envelope, then inspect the produced artifacts at their
registry paths — never assume success from the fact that the skill ran without
erroring.

Two stages are special:

- **`BACKLOG_SYNC`** — respect its `run_policy`. Do not auto-run it on every
  continue.
- **`IMPLEMENTATION`** — `type: composite_skill`. Invoke its `skills` in the
  order fixed by `AGENTS.md` §3 layering and refined by `task_breakdown`:
  `schema-builder` → `data-layer-builder` → `migration-manager` →
  `service-and-router-builder`. Record each sub-step in `pipeline_status`
  (`docs/catalog/{story_id}-pipeline-status.md`) and set
  `implementation_substep` in `workflow-state.yaml`. The stage completes only
  when every sub-step is done; a sub-step failure routes via the stage's
  `loop_back`. Do not add fields to `workflow-state.yaml` to track this.

### 7. Apply the result

- `PASS` / `NOT_APPLICABLE` → `current_stage := stages.<current>.next`,
  `attempt := 1`.
- `CHANGES_REQUIRED` → verify the named key exists in
  `stages.<current>.loop_back`; route to its target; `attempt += 1` if that
  stage was attempted before. An unknown key → hold `BLOCKED`, human decision.
- `BLOCKED` → keep the stage; `status: BLOCKED`; surface `blocking_issues`.

Never advance past a stage whose skill reported anything other than `PASS` or
`NOT_APPLICABLE`. Never skip a stage because the change "looks obviously fine".

### 8. Record the transition

Update `workflow-state.yaml` per `state-schema.md`. Append exactly one
`history.jsonl` event. Stop — do not recursively continue to another stage.

## Continue Result

Return: active Story; the stage processed; the skill routed to; the verdict;
produced artifacts with versions; the transition; the ending stage; workflow
status; the human gate if any, with its exact approval command; blocking issues;
and the recommended next command — normally `/so:next`, or `/so:approve` at a
gate.
