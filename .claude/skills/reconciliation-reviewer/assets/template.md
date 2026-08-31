# Reconciliation Report: {{Story Title}}

**Story ID:** {{STORY-ID}}
**Reviewed:** {{YYYY-MM-DD}}
**Overall Verdict:** {{Pass | Pass with Issues | Fail}}

## Summary

{{2-4 sentences: what was reconciled, the verdict, and the single biggest reason for it (if not Pass).}}

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| AC-1 | "{{exact quoted text from spec}}" | {{Yes/No}} | {{test file::function}} | {{Yes/No}} | {{Yes/Partial/No}} | {{note if Partial or No}} |

<!-- One row per AC in the spec, no exceptions — every AC must appear here exactly once, even if no matrix row exists. -->

## Spec Drift

{{Delete this section only if none were found.}}

- **[{{Low/Medium/High}}] {{short label}}** — Spec/API design says: "{{exact quote}}". Shipped code does: "{{what actually happens, cited file:line}}". {{Why this is a divergence, not a reasonable implementation detail.}}

## Verdict Rationale

{{1-3 sentences explicitly connecting the findings above to the Overall Verdict at the top.}}

<!--
Verdict rules:
- Fail: any AC has no matrix row, a missing test function, a non-asserting test, or confirmed spec drift.
- Pass with Issues: full coverage and no drift, but a test's assertion could be tighter than it is.
- Pass: every AC fully covered, every test asserts the actual AC behavior, no drift found.
-->
