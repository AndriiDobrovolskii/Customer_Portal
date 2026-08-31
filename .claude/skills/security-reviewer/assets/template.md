# Security Review: {{Story Title}}

**Story ID:** {{STORY-ID}}
**Reviewed:** {{YYYY-MM-DD}}
**Overall Verdict:** {{Pass | Fail}}

## Summary

{{2-4 sentences: what was reviewed, the verdict, and the specific §7 rule violated if Fail.}}

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | {{Pass/Fail}} | {{file:line}} |
| No plaintext/reversible encryption for credentials | {{Pass/Fail}} | {{file:line}} |
| No tokens/hashes/PII in logs; no `print()` | {{Pass/Fail}} | {{file:line}} |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | {{Pass/Fail}} | {{file:line}} |
| Parameterized SQL only, no string interpolation | {{Pass/Fail}} | {{file:line}} |
| Uniform auth-failure response, no differentiation leaked | {{Pass/Fail}} | {{file:line}} |

## Advisory Findings (non-§7, does not force Fail)

{{Delete this section only if none were found.}}

- **[{{Low/Medium/High}}] {{short label}}** — {{finding, cited evidence}}. {{Why this is worth addressing even though it isn't a §7 non-negotiable.}}

## Verdict Rationale

{{1-2 sentences. Any single Fail row above forces the Overall Verdict to Fail — name which one.}}

<!--
Verdict rules:
- Fail: any one of the six §7 checklist rows is Fail. No "Pass with Issues" exists for this skill.
- Pass: all six rows Pass. Advisory findings, if any, don't change this.
-->
