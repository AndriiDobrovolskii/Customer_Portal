---
artifact_type: plan_review
story: US-4.2
version: 2
status: ARCHIVED
created_at: "2026-09-05T21:00:00Z"
updated_at: "2026-09-05T21:00:00Z"
produced_by: plan-reviewer
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/plans/US-4.2-task-breakdown.md
    version: 2
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/reviews/plans/US-4.2-plan-review.md (v1)
---

# Plan Review: Ticket Replies

**Story ID:** US-4.2
**Plan Reviewed:** docs/plans/US-4.2-implementation-plan.md (v2)
**Task Breakdown Reviewed:** docs/plans/US-4.2-task-breakdown.md (v2)
**Reviewed:** 2026-09-05
**Overall Verdict:** PASS

## Revision Note (v2)

v1 of this review (PASS, no findings) reviewed `implementation_plan` v1 /
`task_breakdown` v1 — both now `SUPERSEDED`. `implementation_plan` v2 adds
Architectural Change #12 (a dedicated non-superuser `app_runtime` PostgreSQL
role) per the `HUMAN_REDIRECTED` transition recorded at
`docs/workflow/history.jsonl` (2026-09-05T18:30:00Z): `IMPLEMENTATION` T3
proved the deployed role is a PostgreSQL superuser, which bypasses RLS
regardless of `FORCE ROW LEVEL SECURITY`, falsifying TR-AC3 as designed.
`task_breakdown` v2 adds T4 (migration-manager: role-provisioning script +
`tests/conftest.py` fixture rewiring) and folds `app/main.py`'s one-line
`lifespan` change into T5. This revision re-reviews the full v2 pair — not
only the delta — against the current, non-stale inputs listed above.
Architectural Changes #1–#11 and T1–T3 are unchanged from v1's already-passed
review and are re-confirmed, not re-argued from scratch.

## Summary

Reviewed `implementation_plan` v2 and `task_breakdown` v2 against
`impact_analysis` v2, `specification` v6, `api_design` v3/`openapi` v3, and
`db_design` v3/`entity_model` v3. Every `impact_analysis` v2 item still has a
corresponding, correctly-scoped plan section or Files-To-Modify row (Change
#12's files have no `impact_analysis` origin, but trace instead to the
recorded `HUMAN_REDIRECTED` decision and to TR-AC3 itself — see "Scope
Creep" below, not a coverage gap). The task breakdown's T1–T7 sequence still
matches `AGENTS.md` §3's build order and the migration-before-model-use rule,
including the new T4; T4's placement (after T3, gating T7) is correct even
though it sits outside the router→service→repository chain. The Risks and
Testing/Validation Strategy sections were extended with two new, concrete
risks (blast-radius of the whole-application role switch; provisioning as an
out-of-band per-environment step) and a full-suite regression re-run — not
generic placeholders. No blocking or non-blocking findings that require a
loop-back; one informational note on the T4/T5 skill-assignment question the
task breakdown itself flagged for this stage, resolved below as acceptable.

## Impact-Analysis Coverage

| Impact Analysis Item | Status | Covered By (plan section) | Notes |
|---|---|---|---|
| `app/modules/support/models.py` (new `TicketReply`; additive `Ticket.first_response_at`; additive `Attachment.ticket_reply_id`) | Covered | Files To Modify — `models.py`; Architectural Changes carried from v1 | Matches db-design v3 shape; T2 already `PASS`. |
| New Alembic revision (`migrations/versions/`), incl. carried DR-2 finding | Covered | Files To Create — Migration row; Risks 1, 4, 5 | DR-2 now resolved (plain `CREATE INDEX`, not `CONCURRENTLY`) per `docs/catalog/US-4.2-pipeline-status.md` v2; T3 already proven via a real upgrade→downgrade→upgrade cycle. |
| `app/modules/support/repository.py` (`TicketReplyRepository`; `TicketRepository.update()`; `AttachmentRepository.bind_to_reply()`) | Covered | Files To Modify — `repository.py`; Architectural Changes §3, §11 | T2 already `PASS`. |
| `app/modules/support/cache.py` (rate-limit cache) | Covered | Files To Modify — `cache.py`; Architectural Changes §7 | T2 already `PASS`. |
| `app/core/cache_keys.py` (key-builder function) | Covered | Files To Modify — `cache_keys.py`; Architectural Changes §7 | T2 already `PASS`. |
| `app/modules/support/service.py` (actor-kind branch, status-gating, FR-5, rate limit, `first_response_at`, email dispatch) | Covered | Files To Modify — `service.py`; Architectural Changes §4, §5; Task T5 | Status-gating table restated verbatim from api-design v3. |
| RLS session-context mechanism (placement left open by impact-analysis) | Covered | Architectural Changes §2 | Module-scoped `get_rls_session`, unchanged from v1's already-passed decision. |
| `app/core/email.py` (`EmailSender` Protocol + `LoggingEmailSender`) | Covered | Files To Modify — `email.py`; Architectural Changes §8; Task T5 | |
| `app/core/config.py` (new `support_queue_email` field) | Covered | Files To Modify — `config.py`; Architectural Changes §9; Task T5 | |
| `app/modules/support/router.py` (two new routes) | Covered | Files To Modify — `router.py`; Architectural Changes §10; Task T6 | `GET` route's own `limit` bound closed per openapi v3. |
| `app/modules/support/dependencies.py` (new provider(s), RLS dependency) | Covered | Files To Modify — `dependencies.py`; Architectural Changes §2; Task T6 | |
| `app/modules/support/schemas.py` (new schemas) | Covered | Files To Modify — `schemas.py`; Task T1 | T1 already `PASS`. |
| `app/modules/support/exceptions.py` (new exception classes) | Covered | Files To Modify — `exceptions.py`; Architectural Changes §6; Task T5 | |
| Cross-Module Ripple — `roles.dependencies.require_scope` (existing, reused) | Covered | Files To Modify — `router.py` note | |
| Test-Surface — `tests/integration/modules/support/test_support_router.py` | Covered | Testing Strategy — Integration | Names TR-AC1–TR-AC7 plus the NFR's RLS-specific test; now also the full-suite regression re-run (v2 addition). |
| Test-Surface — `tests/unit/modules/support/test_support_service.py` | Covered | Testing Strategy — Unit | Unaffected by v2 (infrastructure change, not service logic). |
| Test-Surface — RLS migration proof | Covered | Validation Strategy; Testing Strategy — Integration | Already executed at T3; re-verification (not re-run) now scheduled at T4. |
| `.env.example` | Covered | Files To Modify — `.env.example`; Task T5 | |
| `migrations/env.py` (protected file, `AGENTS.md` §7.9) | Covered | Files To Modify — `migrations/env.py`; Risk 4 | v2 confirms Change #12 does not touch it (Alembic keeps using `database_url`, the owner-role URL) — still expected zero-diff. |

**Not in `impact_analysis` v2, by design — not a coverage gap:** `scripts/db/provision_runtime_role.sql` (new), `app/main.py` (new to this story's footprint), `tests/conftest.py` (new to this story's footprint), and `app/core/config.py`'s `runtime_database_url` field. None of these trace to `impact_analysis` v2 (produced 2026-09-05T13:00:00Z, before `IMPLEMENTATION` T3 discovered the superuser-bypass defect at 18:00:00Z that day) or to the original spec text. They trace instead to the recorded `HUMAN_REDIRECTED` transition (`docs/workflow/history.jsonl`, 2026-09-05T18:30:00Z) and, substantively, to TR-AC3 itself (the RLS guarantee the story's own NFR and acceptance criteria require) — see "Scope Creep" below for why this is not treated as untraced scope.

## Layering Order (Task Breakdown)

None. T1 (schema-builder) and T2 (data-layer-builder) remain parallel-eligible with no cross-dependency; T3 (migration-manager) depends on T2, matching the migration-before-model-use rule; **T4 (NEW, migration-manager) depends on T3** — correct, since it grants privileges on tables T3 creates and its own re-verification step needs T3's schema live; T5 (service, depends on T1, T3) and T6 (router, depends on T5) follow `AGENTS.md` §3's bottom-up build order; T7 (gate-enforcer) runs last against T1–T6, and correctly cannot be considered proven until T4 also completes (its full-suite regression pass is the actual evidence T4's `GRANT` list is complete). T4 sits outside the `router→dependencies→service→repository/cache→models/schemas` chain entirely (it is role/connection provisioning, not module code) — the task breakdown's own "Notes" section states this correctly rather than forcing it into a layer it doesn't belong to. The stage-map's fixed composite-skill order (schema-builder → data-layer-builder → migration-manager → service-and-router-builder) is preserved; T4 stays inside migration-manager's slot in that sequence.

## Risk Realism

None. Risks 1–2 (RLS `FORCE ROW LEVEL SECURITY` / `SET LOCAL` session-context) and Risk 6 (rate-limit key collision) are unchanged from v1 and remain concrete. Risk 4 (`migrations/env.py`, protected file) and Risk 5 (DR-2) are carried and, per `docs/catalog/US-4.2-pipeline-status.md` v2, Risk 5 is now confirmed resolved rather than merely mitigated. **New in v2:** Risk 7 names the specific hazard of switching the application's entire runtime connection role (a privilege gap surfacing in an unrelated module, not `support`) with a concrete mitigation (full existing test suite re-run as proof, not code inspection) — this is exactly the kind of blast-radius risk `AGENTS.md` §4's PostgreSQL-hazards guidance expects named, not glossed over. Risk 8 names the operational hazard of the provisioning script never being run against a given environment, with a concrete mitigation scoped to what this plan actually controls (automating it inside `tests/conftest.py` for the harness's own CI/local-dev path) while correctly deferring real-deployment documentation to `documentation-and-adrs` rather than silently assuming someone else has scheduled it.

## Test-Strategy Realism

None. The Testing Strategy section still names specific unit and integration test cases per `AGENTS.md` §5's fake-vs-real-infrastructure split, unchanged from v1 where unaffected. **New in v2:** the full-suite regression pass is stated concretely — which test directories must be re-run (`tests/integration/modules/{users,roles,admin_users,audit,profile}/...`), against what fixture change, and why it counts as proof rather than a "testing will catch it" placeholder (Risk 7's actual mitigation, not a separate unverified claim). The Validation Strategy's secret-scan note (provisioning script's password placeholder must not read as a real credential) is a concrete, checkable instruction, not vague guidance.

## Scope Creep

None requiring a loop-back. Every Architectural Change #1–#11 and every original Files-To-Modify/Create row traces to `impact_analysis` v2 or an item it explicitly left as an open decision for this stage, unchanged from v1's finding. **Architectural Change #12 and its four new/changed files are the one item in this plan with no `impact_analysis` origin** — but this is a documented, human-authorized correction, not an unreviewed addition: it is grounded in the `HUMAN_REDIRECTED` transition (`docs/workflow/history.jsonl`, 2026-09-05T18:30:00Z, `decided_by: sbruhov@gmail.com`), itself triggered by `migration-manager`'s own `BLOCKED` finding that the deployed role bypasses RLS — a defect in achieving TR-AC3, not a feature this plan invented. `AGENTS.md` §7.8's "no unilateral scope changes" targets changes a skill makes on its own initiative; this one was explicitly directed by the human at a recorded decision point, the same evidentiary bar this story's own OD-8 resolution and the `DESIGN_REVIEW → CLARIFICATION` `HUMAN_REDIRECTED` precedent (2026-09-05T09:00:00Z) already established. No finding.

**Informational note — T4/T5 skill assignment (carried from `task_breakdown` v2's own "Assignment note," not a defect):** `task_breakdown` v2 assigns `scripts/db/provision_runtime_role.sql` + `tests/conftest.py`'s fixture change to **migration-manager** (T4) and folds `app/main.py`'s one-line change into **service-and-router-builder**'s T5. Both are wider than those skills' stated file footprints. Judged acceptable: T4's work is idempotent, guarded PostgreSQL DDL/role provisioning — the same domain migration-manager already owns for `AGENTS.md` §4 hazards, and its own verification step (re-running T3's RLS tests) is literally migration-manager's existing responsibility. `app/main.py`'s fold into T5 mirrors this same story's own v1 precedent (bundling `support_queue_email`/`.env.example` into the service task rather than inventing a task for a single-line, non-module change), which passed `HUMAN_PLAN_APPROVAL` once already without objection. If the human disagrees with either assignment, the correct loop-back is `changes_required_sequencing` (stays within `IMPLEMENTATION_PLANNING`), not `ARCHITECTURE_PLANNING` — the *what* was already settled by Architectural Change #12; only the *who* was in question, and this review finds no defect in the answer given.

## Verdict Rationale

Full `impact_analysis` v2 coverage (with the one exception explicitly traced to a recorded human decision rather than an untraced addition), correct `AGENTS.md` §3 layering order including the new T4, concrete and extended risk/test-strategy sections addressing the new architectural change's actual hazards, and no untraceable scope — all four Pass criteria are met with no blocking or non-blocking findings requiring a loop-back. `PASS`.
