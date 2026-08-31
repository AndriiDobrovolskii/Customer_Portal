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
Input Artifacts: docs/verification/<StoryId>-verification-report.md; docs/reconciliation/<StoryId>-reconciliation-report.md; docs/security/<StoryId>-security-review.md; gate-enforcer's reported result (chat report — gate-enforcer writes no docs/ file).
Output Artifacts: docs/pr/<StoryId>-pr-description.md, echoed in chat.
```

## Required Context

Read, in order:

1. `docs/verification/<StoryId>-verification-report.md` — confirm `implementation-verifier`'s verdict is Pass.
2. `docs/reconciliation/<StoryId>-reconciliation-report.md` — confirm `reconciliation-reviewer`'s verdict is Pass.
3. `docs/security/<StoryId>-security-review.md` — confirm `security-reviewer`'s verdict is Pass.
4. `gate-enforcer`'s most recent report for this story (chat transcript or wherever the user has it) — confirm its verdict.
5. `docs/specifications/<StoryId>-*-spec.md` and `docs/plans/<StoryId>-implementation-plan.md` — for the summary and linked-story content.
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
8. Write `docs/pr/<StoryId>-pr-description.md` and echo the same content in chat.
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

- `docs/pr/<StoryId>-pr-description.md`, echoed in chat.

## Completion Criteria

Complete only when all four gate verdicts are confirmed Pass, the draft is written to both the doc file and chat, and the "this is drafted content, not submitted" statement is present.
