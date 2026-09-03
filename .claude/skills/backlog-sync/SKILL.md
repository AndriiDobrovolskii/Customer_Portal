---
name: backlog-sync
description: >
  Synchronizes User Stories from the configured GitHub source into local
  repository artifacts. Creates or updates docs/stories/ files and
  docs/catalog/stories.yaml, preserves GitHub Issue identity, and detects
  local/remote conflicts without silently overwriting locally modified
  requirements. Owns the BACKLOG_SYNC stage and the story catalog. Use when
  the user asks to "sync the backlog", "pull US-x.y from GitHub", or when a
  Story is being activated via /so:start and needs a local story file. Does not
  write specifications, designs, or workflow state, and never edits a GitHub
  Issue without explicit per-operation human approval.
---

# Backlog Sync

## Purpose

Own the **BACKLOG_SYNC** stage. Bring the active User Story (and, on demand, the
wider backlog) from the configured GitHub source into local artifacts so the rest
of the workflow has an authoritative local Story.

This skill also **owns `docs/catalog/stories.yaml`** (registry key
`story_catalog`) and may update `docs/workflow/active-story.yaml` when activating
a Story on the orchestrator's behalf.

## Canonical sources

- Workflow / stage: `docs/workflow/stage-map.yaml` (`BACKLOG_SYNC`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` — resolve `story`,
  `story_catalog`. Do not hard-code paths; examples below are illustrative.
- State schema: `docs/workflow/state-schema.md`.
- Result vocabulary: `docs/workflow/artifact-lifecycle.md`.
- Front matter: `docs/workflow/artifact-schema.md` ("Story artifact exception").

## Operational Contract

```
Precondition: A GitHub repository is configured (.mcp.json defines the github server, and docs/catalog/stories.yaml carries source_default.repository), or the sync is explicitly local-only.
Input Artifacts: GitHub MCP issues (read mode); docs/stories/*.md; docs/catalog/stories.yaml; docs/workflow/active-story.yaml.
Output Artifacts: docs/stories/<StoryId>-<slug>.md; docs/catalog/stories.yaml; docs/workflow/active-story.yaml (activation only).
```

## Run policy

Per `stage-map.yaml`, this skill does **not** run on every `/so:next`. Run only:

- on an explicit backlog-sync request;
- during Story activation (`/so:start`);
- on a `RECONCILIATION` `story_source_conflict` loop-back.

## Inputs (registry keys)

- `story`, `story_catalog`
- `docs/workflow/active-story.yaml`
- GitHub MCP (read mode) — issues in the configured repository
- `AGENTS.md`

If no GitHub repository is configured (no `repository` in
`active-story.yaml.source`, none in `stories.yaml` `source_default`, and none
derivable from `.mcp.json`):

- treat local `docs/stories/*.md` as authoritative;
- keep `source.type` / `repository` / `issue_number` / `issue_url` as recorded,
  or `null`;
- return `PASS` with a `non_blocking_findings` note that no remote source is
  configured.

Never fabricate a repository name or issue number.

## Preconditions

- Every consumed artifact is current (`status` not `SUPERSEDED` / `ARCHIVED`).
- `docs/catalog/stories.yaml` parses and every `path` in it resolves.
- If `active-story.yaml` and `workflow-state.yaml` disagree on which Story is
  active → `BLOCKED`. Do not guess which is authoritative.

## Responsibilities

1. Identify GitHub Issues that represent User Stories (by label / project /
   naming convention configured for the repository).
2. For the target Story (active Story, or each backlog Story on a full sync):
   - resolve its canonical **epic-dotted** id (`US-3.3`) and `slug`;
   - create or update the local `story` artifact at the registry path;
   - preserve GitHub Issue identity: number, URL, and last-synced marker;
   - keep the Story body faithful to the Issue — do not reinterpret or add
     requirements.
3. Maintain `docs/catalog/stories.yaml`:
   - one entry per Story with `id`, `slug`, `path`, `epic`, `title`, `state`,
     and a `source` block;
   - `state` ∈ `BACKLOG | READY | IN_PROGRESS | COMPLETED | ARCHIVED`;
   - update `state` only for legitimate transitions. A human or the orchestrator
     drives `IN_PROGRESS` / `COMPLETED` / `ARCHIVED`; this skill may set
     `BACKLOG` → `READY` when an Issue becomes ready.
   - never remove or rewrite a `retired_id` — it is what keeps
     `docs/workflow/history.jsonl` and pre-migration artifacts traceable.
4. On activation delegation from the orchestrator: also write
   `docs/workflow/active-story.yaml` per `state-schema.md`.

## Source-of-truth policy

- **Before a Story is `IN_PROGRESS`**: the GitHub Issue is authoritative for the
  Story title, description, and Acceptance Criteria. Overwrite the local Story to
  match, preserving local formatting only.
- **After a Story is `IN_PROGRESS`**: the local approved Specification and
  downstream artifacts are authoritative for delivery detail. A change to the
  Issue's requirements requires **explicit resynchronization** and invalidates
  dependent artifacts (Specification onward) — report it, do not auto-apply.
- Local edits to an `IN_PROGRESS` Story that diverge from the Issue are a
  **conflict**.

## Conflict handling

When the local Story and the GitHub Issue materially disagree and the Story is
`IN_PROGRESS` (or no source-of-truth rule resolves it):

1. Do not overwrite either side.
2. Record the differing fields (title / intent / business value / each
   Acceptance Criterion / Definition of Done / labels).
3. Classify each difference: `formatting_only`, `approved_clarification`,
   `unapproved_requirement_change`, `missing_sync`, `remote_drift`.
4. Return `verdict: BLOCKED` with `blocking_issues` naming the conflicting
   fields; recommend human resolution.

## Output

- `story` artifact(s) under `docs/stories/` with the **story front matter**
  defined in `docs/workflow/artifact-schema.md`: `id`, `epic`, `title`, `slug`,
  `priority`, and a `source` block:

  ```yaml
  source:
    type: github_issue | local_only
    repository: <owner/repo or null>
    issue_number: <int or null>
    issue_url: <string or null>
    last_synced_at: <ISO-8601 or null>
  ```

  The Story is a workflow **input**, not a produced artifact — it does NOT carry
  `produced_by` / `inputs` / `version`, and it keeps no mutable lifecycle
  `status` field. That lives in the catalog.
- Updated `docs/catalog/stories.yaml`.
- Optionally updated `docs/workflow/active-story.yaml` (activation only).

## Result Envelope

Return exactly this; `story-orchestrator` records the transition — this skill
does not update `workflow-state.yaml`:

```yaml
result:
  verdict: PASS | BLOCKED
  stage: BACKLOG_SYNC
  story: <StoryId>
  artifact_status: DRAFT | APPROVED
  artifacts:
    - docs/stories/<StoryId>-<slug>.md
    - docs/catalog/stories.yaml
  next_stage: CLARIFICATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

- `PASS` — Story synced (or local source confirmed); catalog updated.
- `BLOCKED` — unresolved source-of-truth conflict, or state files disagree.
  `BACKLOG_SYNC` has no `loop_back` map: conflicts are always `BLOCKED`, never
  `CHANGES_REQUIRED`.

## Prohibited

- Do not modify requirements or Acceptance Criteria beyond faithful copying.
- Do not resolve Open Decisions.
- Do not write `docs/workflow/workflow-state.yaml` (orchestrator only).
- Do not create branches, commits, or Pull Requests.
- Do not perform write operations on GitHub Issues unless a human explicitly
  approves that specific operation (`AGENTS.md` §1: propose, never execute
  unilaterally on shared state).
- Do not use the retired sequential ids (`US-0NN`) for anything new.

## Verification Checklist

- [ ] The resolved Story id is epic-dotted and matches its filename.
- [ ] Every catalog entry's `path` resolves to a file that exists.
- [ ] Issue identity (number, URL, `last_synced_at`) is recorded, or all `null`
      with `type: local_only` — never a fabricated value.
- [ ] No Acceptance Criterion was reworded, merged, or added.
- [ ] `retired_id` values are preserved unchanged.

## Completion Criteria

Complete when the target Story exists locally at its registry path with faithful
content and correct source identity, the catalog reflects it, and either no
conflict exists or every conflicting field is named in `blocking_issues`.
