---
name: pr-creator
description: Pushes the story's current branch to origin and opens (or updates) the real GitHub Pull Request via the github MCP server, using pr-preparer's drafted title and body verbatim from docs/pr/{StoryId}-pr-summary.md. Use only when a human gives an explicit, separate instruction to create/open the PR for a story (e.g. "create the PR for US-x.y", "open the PR now") — never in response to a general "advance the story" or "run /so:next" request. This is the one skill in the workflow permitted to run `git push` and call `create_pull_request`/`update_pull_request`; it never runs on its own initiative (AGENTS.md §10), and story-orchestrator's continue mode treats reaching its stage (PR_CREATION) as a stop condition exactly like BACKLOG_SYNC. Does not draft PR content (pr-preparer's job), does not merge a PR, and never force-pushes.
---

# PR Creator

## Purpose

Perform the one real, externally-visible side effect in this delivery
workflow: push the story's branch to `origin` and open the actual GitHub Pull
Request, carrying over `pr-preparer`'s drafted title and body verbatim rather
than re-deriving them. Everything upstream of this skill only produces local
documents; this is where the story's work becomes visible outside the
repository.

Because of that, this skill runs **only on its own separate, explicit human
instruction** — never automatically, never as a side effect of approving
`HUMAN_PR_APPROVAL`, and never chained by `story-orchestrator`'s `/so:next`.
Running this skill does not itself carry approval for `READY_FOR_PR`; a human
still reviews the actual opened PR and decides.

## Operational Contract

```
Precondition: docs/pr/<StoryId>-pr-summary.md exists with verdict PASS recorded upstream (PR_PREPARATION), and a human has given this skill its own explicit instruction to run.
Input Artifacts: docs/stories/<StoryId>-<slug>.md (for source.repository when set); docs/pr/<StoryId>-pr-summary.md.
Output Artifacts: docs/pr/<StoryId>-pr-record.md; the real GitHub Pull Request (remote side effect).
```

## Required Context

Read, in order:

1. `docs/stories/<StoryId>-<slug>.md` front matter — `source.repository`
   (`"owner/repo"`) when `source.type: github_issue`. When absent or
   `local_only`, resolve `owner`/`repo` from `git remote get-url origin`
   instead (parse the `github.com[:/]<owner>/<repo>(.git)?` shape); never
   hard-code an owner or repo name.
2. `docs/pr/<StoryId>-pr-summary.md` — confirm `status` is not `SUPERSEDED`
   and read its `## Suggested PR Title` and full body content.
3. `docs/pr/<StoryId>-pr-record.md`, if it already exists from a prior run —
   determines create vs. update (see Workflow step 6).

## Preconditions

- `docs/pr/<StoryId>-pr-summary.md` exists, is current (not `SUPERSEDED`), and
  its owning stage (`PR_PREPARATION`) recorded `PASS`. If missing or not
  `PASS`, stop `BLOCKED` — name `PR_PREPARATION` as the blocker; never invent
  PR content here.
- The current git branch is **not** the repository's default branch. Opening
  a PR from the default branch onto itself is never correct — stop `BLOCKED`
  if so.
- The working tree has no uncommitted changes relevant to the story (`git
  status --porcelain`). Pushing a PR while local edits sit uncommitted would
  misrepresent what the PR actually contains — stop `BLOCKED` and name the
  files, rather than silently pushing a partial state.

## Workflow

1. Resolve `owner`/`repo` per Required Context step 1.
2. Resolve the head branch: `git rev-parse --abbrev-ref HEAD`.
3. Resolve the base branch: the repository's actual default branch (e.g. via
   `git remote show origin` or equivalent) — never hard-code `main` when the
   repository's default differs. Confirm head ≠ base.
4. **Staleness check.** Compare the story's latest commit timestamp (`git log
   -1 --format=%cI HEAD`) against `docs/pr/<StoryId>-pr-summary.md`'s
   `updated_at`. If a commit lands *after* that timestamp, the summary was
   drafted against an older tree — emit `CHANGES_REQUIRED`,
   `loop_back_stage: PR_PREPARATION` (key `stale_pr_summary`), and stop before
   pushing or touching the remote.
5. **State the plan** before acting: head branch, resolved owner/repo, base
   branch, and the PR title from `## Suggested PR Title`. This is the
   record of what is about to become externally visible — surface it plainly
   rather than pushing silently.
6. Push: `git push -u origin HEAD` (idempotent whether or not upstream
   tracking already exists). **Never `--force` or `--force-with-lease`** — a
   rejected (non-fast-forward) push means the remote branch diverged; stop
   `BLOCKED` with the exact git error and let a human resolve it (rebase/merge
   is their call, not this skill's).
7. Verify the push actually landed: `git fetch origin <head-branch>` then
   compare `git rev-parse HEAD` to `git rev-parse origin/<head-branch>` — they
   must match. Do not trust a zero exit code alone.
8. Determine create vs. update:
   - If `docs/pr/<StoryId>-pr-record.md` already exists and its recorded PR is
     still open (`mcp__github__pull_request_read`, method `get`), call
     `mcp__github__update_pull_request` with the current title/body from
     `pr_summary` and bump the `pull_request` artifact's `version`.
   - Otherwise, check for a stray untracked existing PR first
     (`mcp__github__list_pull_requests`, `head: "<owner>:<head-branch>"`,
     `state: "open"`) — if one exists, adopt it (record it, do not open a
     duplicate) and still align its title/body via `update_pull_request`.
   - Otherwise, call `mcp__github__create_pull_request` with `owner`, `repo`,
     `title` (the `## Suggested PR Title` content), `head`, `base`, and `body`
     (the full `pr_summary` content following the front matter, verbatim).
9. Write `docs/pr/<StoryId>-pr-record.md`: PR `html_url`, `number`, `head`,
   `base`, the verified pushed commit SHA, `created_at`/`updated_at`.
10. Report the PR URL back plainly as the final, user-visible result of this
    stage.

## Constraints

- Never run without this skill having been given its own explicit,
  separate human instruction — "the story reached PR_CREATION" is not that
  instruction.
- Never `--force`/`--force-with-lease` push. A rejected push is `BLOCKED`,
  not a reason to overwrite the remote.
- Never merge a Pull Request, and never change its base to a non-default
  branch without the human explicitly asking for that.
- Never draft or rewrite PR title/body content — carry `pr_summary` over
  verbatim; drafting is `pr-preparer`'s job.
- Never open a second PR for the same head branch when one already exists —
  update it instead.
- Never push while the working tree has uncommitted changes relevant to the
  story.

## Verification Checklist

- [ ] `pr_summary` confirmed current and `PASS` before anything else ran.
- [ ] Head branch confirmed different from the resolved default branch.
- [ ] Staleness check performed (commit timestamp vs. `pr_summary.updated_at`)
      before pushing.
- [ ] The plan (head, owner/repo, base, title) was stated before the push.
- [ ] Push verified by comparing local `HEAD` to `origin/<branch>` after
      fetch — not inferred from exit code alone.
- [ ] Existing-PR check performed before calling `create_pull_request`, so no
      duplicate PR was opened.
- [ ] `docs/pr/<StoryId>-pr-record.md` written with the real URL/number/SHA.
- [ ] The PR URL was reported back in plain text.

## Outputs

- `docs/pr/<StoryId>-pr-record.md`.
- The real, opened (or updated) GitHub Pull Request — reported by URL.

## Completion Criteria

Complete only when the branch is verifiably pushed, the Pull Request exists
(or was correctly updated, not duplicated) on the remote, `pr-record.md` is
written with real (not assumed) URL/number/SHA, and the URL has been reported
to the human.

---

# Harness Contract

This skill owns the `PR_CREATION` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml`
  (`PR_CREATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` — **authoritative**.
  Resolve `story` and `pr_summary` as inputs, `pull_request` as the owned
  output. Any path shown elsewhere in this skill is illustrative; the
  registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.
- The explicit-trigger requirement and its rationale: `AGENTS.md` §10.

## Inputs (registry keys)

- `story`
- `pr_summary`

## Preconditions (harness)

- `pr_summary` is current: `status` is not `SUPERSEDED` or `ARCHIVED`, and its
  owning stage (`PR_PREPARATION`) recorded `PASS`.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active, and `current_stage` is `PR_CREATION`.
- This dispatch was triggered by the human's own separate, explicit
  instruction to create/open the PR — not inferred from any prior approval or
  from a general "advance the story" request.

## Result Envelope

Return exactly this. `story-orchestrator` records the transition; this skill
never writes `docs/workflow/workflow-state.yaml`.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: PR_CREATION
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/pr/<StoryId>-pr-record.md
  pull_request_url: <html_url or null>
  next_stage: READY_FOR_PR
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other
key is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `stale_pr_summary` | `PR_PREPARATION` |

- `PASS` — the branch is verifiably pushed and the PR is open (created or
  correctly updated, never duplicated) at the reported URL.
- `CHANGES_REQUIRED` — `stale_pr_summary`: a commit landed after
  `pr_summary.updated_at`; its content no longer describes the tree about to
  be pushed.
- `BLOCKED` — `pr_summary` missing/stale/not `PASS`; head branch equals the
  default branch; uncommitted changes present; the push was rejected
  (diverged remote); or push verification failed (local `HEAD` does not match
  `origin/<branch>` after the push).

## Prohibited (harness)

- Do not update workflow state (`workflow-state.yaml`, `active-story.yaml`,
  `history.jsonl`) — `story-orchestrator` owns those.
- Do not produce an artifact this skill does not own in
  `docs/workflow/artifact-paths.yaml`.
- Do not resolve Open Decisions.
- Do not emit a retired verdict (`Pass`, `Fail`, `Pass with Issues`,
  `APPROVED`, …) — see `artifact-lifecycle.md` §2.
- Do not use the retired sequential story ids (`US-0NN`) or retired stage
  identifiers.
- Do not merge a Pull Request.
- Do not force-push under any circumstance.
- Do not run without an explicit, separate human instruction to do so.
