---
artifact_type: delivery_summary
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-04T15:00:00Z"
updated_at: "2026-09-04T15:30:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/workflow/workflow-state.yaml
    version: null
  - path: docs/catalog/US-4.1-pipeline-status.md
    version: null
supersedes: null
---

# Delivery Summary: Support Tickets (Create) (US-4.1)

## Identity

- **Story ID:** US-4.1 (retired id: US-014)
- **Epic:** EPIC-4 — Feedback / Support
- **Story file:** `docs/stories/US-4.1-create-ticket.md`
- **Source:** local_only (no configured GitHub Issue source)
- **Final catalog state:** ARCHIVED (was IN_PROGRESS)

## Delivery

- **Pull Request:** #16 (`feat: add self-service support ticket creation
  (US-4.1)`), merged into `main` 2026-09-04T07:54:07Z via merge commit
  `de191f3a4f5f7ff34e28bc9089aed6ef96148e51`.
  https://github.com/AndriiDobrovolskii/Customer_Portal/pull/16
- **Final branch:** `feat/us-4.1-create-ticket`, already pushed and merged.
  **Correction (this run, superseding an earlier error in this same archive
  pass):** the first version of this section incorrectly stated the branch
  was unmerged and no PR existed. That was checked against the local `main`
  ref without first running `git fetch origin` — `origin/main` already
  contained PR #16, merged hours before this archive session started. The
  `COMPLETED` gate's 2026-09-04T14:00:00Z approval "confirming the Pull
  Request has been merged" was correct; my initial archive-run finding was
  not. See `docs/workflow/history.jsonl` for both the original (incorrect)
  and corrected entries.
- **Activation timestamp:** 2026-09-03T00:00:00Z.
- **Completion timestamp:** 2026-09-04T13:00:00Z (`workflow-state.yaml`,
  stage reached `COMPLETED`).
- **Archive timestamp:** 2026-09-04T15:00:00Z (this run).

## Artifact Inventory

| Type | Path | Version | Status |
|---|---|---|---|
| story | docs/stories/US-4.1-create-ticket.md | — | (input, no status field) |
| story_catalog | docs/catalog/stories.yaml | — | ARCHIVED (this run) |
| clarification_report | docs/evidence/US-4.1-clarification-report.md | 1 | ARCHIVED |
| open_decisions | docs/decisions/US-4.1-open-decisions.md | 1 | ARCHIVED (OD-3 remains unresolved, carried below) |
| specification | docs/specifications/US-4.1-spec.md | 1 | ARCHIVED |
| specification_review | docs/reviews/specifications/US-4.1-spec-review.md | 1 | ARCHIVED |
| api_design | docs/designs/api/US-4.1-api-design.md | 3 | ARCHIVED |
| openapi | docs/designs/api/US-4.1-openapi.yaml | 3 | ARCHIVED (no front matter; version tracked via api_design) |
| database_design | docs/designs/database/US-4.1-db-design.md | 3 | ARCHIVED |
| entity_model | docs/designs/database/US-4.1-entity-model.md | 3 | ARCHIVED |
| design_review | docs/reviews/designs/US-4.1-design-review.md | 3 | ARCHIVED |
| impact_analysis | docs/impact-analysis/US-4.1-impact-analysis.md | 1 | ARCHIVED |
| implementation_plan | docs/plans/US-4.1-implementation-plan.md | 1 | ARCHIVED |
| task_breakdown | docs/plans/US-4.1-task-breakdown.md | 1 | ARCHIVED |
| plan_review | docs/reviews/plans/US-4.1-plan-review.md | 1 | ARCHIVED |
| test_strategy | docs/tests/US-4.1-test-strategy.md | 5 | ARCHIVED |
| ac_test_matrix | docs/tests/US-4.1-ac-test-matrix.md | 5 | ARCHIVED |
| test_generation_report | docs/evidence/US-4.1-test-generation-report.md | 5 | ARCHIVED |
| implementation_report | docs/evidence/US-4.1-implementation-report.md | 5 | ARCHIVED |
| quality_gate_report | docs/evidence/US-4.1-quality-gate-report.md | 5 | ARCHIVED |
| implementation_verification | docs/verification/US-4.1-implementation-verification.md | 3 | ARCHIVED |
| security_review | docs/reviews/security/US-4.1-security-review.md | 2 | ARCHIVED |
| reconciliation | docs/reviews/reconciliation/US-4.1-reconciliation.md | 2 | ARCHIVED |
| traceability | docs/reconciliation/US-4.1-traceability.md | 2 | ARCHIVED |
| pr_summary | docs/pr/US-4.1-pr-summary.md | 1 | ARCHIVED |
| pipeline_status | docs/catalog/US-4.1-pipeline-status.md | — | historical, cross-story artifact — preserved in place |

**Status backfill note:** all artifacts above except `design_review` were still
`status: DRAFT` in front matter when this archive run started, despite each
one's owning skill having already recorded a `PASS` verdict (and, where a
human gate consumed it, an explicit `/so:approve`) in `workflow-state.yaml`.
No skill in this story's execution ever wrote `status: APPROVED`. This run
backfilled each straight to `ARCHIVED`, reflecting the already-recorded
verdict/approval rather than re-deriving one — no new review judgment was
made. Flagged as a gap worth fixing at the source (the owning skills should
set `status: APPROVED` themselves on a `PASS` verdict) so future stories don't
require this same backfill at archive time.

## Final Acceptance-Criteria Result

7/7 ACs traced (`traceability` v2 above), reconciliation-reviewer verdict PASS.
ST-AC1, ST-AC2, ST-AC4, ST-AC5, ST-AC6 and ST-AC7 (all 7 sub-clauses, closed by
TEST_WRITING attempt 5's purge-script tests) are fully covered. ST-AC3's
"unknown category" sub-case remains untestable, explicitly excluded from the
PASS verdict as blocked on OD-3 (a stakeholder decision on the category enum,
not a pipeline-fixable gap).

## Final Verdicts

| Stage | Verdict |
|---|---|
| IMPLEMENTATION_VERIFICATION (v3) | PASS |
| SECURITY_REVIEW (v2) | PASS (1 Low, non-blocking advisory) |
| RECONCILIATION (v2) | PASS |
| QUALITY_GATE (v5) | PASS — 603/603 tests, 96.18% coverage, migration cycle proven |

## Known Limitations / Deferred Work (all disclosed, none blocking)

- **OD-3 (category enum)** — `tickets.category` has no DB-level `CHECK`/`ENUM`
  constraint pending a stakeholder decision on allowed values. Blocks ST-AC3's
  unknown-category sub-case.
- **BR-007 FK `ondelete` mechanics** — `tickets.requester_id` /
  `attachments.uploaded_by` default to `RESTRICT` pending the pre-existing
  account-erasure job's mechanics (legal/DPO sign-off pending, open since
  before this story).
- **Idempotency poll-exhaustion path** — the concurrent-replay bounded poll's
  exhaustion path returns an undocumented `500` (no contract slug); confirmed
  as designed implementation behavior, not a gap.
- **[Low, Spec Drift] `ticket_number` guessability** — sequentially guessable
  (`CP-{year}-{seq:07d}`), in tension with FR-1's own non-guessability clause.
  Traces to an approved, `DESIGN_REVIEW`-passed design decision (v3), not
  undisclosed drift. Not currently exploitable — no endpoint looks up by
  `ticket_number`. Worth a product decision before a future story adds one.
- **Audit destination wording** — FR-1's spec text says "`ticket_audit_log`";
  shipped code correctly writes to the existing `audit_log` table
  (`category="tickets"`) per `DESIGN_REVIEW`'s DR-1 fix. Spec-text-only gap.
- Commit-hygiene concern flagged by `pr-preparer` (unrelated US-3.3 evidence
  files, `.claude/settings.json.graphify-bak`, `graphify-out/`, an unrelated
  `.gitignore` edit) is **resolved** — the working tree is clean as of this
  archive run; those items were committed separately (`b435a69`, `9f86883`).

## Proposed Knowledge Updates (NOT applied — pending human review)

### `docs/product/business-rules.md`

`BR-016` (attachment ownership / IDOR prevention) already exists and
accurately reflects what shipped — no change needed there. Three candidate
new entries for behavior this story shipped but that isn't yet captured as a
business rule:

1. **Ticket-creation idempotency** — a `POST /v1/support/tickets` request
   carrying a previously-used `Idempotency-Key` returns the original ticket if
   the request body matches, or a conflict error if it doesn't; a concurrent
   in-flight request with the same key waits (bounded poll) rather than
   creating a duplicate.
2. **Ticket-creation rate limit** — a customer may create at most 5 tickets
   per hour; further attempts within the window return `429` with
   `Retry-After` (failed/rejected attempts still consume the budget).
3. **Account-deactivated ticket-creation gate** — a deactivated account cannot
   create a ticket (`403`), checked before any idempotency claim or write
   (mirrors the login-time deactivation gate; no auto-reactivation grace
   period, unlike login's OD-10 path, since ticket creation has no such
   precedent).

### `docs/ARCHITECTURE.md`

No change proposed. §3.7 ("Exactly one commit per business operation") already
covers the pattern this story used (`AuditLogService.record_event` not
self-committing so `TicketService.create_ticket` owns the single commit) —
this is an instance of the existing rule, not a new one.

## History Reference

`docs/workflow/history.jsonl` — see the `US-4.1` events, including this run's
final `ARCHIVED` event.

## Recommendation

`docs/catalog/stories.yaml` shows `US-4.2` (Ticket Replies) and `US-4.3`
(Ticket Resolution) as the remaining `BACKLOG` stories in EPIC-4, each
depending on the previous. `/so:start US-4.2` is the unambiguous next
candidate — not run here, per this skill's recommendation-only mandate. Note
`US-4.2`'s own catalog entry already flags its draft specification as
predating the current codebase, same as US-4.1's did.
