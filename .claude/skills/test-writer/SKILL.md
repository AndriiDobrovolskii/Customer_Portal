---
name: test-writer
description: Turns a story's approved Acceptance Criteria, specification, API design, and DB design into an executable test plan and test code — unit tests with hand-written fakes and integration tests against real PostgreSQL/Valkey — before or alongside implementation. Use when a story's designs are approved and tests need to be written from acceptance criteria ("write tests for US-xxx," "turn these ACs into tests"). Follows this project's testing rules in AGENTS.md §5 (no unittest.mock under tests/integration/, fakes over MagicMock, AAA structure); does not write application code.
---

# Test Writer

## Purpose

Create executable evidence that an implementation satisfies a story's Acceptance Criteria. This turns each AC into one or more concrete test cases before (or alongside) the implementation itself, so "done" means "passing tests trace to every AC," not "code that looks right."

## Operational Contract

```
Precondition: spec review, API design, and DB design are approved for the story.
Input Artifacts: docs/specifications/<StoryId>-spec.md, docs/designs/api/<StoryId>-openapi.yaml, docs/designs/database/<StoryId>-entity-model.md, docs/plans/<StoryId>-implementation-plan.md (if it exists).
Output Artifacts: tests/unit/modules/<module>/*, tests/integration/modules/<module>/*, docs/tests/<StoryId>-traceability-matrix.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — the Acceptance Criteria and Validation Rules sections are the primary source.
2. `docs/designs/api/<StoryId>-openapi.yaml` — request/response shapes to assert against.
3. `docs/designs/database/<StoryId>-entity-model.md` — persisted-state assertions (what should actually be in the DB after the call).
4. `docs/plans/<StoryId>-implementation-plan.md` (if it exists) — which files/layers this story touches, so tests land in the matching `tests/unit/...` / `tests/integration/...` path.
5. `AGENTS.md` §5 (Testing Requirements) — this project's binding testing rules; every rule below cites back to it.

## Preconditions

Spec review, API design, and DB design should be approved before writing tests against them — testing an unapproved contract means rewriting tests when the contract changes. If any is missing, say so; proceed anyway only if the user explicitly wants tests drafted against a draft contract.

## Test Levels — this project's split (`AGENTS.md` §5)

- **Unit** (`tests/unit/modules/<module>/test_<module>_service.py`) — business logic in isolation. Repositories and cache gateways are replaced with hand-written fakes implementing the same `Protocol` — never `MagicMock`, which returns a `Mock()` for everything and proves nothing. Every branch gets a case: happy path, each failure path, each boundary. Domain exceptions asserted via `pytest.raises`.
- **Integration** (`tests/integration/modules/<module>/test_<module>_router.py`) — real PostgreSQL and real Valkey, schema from `alembic upgrade head` (never `create_all()`), HTTP via `AsyncClient(transport=ASGITransport(app=app))`. **`unittest.mock`, `patch`, `AsyncMock`, `MagicMock`, `monkeypatch.setattr` on DB/cache/repository/service are forbidden here** — a pre-commit hook blocks it. Only genuine external egress (payment, email/SMS) may be substituted, via `app.dependency_overrides` with a hand-written recording fake.

## Workflow

1. Build an AC → Test mapping: every Acceptance Criterion in the spec gets at least one row.
2. For each AC, derive: the positive (happy-path) case, negative cases (each stated failure mode), boundary cases (length/value edges from the Validation Rules section), and any security-relevant case (missing token, expired token, wrong role/scope — every protected route per `AGENTS.md` §5 needs all four).
3. Assign each case to unit or integration per the split above — a pure business-rule branch is unit; anything that needs a real request/response/DB round-trip is integration.
4. Write the tests: AAA structure with `# Arrange` / `# Act` / `# Assert` comments, one logical assertion target per test, `@pytest.mark.parametrize` instead of `if`/`for` inside a test body, no `sleep`/retry-until-pass/unseeded randomness — an injected clock or `freezegun` for time-dependent logic.
5. For integration tests on list/nested-data endpoints, consider a statement-count assertion so a lazy-loading regression fails the test rather than silently degrading latency (`AGENTS.md` §5's "statement-count ceiling" rule).
6. Assert status code **and** body shape **and** persisted state — not just one of the three.
7. Generate the traceability matrix (AC → test function name) as part of the output, so a reviewer can confirm no AC was left untested.

## Output Artifacts

- Test source files under `tests/unit/modules/<module>/` and `tests/integration/modules/<module>/`, following this project's existing naming: `test_<unit>_<scenario>_<expected>`.
- `docs/tests/<StoryId>-traceability-matrix.md` — AC ID → test function(s), plus which are unit vs. integration.

## Constraints

- Do not weaken a test to make it pass — no `skip`/`xfail` over a real gap, no lowering an assertion to match actual (possibly wrong) output, no mocking infrastructure in `tests/integration/`.
- Do not invent an AC the spec doesn't state; if a case seems necessary but isn't covered by any AC, note it as a gap rather than testing scope the spec never asked for.

## Completion Criteria

Complete only when every AC has at least one passing-shaped test (happy path, negative, boundary as applicable), every protected endpoint has the four security cases from `AGENTS.md` §5, the traceability matrix is written, and no integration test uses a forbidden mock.
