---
artifact_type: delivery_summary
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T18:25:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/workflow/workflow-state.yaml
    version: null
  - path: docs/catalog/US-5.2-pipeline-status.md
    version: null
supersedes: null
---

# Delivery Summary: Account & Profile Self-Service (Frontend) (US-5.2)

## Identity

- **Story ID:** US-5.2
- **Epic:** EPIC-5 — Frontend
- **Story file:** `docs/stories/US-5.2-account-self-service-ui.md`
- **Source:** GitHub Issue #25, `AndriiDobrovolskii/Customer_Portal`
- **Final catalog state:** ARCHIVED (was IN_PROGRESS)

## Delivery

- **Pull Request:** #33 (`feat: account self-service UI (US-5.2)`), state
  MERGED into `main`, mergedAt 2026-09-08T15:14:13Z.
  https://github.com/AndriiDobrovolskii/Customer_Portal/pull/33
  Independently verified this run: `gh pr view --json state,mergedAt,baseRefName,headRefName,url`
  (`state=MERGED`, `base=main`, `head=feat/us-5.2-account-self-service-ui`) and
  `git fetch origin` + `git merge-base --is-ancestor feat/us-5.2-account-self-service-ui origin/main` (true).
- **Final branch:** `feat/us-5.2-account-self-service-ui`, pushed and merged.
- **Activation timestamp:** 2026-09-08T00:00:00Z (`active-story.yaml.activated_at`).
- **Completion timestamp:** 2026-09-08T17:55:00Z (`workflow-state.yaml.completed_at`,
  stage first reached `COMPLETED`).
- **Archive timestamp:** 2026-09-08T18:25:00Z (this run's consolidation).

## Artifact Inventory

| Type | Path | Version | Status |
|---|---|---|---|
| story | docs/stories/US-5.2-account-self-service-ui.md | — | (input, no status field) |
| story_catalog | docs/catalog/stories.yaml | — | ARCHIVED (this run) |
| clarification_report | docs/evidence/US-5.2-clarification-report.md | 1 | DRAFT — never named in a human_gate's `required_artifacts`, so never bumped per `artifact-lifecycle.md`; preserved as-is |
| open_decisions | docs/decisions/US-5.2-open-decisions.md | 1 | DRAFT — same reason; OD-3, OD-5, OD-6, OD-7 left OPEN by design, OD-1/OD-2/OD-4 RESOLVED at `HUMAN_SPEC_APPROVAL` |
| specification | docs/specifications/US-5.2-spec.md | 2 | ARCHIVED (was APPROVED) |
| specification_review | docs/reviews/specifications/US-5.2-spec-review.md | — | ARCHIVED (was APPROVED) |
| api_design | — | — | NOT_APPLICABLE (frontend-only, no new API contract) |
| openapi | — | — | NOT_APPLICABLE |
| database_design | — | — | NOT_APPLICABLE (no schema/migration impact) |
| entity_model | — | — | NOT_APPLICABLE |
| design_review | docs/reviews/designs/US-5.2-design-review.md | 1 | ARCHIVED (was DRAFT; stub documenting both areas out of scope) |
| impact_analysis | docs/impact-analysis/US-5.2-impact-analysis.md | 1 | ARCHIVED (was DRAFT) |
| implementation_plan | docs/plans/US-5.2-implementation-plan.md | 1 | ARCHIVED (was APPROVED) |
| task_breakdown | docs/plans/US-5.2-task-breakdown.md | 1 | ARCHIVED (was APPROVED) |
| plan_review | docs/reviews/plans/US-5.2-plan-review.md | 1 | ARCHIVED (was APPROVED) |
| test_strategy | docs/tests/US-5.2-test-strategy.md | 1 | ARCHIVED (was DRAFT) |
| ac_test_matrix | docs/tests/US-5.2-ac-test-matrix.md | 1 | ARCHIVED (was DRAFT) |
| test_generation_report | docs/evidence/US-5.2-test-generation-report.md | 1 | ARCHIVED (was DRAFT) |
| implementation_report | docs/evidence/US-5.2-implementation-report.md | 1 | ARCHIVED (was DRAFT) |
| quality_gate_report | docs/evidence/US-5.2-quality-gate-report.md | 1 | ARCHIVED (was DRAFT) |
| implementation_verification | docs/verification/US-5.2-implementation-verification.md | 1 | ARCHIVED (was APPROVED) |
| security_review | docs/reviews/security/US-5.2-security-review.md | 1 | ARCHIVED (was APPROVED) |
| reconciliation | docs/reviews/reconciliation/US-5.2-reconciliation.md | 1 | ARCHIVED (was APPROVED) |
| traceability | docs/reconciliation/US-5.2-traceability.md | 1 | ARCHIVED (was APPROVED) |
| pr_summary | docs/pr/US-5.2-pr-summary.md | 1 | ARCHIVED (was APPROVED — corrected from DRAFT during the `COMPLETED` gate correction earlier this run) |
| pipeline_status | docs/catalog/US-5.2-pipeline-status.md | 2 | DRAFT — historical, cross-story artifact, preserved in place untouched (matching the US-4.4/US-5.1 precedent) |

**Status backfill note:** 9 of the artifacts above (`design_review`,
`impact_analysis`, `test_strategy`, `ac_test_matrix`, `test_generation_report`,
`implementation_report`, `quality_gate_report`, plus `specification` and the
already-`APPROVED` set) were bumped to `ARCHIVED` in this run. This is the
same pattern flagged in `[[US-5.1-delivery-summary]]`, `[[US-4.4-delivery-summary]]`,
et al: artifacts never named in a human_gate's `required_artifacts` list are
never touched by the `DRAFT`→`APPROVED` bump rule, so they arrive at archive
time still `DRAFT` despite the owning stage's recorded `PASS` verdict. Archive
mode moves every Story artifact still in a non-terminal status straight to
`ARCHIVED`, reflecting the already-recorded verdict rather than re-deriving one.
`clarification_report` and `open_decisions` are left `DRAFT`, consistent with
prior deliveries' handling, since this run does not own a rule to change that.

## Final Acceptance-Criteria Result

PS-AC1 through PS-AC7 plus cross-cutting XC-AC1/XC-AC2 all mapped in
`traceability` v1 (`reconciliation-reviewer` verdict PASS). PS-AC1 (profile
*view*) is the one explicit, spec-sanctioned deferral: no `GET /profile` /
`GET /users/me` endpoint exists yet, so the profile form ships write-only
this Story (OD-5, OPEN, deferred to a future backend Story). OD-1, OD-2, and
OD-4 were RESOLVED at `HUMAN_SPEC_APPROVAL` and shipped per their resolutions
(conditional `If-Match: *`, MFA enroll/disable requiring `current_password` +
TOTP code, deactivation requiring `current_password`). OD-3, OD-6, OD-7
remain OPEN, each implemented and tested against a recorded default rather
than a resolved decision (enrollment-scoped-token navigation, locale set,
timezone input scope).

## Final Verdicts

| Stage | Verdict |
|---|---|
| QUALITY_GATE | PASS — 44/44 test files, 192/192 tests, 0 failures. Coverage 96.71%/94.57%/85.39%/96.71% (stmt/branch/func/line); functions clears the 85% floor by a narrow margin (152/178) |
| IMPLEMENTATION_VERIFICATION | PASS |
| SECURITY_REVIEW | PASS |
| RECONCILIATION | PASS |

## Known Limitations / Deferred Work (all disclosed, none blocking)

- **PS-AC1 (profile view) has no dedicated test and ships write-only** — no
  `GET /profile` / `GET /users/me` endpoint exists this Story; a
  spec-sanctioned deferral (OD-5, OPEN), not a gap.
- **OD-3, OD-6, OD-7 remain OPEN** — enrollment-scoped-token navigation
  (banner-link-only default), locale set, and timezone input scope were each
  implemented and tested against this pass's own recorded default rather
  than a resolved Open Decision.
- **Sensitive values (MFA secret/otpauth_uri/recovery_codes,
  current_password) pass through TanStack Query's in-memory mutation cache**,
  not only screen-local `useState` as the spec's Client State Notes literally
  describe. Nothing reaches storage or logs; byte-for-byte spec fidelity
  would call for an explicit `mutation.reset()` after each flow completes.
- **`httpClient.ts`'s new `httpPatch` re-implements its own 401-refresh-retry
  branch** rather than routing through the existing `performRequest` helper
  that already has one. Both copies are correct and tested today; flagged as
  a duplication/drift risk for whoever next touches this seam.
- **`ProfileScreen.tsx:14` imports `SUPPORTED_LOCALES`/`ProfileRead`/
  `ProfileUpdateRequest` directly from `api/types.ts`**, a Minor/non-blocking
  `AGENTS.md` §3 Frontend layer deviation — same class as an accepted US-5.1
  precedent, no runtime coupling into fetch/tokens, no secret exposure.
- **`useProfileUpdate.ts` always sends `If-Match`** (cached ETag or literal
  `*`) rather than PS-AC2's literal "omitted otherwise" wording — OD-1's
  recorded resolution, valid HTTP semantics, an AC-wording deviation rather
  than a technical-compliance issue.
- **Function coverage clears the 85% floor by a narrow margin** (85.39%,
  152/178) — a single future untested function-heavy module could push it
  back under threshold, as `queryClient.ts` did before this Story's fix.
- **`npm install` reports 8 dev-dependency vulnerabilities** (5 moderate, 1
  high, 2 critical) — untriaged, carried over from US-5.1 and prior.
- **`LoginScreen.tsx` modified additively** (renders optional
  `location.state.message`) though not named in the implementation plan's
  Files To Modify — required by FR-7/PS-AC7 and `task_breakdown` T10's own
  verification bullet; existing tests still pass.
- **PS-AC3/FR-3 (confirm-email-change) specifies no expired/invalid outcome
  distinction**, unlike PS-AC4/FR-4 (verify-email); likely covered by
  XC-AC1's generic handling but unconfirmed (carried unchanged from spec
  review v1).

## Proposed Knowledge Updates

**Not yet applied** — pending explicit human approval in this session per
`archive-flow.md` step 7. Presented below for review.

### `docs/product/business-rules.md`

No new business rule proposed. This Story is a pure frontend consumer of
already-documented backend rules (BR-008 single-use refresh/family
revocation, BR-013 MFA grace period) and introduces no new server-side
behavior or new endpoint contract.

### `docs/ARCHITECTURE.md`

No new architectural pattern proposed. This Story extends the frontend stack
already documented from US-5.1 (§8: `frontend/` React+Vite+TS layering,
TanStack Query, `api/` as sole fetch boundary) with new screens, hooks, and
API modules following that same layering — no new pattern, seam, or
cross-cutting mechanism introduced. The one new transport-layer addition
(`httpClient.ts`'s `httpPatch`, with its own independent 401-refresh-retry
branch alongside `performRequest`'s pre-existing one) is a duplication worth
future cleanup, not a documented architectural decision — noted above under
Known Limitations instead.

**Source:** `docs/plans/US-5.2-implementation-plan.md`;
`docs/verification/US-5.2-implementation-verification.md`;
`docs/reviews/security/US-5.2-security-review.md`.

## History Reference

`docs/workflow/history.jsonl` — see the `US-5.2` events, including the
`HUMAN_APPROVED` event at `READY_FOR_PR` (2026-09-08T17:55:00Z), the
`HUMAN_APPROVED` event at `COMPLETED` (2026-09-08T18:05:00Z — verified
against the actual repository via `gh pr view` and
`git merge-base --is-ancestor` before recording), this run's `CORRECTION`
event (2026-09-08T18:15:00Z, see Process Note below), and this run's final
`ARCHIVED` consolidation event.

**Process note:** the `/so:approve` run at the `COMPLETED` gate repeated a
mistake `[[US-5.1-delivery-summary]]` and `[[US-4.3-delivery-summary]]` had
already caught and documented — writing `current_stage: ARCHIVED` and
`status: ARCHIVED` directly from `/so:approve`, instead of leaving
`current_stage` at `COMPLETED` for archive mode to advance per
`archive-flow.md` steps 9-10. Caught and self-corrected in
`workflow-state.yaml` at the start of this `/so:archive` run, before any
archive-mode step executed (no archive-mode consolidation had run yet, so
nothing else was affected). That same correction also bumped `pr_summary`'s
front-matter `status` from `DRAFT` to `APPROVED` — owed since the
`READY_FOR_PR` gate approval per `artifact-lifecycle.md`'s bump rule, and
missed at that time. `history.jsonl`'s original `HUMAN_APPROVED` (COMPLETED →
ARCHIVED) event was left as written (append-only); a `CORRECTION` event
records the fix.

## Recommendation

`docs/catalog/stories.yaml` shows US-5.3 and US-5.4 (EPIC-5 frontend
follow-ups) in `BACKLOG`; US-5.4 explicitly depends on this Story's
ETag/response-header API client support. Recommend `/so:start US-5.3` or
`/so:start US-5.4` next, whichever the user prioritizes — no explicit
priority stated this session.

## GitHub Sync

Issue #25 (source Issue for this Story) closed 2026-09-08T18:30:00Z on
explicit human approval, with a comment referencing PR #33 and this delivery
summary. `gh issue close 25 --comment "..."` was the only GitHub write
performed by this run; no Pull Request was created, pushed, or merged by the
harness (PR #33 was opened and merged by the human beforehand).
