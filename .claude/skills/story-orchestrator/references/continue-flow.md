# Continue Flow

Advance the active Story automatically through consecutive workflow stages —
one skill dispatch per stage, one `history.jsonl` event per transition —
without waiting for a separate invocation between them. Primary mode, also
invoked as `/so:next`.

## Inputs

- `docs/workflow/active-story.yaml`
- `docs/workflow/workflow-state.yaml`
- `docs/workflow/stage-map.yaml` (workflow + routing authority)
- `docs/workflow/artifact-paths.yaml` (path authority)
- `docs/workflow/artifact-lifecycle.md`, `docs/workflow/state-schema.md`
- `AGENTS.md`

## Outer loop

Run the **Per-stage algorithm** below once per stage, stage after stage, in
the same invocation — do not wait for the user to call `/so:next` again just
to move from one automated `PASS` to the next. Stop the loop, ending the run,
the moment any of these **stop conditions** is hit:

- **Human gate reached.** The (possibly just-advanced) `current_stage` is
  `type: human_gate`. Invoke no skill for it. Report the gate per step 3 and
  end the run — never infer approval, never invoke a gate's skill (it has
  none), never treat this as an error.
- **`BLOCKED`.** A stage skill returns `BLOCKED`. Hold that stage,
  `status: BLOCKED`, surface `blocking_issues`, end the run.
- **`CHANGES_REQUIRED` attempt cap exhausted.** A stage skill returns
  `CHANGES_REQUIRED` and the `loop_back` target has already been attempted
  `MAX_STAGE_ATTEMPTS` (3) times this delivery without reaching `PASS`. Do not
  re-attempt a fourth time — hold `status: BLOCKED` at the looped-back stage,
  report the repeated finding across attempts, and end the run for a human
  decision. (Under the cap: apply the loop-back per step 7 and continue the
  outer loop as normal — this is not a stop condition by itself.)
- **Inconsistent / invariant failure.** Steps 1, 2, or 4 fail (story mismatch,
  retired stage identifier, stale/SUPERSEDED input, unresolved blocking Open
  Decision, etc.). Hold, report, name the earliest responsible stage, end the
  run. Never route around this.
- **`BACKLOG_SYNC` reached.** Its `run_policy` still applies — never auto-run
  it on a `continue`. End the run and report that an explicit backlog sync (or
  Story activation) is needed.
- **Safety fuse.** `MAX_TRANSITIONS_PER_RUN` (25) transitions have been
  recorded in this single invocation. End the run and report that `/so:next`
  should be invoked again to keep going. `stage_order` has ~24 entries end to
  end, so hitting this is a sign something is looping wrong, not an expected
  outcome — investigate before re-invoking.

Every iteration performs exactly one workflow transition (or ends the run
without one, at a stop condition) and appends exactly one `history.jsonl`
event per transition actually made — never batch multiple stages into one
event, and never skip recording a transition that happened.

## Per-stage algorithm

### 1. Resolve the active Story

Read `active-story.yaml`. Confirm exactly one `active_story` and that
`workflow-state.yaml.story` matches. If none: stop with
`BLOCKED — run /so:start <StoryId>`. If they disagree: stop `INCONSISTENT`. Do
not guess which file is authoritative. (Re-check this on every iteration — a
run that processes several stages must not silently keep going against a
Story mismatch that appears mid-run.)

### 2. Resolve the current stage

Read `current_stage`, `status`, `attempt`, `pending_human_gate`. `current_stage`
must be a member of `stage-map.yaml` `stage_order`. If it is a
`retired_identifiers` key instead, report the canonical replacement and stop
`INCONSISTENT` — do not silently translate it.

### 3. If the current stage is a human gate (`type: human_gate`)

Invoke no skill. This is an outer-loop stop condition: report the gate and end
the run here regardless of how many stages were already processed this
invocation. Depending on `pending_human_gate.status`:

- `PENDING` → re-report the gate (required artifacts with versions, the
  automated verdict, blocking findings, and the exact `/so:approve` |
  `/so:reject` command) and stop.
- `APPROVED` → bump `status: APPROVED` in the front matter of every artifact in
  `pending_human_gate.required_artifacts` (`artifact-lifecycle.md`'s `DRAFT` →
  `APPROVED` rule — a front-matter field update, not content editing); advance
  `current_stage` to the gate's `on_approve`, clear `pending_human_gate`, set
  `status`, append history, stop.
- `REJECTED` → route to the gate's `on_reject`, clear `pending_human_gate`,
  append history, stop.

If `pending_human_gate` is `null`, build it per `state-schema.md` and stop
`WAITING_FOR_HUMAN`.

**A review skill's `PASS` is never human approval.** Never infer one from the
other, and never let a run of consecutive automated `PASS`es carry the
workflow past a gate — a gate always ends the run.

### 4. Validate workflow invariants

State files agree; no artifact for this story is `SUPERSEDED` while a downstream
artifact still records its old version; no blocking Open Decision affects the
stage about to run; no `TODO` / `TBD` / `FIXME` in an `APPROVED` artifact the
stage depends on. On failure: hold, report, and recommend the earliest
responsible stage. Do not route. (An outer-loop stop condition.)

### 5. Check for existing stage output

Resolve `stages.<current>.outputs` through `artifact-paths.yaml`. If a current,
valid output already exists — right `story`, `status` not `SUPERSEDED` or
`ARCHIVED`, inputs not stale, no open `CHANGES_REQUIRED` / `BLOCKED` record —
do not regenerate. Validate it and go to step 7 using its recorded verdict.
Otherwise continue.

### 6. Invoke the one responsible skill — via an isolated sub-agent dispatch

`skill := stages.<current>.skill`. Confirm it exists under `.claude/skills/`.
Resolve the Story id and every input path this stage needs, per `stage-map.yaml`
`inputs` and `artifact-paths.yaml`.

Dispatch the skill's actual work to a fresh, isolated sub-agent (the `Agent`
tool, `subagent_type: general-purpose`) rather than invoking it inline via the
`Skill` tool. Every stage skill in `stage-map.yaml` already reads its inputs
from files, never from conversation history, so it is self-contained by
construction — safe to run with none of the orchestrator's own context.
Dispatching this way keeps the orchestrator session growing only by one short
Result Envelope per stage, instead of by each stage's full working transcript
(confirmed on a manual `CLARIFICATION` dispatch for `US-5.1`, 2026-09-07: the
sub-agent used ~105K tokens and 26 tool calls of its own; the orchestrator
absorbed none of it). This is what makes running several stages in one
invocation affordable — the outer loop's own context grows by one Result
Envelope per stage, not by each stage's transcript.

The dispatch prompt MUST:
- name the exact skill file to follow (`.claude/skills/<skill>/SKILL.md`) and
  instruct the sub-agent to follow it exactly, including its own required
  reading order;
- name the Story id and every resolved input path explicitly — never let the
  sub-agent guess or re-derive them;
- state which artifacts it does NOT own and must not write
  (`docs/workflow/workflow-state.yaml`, `docs/workflow/active-story.yaml`,
  `docs/workflow/history.jsonl` — `story-orchestrator` only), and that it must
  never create commits, branches, or Pull Requests;
- require the response to be ONLY the exact Result Envelope block plus a short
  (~1 paragraph) summary — explicitly forbid pasting full artifact contents or
  its own working transcript back to the orchestrator.

Wait for the sub-agent to finish. Read the Result Envelope it returns, then
independently inspect the artifacts it claims to have produced at their
registry paths — never assume success from the sub-agent's own narration, and
never accept a report that omits the Result Envelope block; re-dispatch or
hold `BLOCKED` if it does.

Two stages are special:

- **`BACKLOG_SYNC`** — an outer-loop stop condition (see above). Never
  auto-dispatch it on a `continue`.
- **`IMPLEMENTATION`** — `type: composite_skill`. Resolve the Story's `track`
  (`docs/stories/<StoryId>.md` front matter; absent means `backend`) and
  dispatch each skill in `stages.IMPLEMENTATION.skills_by_track[track]` as its
  OWN separate sub-agent dispatch, one after another within this same stage —
  for `backend`, that's `schema-builder`, `data-layer-builder`,
  `migration-manager`, `service-and-router-builder` in the order fixed by
  `AGENTS.md` §3 layering and refined by `task_breakdown`; for `frontend`,
  that's `frontend-builder`. Never one dispatch for the whole composite stage;
  that would reintroduce the same context growth this change exists to avoid.
  Record each sub-step in `pipeline_status`
  (`docs/catalog/{story_id}-pipeline-status.md`) and set
  `implementation_substep` in `workflow-state.yaml`. The stage completes only
  when every sub-step is done — only then does step 7 apply and the outer loop
  advance past `IMPLEMENTATION`; a sub-step failure routes via the stage's
  `loop_back` (an outer-loop stop condition once the attempt cap applies). Do
  not add fields to `workflow-state.yaml` to track this.

### 7. Apply the result

- `PASS` / `NOT_APPLICABLE` → `current_stage := stages.<current>.next`,
  `attempt := 1`, record the transition (step 8), then continue the outer loop
  at the new `current_stage` — do not stop merely because a transition was
  recorded.
- `CHANGES_REQUIRED` → verify the named key exists in
  `stages.<current>.loop_back`; an unknown key is an outer-loop stop condition
  (hold `BLOCKED`, human decision). Otherwise check the attempt cap (outer
  loop, above): under the cap, route to the loop-back target, `attempt += 1`,
  record the transition, and continue the outer loop there; at the cap, stop.
- `BLOCKED` → keep the stage; `status: BLOCKED`; surface `blocking_issues`; an
  outer-loop stop condition.

Never advance past a stage whose skill reported anything other than `PASS` or
`NOT_APPLICABLE`. Never skip a stage because the change "looks obviously fine".

### 8. Record the transition

Update `workflow-state.yaml` per `state-schema.md`. Append exactly one
`history.jsonl` event for this transition. Then return to the outer loop:
either process the next stage (step 1 of the next iteration) or, if a stop
condition applies, end the run.

## Continue Result

Return, for the whole run: the active Story; the ordered list of stages
processed this invocation, each with the skill routed to, its verdict, and the
artifacts it produced with versions; the final transition; the ending stage;
workflow status; the human gate the run stopped at, if any, with its exact
approval command; blocking issues if the run ended `BLOCKED`; and the
recommended next command — normally `/so:approve` at a gate, or `/so:next`
only if the run ended on the safety fuse or an `INCONSISTENT` state that needs
a retry after a fix.
