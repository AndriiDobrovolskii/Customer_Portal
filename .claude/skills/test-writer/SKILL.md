---
name: test-writer
description: Turns a story's approved Acceptance Criteria and specification into an executable test plan and test code before or alongside implementation. For a `track: backend` Story (default) — unit tests with hand-written fakes and integration tests against real PostgreSQL/Valkey, using the API/DB design. For a `track: frontend` Story — Vitest unit tests and React-Testing-Library-plus-MSW integration tests, using the spec's own API Contract table as the reference (no separate API/DB design exists on this track). Use when a story's designs are approved and tests need to be written from acceptance criteria ("write tests for US-xxx," "turn these ACs into tests"). Follows this project's testing rules in AGENTS.md §5 (no unittest.mock under tests/integration/, fakes over MagicMock, AAA structure — or, frontend, no vi.mock() on the unit under test, MSW for the network boundary); does not write application code.
---

# Test Writer

## Purpose

Create executable evidence that an implementation satisfies a story's Acceptance Criteria. This turns each AC into one or more concrete test cases before (or alongside) the implementation itself, so "done" means "passing tests trace to every AC," not "code that looks right."

**Track first.** Read the Story's `track` field (`docs/stories/<StoryId>.md` front matter;
absent means `backend`) before anything else — it picks which half of every section below
applies, including which directory the tests land in and which mocking rules bind.

## Operational Contract

```
Precondition: spec review, API design, and DB design are approved for the story.
Input Artifacts: docs/specifications/<StoryId>-spec.md, docs/designs/api/<StoryId>-openapi.yaml, docs/designs/database/<StoryId>-entity-model.md, docs/plans/<StoryId>-implementation-plan.md (if it exists).
Output Artifacts: tests/unit/modules/<module>/*, tests/integration/modules/<module>/*, docs/tests/<StoryId>-ac-test-matrix.md.
```

## Required Context

**`track: backend`** — read, in order:

1. `docs/specifications/<StoryId>-spec.md` — the Acceptance Criteria and Validation Rules sections are the primary source.
2. `docs/designs/api/<StoryId>-openapi.yaml` — request/response shapes to assert against.
3. `docs/designs/database/<StoryId>-entity-model.md` — persisted-state assertions (what should actually be in the DB after the call).
4. `docs/plans/<StoryId>-implementation-plan.md` (if it exists) — which files/layers this story touches, so tests land in the matching `tests/unit/...` / `tests/integration/...` path.
5. `AGENTS.md` §5 (Testing Requirements) — this project's binding testing rules; every rule below cites back to it.

**`track: frontend`** — read, in order:

1. `docs/specifications/<StoryId>-spec.md` — Acceptance Criteria, plus its own API Contract table (the reference contract; no separate `openapi.yaml` exists on this track).
2. `docs/plans/<StoryId>-implementation-plan.md` / `task-breakdown.md` (if they exist) — which `frontend/src/...` files this story touches, so tests land alongside them.
3. `AGENTS.md` §5's Frontend subsection — this track's binding testing rules.

## Preconditions

**`track: backend`**: spec review, API design, and DB design should be approved before writing tests against them — testing an unapproved contract means rewriting tests when the contract changes. If any is missing, say so; proceed anyway only if the user explicitly wants tests drafted against a draft contract.

**`track: frontend`**: spec review should be approved. API/DB design being `NOT_APPLICABLE` is expected on this track, not a missing precondition.

## Test Levels

**`track: backend`** (`AGENTS.md` §5):

- **Unit** (`tests/unit/modules/<module>/test_<module>_service.py`) — business logic in isolation. Repositories and cache gateways are replaced with hand-written fakes implementing the same `Protocol` — never `MagicMock`, which returns a `Mock()` for everything and proves nothing. Every branch gets a case: happy path, each failure path, each boundary. Domain exceptions asserted via `pytest.raises`.
- **Integration** (`tests/integration/modules/<module>/test_<module>_router.py`) — real PostgreSQL and real Valkey, schema from `alembic upgrade head` (never `create_all()`), HTTP via `AsyncClient(transport=ASGITransport(app=app))`. **`unittest.mock`, `patch`, `AsyncMock`, `MagicMock`, `monkeypatch.setattr` on DB/cache/repository/service are forbidden here** — a pre-commit hook blocks it. Only genuine external egress (payment, email/SMS) may be substituted, via `app.dependency_overrides` with a hand-written recording fake.

**`track: frontend`** (`AGENTS.md` §5's Frontend subsection):

- **Unit** (`frontend/src/hooks/<hook>.test.ts`, or colocated with the function under test) — a hook or pure function in isolation. Prefer a real MSW handler over a hand-mocked `fetch`.
- **Integration** (`frontend/src/screens/<Screen>.test.tsx`) — React Testing Library renders the real component tree; MSW intercepts network calls with handlers shaped like the actual backend responses, including non-conforming shapes an Open Decision flagged (e.g. `/auth/register`'s two non-RFC7807 error bodies). **`vi.mock()` on the component/hook/store actually under test is forbidden** — mock the network (MSW), not the code being tested.

## Workflow

1. Build an AC → Test mapping: every Acceptance Criterion in the spec gets at least one row.
2. For each AC, derive: the positive (happy-path) case, negative cases (each stated failure mode), boundary cases (length/value edges from the Validation Rules section), and any security-relevant case (missing token, expired token, wrong role/scope — every protected route per `AGENTS.md` §5 needs all four; for `track: frontend`, this means asserting the route guard's redirect, not a server-side 401/403, since the frontend has no auth logic of its own to bypass).
3. Assign each case to unit or integration per the split above — a pure business-rule branch is unit; anything that needs a real request/response round-trip (DB, for backend; MSW-backed network, for frontend) is integration.
4. **`track: backend`**: AAA structure with `# Arrange` / `# Act` / `# Assert` comments, one logical assertion target per test, `@pytest.mark.parametrize` instead of `if`/`for` inside a test body, no `sleep`/retry-until-pass/unseeded randomness — an injected clock or `freezegun` for time-dependent logic. **`track: frontend`**: same AAA discipline; async assertions via React Testing Library's `waitFor`/`findBy*`, never a fixed `setTimeout` or a retry loop.
5. For integration tests on list/nested-data endpoints (backend only), consider a statement-count assertion so a lazy-loading regression fails the test rather than silently degrading latency (`AGENTS.md` §5's "statement-count ceiling" rule).
6. Assert status code **and** body shape **and** persisted state (backend) / rendered result (frontend) — not just one of the three.
7. Generate the traceability matrix (AC → test function name) as part of the output, so a reviewer can confirm no AC was left untested.

## Output Artifacts

**`track: backend`**:
- Test source files under `tests/unit/modules/<module>/` and `tests/integration/modules/<module>/`, following this project's existing naming: `test_<unit>_<scenario>_<expected>`.

**`track: frontend`**:
- Test source files colocated with the code under test in `frontend/src/**/*.test.ts(x)`.

**Both tracks**:
- `docs/tests/<StoryId>-ac-test-matrix.md` — AC ID → test function(s), plus which are unit vs. integration.

## Constraints

- Do not weaken a test to make it pass — no `skip`/`xfail` over a real gap, no lowering an assertion to match actual (possibly wrong) output, no mocking infrastructure in `tests/integration/` (backend) or the unit under test via `vi.mock()` (frontend).
- Do not invent an AC the spec doesn't state; if a case seems necessary but isn't covered by any AC, note it as a gap rather than testing scope the spec never asked for.

## Completion Criteria

Complete only when every AC has at least one passing-shaped test (happy path, negative, boundary as applicable), every protected endpoint/route has its track's required security cases, the traceability matrix is written, and no test uses a forbidden mock for its track.

---

# Harness Contract

This skill owns the `TEST_WRITING` stage of `docs/workflow/stage-map.yaml`.

**This stage now produces three artifacts.** The single traceability matrix
described above is split, and an evidence report is added:

- `test_strategy` (`docs/tests/<StoryId>-test-strategy.md`) — what will be
  tested at which level and why: unit vs integration split, the fakes needed,
  the fixtures, and any statement-count ceiling per `AGENTS.md` §5.
- `ac_test_matrix` (`docs/tests/<StoryId>-ac-test-matrix.md`) — the AC ID →
  test function mapping. This is the migrated home of the old traceability
  matrix; historical stories have only this one.
- `test_generation_report` (`docs/evidence/<StoryId>-test-generation-report.md`)
  — what was actually generated: files written, tests added, anything an AC
  needed that could not be tested yet and why.

All three carry front matter per `artifact-schema.md`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`TEST_WRITING`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `api_design`, `openapi`, `database_design`, `entity_model`, `impact_analysis`, `implementation_plan`, `task_breakdown`, `plan_review`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `impact_analysis`
- `implementation_plan`
- `task_breakdown`
- `plan_review`

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
  stage: TEST_WRITING
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/tests/<StoryId>-test-strategy.md
    - docs/tests/<StoryId>-ac-test-matrix.md
    - docs/evidence/<StoryId>-test-generation-report.md
  next_stage: IMPLEMENTATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required_tests` | `TEST_WRITING` |
| `invalid_specification` | `SPECIFICATION` |
| `invalid_api_design` | `API_DESIGN` |
| `invalid_database_design` | `DB_DESIGN` |

- `PASS` - every acceptance criterion has at least one test that asserts its
  stated behavior, and the matrix rows name test functions that exist.
- `CHANGES_REQUIRED` - use the `invalid_*` keys when an upstream artifact is
  untestable as written; `changes_required_tests` when only the tests are.
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
