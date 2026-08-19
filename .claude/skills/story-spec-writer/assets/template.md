# Specification: {{Story Title}}

**Source:** {{path/to/source-file}}
**Story ID:** {{STORY-ID, or "N/A" if the source has none}}
**Generated:** {{YYYY-MM-DD}}
**Status:** Draft

## Summary

{{1-3 sentences describing what this spec covers. Paraphrase only — do not add scope the source didn't state.}}

## Background

{{Narrative / context copied or lightly paraphrased from the source story. Omit this whole section if the source has no background or "as a user..." narrative — don't manufacture one.}}

## Functional Requirements

### FR-1: {{short descriptive title}}

{{The requirement, restated clearly from the source. Every sentence here must trace back to something the source actually said.}}

**Derived from:** AC-1

### FR-2: {{short descriptive title}}

{{...}}

**Derived from:** AC-2, AC-3

<!-- Add one FR block per distinct requirement. A single AC can spawn multiple FRs if it bundles multiple behaviors; a single FR can cite multiple ACs if they jointly describe one requirement. Every FR must cite at least one AC ID. -->

## Non-Functional Requirements

{{Only include this section if the source explicitly states non-functional requirements (performance, security, accessibility, etc.). Delete the section entirely if none were given — do not invent typical NFRs.}}

## Out of Scope

{{Only include if the source explicitly says something is out of scope. Delete otherwise.}}

## Open Questions

{{List anything ambiguous, missing, contradictory, or under-specified in the source that a reader would need to resolve before implementation. This is where gaps go instead of invented requirements. Delete this section only if there truly are none.}}

- {{Open question, phrased so a reviewer can answer it directly}}

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AC-1  | "{{exact quoted text}}" | FR-1 |
| AC-2  | "{{exact quoted text}}" | FR-2 |
| AC-3  | "{{exact quoted text}}" | FR-2 |

<!-- Every row's AC text must be an exact quote from the source, not a paraphrase. Every AC from the source must appear in this table exactly once, even if its "Covered by" cell points to an Open Question because nothing in the spec addresses it yet. -->
