# PR Draft: {{Story Title}} ({{StoryId}})

**Gates confirmed:** gate-enforcer {{Pass}} · implementation-verifier {{Pass}} · reconciliation-reviewer {{Pass}} · security-reviewer {{Pass}}

## Title

{{feat|fix|refactor}}: {{short, specific summary, under ~70 chars}}

## Summary

- {{what changed, 1-3 bullets}}
- {{why — link to docs/stories/<StoryId>.md and docs/specifications/<StoryId>-spec.md}}

## Test Plan

- [ ] Unit tests: {{summary, e.g. "12 new cases in test_<module>_service.py"}}
- [ ] Integration tests: {{summary, e.g. "4 new cases in test_<module>_router.py, real Postgres/Valkey"}}
- [ ] Coverage: {{result from gate-enforcer's report}}
- [ ] Migration cycle: {{upgrade/downgrade/upgrade result, if applicable}}
- [ ] Security review: {{docs/reviews/security/<StoryId>-security-review.md verdict}}
- [ ] AC reconciliation: {{docs/reviews/reconciliation/<StoryId>-reconciliation.md verdict}}

## Risk / Rollback

{{From planner's Risks section — delete if none apply.}}

## Config Changes

{{.env.example diff summary, or "None" if no settings changed.}}

## Scope Note

{{Confirmation that no unrelated files/refactors are included, or a flagged concern if one was found.}}

---
**This is drafted content only.** Pushing the branch or opening the PR requires an explicit separate instruction (`git push`, `gh pr create`).
