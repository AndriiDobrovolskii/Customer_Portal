# Start Flow

Activate one eligible User Story and initialize its workflow state. Explicit and
infrequent; not used during normal continuation.

## Required input

Story id in epic-dotted form, e.g. `/so:start US-4.1`. The retired sequential
form (`US-014`) is not accepted.

## Preconditions

- no other Story is active (`active-story.yaml.active_story` is `null`, or the
  request names the already-active Story);
- the requested Story exists locally at the `story` registry path resolved from
  `artifact-paths.yaml`, or can be synced (see below);
- the Story's catalog `state` in `docs/catalog/stories.yaml` is `READY` or
  `BACKLOG` — not `IN_PROGRESS` for a different flow, not `COMPLETED`, not
  `ARCHIVED`;
- the current git branch and working tree are known.

If another Story is active: do not replace it. Require explicit human
resolution.

## Story source

If the Story exists only as a GitHub Issue and a GitHub source is configured,
delegate to `backlog-sync` (read-only) to create the local `story` artifact and
update `story_catalog`, preserving Issue identity. Do not alter requirements. Do
not activate an ambiguous or incomplete Story.

If no GitHub source is configured, the local `story` file is authoritative and
`active-story.yaml.source` fields stay `null`.

## Initialize state

Write `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
per `docs/workflow/state-schema.md`:

- `active-story.yaml`: `active_story`, resolved `story_path`, `source` (nulls if
  no GitHub), `status: IN_PROGRESS`, `activated_at` (runtime), `activated_by`.
- `workflow-state.yaml`: `story`, `workflow: story-delivery`,
  `current_stage: CLARIFICATION` — or `BACKLOG_SYNC` if a sync is required first
  — `previous_stage` / `last_completed_stage` accordingly, `status: IN_PROGRESS`,
  `attempt: 1`, every remaining field null or empty.

Set the catalog `state` for this Story to `IN_PROGRESS`, atomically, via
`backlog-sync` or directly.

Append one `history.jsonl` event: `from_stage: null`, `to_stage:` the initial
stage, `skill: null`, `verdict: "ACTIVATED"`.

Recommended initial stage: `CLARIFICATION`. Never initialize at
`IMPLEMENTATION`, and never at a `human_gate`.

## Pre-existing draft artifacts

This repository carries draft specifications and reviews for stories that were
never run through the pipeline (`US-4.1`..`US-4.3`), written against an older
codebase. A pre-existing artifact is **not** evidence a stage ran. Do not skip
`CLARIFICATION` because a spec file exists — note it as context and start fresh.

## Branch policy

Follow `AGENTS.md` §7.8 and the Git policy. If a Story branch is required but
missing, report it; do not create or switch branches unless the user explicitly
asks.

## Start Result

Return: activated Story; source (Issue if any); initial stage; branch; detected
blockers; and the recommended next command, `/so:next`.
