# Artifact Front-Matter Schema

Authoritative schema for the YAML front matter of every **story-level Markdown
artifact** produced by a workflow skill. Skills MUST emit this block. Reviewers
MUST validate it.

## Required block

```yaml
---
artifact_type: <canonical-artifact-type>   # a key from docs/workflow/artifact-paths.yaml
story: US-3.3                               # epic-dotted canonical Story id
version: 1                                  # integer, starts at 1, +1 per revision
status: DRAFT                               # artifact lifecycle status (artifact-lifecycle.md §1)
created_at: <ISO-8601 timestamp, runtime>   # never hard-coded
updated_at: <ISO-8601 timestamp, runtime>
produced_by: <skill-name>                   # the owning skill from artifact-paths.yaml
inputs:                                     # every artifact this one consumed
  - path: <relative-path>
    version: <integer or null>
supersedes: null                            # or the relative path of the prior version
---
```

## Field rules

| Field | Rule |
|---|---|
| `artifact_type` | Must match a registry key in `artifact-paths.yaml`. |
| `story` | Canonical Story id in **epic-dotted form** (`US-3.3`, not `US-013`). Must equal `workflow-state.yaml.story`. |
| `version` | `1` on first creation. A re-run that changes content increments it. |
| `status` | One of `DRAFT, IN_REVIEW, APPROVED, SUPERSEDED, ARCHIVED`. New artifacts start `DRAFT`. A review stage may advance an input's `status` only through the orchestrator-recorded result; skills do not silently flip another artifact's status. |
| `created_at` / `updated_at` | Generated at runtime from the system clock. Example dates in skill docs are illustrative only and must be labelled as such. |
| `produced_by` | The skill named as `owner` of this `artifact_type` in `artifact-paths.yaml`. |
| `inputs[]` | One entry per consumed artifact, with the version that was read. Enables stale-input detection. |
| `supersedes` | `null` unless this revision replaces an earlier one; then the earlier file's path. The earlier file's `status` becomes `SUPERSEDED`. |

## Staleness contract

- A reviewer that consumes artifact X at `version: N` records
  `{path: X, version: N}` in its own `inputs`.
- If X is later revised to `version: N+1` (old becomes `SUPERSEDED`), any
  downstream artifact still recording `version: N` is **stale**.
- Stale review or evidence artifacts **block progression**
  (`verdict: BLOCKED`) until the dependent stage re-runs against the current
  version.

## OpenAPI YAML exception

`openapi` (`docs/designs/api/{story_id}-openapi.yaml`) is a YAML contract, not
Markdown. It carries traceability via top-level extension keys instead of a
front-matter block:

```yaml
info:
  version: "1"            # mirrors the paired api_design artifact version
x-story: US-3.3
x-source-specification: docs/specifications/US-3.3-spec.md
x-source-specification-version: 1
x-produced-by: openapi-designer
```

The paired `api_design` Markdown artifact carries the full front-matter block and
is the traceability anchor for the contract.

## Story artifact exception

The `story` artifact (`docs/stories/{story_id}-{slug}.md`) is authored by a human
or synced from a GitHub Issue by `backlog-sync` — it is an **input** to the
workflow, not a stage output. It does **not** carry the produced-artifact block
above (no `produced_by`, `inputs`, or `version` progression). Its front matter is:

```yaml
---
id: US-3.3
epic: EPIC-3
title: View Audit Information
slug: view-audit-information
priority: HIGH
source:
  type: github_issue | local_only
  repository: <owner/repo or null>
  issue_number: <int or null>
  issue_url: <string or null>
  last_synced_at: <ISO-8601 or null>
---
```

Story lifecycle status lives in `docs/catalog/stories.yaml`, never in this file.

## Non-Markdown / generated artifacts

`workflow_history` (JSONL), `story_catalog` (YAML), and generated runtime files
are governed by their own schemas (`state-schema.md`, and the catalog header) and
do not use this front matter.

## Historical artifacts

Artifacts produced before the harness migration do not carry this block. They are
read-only history: do not retrofit front matter onto them. Every artifact produced
from the migration forward MUST carry it, and a reviewer that finds a *new*
artifact without it returns `CHANGES_REQUIRED`.
