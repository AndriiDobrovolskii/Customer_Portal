# Pipeline Status: {{StoryId}}

**Active story confirmed:** {{Yes / mismatch flagged — see note}}
**Last updated:** {{YYYY-MM-DD}}

| Stage | Sub-step | Skill | Status | Verdict | Notes |
|---|---|---|---|---|---|
| CLARIFICATION | — | us-clarifier | {{Not Started/In Progress/Done}} | {{Ready for Specification / Not Ready}} | |
| SPECIFICATION | — | story-spec-writer | | | |
| SPEC_REVIEW | — | story-spec-reviewer | | {{Pass/Pass with Issues/Fail}} | |
| DESIGN | API | openapi-designer | | | |
| DESIGN | DB | db-designer | | | |
| PLANNING | Impact analysis | impact-analyzer | | | |
| PLANNING | Plan | planner | | | |
| PLANNING | Task breakdown | implementation-planner | | | |
| PLANNING | Plan review | plan-reviewer | | {{Pass/Pass with Issues/Fail}} | |
| TESTS | — | test-writer | | | |
| IMPLEMENTATION | Schemas | schema-builder | | | |
| IMPLEMENTATION | Data layer | data-layer-builder | | | |
| IMPLEMENTATION | Migration | migration-manager | | | |
| IMPLEMENTATION | Service/Router | service-and-router-builder | | | |
| IMPLEMENTATION | Gate | gate-enforcer | | {{Pass/Fail}} | |
| VERIFICATION | — | implementation-verifier | | {{Pass/Pass with Issues/Fail}} | |
| SECURITY_REVIEW | — | security-reviewer | | {{Pass/Fail}} | |
| RECONCILIATION | — | reconciliation-reviewer | | {{Pass/Pass with Issues/Fail}} | |
| PR | — | pr-preparer | | | |

## Blocking Stage (if any)

{{Name the stage and skill that reported Fail, and the stated reason. Leave blank if the story is progressing or complete.}}
