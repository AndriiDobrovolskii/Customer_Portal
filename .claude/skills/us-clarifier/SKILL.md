---
name: us-clarifier
description: Analyzes a user story from docs/stories/ before spec-writing begins, surfacing ambiguities, missing acceptance criteria, and undecided business/security/validation rules as an Open Decisions log — without inventing answers to them. Use this whenever a story needs to be checked for readiness ("is this story ready for a spec?", "clarify this story," "what's ambiguous about US-xxx?") before handing it to story-spec-writer. This is the upstream gate story-spec-writer assumes has already run — it does not draft a specification itself, and it does not resolve ambiguities by guessing; every open question becomes a recorded Open Decision the user (or a stakeholder) must answer. Trigger this for requests about story readiness, pre-spec clarification, or open-decision logs; not for writing or reviewing a spec (that's story-spec-writer / story-spec-reviewer).
---

# US Clarifier

## Purpose & Role

This skill sits between "a story exists in `docs/stories/`" and "a specification gets written." Its job is to read the story critically — against the product's own established vocabulary and rules, not in isolation — and flag every place where a spec-writer would otherwise have to guess. Guessing at this stage is expensive: an invented validation rule or an assumed authorization boundary that makes it into a spec becomes implementation, and implementation becomes a regression to unwind later.

The skill never fills a gap itself. Its output is a decision log, not a decision.

## Operational Contract

```
Precondition: The target story exists under docs/stories/ and (if the user didn't name one explicitly) matches docs/workflow/active-story.yaml.
Input Artifacts: docs/product/product-vision.md, docs/product/personas.md, docs/product/business-rules.md, docs/product/business-glossary.md, docs/stories/<StoryId>.md, docs/workflow/active-story.yaml, docs/decisions/<StoryId>-open-decisions.md (if it already exists).
Output Artifacts: docs/decisions/<StoryId>-open-decisions.md, docs/evidence/<StoryId>-clarification-report.md.
```

## Required Context

Read, in this order:

1. `docs/product/product-vision.md` and `docs/product/personas.md` — what the product is for and who uses it.
2. `docs/product/business-rules.md` and `docs/product/business-glossary.md` — established rules and vocabulary the story must stay consistent with.
3. The target story in `docs/stories/` (e.g. `docs/stories/US-2.5-mfa-totp.md`).
4. `docs/workflow/active-story.yaml` — confirm the story being clarified is the one currently in scope, or note the mismatch if the user asked for a different one.
5. Any existing `docs/decisions/<StoryId>-open-decisions.md` — this run either confirms those decisions were resolved or supersedes them; it should never silently drop a still-open item.

## Responsibilities

Analyze the story for:

- **Business intent** — actor, trigger, and business value: is it stated, or inferred by the reader?
- **Acceptance criteria** — are they complete, testable, and free of "the system should handle this appropriately"-style non-verifiable language?
- **Security expectations** — authentication/authorization boundaries the story implies but doesn't state.
- **Validation expectations** — field constraints, uniqueness, allowed values the story leaves to the reader's judgment.
- **Dependencies** — other stories, permission scopes, or data this story assumes already exist (cross-check `docs/stories/README.md`'s dependency notes).
- **Assumptions** — anything a spec-writer would have to silently decide to move forward.

## Open Decision Detection

When something cannot be reliably inferred from `docs/product/*` or the story itself:

**Do not invent an answer.** Record an Open Decision instead. Typical triggers: uniqueness rules not stated, password/token policy left implicit, authorization scope unclear, duplicate/conflict handling unspecified, error-response shape unstated, an edge case the acceptance criteria don't cover.

Each Open Decision states: the question, why it can't be inferred (what was checked and came up empty), and the concrete impact of leaving it unresolved (what a spec-writer would otherwise have to guess).

## Outputs

Create both:

- `docs/decisions/<StoryId>-open-decisions.md` — one entry per unresolved question, in the format above.
- `docs/evidence/<StoryId>-clarification-report.md` — a short readiness summary: what's clear, what's ambiguous, and an explicit **Ready for Specification** / **Not Ready — see Open Decisions** verdict.

If a story has zero open decisions, still write both files — an empty Open Decisions log with "none found" is itself evidence the story was checked, not skipped.

## Completion Criteria

Complete only when:

- The story's scope, actors, and business value are understood and restated in the clarification report.
- Every ambiguity found is either resolved by a cited source (`business-rules.md`, `business-glossary.md`, a dependency story) or logged as an Open Decision — never silently dropped.
- The clarification report states an explicit readiness verdict.

Do not write a specification. That is `story-spec-writer`'s job, and it should only be invoked once this skill's verdict is **Ready for Specification** or the user explicitly accepts the open risk.

---

# Harness Contract

This skill owns the `CLARIFICATION` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`CLARIFICATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`

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
  verdict: PASS | BLOCKED
  stage: CLARIFICATION
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/evidence/<StoryId>-clarification-report.md
    - docs/decisions/<StoryId>-open-decisions.md
  next_stage: SPECIFICATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

- `PASS` - scope is understood; every ambiguity is either resolved by a cited
  source or recorded as an Open Decision; both artifacts exist. Open Decisions
  may still be `OPEN`: they are resolved at `HUMAN_SPEC_APPROVAL`, not here.
- `BLOCKED` - the story is missing or unintelligible, or `active-story.yaml`
  and `workflow-state.yaml` disagree on which story is active.

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
