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
