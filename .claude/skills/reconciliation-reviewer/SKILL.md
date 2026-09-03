---
name: reconciliation-reviewer
description: After implementation and testing are complete, reconciles what was actually built and tested against the story's original Acceptance Criteria and approved spec — confirming every AC in the spec has a corresponding row in test-writer's traceability matrix (docs/tests/<StoryId>-ac-test-matrix.md), that the referenced test function exists and actually asserts the AC's stated behavior (not just its existence), and flagging any drift from the approved spec introduced during coding. Use after implementation-verifier and gate-enforcer report green ("reconcile US-xxx against its ACs," "did we build what the spec said," "AC compliance check before PR"). This is AC/business-requirement compliance, distinct from implementation-verifier's AGENTS.md technical/Definition-of-Done compliance — implementation-verifier asks "did we follow the rules," this skill asks "did we build and prove the right thing." Does not write or fix tests itself; gaps are reported, not filled.
---

# Reconciliation Reviewer

## Purpose

Close the loop between "the spec said X" and "the shipped code actually does X, and a test proves it." `implementation-verifier` already confirmed the code follows AGENTS.md's rules; this skill confirms it follows the *story's* rules — every Acceptance Criterion accounted for, tested, and unchanged from what was approved.

## Operational Contract

```
Precondition: implementation-verifier and gate-enforcer both report green for the story.
Input Artifacts: docs/specifications/<StoryId>-spec.md (the Acceptance Criteria); docs/tests/<StoryId>-ac-test-matrix.md (produced by test-writer) and the test files it references; docs/plans/<StoryId>-implementation-plan.md.
Output Artifacts: docs/reviews/reconciliation/<StoryId>-reconciliation.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — the Acceptance Criteria list and Traceability Matrix, ground truth for what "done" means.
2. `docs/tests/<StoryId>-ac-test-matrix.md` — `test-writer`'s AC → test function mapping.
3. The actual test files the matrix references — not just their names, their content.
4. `docs/plans/<StoryId>-implementation-plan.md` — what was planned, to compare against what actually shipped.

## Preconditions

`implementation-verifier` and `gate-enforcer` have both reported green. If either hasn't, stop and name which is missing — reconciling against code that hasn't passed the technical gate yet is premature.

## Workflow

1. For every AC in the spec, confirm a row exists in `docs/tests/<StoryId>-ac-test-matrix.md`. Any AC with no row is a Fail-forcing finding.
2. For every matrix row, open the named test file and confirm the named test function actually exists at that path.
3. Read each test function's body and confirm it **asserts the AC's actual stated behavior** — not merely that it touches related code or exercises the same endpoint. A test that calls the right function but asserts something weaker than the AC states (e.g. asserts a 200 status but not the AC's specific persisted-state claim) counts as a gap, not full coverage.
4. Compare the final implementation against the approved spec for drift introduced during coding — a field renamed, a validation rule loosened, an error code changed from what the spec/API design stated — similar in spirit to `story-spec-reviewer`'s contradiction check, but comparing spec against shipped code instead of spec against story.
5. Assign a verdict: **Pass** (every AC has a matrix row, an existing test, and that test asserts the AC's actual behavior, with no drift) / **Pass with Issues** (full coverage and no drift, but a test's assertion could be tighter) / **Fail** (any AC with no matrix row, a missing test function, a non-asserting test, or confirmed drift from the approved spec).
6. Write the report to `docs/reviews/reconciliation/<StoryId>-reconciliation.md` using `assets/template.md`.

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

- `docs/reviews/reconciliation/<StoryId>-reconciliation.md`.

## Completion Criteria

Complete only when every AC has a confirmed matrix row, an existing and behavior-asserting test, and any spec drift found during implementation has been explicitly named — not silently absorbed into a passing verdict.

---

# Harness Contract

This skill owns the `RECONCILIATION` stage of `docs/workflow/stage-map.yaml`.

**This stage now produces two artifacts, not one.** The single report described
above is split by the registry:

- `reconciliation` (`docs/reviews/reconciliation/<StoryId>-reconciliation.md`) —
  the review: findings, drift register, verdict rationale.
- `traceability` (`docs/reconciliation/<StoryId>-traceability.md`) — the
  end-to-end AC → specification → design → test → code mapping, as a standalone
  table `pr-preparer` and a human reviewer can read on its own.

Both carry front matter per `artifact-schema.md`. Historical stories have only
the combined report, at the `reconciliation` path.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`RECONCILIATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `specification_review`, `api_design`, `openapi`, `database_design`, `entity_model`, `design_review`, `impact_analysis`, `implementation_plan`, `task_breakdown`, `plan_review`, `test_strategy`, `ac_test_matrix`, `test_generation_report`, `implementation_report`, `implementation_verification`, `security_review`, `open_decisions`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `specification_review`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `design_review`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `impact_analysis`
- `implementation_plan`
- `task_breakdown`
- `plan_review`
- `test_strategy`
- `ac_test_matrix`
- `test_generation_report`
- `implementation_report`
- `implementation_verification`
- `security_review`
- `open_decisions`

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
  stage: RECONCILIATION
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/reviews/reconciliation/<StoryId>-reconciliation.md
    - docs/reconciliation/<StoryId>-traceability.md
  next_stage: HUMAN_PR_APPROVAL
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `implementation_drift` | `IMPLEMENTATION` |
| `test_gap` | `TEST_WRITING` |
| `plan_gap` | `ARCHITECTURE_PLANNING` |
| `design_gap` | `API_DESIGN` |
| `specification_gap` | `SPECIFICATION` |
| `story_source_conflict` | `BACKLOG_SYNC` |

- `PASS` - every acceptance criterion has a matrix row, the named test exists,
  and that test actually asserts the criterion's stated behavior - not merely
  that it exists.
- `CHANGES_REQUIRED` - pick the key matching where the gap originates. A test
  asserting less than its criterion states is `test_gap`, not
  `implementation_drift`, when the shipped code is correct.
- `BLOCKED` - a mandatory input is missing or stale.

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
