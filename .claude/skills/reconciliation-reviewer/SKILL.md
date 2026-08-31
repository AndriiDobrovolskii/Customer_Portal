---
name: reconciliation-reviewer
description: After implementation and testing are complete, reconciles what was actually built and tested against the story's original Acceptance Criteria and approved spec — confirming every AC in the spec has a corresponding row in test-writer's traceability matrix (docs/tests/<StoryId>-traceability-matrix.md), that the referenced test function exists and actually asserts the AC's stated behavior (not just its existence), and flagging any drift from the approved spec introduced during coding. Use after implementation-verifier and gate-enforcer report green ("reconcile US-xxx against its ACs," "did we build what the spec said," "AC compliance check before PR"). This is AC/business-requirement compliance, distinct from implementation-verifier's AGENTS.md technical/Definition-of-Done compliance — implementation-verifier asks "did we follow the rules," this skill asks "did we build and prove the right thing." Does not write or fix tests itself; gaps are reported, not filled.
---

# Reconciliation Reviewer

## Purpose

Close the loop between "the spec said X" and "the shipped code actually does X, and a test proves it." `implementation-verifier` already confirmed the code follows AGENTS.md's rules; this skill confirms it follows the *story's* rules — every Acceptance Criterion accounted for, tested, and unchanged from what was approved.

## Operational Contract

```
Precondition: implementation-verifier and gate-enforcer both report green for the story.
Input Artifacts: docs/specifications/<StoryId>-*-spec.md (the Acceptance Criteria); docs/tests/<StoryId>-traceability-matrix.md (produced by test-writer) and the test files it references; docs/plans/<StoryId>-implementation-plan.md.
Output Artifacts: docs/reconciliation/<StoryId>-reconciliation-report.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-*-spec.md` — the Acceptance Criteria list and Traceability Matrix, ground truth for what "done" means.
2. `docs/tests/<StoryId>-traceability-matrix.md` — `test-writer`'s AC → test function mapping.
3. The actual test files the matrix references — not just their names, their content.
4. `docs/plans/<StoryId>-implementation-plan.md` — what was planned, to compare against what actually shipped.

## Preconditions

`implementation-verifier` and `gate-enforcer` have both reported green. If either hasn't, stop and name which is missing — reconciling against code that hasn't passed the technical gate yet is premature.

## Workflow

1. For every AC in the spec, confirm a row exists in `docs/tests/<StoryId>-traceability-matrix.md`. Any AC with no row is a Fail-forcing finding.
2. For every matrix row, open the named test file and confirm the named test function actually exists at that path.
3. Read each test function's body and confirm it **asserts the AC's actual stated behavior** — not merely that it touches related code or exercises the same endpoint. A test that calls the right function but asserts something weaker than the AC states (e.g. asserts a 200 status but not the AC's specific persisted-state claim) counts as a gap, not full coverage.
4. Compare the final implementation against the approved spec for drift introduced during coding — a field renamed, a validation rule loosened, an error code changed from what the spec/API design stated — similar in spirit to `story-spec-reviewer`'s contradiction check, but comparing spec against shipped code instead of spec against story.
5. Assign a verdict: **Pass** (every AC has a matrix row, an existing test, and that test asserts the AC's actual behavior, with no drift) / **Pass with Issues** (full coverage and no drift, but a test's assertion could be tighter) / **Fail** (any AC with no matrix row, a missing test function, a non-asserting test, or confirmed drift from the approved spec).
6. Write the report to `docs/reconciliation/<StoryId>-reconciliation-report.md` using `assets/template.md`.

## Constraints

- This is AC/business-requirement compliance only — do not re-check AGENTS.md technical rules (that's `implementation-verifier`) or re-run the gate (that's `gate-enforcer`).
- Do not write or fix a test yourself — a gap is reported for `test-writer` (or the user) to close, not silently patched here.
- Every finding cites the specific AC ID, test file:line, or spec section it's based on.

## Verification Checklist

- [ ] Every AC in the spec has exactly one row in the traceability matrix — checked, not assumed.
- [ ] Every referenced test function was opened and confirmed to exist.
- [ ] Every test's assertions were read and confirmed to match the AC's actual stated behavior, not just proximity to it.
- [ ] The shipped implementation was compared against the approved spec for drift.
- [ ] The verdict is consistent with the findings (any missing row/function/non-asserting test or confirmed drift forces Fail).

## Outputs

- `docs/reconciliation/<StoryId>-reconciliation-report.md`.

## Completion Criteria

Complete only when every AC has a confirmed matrix row, an existing and behavior-asserting test, and any spec drift found during implementation has been explicitly named — not silently absorbed into a passing verdict.
