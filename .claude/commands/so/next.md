---
description: Advance the active User Story automatically through consecutive workflow stages until a human gate or blocked state.
argument-hint: ""
---

Invoke the story-orchestrator skill in continue mode
(`.claude/skills/story-orchestrator/references/continue-flow.md`).

Requirements:

- process only the active User Story;
- advance automatically through as many consecutive automated stages as
  possible in this one invocation — after each `PASS` / `NOT_APPLICABLE` or
  an under-cap `CHANGES_REQUIRED` loop-back, continue immediately to the next
  stage rather than stopping just because a transition was recorded;
- invoke exactly one stage skill per stage transition — except
  `IMPLEMENTATION`, which is a composite_skill whose four builder sub-steps
  run in the order fixed by AGENTS.md section 3 and refined by the story's
  task_breakdown, tracked in docs/catalog/<StoryId>-pipeline-status.md, each
  sub-step its own dispatch;
- resolve stage routing from docs/workflow/stage-map.yaml and artifact paths
  from docs/workflow/artifact-paths.yaml — never hard-code either;
- read the stage skill's actual Result Envelope and inspect the artifacts it
  produced; never infer success from the skill running without error;
- stop the run — end the invocation without processing another stage — the
  moment any of these is hit:
  - a human gate (HUMAN_SPEC_APPROVAL, HUMAN_PLAN_APPROVAL, HUMAN_PR_APPROVAL,
    READY_FOR_PR, COMPLETED): invoke no skill, set WAITING_FOR_HUMAN, list the
    artifacts to review with versions and the automated verdict, and report
    that /so:approve or /so:reject records the decision. A review skill
    returning PASS is not human approval;
  - a `BLOCKED` verdict from a stage skill;
  - a `CHANGES_REQUIRED` loop-back whose target has already been attempted 3
    times without reaching PASS (report the repeated finding, hold BLOCKED
    for a human decision rather than re-attempting again);
  - an unknown `loop_back` key, a retired stage identifier, or any workflow
    invariant failure — hold, report, name the earliest responsible stage,
    never route around it;
  - `BACKLOG_SYNC` is reached (its run_policy still applies — never auto-run
    it on a continue);
  - 25 transitions have been recorded in this single invocation (safety fuse
    against a runaway loop — report it and that /so:next should be invoked
    again after investigating);
- respect all human gates and configured hooks;
- record each transition in docs/workflow/workflow-state.yaml and append one
  event to docs/workflow/history.jsonl per transition — never batch several
  stages into one event;
- finish with the Continue Result, covering every stage processed this run,
  not just the last one.
