---
name: implementation-verifier
description: Performs the human-judgment half of AGENTS.md §6's Definition of Done after the execution skills have produced code — the parts that aren't mechanically checked by the pre-commit gate: whether the generated Alembic migration file was actually read and its rewriter-unreachable statements guarded (§6.5), whether ORM objects never cross service→router, all nested data is eager-loaded, every cache write carries a TTL, and cross-module calls go service→service (§6.6, marked "not machine-checkable" in AGENTS.md itself), plus the doc-level §6.7 items (response_model/status_code on every route, extra="forbid" and privilege-field exclusion, .env.example updated, no sensitive field in any *Read). Use after gate-enforcer has reported a green gate and before reconciliation-reviewer or security-reviewer run ("verify the Definition of Done for US-xxx," "did we actually satisfy AGENTS.md §6"). Does NOT re-run pre-commit, mypy, lint-imports, coverage, or the upgrade/downgrade cycle — that mechanical half is gate-enforcer's job (§6.1-§6.4 plus the §6.5 command sequence) and this skill trusts a passing gate result rather than reproducing it. Also distinct from reconciliation-reviewer, which checks AC/business-requirement compliance, not AGENTS.md technical compliance — this skill never judges "did we build the right thing," only "did we build it per the rules."
---

# Implementation Verifier

## Purpose

`gate-enforcer` proves the mechanical half of the Definition of Done — commands that either pass or fail. This skill proves the half AGENTS.md §6.6 itself marks "not machine-checkable": judgment calls that require actually reading the code, not running a linter against it. Trust `gate-enforcer`'s green result; don't reproduce it.

## Operational Contract

```
Precondition: gate-enforcer has reported green for §6.1–§6.4 and the §6.5 command sequence. If it hasn't run or reported non-green, stop and say so rather than proceeding.
Input Artifacts: the story's implemented code (schemas.py, models.py, repository.py, cache.py, service.py, router.py); gate-enforcer's report; the migration file from migration-manager.
Output Artifacts: docs/verification/<StoryId>-implementation-verification.md.
```

## Required Context

Read, in order:

1. `gate-enforcer`'s report for this story — confirm which sections it covered and that the verdict was green (or "local gate green, CI-only pending," in which case note the pending items explicitly rather than treating them as verified).
2. The story's implemented code across all layers.
3. The migration file from `migration-manager`, and its own captured upgrade/downgrade/upgrade output.
4. `AGENTS.md` §6.5 (migration human-judgment half), §6.6 (runtime rules, quoted in full below), §6.7 (contract & security doc-level items), and §5 (the four security cases per protected route).

## Preconditions

`gate-enforcer` has reported green for the mechanical checks. If it hasn't run, stop and say so — this skill's checklist assumes that foundation and does not re-verify it.

## Workflow

1. **§6.5 human half.** Confirm the migration's generated file was actually read (per `migration-manager`'s own report) and that every statement the Rewriter can't reach (`add_column`/`drop_column`, `AlterColumnOp`, enum edits, hand-written `op.execute()`) has its own `sa.inspect(op.get_bind())` guard. Confirm `downgrade()` performs real inverse operations, never `pass`.
2. **§6.6 — ORM containment.** Read every service method's return path with file:line evidence: confirm it returns `Schema.model_validate(orm_obj)` or an equivalent domain object, never the ORM instance itself, and that the return annotation is an explicit `-> *Read`/domain type, never `Any` or the model class.
3. **§6.6 — Eager loading.** For every relationship touched by this story, confirm with file:line evidence that the repository query includes the eager-load strategy the model's `lazy="raise_on_sql"` comment specifies, and that no collection `joinedload()` is combined with `LIMIT`/`OFFSET`.
4. **§6.6 — Cache TTL.** For every cache write in scope, confirm a TTL is set with the call site cited; if no cache write exists in this diff, state that explicitly rather than skipping the item.
5. **§6.6 — Service→service discipline.** Confirm every cross-module call in the story's service targets another module's service class, never its router, citing the import.
6. **§6.7 — Contract & security doc-level.** Confirm every new/changed route declares both `response_model` and `status_code`; every inbound schema sets `extra="forbid"` and excludes privilege fields (cite the actual field list checked, not just AGENTS.md's example list); `.env.example` was updated if a new setting was introduced; no sensitive field appears in any `*Read` schema.
7. **§5 security cases.** Confirm every protected route has tests for no token, expired token, malformed token, insufficient permissions, and revoked session — cite the test file/function names, don't just assert they exist.
8. Assign a verdict: **Pass** / **Pass with Issues** (a minor doc-level gap, e.g. `.env.example` lagging by a non-security setting) / **Fail** (any ORM leak, missing eager-load, TTL-less cache write, service→router cross-module call, or missing `response_model`/`status_code`).
9. Write the report to `docs/verification/<StoryId>-implementation-verification.md` using `assets/template.md`.

## Constraints

- Do not re-run `pre-commit`, `mypy`, `lint-imports`, coverage, or the migration upgrade/downgrade/upgrade cycle — trust `gate-enforcer`'s captured result for those.
- Do not judge AC/business-requirement compliance ("did we build the right thing") — that's `reconciliation-reviewer`'s job. This skill only judges AGENTS.md technical compliance.
- Every checklist item requires cited evidence (file:line or command output) — a blanket "looks fine" is not acceptable.

## Verification Checklist

- [ ] §6.5: migration file confirmed read; rewriter-unreachable statements guarded; `downgrade()` real.
- [ ] §6.6: no ORM object crosses service→router, with evidence.
- [ ] §6.6: every touched relationship eager-loaded per its declared strategy, with evidence.
- [ ] §6.6: every cache write has a TTL, or explicitly N/A.
- [ ] §6.6: every cross-module call targets a service, never a router, with evidence.
- [ ] §6.7: `response_model`/`status_code` on every route; `extra="forbid"`+privilege exclusion on every inbound schema; `.env.example` current; no sensitive `*Read` field.
- [ ] §5: all four security cases exist per protected route, with test names cited.
- [ ] Verdict is consistent with the findings.

## Outputs

- `docs/verification/<StoryId>-implementation-verification.md`.

## Completion Criteria

Complete only when every §6.5/§6.6/§6.7 item has an explicit checked/not-checked status backed by cited evidence, and the verdict follows from those findings — not asserted independently of them.

---

# Harness Contract

This skill owns the `IMPLEMENTATION_VERIFICATION` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`IMPLEMENTATION_VERIFICATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `specification_review`, `impact_analysis`, `implementation_plan`, `task_breakdown`, `plan_review`, `implementation_report`, `quality_gate_report`, `api_design`, `openapi`, `database_design`, `entity_model`, `test_strategy`, `ac_test_matrix`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `specification_review`
- `impact_analysis`
- `implementation_plan`
- `task_breakdown`
- `plan_review`
- `implementation_report`
- `quality_gate_report`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `test_strategy`
- `ac_test_matrix`

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
  stage: IMPLEMENTATION_VERIFICATION
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/verification/<StoryId>-implementation-verification.md
  next_stage: SECURITY_REVIEW
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required` | `IMPLEMENTATION` |

- `PASS` - the implementation satisfies AGENTS.md and the Definition of Done,
  verified independently rather than taken from the implementation report.
- `CHANGES_REQUIRED` - Critical or Major findings against the rules.
- `BLOCKED` - a mandatory input is missing or stale, or the working tree does
  not match what the implementation report claims.

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
