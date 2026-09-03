---
name: pr-preparer
description: Prepares the final pull request content for a story once gate-enforcer, implementation-verifier, reconciliation-reviewer, and security-reviewer have all reported Pass — verifying all four passed, drafting the PR title and description (summary, linked story/spec, test-plan checklist), confirming .env.example was updated if settings changed, and confirming commit hygiene (no unrelated files, no drive-by refactors per AGENTS.md §7.8). Use when the user asks to "prepare the PR for US-xxx" or "get this ready to submit." Does NOT push, open, or merge the PR itself, and does NOT run git/gh commands unprompted — consistent with this project's "propose, never execute unilaterally" stance (AGENTS.md §1) on shared-state actions. It hands the drafted title/description/checklist to the user (or to an explicitly user-invoked git/gh command) rather than acting on the remote itself.
---

# PR Preparer

## Purpose

Draft the PR a human will actually submit — title, description, and test-plan checklist — only once every upstream gate has actually passed. This skill never touches the remote; it hands off content, the same way `story-spec-reviewer` hands off findings without editing the spec itself.

## Operational Contract

```
Precondition: gate-enforcer, implementation-verifier, reconciliation-reviewer, and security-reviewer all report Pass for the story.
Input Artifacts: docs/verification/<StoryId>-implementation-verification.md; docs/reviews/reconciliation/<StoryId>-reconciliation.md; docs/reviews/security/<StoryId>-security-review.md; gate-enforcer's reported result (chat report — gate-enforcer writes no docs/ file).
Output Artifacts: docs/pr/<StoryId>-pr-summary.md, echoed in chat.
```

## Required Context

Read, in order:

1. `docs/verification/<StoryId>-implementation-verification.md` — confirm `implementation-verifier`'s verdict is Pass.
2. `docs/reviews/reconciliation/<StoryId>-reconciliation.md` — confirm `reconciliation-reviewer`'s verdict is Pass.
3. `docs/reviews/security/<StoryId>-security-review.md` — confirm `security-reviewer`'s verdict is Pass.
4. `gate-enforcer`'s most recent report for this story (chat transcript or wherever the user has it) — confirm its verdict.
5. `docs/specifications/<StoryId>-spec.md` and `docs/plans/<StoryId>-implementation-plan.md` — for the summary and linked-story content.
6. `.env.example` and the story's changed settings (if any) — confirm alignment.

## Preconditions

All four gates — `gate-enforcer`, `implementation-verifier`, `reconciliation-reviewer`, `security-reviewer` — report Pass. If any is missing or not Pass, stop and name exactly which one is blocking; never draft a PR around a failing or unrun gate.

## Workflow

1. Confirm all four gate results directly from their reports — don't take a user's verbal "it's all good" as a substitute for reading the actual verdicts.
2. Draft the PR title — short, specific, under ~70 characters, matching this repo's commit-message style (feature/fix/refactor prefix as appropriate).
3. Draft the summary: what changed and why, linking the story and spec paths.
4. Build the test-plan checklist from the traceability matrix and the gate/verification reports — what was tested, unit vs. integration, and the coverage result.
5. Note any risk/rollback considerations `planner`'s Risks section flagged.
6. Confirm `.env.example` reflects any new settings the story introduced (per `AGENTS.md` §4's "Config & secrets" rule) — flag a mismatch rather than silently including or omitting it.
7. Confirm commit hygiene: no unrelated files in scope, no drive-by refactor beyond the story (`AGENTS.md` §7.8) — flag anything that looks out of scope rather than silently drafting around it.
8. Write `docs/pr/<StoryId>-pr-summary.md` and echo the same content in chat.
9. State explicitly at the end: this is drafted content only — pushing the branch or opening the PR requires an explicit user instruction to run `git push`/`gh pr create`.

## Constraints

- Never push, open, or merge a PR, and never run `git push`/`gh pr create` unprompted — draft only.
- Never draft around a failing or missing gate; name the blocker instead.
- Flag scope/commit-hygiene concerns rather than silently omitting them from the draft.

## Verification Checklist

- [ ] All four gate verdicts (`gate-enforcer`, `implementation-verifier`, `reconciliation-reviewer`, `security-reviewer`) confirmed Pass from their actual reports.
- [ ] PR title is short, specific, and follows this repo's style.
- [ ] Summary links the story and spec paths.
- [ ] Test-plan checklist reflects the actual traceability matrix and gate results, not a generic template.
- [ ] `.env.example` alignment confirmed or a mismatch flagged.
- [ ] Commit hygiene confirmed or a concern flagged.
- [ ] The draft states plainly that pushing/opening the PR needs an explicit separate instruction.

## Outputs

- `docs/pr/<StoryId>-pr-summary.md`, echoed in chat.

## Completion Criteria

Complete only when all four gate verdicts are confirmed Pass, the draft is written to both the doc file and chat, and the "this is drafted content, not submitted" statement is present.

---

# Harness Contract

This skill owns the `PR_PREPARATION` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`PR_PREPARATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `impact_analysis`, `implementation_plan`, `implementation_report`, `implementation_verification`, `security_review`, `reconciliation`, `traceability`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `impact_analysis`
- `implementation_plan`
- `implementation_report`
- `implementation_verification`
- `security_review`
- `reconciliation`
- `traceability`

## Preconditions (harness)

- Every consumed artifact is current: `status` is not `SUPERSEDED` or
  `ARCHIVED`, and the `version` this skill records in its own `inputs` is the
  version actually on disk. A stale input is `BLOCKED`, not a caveat.
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` input that this stage depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active.

## Result Envelope

Return exactly this. `story-orchestrator` records the transition; this skill
never writes `docs/workflow/workflow-state.yaml`.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: PR_PREPARATION
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/pr/<StoryId>-pr-summary.md
  next_stage: READY_FOR_PR
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `stale_reconciliation` | `RECONCILIATION` |

- `PASS` - all four upstream reviews passed, the PR title, description, and
  test-plan checklist are drafted, `.env.example` is current if settings
  changed, and commit hygiene is confirmed.
- `CHANGES_REQUIRED` - `stale_reconciliation`: the working tree moved after
  RECONCILIATION ran, so its verdict no longer describes what would ship.
- `BLOCKED` - an upstream review is missing, stale, or did not pass.

## Prohibited (harness)

- Do not update workflow state (`workflow-state.yaml`, `active-story.yaml`,
  `history.jsonl`) - `story-orchestrator` owns those.
- Do not produce an artifact this skill does not own in
  `docs/workflow/artifact-paths.yaml`.
- Do not resolve Open Decisions.
- Do not emit a retired verdict (`Pass`, `Fail`, `Pass with Issues`,
  `APPROVED`, ...) - see `artifact-lifecycle.md` section 2.
- Do not use the retired sequential story ids (`US-0NN`) or retired stage
  identifiers (`DESIGN`, `PLANNING`, `TESTS`, `VERIFICATION`, `PR`).
- Do not create commits, branches, or Pull Requests.
