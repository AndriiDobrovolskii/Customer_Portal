# Pipeline Status: {{StoryId}}

**Active story confirmed:** {{Yes / mismatch flagged — see note}}
**Last updated:** {{YYYY-MM-DD}}

Stages and their order come from `docs/workflow/stage-map.yaml`; this table
mirrors it. Verdicts are the four in `docs/workflow/artifact-lifecycle.md` §2 —
`PASS`, `CHANGES_REQUIRED`, `BLOCKED`, `NOT_APPLICABLE`. Human gates are decided
by `/so:approve` or `/so:reject`, never by a skill.

| Stage | Sub-step | Skill | Status | Verdict | Notes |
|---|---|---|---|---|---|
| BACKLOG_SYNC | — | backlog-sync | {{Not Started/In Progress/Done}} | | run only on activation, explicit sync, or a story_source_conflict loop-back |
| CLARIFICATION | — | us-clarifier | | | |
| SPECIFICATION | — | story-spec-writer | | | |
| SPEC_REVIEW | — | story-spec-reviewer | | | |
| HUMAN_SPEC_APPROVAL | — | *human gate* | | {{APPROVED/REJECTED/PENDING}} | recorded by /so:approve |
| API_DESIGN | — | openapi-designer | | | optional: NOT_APPLICABLE if no public API change |
| DB_DESIGN | — | db-designer | | | optional: NOT_APPLICABLE if no persistence change |
| DESIGN_REVIEW | — | design-reviewer | | | optional: NOT_APPLICABLE only if both designs were |
| IMPACT_ANALYSIS | — | impact-analyzer | | | |
| ARCHITECTURE_PLANNING | — | planner | | | what changes |
| IMPLEMENTATION_PLANNING | — | implementation-planner | | | in what order |
| PLAN_REVIEW | — | plan-reviewer | | | |
| HUMAN_PLAN_APPROVAL | — | *human gate* | | {{APPROVED/REJECTED/PENDING}} | recorded by /so:approve |
| TEST_WRITING | — | test-writer | | | |
| IMPLEMENTATION | Schemas | schema-builder | | | |
| IMPLEMENTATION | Data layer | data-layer-builder | | | |
| IMPLEMENTATION | Migration | migration-manager | | | upgrade → downgrade → upgrade proven |
| IMPLEMENTATION | Service/Router | service-and-router-builder | | | |
| QUALITY_GATE | — | gate-enforcer | | | real captured output, never an asserted pass |
| IMPLEMENTATION_VERIFICATION | — | implementation-verifier | | | |
| SECURITY_REVIEW | — | security-reviewer | | | |
| RECONCILIATION | — | reconciliation-reviewer | | | |
| HUMAN_PR_APPROVAL | — | *human gate* | | {{APPROVED/REJECTED/PENDING}} | recorded by /so:approve |
| PR_PREPARATION | — | pr-preparer | | | drafts only; a human opens the PR |
| READY_FOR_PR | — | *human gate* | | {{APPROVED/PENDING}} | |
| COMPLETED | — | *human gate* | | {{APPROVED/PENDING}} | human confirms the PR merged |
| ARCHIVED | — | story-orchestrator | | | archive mode only, explicitly invoked |

## Blocking Stage (if any)

{{Name the stage and skill that returned CHANGES_REQUIRED or BLOCKED, the
loop-back key it chose, and the stated reason. Leave blank if the story is
progressing or complete.}}

## Carried Non-Blocking Findings

{{Advisory findings a stage passed forward. Each must be repeated by the next
stage that consumes that review, not quietly dropped.}}
