# Plan Review: {{Story Title}}

**Story ID:** {{STORY-ID}}
**Plan Reviewed:** {{docs/plans/<StoryId>-implementation-plan.md}}
**Task Breakdown Reviewed:** {{docs/plans/<StoryId>-task-breakdown.md}}
**Reviewed:** {{YYYY-MM-DD}}
**Overall Verdict:** {{Pass | Pass with Issues | Fail}}

## Summary

{{2-4 sentences: what was reviewed, the verdict, and the single biggest reason for it (if not Pass).}}

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| {{affected file/module from impact-analysis}} | {{Covered / Partially Covered / Missing}} | {{plan section, or "—" if Missing}} | {{note if Partially Covered or Missing}} |

<!-- One row per item in impact-analysis.md, no exceptions. -->

## Layering Order (Task Breakdown)

{{Delete this section only if the task breakdown has no ordering issue.}}

- **[{{Medium/High}}] {{short label}}** — Task {{T-id}} ({{skill}}) depends on {{T-id}}, but is sequenced before it / touches a layer AGENTS.md §3 says should come later. {{Why this breaks the downward-only direction or the migration-before-model-use rule.}}

## Risk Realism

{{Delete this section only if the plan's Risks section adequately covers migration/concurrency/contract-breaking hazards implied by the impact analysis or DB design.}}

- **[{{Low/Medium/High}}] {{short label}}** — Plan says: "{{exact quote from Risks section}}". {{What specific hazard from AGENTS.md §4 or the DB design this doesn't address.}}

## Test-Strategy Realism

{{Delete this section only if the plan's Testing Strategy concretely names unit-vs-integration split per AGENTS.md §5.}}

- **[{{Low/Medium/High}}] {{short label}}** — Plan says: "{{exact quote}}". {{Why this is too vague to act on, or what AGENTS.md §5 split it fails to address.}}

## Scope Creep

{{Delete this section only if none were found.}}

- **[{{Low/Medium/High}}] {{short label}}** — Plan/task-breakdown item: "{{exact quote}}". {{What impact-analysis or spec content this fails to trace back to.}}

## Verdict Rationale

{{1-3 sentences explicitly connecting the findings above to the Overall Verdict at the top.}}

<!--
Verdict rules:
- Fail: any impact-analysis item is Missing/Partially Covered from the plan, OR any layering-order violation was found in the task breakdown.
- Pass with Issues: full impact-analysis coverage, correct layering order, but risk/test-strategy gaps or minor scope creep were found.
- Pass: full coverage, correct ordering, realistic risk/test strategy, no scope creep.
-->
