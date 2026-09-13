---
artifact_type: clarification_report
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T07:10:29Z"
updated_at: "2026-09-13T13:15:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/product/product-vision.md
    version: null
  - path: docs/product/personas.md
    version: null
  - path: docs/product/business-rules.md
    version: null
  - path: docs/product/business-glossary.md
    version: null
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: 1
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: docs/evidence/US-5.4-clarification-report.md (v1)
---

# Clarification Report: US-5.4 — Admin Console (Frontend)

## Why this revision exists

This is a re-run of `CLARIFICATION`, not a first pass. `PLAN_REVIEW` returned
`BLOCKED` (`docs/reviews/plans/US-5.4-plan-review.md`,
`docs/workflow/history.jsonl` at the `PLAN_REVIEW` entry preceding
`2026-09-13T12:45:00Z`) because the `APPROVED` v1 specification still carried
four Open Decisions (OD-1..OD-4) as `OPEN`, and the task breakdown had tied
them directly to tasks T16, T19, T20, T21. `story-orchestrator` recorded a
`HUMAN_REDIRECTED` transition from `PLAN_REVIEW` back to `CLARIFICATION` at
`2026-09-13T12:45:00Z`, carrying a human-supplied resolution for each of the
four items as authoritative input to this run. This report and the paired
`docs/decisions/US-5.4-open-decisions.md` (version 2) formalize those
resolutions; they do not invent or infer any of them.

## Business Intent (restated)

**Actor:** the Administrator persona (internal staff, MFA-mandatory,
`docs/product/personas.md`). **Trigger:** EPIC-3's backend admin/audit
capabilities (US-3.1 manage users, US-3.2 manage roles, US-3.3 view audit
information) already exist as APIs with no UI. **Business value:** makes
those capabilities usable end-to-end by a human administrator instead of
only via raw API calls — explicitly named in the User Story and matching
Product Goal 5 ("Administrative functionality"), `docs/product/
product-vision.md`. This restates version 1's finding unchanged; nothing in
this pass altered the story's scope, actors, or business value.

## Dependency Check

Unchanged from version 1 — re-confirmed on this pass:

- **US-5.1** and **US-5.2** are both `ARCHIVED` (`docs/catalog/stories.yaml`)
  and supply the shared frontend scaffold and ETag/`If-Match` support this
  story depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree the active story is `US-5.4`, currently at stage `CLARIFICATION`
  (`current_stage: CLARIFICATION`, `previous_stage: PLAN_REVIEW`) — no
  mismatch.

## What's Clear

All of version 1's "What's Clear" findings still hold (the CRUD/admin
surface, Assumption #5's `roles`-immutable-on-`PATCH` verification, Assumption
#6's no-delete verification, the cosmetic-gating security posture, and the
Non-Functional/Security Requirements section) — nothing in this pass
contradicts them. In addition, the four items that were open in version 1
are now resolved:

## Open Decisions Resolved This Pass

All four items are now `RESOLVED` (source: **human decision, 2026-09-13**),
recorded in full in `docs/decisions/US-5.4-open-decisions.md` (version 2):

| # | Decision | Resolution |
|---|---|---|
| OD-1 | Audit Log screen's default `from`/`to` window on initial load | Last 7 days (`from = now - 7d`, `to = now`, ISO 8601 UTC), both pre-filled visibly in the date pickers |
| OD-2 | Audit log `event` filter: free text or fixed vocabulary | Free-text input with an illustrative placeholder |
| OD-3 | Role replacement UI: full-replace multi-select or add/remove controls | Multi-select showing the final target role set; confirmation dialog computes and shows Gained = selected − current and Lost = current − selected; save disabled if neither set changed |
| OD-4 | Create User's role picker source | Catalogue-driven, from `GET /admin/roles`, reusing the same query hook as role replacement |

None of these were guessed or inferred by this skill — each is a direct
transcription of the human-supplied resolution recorded in
`docs/workflow/history.jsonl` at `2026-09-13T12:45:00Z`, per this skill's own
contract that Open Decisions are resolved at `HUMAN_SPEC_APPROVAL` (or, as in
this redirected case, by an explicit human decision fed back into a
`CLARIFICATION` re-run) — never invented by `us-clarifier` itself.

## Re-check of Normal Responsibilities

This pass re-read `docs/product/product-vision.md`, `personas.md`,
`business-rules.md`, `business-glossary.md`, and the story itself against
this skill's full Responsibilities checklist (business intent, acceptance
criteria, security expectations, validation expectations, dependencies,
assumptions). No new ambiguity was found beyond the four now-resolved items.
The two version-1 "Findings Resolved by Citation" items (the `UserRead.status`
enum already documented in `docs/designs/api/US-3.1-openapi.yaml:402-404`,
and the Create User empty-role-list edge case already covered by XC-AC3)
remain resolved by citation and are unaffected by this pass.

**No new Open Decisions were recorded in this revision.**

## Readiness Verdict

**PASS — fully ready, no open items.**

Scope, actors, and business value are unambiguous (unchanged from version 1).
All four Open Decisions that were `OPEN` in version 1 are now `RESOLVED` with
a cited source (human decision, 2026-09-13) in
`docs/decisions/US-5.4-open-decisions.md` (version 2). No new ambiguity was
found during this re-check. Nothing found requires a backend, API, or DB
change (Assumption #8 remains confirmed `NOT_APPLICABLE`). `docs/workflow/
active-story.yaml` and `docs/workflow/workflow-state.yaml` agree on the
active story and stage.

This story is now ready to proceed to `SPECIFICATION` for a v2 specification
that incorporates the four resolutions directly, rather than carrying them
forward as Open Decisions.

## Non-Blocking Findings

Carried forward unchanged from version 1 (neither blocks this story's
progression, both remain worth a maintainer's attention independent of this
story):

1. The story's own Open Question 1 rests on a stale premise —
   `UserRead.status`'s value set is already documented
   (`docs/designs/api/US-3.1-openapi.yaml:402-404`,
   `enum: [invited, active, deactivated]`).
2. `docs/specifications/US-3.3-spec.md` FR-5's Open Questions note says the
   shipped behavior is undecided for "only one of `from`/`to` supplied," but
   `app/modules/audit/service.py:124-129` already rejects the request
   whenever *either* bound is missing — that archived spec's Open Questions
   section appears not to have been updated to match the shipped code.
