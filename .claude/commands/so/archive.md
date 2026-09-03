---
description: Archive the completed active User Story after required human gates.
argument-hint: ""
---

Invoke the story-orchestrator skill in archive mode
(`.claude/skills/story-orchestrator/references/archive-flow.md`).

Requirements:

- require workflow-state.yaml current_stage == COMPLETED and explicit human
  invocation of this command; never infer archiving from a merged PR;
- create the delivery summary at the `delivery_summary` path resolved from
  docs/workflow/artifact-paths.yaml;
- set the Story's catalog state to ARCHIVED in docs/catalog/stories.yaml;
- update docs/knowledge/project-state.md; propose — do not auto-apply —
  business-rules and docs/ARCHITECTURE.md updates for human approval. Never
  edit AGENTS.md (AGENTS.md section 7.8);
- preserve all historical artifacts in place — do not move or delete them;
- do not merge a Pull Request;
- request human approval before any remote GitHub write;
- clear active-story.yaml and set current_stage ARCHIVED only after the
  delivery summary is written; append one history.jsonl event.
