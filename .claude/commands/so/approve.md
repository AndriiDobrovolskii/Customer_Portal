---
description: Record human approval for the current workflow human gate.
argument-hint: "[optional comment]"
---

Invoke the story-orchestrator skill to record human approval of the current
human gate.

Optional approver comment:

$ARGUMENTS

Requirements:

- read docs/workflow/workflow-state.yaml; current_stage MUST be a stage whose
  type is `human_gate` in docs/workflow/stage-map.yaml (HUMAN_SPEC_APPROVAL,
  HUMAN_PLAN_APPROVAL, HUMAN_PR_APPROVAL, READY_FOR_PR, COMPLETED). If it is
  not, refuse and report the current stage;
- confirm every artifact in the gate's `required_artifacts` exists, is current
  (not SUPERSEDED or ARCHIVED), and that its recorded automated verdict is PASS
  with no blocking findings; if not, refuse and report what is missing;
- if current_stage is COMPLETED (stage-map.yaml `approval_precondition`): verify
  against the actual repository, not the approver's stated word, that the
  story's Pull Request is merged into the default branch - e.g. `git fetch`
  then `git merge-base --is-ancestor <tip-commit> origin/<default-branch>`, or
  `gh pr view --json state,mergedAt`. If the branch/PR cannot be found, the
  check fails, or it is inconclusive, refuse the approval and report exactly
  what was checked and what was found, per AGENTS.md section 10;
- set pending_human_gate.status = APPROVED, decided_at (runtime), decided_by;
  store the comment;
- append a docs/workflow/history.jsonl event with verdict "HUMAN_APPROVED";
- advance current_stage to the gate's `on_approve` target; clear
  pending_human_gate; set workflow status to IN_PROGRESS, or COMPLETED /
  ARCHIVED when entering those stages;
- do not invoke any stage skill;
- do not create, push, or merge a Pull Request (AGENTS.md section 1: propose,
  never execute unilaterally on shared state);
- finish with the Continue Result.
