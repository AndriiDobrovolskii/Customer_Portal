---
description: Record human rejection of the current workflow human gate.
argument-hint: "<reason>"
---

Invoke the story-orchestrator skill to record human rejection of the current
human gate.

Rejection reason (required):

$ARGUMENTS

Requirements:

- read docs/workflow/workflow-state.yaml; current_stage MUST be a stage whose
  type is `human_gate` in docs/workflow/stage-map.yaml. If it is not, refuse and
  report the current stage;
- require a non-empty reason; store it as pending_human_gate.comment;
- set pending_human_gate.status = REJECTED, decided_at (runtime), decided_by;
- append a docs/workflow/history.jsonl event with verdict "HUMAN_REJECTED";
- route current_stage to the gate's `on_reject` target; clear
  pending_human_gate; set workflow status to IN_PROGRESS;
- do not invoke any stage skill;
- finish with the Continue Result, including the loop-back target and the
  recommended next command.
