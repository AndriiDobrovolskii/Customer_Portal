---
name: gate-enforcer
description: Runs and reports the full post-generation verification gate for a story's implementation — pre-commit run --all-files, mypy app tests, lint-imports, pytest --cov=app --cov-report=term-missing --cov-fail-under=85 where runnable locally — plus the runtime rules no tool checks (AGENTS.md §6.6): ORM objects never reaching a router, every relationship eager-loaded appropriately, every cache write carrying a TTL, cross-module calls going service→service (never service→another module's router), and no typing.Any/# type: ignore/os.getenv outside core.config. Use after schema-builder/data-layer-builder/service-and-router-builder/migration-manager have produced code and it's time to confirm the Definition of Done before commit or PR ("run the gate for US-xxx," "is this ready to commit," "check this passes CI," "verify the definition of done"). Never proposes bypassing a failing check — no --no-verify, SKIP=<hook>, narrowed mypy scope, coverage excludes, or disabled import-linter contracts; a failing check is reported and the skill stops there, per AGENTS.md §7.9 naming "reporting a check as passing without running it" the most serious violation available. Does not fix failures itself and does not perform a substantive architecture/security code review (that belongs to other pipeline stages) — this is the mechanical-gate-plus-runtime-rules check only, run before commit/PR, not a replacement for them.
---

# Gate Enforcer

## Purpose

Run this codebase's actual quality gate and report exactly what happened — never what should happen, never what would probably happen. AGENTS.md §7.9 names "reporting a check as passing without running it" as the single most serious violation available to an agent, because it silently disables every other rule in the file. This skill exists to make that failure mode structurally impossible: every checklist item below requires captured, quoted command output.

## Operational Contract

```
Precondition: schema-builder, data-layer-builder, service-and-router-builder, and migration-manager (where applicable) have produced code for this story; git status/git diff shows real changes.
Input Artifacts: the story's changed files; pyproject.toml ([tool.importlinter]/[tool.mypy]/[tool.ruff]/[tool.coverage] sections); .pre-commit-config.yaml; AGENTS.md §6 and §7.
Output Artifacts: a chat report only (no docs/ file — docs/verification/ belongs to implementation-verifier, not this skill).
```

## Required Context

Read, in order:

1. `AGENTS.md` §6 (Definition of Done, all 7 items) and §7 (Prohibited Actions, especially §7.9's bypass list).
2. `pyproject.toml`'s `[tool.importlinter]`, `[tool.mypy]`, `[tool.ruff]`, `[tool.coverage]` sections — read as the *actual current* thresholds/contracts, never assumed from memory (this project currently sets `--cov-fail-under=85`, `mypy strict` with `exclude = ["migrations/"]`, and 5 import-linter contracts — but re-read the file each run, since these can change).
3. `.pre-commit-config.yaml` — confirm which hooks actually run locally (`ruff`, `ruff-format`, `mypy`, `lint-imports`, `unit-tests`, `no-mock-in-integration-tests`, `detect-secrets`, in this repo).

## Preconditions

Implementation code already exists for the story (`git status`/`git diff` shows something). If nothing changed, say so rather than running an empty gate.

## Workflow

### Part A — mechanical (always paste real captured output; never assert a result without running it)

1. `pre-commit run --all-files` — capture full output. A Ruff auto-fix modifying files is expected and not itself a failure (per AGENTS.md §6 "When a hook fails"): `git add -u` and re-run. A real mypy/lint-imports/secret-scan failure is not auto-fixable and is a stop.
2. `mypy app tests` — capture full output; must target the whole project, never a single file.
3. `lint-imports` — capture full output; confirm zero broken contracts, and confirm `pyproject.toml` gained no new `ignore_imports`/`exhaustive = false` (diff against the last committed version if available).
4. `pytest --cov=app --cov-report=term-missing --cov-fail-under=85` — run what's actually runnable in this environment. If integration tests need containers unavailable here, report explicitly "not run here — CI is the authority per AGENTS.md §6," never a silent skip or a claimed pass.
5. Migration cycle — confirm `migration-manager` already captured a real `upgrade → downgrade → upgrade`, or run and capture it here. `mypy`'s `exclude = ["migrations/"]` means this cycle is the *only* proof for that code — it can't be waved through.

### Part B — runtime rules (AGENTS.md §6.6, explicitly marked "not machine-checkable" in AGENTS.md itself)

6. **ORM containment** — grep changed `router.py` files for model imports (there should be none); check every changed `service.py` return annotation is `-> *Read`/a domain type, never a model, never `Any`.
7. **Eager loading** — for every touched relationship, confirm the repository query uses the strategy declared on the model's `lazy="raise_on_sql"` comment (`joinedload`/`selectinload`/`contains_eager`); flag any relationship access with no accompanying eager-load in the same query.
8. **Cache TTL** — grep for cache-gateway write calls and confirm each carries a TTL; if no `cache.py` exists in this diff, report "N/A — no cache writes in this diff," not a false pass.
9. **Cross-module discipline** — grep changed `service.py` files for `from app.modules.<other>.router import` (forbidden) vs. `...service import` (required).
10. **Banned idioms** — grep the diff for `typing.Any`, `# type: ignore`, `cast(`, and `os.getenv`/`os.environ` outside `app/core/config.py`; each hit is a finding unless it's the one documented `migrations/env.py` exemption already carved into `pyproject.toml`'s `per-file-ignores`/mypy override.
11. **Contract & security spot-check (§6.7)** — every new/changed route declares `response_model` and `status_code`; every inbound schema sets `extra="forbid"` and excludes privilege fields; no sensitive field in any `*Read`; `.env.example` updated if a setting was added.

### On any failure

Report the failing check verbatim, stop, and explicitly refuse to propose any of: `--no-verify`/`-n`, `SKIP=<hook>`, `pre-commit uninstall`, narrowing mypy to one file, adding `exclude:`/`ignore_imports`/`exhaustive=false`, lowering `--cov-fail-under`, adding coverage excludes, or commenting out an assertion. Name AGENTS.md §7.9 as the reason.

### Verdict

**PASS** only if every Part A check runnable locally actually passed and every Part B item is confirmed-compliant or explicitly N/A, with nothing not-run-locally asserted as passing. Otherwise **FAIL** with the specific unmet list, or a labeled "local gate green, CI-only checks pending" state for the documented CI-only items (integration tests with containers, the coverage threshold if it needs those tests, the Alembic cycle if not already run).

## Constraints

- Never propose or apply a gate bypass of any kind (see On any failure).
- Never claim a check passed without having run it and captured its real output.
- This skill fixes nothing — it reports. Fixing a failure is the responsibility of whichever generating skill produced the failing code.

## Verification Checklist

- [ ] `pre-commit run --all-files` output captured and quoted.
- [ ] `mypy app tests` output captured and quoted.
- [ ] `lint-imports` output captured and quoted; no new `ignore_imports`/`exhaustive=false`.
- [ ] `pytest --cov=app ... --cov-fail-under=85` output captured and quoted, or explicitly marked not-runnable-here.
- [ ] Migration upgrade→downgrade→upgrade output captured and quoted (or confirmed already captured by `migration-manager`).
- [ ] ORM containment checked with evidence.
- [ ] Eager-loading strategy checked per touched relationship, with evidence.
- [ ] Cache TTL checked per cache write, or explicitly N/A.
- [ ] Cross-module import discipline checked with evidence.
- [ ] Banned-idiom grep run and results reported.
- [ ] §6.7 contract/security spot-check completed.
- [ ] No bypass was proposed for any failing check.

## Outputs

- A chat report structured like `assets/report-template.md`, covering every item above with its result (Pass/Fail/N/A) and evidence.

## Completion Criteria

Complete only when every applicable check has a real captured result, the verdict is consistent with those results, and no failing check was accompanied by a bypass suggestion.

---

# Harness Contract

This skill owns the `QUALITY_GATE` stage of `docs/workflow/stage-map.yaml`.

**This stage now writes two durable artifacts.** The Operational Contract above
says "a chat report only" — that is superseded. `QUALITY_GATE` runs after all
four `IMPLEMENTATION` builder sub-steps and is the only skill positioned to
aggregate them, so the registry makes it the owner of both:

- `quality_gate_report` (`docs/evidence/<StoryId>-quality-gate-report.md`) — the
  mechanical evidence: every gate command with its **real captured output**.
  This is the file that makes AGENTS.md §7.9 auditable after the fact, so a
  check that could not run here is recorded as not-run with CI named as the
  authority, never as a pass.
- `implementation_report` (`docs/evidence/<StoryId>-implementation-report.md`) —
  what was actually built: modules, files, endpoints, migrations, and per-task
  status against `task_breakdown`. `implementation-verifier`,
  `security-reviewer`, `reconciliation-reviewer`, and `pr-preparer` all consume
  it, and `implementation-verifier` explicitly checks it for accuracy rather
  than trusting it.

This does **not** make this skill a reviewer. It still runs the gate and reports
what happened; it does not judge architecture or security.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`QUALITY_GATE`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `implementation_plan`, `task_breakdown`, `ac_test_matrix`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `implementation_plan`
- `task_breakdown`
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
  stage: QUALITY_GATE
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/evidence/<StoryId>-implementation-report.md
    - docs/evidence/<StoryId>-quality-gate-report.md
  next_stage: IMPLEMENTATION_VERIFICATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required` | `IMPLEMENTATION` |

- `PASS` - every gate command was actually run and its real output captured,
  and all of them passed.
- `CHANGES_REQUIRED` - a check failed. Report exactly which, with its output,
  and route back to `IMPLEMENTATION`. Never propose a bypass
  (`--no-verify`, `SKIP=`, a narrowed mypy scope, a coverage exclude) -
  AGENTS.md section 7.9.
- `BLOCKED` - a check could not be run in this environment. Say so
  explicitly and name CI as the authority; never record it as a pass.

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
