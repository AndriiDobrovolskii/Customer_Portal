---
description: Show the current User Story workflow status.
argument-hint: ""
---

Invoke the story-orchestrator skill in status mode
(`.claude/skills/story-orchestrator/references/status-flow.md`).

Requirements:

- use read-only operations;
- do not invoke a stage skill;
- do not modify workflow state or any artifact;
- resolve the stage from docs/workflow/stage-map.yaml and every path from
  docs/workflow/artifact-paths.yaml;
- report workflow health, the current stage's inputs and outputs with their
  status, stale inputs, blockers, the pending human gate with its exact
  approval command, and the recommended next command;
- report INCONSISTENT if current_stage is a retired identifier
  (DESIGN, PLANNING, TESTS, VERIFICATION, PR, ...) rather than silently
  translating it to its canonical replacement.
