# Verification Report: {{Story Title}}

**Story ID:** {{STORY-ID}}
**gate-enforcer Result Relied On:** {{Pass / Local gate green, CI-only pending — list which}}
**Reviewed:** {{YYYY-MM-DD}}
**Overall Verdict:** {{Pass | Pass with Issues | Fail}}

## Summary

{{2-4 sentences: what was verified, the verdict, and the single biggest reason for it (if not Pass).}}

## §6.5 — Migration Human Half

- Generated file read: {{Yes/No}} — evidence: {{migration-manager report reference}}
- Rewriter-unreachable statements guarded: {{Pass/Fail}} — evidence: {{file:line}}
- `downgrade()` real, not `pass`: {{Pass/Fail}} — evidence: {{file:line}}

## §6.6 — Runtime Rules

| Rule | Result | Evidence |
|---|---|---|
| ORM never crosses service→router | {{Pass/Fail}} | {{file:line}} |
| All nested data eager-loaded | {{Pass/Fail/N/A}} | {{file:line}} |
| Every cache write has a TTL | {{Pass/Fail/N/A — no cache writes}} | {{file:line}} |
| Cross-module calls go service→service | {{Pass/Fail}} | {{file:line}} |

## §6.7 — Contract & Security

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` on every route | {{Pass/Fail}} | {{file:line}} |
| `extra="forbid"` + privilege exclusion on inbound schemas | {{Pass/Fail}} | {{file:line}} |
| `.env.example` updated (if applicable) | {{Pass/Fail/N/A}} | {{file:line}} |
| No sensitive field in any `*Read` | {{Pass/Fail}} | {{file:line}} |

## §5 — Security Test Cases (per protected route)

| Route | No Token | Expired | Malformed | Insufficient Perms | Revoked |
|---|---|---|---|---|---|
| {{route}} | {{test name}} | {{test name}} | {{test name}} | {{test name}} | {{test name}} |

## Verdict Rationale

{{1-3 sentences explicitly connecting the findings above to the Overall Verdict at the top.}}

<!--
Verdict rules:
- Fail: any ORM leak, missing eager-load, TTL-less cache write, service→router cross-module call, or missing response_model/status_code.
- Pass with Issues: a minor doc-level gap only (e.g. non-security .env.example lag).
- Pass: every item above is Pass or explicit N/A.
-->
