---
artifact_type: delivery_summary
story: US-4.2
version: 1
status: ARCHIVED
created_at: "2026-09-06T05:00:00Z"
updated_at: "2026-09-06T05:00:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/workflow/workflow-state.yaml
    version: null
  - path: docs/catalog/US-4.2-pipeline-status.md
    version: null
supersedes: null
---

# Delivery Summary: Ticket Replies (US-4.2)

## Identity

- **Story ID:** US-4.2 (retired id: US-015)
- **Epic:** EPIC-4 — Feedback / Support
- **Story file:** `docs/stories/US-4.2-ticket-replies.md`
- **Source:** local_only (no configured GitHub Issue source)
- **Final catalog state:** ARCHIVED (was IN_PROGRESS)

## Delivery

- **Pull Request:** #17 (`feat: ticket replies with RLS-enforced internal
  visibility (US-4.2)`), merged into `main` 2026-09-05T00:16:27Z via merge
  commit `44587b795ae090335bdf3984f15e891b7eeecf91`.
  https://github.com/AndriiDobrovolskii/Customer_Portal/pull/17
  Independently re-verified this run: `git fetch origin` +
  `git merge-base --is-ancestor 34a0e7d origin/main` (true) +
  `gh pr view 17 --json state,mergedAt,baseRefName,headRefName,mergeCommit`
  (`state=MERGED`, `base=main`, `head=feat/us-4.2-ticket-replies`, merge
  commit matches `origin/main`'s tip) — not taken on the prior approval's word
  alone.
- **Final branch:** `feat/us-4.2-ticket-replies`, pushed and merged.
- **Activation timestamp:** 2026-09-04T16:00:00Z (`active-story.yaml`).
- **Completion timestamp:** 2026-09-06T02:30:00Z (`workflow-state.yaml`
  `completed_at`, stage first reached `COMPLETED`). The gate's approval was
  retracted at 03:30 (unverified merge claim) and re-approved, independently
  verified, at 04:00 — see History Reference.
- **Archive timestamp:** 2026-09-06T05:00:00Z (`workflow-state.yaml`
  `archived_at`, this run's consolidation completing — distinct from the
  04:00 mechanical `COMPLETED`→`ARCHIVED` stage transition).

## Artifact Inventory

| Type | Path | Version | Status |
|---|---|---|---|
| story | docs/stories/US-4.2-ticket-replies.md | — | (input, no status field) |
| story_catalog | docs/catalog/stories.yaml | — | ARCHIVED (this run) |
| clarification_report | docs/evidence/US-4.2-clarification-report.md | 3 | ARCHIVED |
| open_decisions | docs/decisions/US-4.2-open-decisions.md | 3 | ARCHIVED (all 8 ODs resolved) |
| specification | docs/specifications/US-4.2-spec.md | 6 | ARCHIVED |
| specification_review | docs/reviews/specifications/US-4.2-spec-review.md | 6 | ARCHIVED |
| api_design | docs/designs/api/US-4.2-api-design.md | 3 | ARCHIVED |
| openapi | docs/designs/api/US-4.2-openapi.yaml | 3 | ARCHIVED (no front matter; version tracked via api_design) |
| database_design | docs/designs/database/US-4.2-db-design.md | 3 | ARCHIVED |
| entity_model | docs/designs/database/US-4.2-entity-model.md | 3 | ARCHIVED |
| design_review | docs/reviews/designs/US-4.2-design-review.md | 3 | ARCHIVED |
| impact_analysis | docs/impact-analysis/US-4.2-impact-analysis.md | 2 | ARCHIVED |
| implementation_plan | docs/plans/US-4.2-implementation-plan.md | 2 | ARCHIVED |
| task_breakdown | docs/plans/US-4.2-task-breakdown.md | 2 | ARCHIVED |
| plan_review | docs/reviews/plans/US-4.2-plan-review.md | 2 | ARCHIVED |
| test_strategy | docs/tests/US-4.2-test-strategy.md | 3 | ARCHIVED |
| ac_test_matrix | docs/tests/US-4.2-ac-test-matrix.md | 3 | ARCHIVED |
| test_generation_report | docs/evidence/US-4.2-test-generation-report.md | 3 | ARCHIVED |
| implementation_report | docs/evidence/US-4.2-implementation-report.md | 1 | ARCHIVED |
| quality_gate_report | docs/evidence/US-4.2-quality-gate-report.md | 1 | ARCHIVED |
| implementation_verification | docs/verification/US-4.2-implementation-verification.md | 1 | ARCHIVED |
| security_review | docs/reviews/security/US-4.2-security-review.md | 1 | ARCHIVED |
| reconciliation | docs/reviews/reconciliation/US-4.2-reconciliation.md | 1 | ARCHIVED |
| traceability | docs/reconciliation/US-4.2-traceability.md | 1 | ARCHIVED |
| pr_summary | docs/pr/US-4.2-pr-summary.md | 1 | ARCHIVED |
| pipeline_status | docs/catalog/US-4.2-pipeline-status.md | 6 | historical, cross-story artifact — preserved in place |

**Status backfill note:** 22 of the artifacts above (every row with a version
number except `pipeline_status`) were still `status: DRAFT` in front matter
when this archive run started, despite each one's owning skill having already
recorded a `PASS` verdict (and, where a human gate consumed it, an explicit
`/so:approve`) in `docs/workflow/workflow-state.yaml` and
`docs/workflow/history.jsonl`. No skill in this story's execution wrote
`status: APPROVED` — the same gap `[[US-4.1-delivery-summary]]` already
flagged as worth fixing at the source. This run backfilled all 22 straight to
`ARCHIVED`, reflecting the already-recorded verdict/approval rather than
re-deriving one — no new review judgment was made. (`story` and
`story_catalog` carry no front-matter status field; `delivery_summary` was
created `ARCHIVED` directly by this run, never `DRAFT`; `pipeline_status`
stays `DRAFT`, preserved in place as a historical cross-story artifact.)

## Final Acceptance-Criteria Result

7/7 ACs (TR-AC1–TR-AC7) traced (`traceability` v1 above), reconciliation-reviewer
verdict PASS. Every AC has a matrix row, a named test confirmed to exist at its
stated path, and that test's assertions confirmed to check the AC's actual
stated behavior. Two documented, non-blocking coverage gaps (not reconciliation
defects): API_DESIGN Open Question #2's exact "agent-shaped but missing
`tickets:write`" combination is unit-tested only, not reachable via real HTTP
under the shipped role seed; migration reversibility is `migration-manager`'s
domain, tracked separately.

## Final Verdicts

| Stage | Verdict |
|---|---|
| QUALITY_GATE | PASS — 688/688 tests, 96.30% coverage, migration `upgrade→downgrade→upgrade` re-proven |
| IMPLEMENTATION_VERIFICATION | PASS |
| SECURITY_REVIEW | PASS (2 Low, non-blocking advisories) |
| RECONCILIATION | PASS |

## Known Limitations / Deferred Work (all disclosed, none blocking)

- **API_DESIGN OQ-2** — the exact "agent-shaped request but missing
  `tickets:write`" scope combination is unit-tested only; not reachable via
  real HTTP under the shipped role seed.
- **Migration reversibility scope** — `migration-manager`'s domain, tracked
  separately from this story's own AC coverage.
- **New non-superuser `app_runtime` DB role is now load-bearing for RLS.**
  `scripts/db/provision_runtime_role.sql` must be run once per environment
  before deploying this change (or before this codebase reaches a real
  production target) — see Proposed Knowledge Updates below. Its placeholder
  password (`CHANGE_ME_IN_PRODUCTION`) must be overridden via the deploy
  pipeline, same discipline as `Settings.jwt_secret_key` (Low security
  advisory, `docs/reviews/security/US-4.2-security-review.md`).
- **BR-017's auto-close half remains unbuilt.** OD-8 resolved only the
  reply-side reopen transition (customer reply on a `"resolved"` ticket →
  `"waiting_on_support"`). The complementary 7-day auto-close job and its
  shared boundary constant are US-4.3's responsibility, not yet built.
- **`ticket_number` guessability** (US-4.1, Low security advisory) — carried
  forward unchanged; no endpoint in this story adds a `ticket_number`-keyed
  lookup.
- **`.gitignore`'s `docs/knowledge` addition** — flagged by `pr-preparer` as
  untraceable to this story's artifacts; acknowledged and accepted at the
  `READY_FOR_PR` human gate (2026-09-06T02:30:00Z comment), not corrected.
- **Two harness process-improvement edits ride alongside this delivery,
  currently uncommitted in the working tree:** `AGENTS.md` (RLS-seeding rule;
  the `created_at` tie-break determinism rule) and
  `docs/workflow/stage-map.yaml` (new `IMPLEMENTATION.loop_back.changes_required_tests`
  key) codify lessons this story's own three `HUMAN_REDIRECTED` test-fix
  cycles produced (T3→ARCHITECTURE_PLANNING, T4→TEST_WRITING, T5/T6→TEST_WRITING).
  `.claude/commands/so/approve.md` also carries an uncommitted edit (the
  `COMPLETED` gate's mandatory-verification addition, added after this
  story's own retracted-approval incident at 2026-09-06T03:30:00Z). None of
  these are Story artifacts this skill owns, and archive mode does not commit
  or otherwise act on them — noted here only so they aren't mistaken for
  stray/unclassified state on a future run.

## Proposed Knowledge Updates (NOT applied — pending human review)

### `docs/product/business-rules.md`

`BR-015` (internal-reply RLS invisibility) and `BR-016` (attachment ownership,
reused unchanged from US-4.1) already exist and accurately reflect what
shipped — no change needed there. One candidate new entry for behavior this
story shipped but that isn't yet captured as a business rule:

1. **Ticket reply status transitions.** An agent's public reply to an `open`
   or `waiting_on_support` ticket advances it to `waiting_on_customer` and
   stamps `first_response_at` on the first such reply only (later replies do
   not restamp it); an agent's public reply to a `resolved` ticket leaves it
   `resolved` unchanged (no side effect). A customer's reply to a ticket in
   `waiting_on_customer` advances it to `waiting_on_support`; a customer's
   reply to a `resolved` ticket reopens it to `waiting_on_support` (the
   reply-side half of BR-017's reopen behavior — the auto-close job half is
   not yet built). A reply to a `closed` ticket is rejected outright
   (`409 ticket-closed`); no reply is persisted. Internal notes (agent-only,
   `visibility="internal"`) never trigger a status transition. Visibility
   defaults to `public` for both actor kinds when omitted; only an agent may
   set `internal` (a customer attempting to is rejected `403`, no reply
   persisted).

### `docs/ARCHITECTURE.md`

One candidate addition — this story introduces a pattern not yet documented
anywhere in the file:

1. **§3.6 (Dependency Injection) or a new subsection — dedicated non-superuser
   runtime DB role.** The single previously-configured database role
   (`postgres`, via `DATABASE_URL`) is a PostgreSQL superuser and
   unconditionally bypasses Row-Level Security regardless of `FORCE ROW LEVEL
   SECURITY` — discovered this story when `TR-AC3`'s RLS guarantee failed to
   hold under it (see `docs/plans/US-4.2-implementation-plan.md` v2
   Architectural Change #12, and the `IMPLEMENTATION` T3 `BLOCKED` finding in
   `docs/catalog/US-4.2-pipeline-status.md`). This story provisions a second,
   dedicated `app_runtime` role (`NOSUPERUSER NOBYPASSRLS`, via
   `scripts/db/provision_runtime_role.sql`, idempotent, dynamic
   `current_database()`-scoped `GRANT`s) and switches the application's own
   request-serving DB connection to it (`app/main.py`'s `lifespan`,
   `Settings.runtime_database_url`) while Alembic migrations continue running
   as the existing owner role (`migrations/env.py` unchanged,
   `Settings.database_url`). **Any future story that adds a table/column
   reachable through the app's normal request path must confirm
   `provision_runtime_role.sql`'s blanket `GRANT`s (and its
   `ALTER DEFAULT PRIVILEGES`) still cover it** — proven this story only by a
   full-suite regression run under `app_runtime`, not by inspection
   (`implementation_plan` v2 Risk 7). This is architecturally binding for any
   story touching Row-Level Security or adding persistence the request path
   must reach — not this story's own local detail.

## History Reference

`docs/workflow/history.jsonl` — see the `US-4.2` events, including the
`HUMAN_REDIRECTED` routing decisions (T3→`ARCHITECTURE_PLANNING`,
T4→`TEST_WRITING`, T5/T6→`TEST_WRITING`), the retracted-then-reverified
`COMPLETED` approval, and this run's final `ARCHIVED` consolidation event.

## Recommendation

`docs/catalog/stories.yaml` shows `US-4.3` (Ticket Resolution) as the sole
remaining `BACKLOG` story in EPIC-4, depending on this story. `/so:start
US-4.3` is the unambiguous next candidate — not run here, per this skill's
recommendation-only mandate. `US-4.3`'s own catalog entry already flags its
draft specification as predating the current codebase, the same caveat
US-4.1's and US-4.2's own pre-existing drafts carried; expect a `CLARIFICATION`
pass to resolve BR-017's still-unbuilt auto-close half explicitly against this
story's OD-8 resolution (reply-side reopen already shipped; auto-close job and
shared boundary constant are what remains).
