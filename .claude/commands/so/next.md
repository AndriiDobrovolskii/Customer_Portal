---
description: Advance the active User Story by one workflow stage.
argument-hint: ""
---

Invoke the story-orchestrator skill in continue mode
(`.claude/skills/story-orchestrator/references/continue-flow.md`).

Requirements:

- process only the active User Story;
- perform at most one workflow transition;
- invoke at most one stage skill — except IMPLEMENTATION, which is a
  composite_skill whose four builder sub-steps run in the order fixed by
  AGENTS.md section 3 and refined by the story's task_breakdown, tracked in
  docs/catalog/<StoryId>-pipeline-status.md;
- resolve stage routing from docs/workflow/stage-map.yaml and artifact paths
  from docs/workflow/artifact-paths.yaml — never hard-code either;
- read the stage skill's actual Result Envelope and inspect the artifacts it
  produced; never infer success from the skill running without error;
- at a human gate (HUMAN_SPEC_APPROVAL, HUMAN_PLAN_APPROVAL, HUMAN_PR_APPROVAL,
  READY_FOR_PR, COMPLETED): invoke no skill, set WAITING_FOR_HUMAN, list the
  artifacts to review with versions and the automated verdict, and report that
  /so:approve or /so:reject records the decision. A review skill returning PASS
  is not human approval;
- respect all human gates and configured hooks;
- record the transition in docs/workflow/workflow-state.yaml and append one
  event to docs/workflow/history.jsonl;
- finish with the Continue Result;
- do not recursively continue to another stage.
