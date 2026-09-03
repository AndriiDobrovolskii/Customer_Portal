---
description: Activate a User Story and initialize its workflow.
argument-hint: <StoryId>
---

Invoke the story-orchestrator skill in start mode
(`.claude/skills/story-orchestrator/references/start-flow.md`).

Requested Story:

$ARGUMENTS

Requirements:

- activate only the explicitly requested Story, named in epic-dotted form
  (`US-4.1`); reject a retired sequential id (`US-014`) and report the
  canonical replacement from docs/workflow/artifact-paths.yaml
  `retired_id_scheme`;
- do not replace another active Story;
- initialize docs/workflow/active-story.yaml and docs/workflow/workflow-state.yaml
  per docs/workflow/state-schema.md;
- set the Story's catalog state to IN_PROGRESS in docs/catalog/stories.yaml;
- append an activation event to docs/workflow/history.jsonl;
- treat any pre-existing draft specification or review for this Story as
  context only, never as evidence a stage already ran;
- do not start stage execution automatically;
- finish with the Start Result and recommend /so:next.
