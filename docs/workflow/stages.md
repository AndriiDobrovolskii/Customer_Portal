# Workflow Stages — Human-Readable Overview

**Non-normative.** `docs/workflow/stage-map.yaml` is the only authority for
stage identifiers, order, ownership, and routing. If this document and the stage
map ever disagree, the stage map wins and this file is the bug.

## The flow

```
BACKLOG_SYNC
    ↓
CLARIFICATION ──→ SPECIFICATION ──→ SPEC_REVIEW ──→ ⛌ HUMAN_SPEC_APPROVAL
                                                          ↓
API_DESIGN ──→ DB_DESIGN ──→ DESIGN_REVIEW ──→ IMPACT_ANALYSIS
                                                          ↓
ARCHITECTURE_PLANNING ──→ IMPLEMENTATION_PLANNING ──→ PLAN_REVIEW
                                                          ↓
                                              ⛌ HUMAN_PLAN_APPROVAL
                                                          ↓
TEST_WRITING ──→ IMPLEMENTATION ──→ QUALITY_GATE ──→ IMPLEMENTATION_VERIFICATION
                                                          ↓
SECURITY_REVIEW ──→ RECONCILIATION ──→ ⛌ HUMAN_PR_APPROVAL
                                                          ↓
PR_PREPARATION ──→ ⛌ READY_FOR_PR ──→ ⛌ COMPLETED ──→ ARCHIVED

⛌ = the workflow stops for a person.
```

## What each stage is for

| Stage | Skill | In one line |
|---|---|---|
| `BACKLOG_SYNC` | `backlog-sync` | Pull the Story from GitHub into `docs/stories/` and the catalog. |
| `CLARIFICATION` | `us-clarifier` | Find every place a spec-writer would otherwise guess, and log it as an Open Decision. |
| `SPECIFICATION` | `story-spec-writer` | Turn the clarified Story into the source of truth for everything downstream. |
| `SPEC_REVIEW` | `story-spec-reviewer` | Is the spec complete, testable, and free of invented requirements? |
| `API_DESIGN` | `openapi-designer` | Decide the endpoint shape before any route is written. |
| `DB_DESIGN` | `db-designer` | Decide the persistence shape as SQLAlchemy 2.0 declarative models. |
| `DESIGN_REVIEW` | `design-reviewer` | One pass over both designs together, plus their cross-model consistency. |
| `IMPACT_ANALYSIS` | `impact-analyzer` | Survey the blast radius: affected files, cross-module reach, migration risk. |
| `ARCHITECTURE_PLANNING` | `planner` | **What** changes, which files, which risks, how it gets validated. |
| `IMPLEMENTATION_PLANNING` | `implementation-planner` | **In what order**, and which execution skill runs each task. |
| `PLAN_REVIEW` | `plan-reviewer` | Does the plan actually deliver the spec, within the layering rules? |
| `TEST_WRITING` | `test-writer` | Acceptance criteria become executable tests, before the code exists. |
| `IMPLEMENTATION` | four builder skills | Code generation, in layering order. |
| `QUALITY_GATE` | `gate-enforcer` | Run the real gate and paste the real output. Nothing is asserted unrun. |
| `IMPLEMENTATION_VERIFICATION` | `implementation-verifier` | Independent check that the build satisfies AGENTS.md and the Definition of Done. |
| `SECURITY_REVIEW` | `security-reviewer` | Threat-oriented review of what shipped. |
| `RECONCILIATION` | `reconciliation-reviewer` | Did we build and *prove* the thing the spec asked for? |
| `PR_PREPARATION` | `pr-preparer` | Draft the PR title, description, and test plan. |
| `ARCHIVED` | `story-orchestrator` | Consolidate what was learned into `project-state.md`. |

## The three review layers, and why they are not redundant

They ask different questions, and a change can pass one while failing another:

- **`QUALITY_GATE`** — *did the checks run and pass?* Mechanical. pytest, mypy
  strict, lint-imports, pre-commit, plus the runtime rules
  (`AGENTS.md` §6.6) that no tool can check.
- **`IMPLEMENTATION_VERIFICATION`** — *did we follow the rules?* Technical
  compliance with `AGENTS.md` and the Definition of Done, verified independently
  rather than taken from the implementation's own report.
- **`RECONCILIATION`** — *did we build the right thing, and prove it?* Every
  acceptance criterion has a test that actually asserts the criterion's stated
  behavior, not merely a test that exists.

## Human gates

Five stages stop for a person: `HUMAN_SPEC_APPROVAL`, `HUMAN_PLAN_APPROVAL`,
`HUMAN_PR_APPROVAL`, `READY_FOR_PR`, `COMPLETED`.

**A review skill returning `PASS` is not human approval.** Approval is recorded
only by `/so:approve` (or `/so:reject`). The orchestrator may never infer one
from the other.

Consistent with `AGENTS.md` §1, the harness proposes and a human executes every
shared-state action: skills do not push, open, or merge Pull Requests.

## Commands

| Command | What it does |
|---|---|
| `/so:start <StoryId>` | Activate a Story and initialize its workflow state. |
| `/so:next` | Advance exactly one stage. Never two. |
| `/so:status` | Read-only: where the Story is, what is stale, what is blocking. |
| `/so:approve [comment]` | Record human approval at the current human gate. |
| `/so:reject <reason>` | Record human rejection and route to the gate's loop-back target. |
| `/so:archive` | After `COMPLETED`: write the delivery summary and consolidate knowledge. |

## Loop-backs

A failing stage does not stop the workflow dead — it routes backward to the
stage that can actually fix the problem. Each stage declares its legal targets
under `loop_back` in the stage map, and a skill may only name a key defined
there. An unknown key is rejected and the stage holds as `BLOCKED`.

For example, `RECONCILIATION` can route to `IMPLEMENTATION` (the code drifted),
`TEST_WRITING` (a criterion is under-tested), `ARCHITECTURE_PLANNING`,
`API_DESIGN`, `SPECIFICATION`, or `BACKLOG_SYNC` (the local Story disagrees with
its GitHub source) — depending on where the gap actually originates.
