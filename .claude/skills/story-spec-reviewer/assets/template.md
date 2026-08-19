# Spec Review: {{Story Title}}

**Original Story:** {{path/to/US-xxx.md}}
**Spec Reviewed:** {{path/to/US-xxx-spec.md}}
**Story ID:** {{STORY-ID, or "N/A" if the source has none}}
**Reviewed:** {{YYYY-MM-DD}}
**Overall Verdict:** {{Pass | Pass with Issues | Fail}}

## Summary

{{2-4 sentences: what was reviewed, the verdict, and the single biggest reason for it (if not Pass). Do not restate the whole findings list here — that's what the sections below are for.}}

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AC-1  | "{{exact quoted text from story}}" | {{Covered / Partially Covered / Missing}} | {{FR-x, or "—" if Missing}} | {{brief note if Partially Covered or Missing}} |

<!-- One row per AC in the original story, no exceptions — every AC must appear here exactly once, even if Missing. Quoted text must be verbatim, not paraphrased. -->

## Ambiguities & Non-Verifiable Statements

{{Delete this section only if none were found.}}

- **[{{Low/Medium/High}}] {{short label}}** — Spec says: "{{exact quote}}" ({{spec section}}). {{Why this can't be verified or acted on as written — what question a developer would have to ask.}}

## Contradictions With Original Story

{{Delete this section only if none were found. Any entry here forces the verdict to Fail.}}

- **[{{Medium/High}}] {{short label}}** — Story says: "{{exact quote}}" ({{story location}}). Spec says: "{{exact quote}}" ({{spec section}}). {{Why these conflict.}}

## Scope Creep

{{Delete this section only if none were found. Content here is not traceable to any AC or business context in the original story.}}

- **[{{Low/Medium/High}}] {{short label}}** — Spec says: "{{exact quote}}" ({{spec section}}). {{What story content, if any, this was supposed to derive from, and why it goes beyond it — or state plainly that no such content exists in the story.}}

## Missing Edge Cases, Boundary Conditions & Error Handling

{{Delete this section only if none were found.}}

- **[{{Low/Medium/High}}] {{short label}}** — {{The scenario the spec doesn't address (e.g. empty input, max threshold, permission denial, concurrent access, failure/timeout).}} {{Why the story's scope implies this should be addressed — cite the AC or context it derives from. If genuinely uncertain whether it's in scope, phrase as a question instead of an assertion.}}

## Verdict Rationale

{{1-3 sentences explicitly connecting the findings above to the Overall Verdict at the top. E.g. "Fail: AC-3 is Missing and one Contradiction was found (see above); both block implementation." A Pass with no findings sections above may simply state that no blocking issues were found.}}

<!--
Verdict rules:
- Fail: any AC is Missing or Partially Covered, OR any Contradiction was found.
- Pass with Issues: full AC coverage, no contradictions, but Ambiguities / Scope Creep / Missing Edge Cases were found.
- Pass: full AC coverage, no contradictions, and only trivial or no other findings.
-->
