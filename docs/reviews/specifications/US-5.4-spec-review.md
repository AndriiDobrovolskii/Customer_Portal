---
artifact_type: specification_review
story: US-5.4
version: 2
status: APPROVED
created_at: "2026-09-13T14:00:00Z"
updated_at: "2026-09-13T14:00:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: docs/reviews/specifications/US-5.4-spec-review.md (v1)
---

# Spec Review: Admin Console (Frontend)

**Original Story:** docs/stories/US-5.4-admin-console-ui.md
**Spec Reviewed:** docs/specifications/US-5.4-spec.md (version 2)
**Story ID:** US-5.4
**Reviewed:** 2026-09-13
**Overall Verdict:** PASS

## Summary

This is a re-review of specification version 2, a revision of the previously-`APPROVED` version 1 (`docs/reviews/specifications/US-5.4-spec-review.md`, v1) that `PLAN_REVIEW` found still carrying four unresolved Open Decisions tied directly to task-breakdown tasks. Version 2 incorporates all four now-`RESOLVED` Open Decisions (`docs/decisions/US-5.4-open-decisions.md`, v2: OD-1–OD-4) into exactly FR-3, FR-5, and FR-8, as the spec's own revision note claims; this was independently confirmed against the open-decisions artifact and against the underlying code/contract citations each resolution relies on (all verified accurate — see Ambiguities/Contradictions below, both empty of any new blocking issue). All 12 Acceptance Criteria remain Covered, no Contradiction or Scope Creep was found, and no unresolved blocking Open Decision remains against this version. Three non-blocking Missing-Edge-Case gaps carried forward unchanged from the v1 review (audit-log row-key stability, scopes lifecycle detail, unrecognized status/roles rendering) are still present, plus two new low-severity findings specific to this revision (a dangling FR-4→FR-5 cross-reference, and a stray trailing tag in the artifact body). None of these blocks approval.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AD-AC1 | "Given an authenticated admin holding users:read on /admin/users Then GET /admin/users renders each user's email, display_name, status, roles, created_at and last_login_at And q / status / role filters re-request the list and reset the cursor And a non-null next_cursor drives a \"Load more\" that appends the next page And no total count or page number is displayed anywhere" | Covered | FR-1 | Unchanged from v1; fixed `status` enum citation (`docs/designs/api/US-3.1-openapi.yaml`) independently re-verified accurate. |
| AD-AC2 | "Given an admin opening a user Then GET /admin/users/{id} is called and the ETag response header is captured into client state And that ETag is sent as If-Match on the next PATCH for that user" | Covered | FR-2 | Unchanged from v1. |
| AD-AC3 | "Given an admin holding users:write When they submit email, display_name and roles Then POST /admin/users is called with exactly those fields and no password field is present anywhere in the form And on 201 they land on the new user's detail screen" | Covered | FR-3 | Rewritten in v2 to add Resolution OD-4 (catalogue-driven role picker sourced from `GET /admin/roles`); citation to `app/modules/roles/service.py`'s silent-drop-on-unrecognized-name behavior independently re-verified accurate. |
| AD-AC4 | "Given the user-edit form When any editable field (display_name, locale, timezone, avatar_url) is changed Then a non-empty reason is required before submission is allowed And PATCH /admin/users/{id} is called with If-Match and the reason And a 412 shows a conflict state; an immutable-field problem renders its detail" | Covered | FR-4 | Unchanged from v1. See Ambiguities: its "(see FR-5)" pointer for the immutable-field problem does not resolve in FR-5's v2 text. |
| AD-AC5 | "Given the user-edit screen Then roles are never included in the PATCH body When the admin changes role assignment and saves Then GET /admin/roles supplies the selectable catalogue and PUT /admin/users/{id}/roles is called with the full replacement list And an admin lacking roles:write sees the role control disabled, and a server 403 still renders correctly if it is attempted And role replacement sits behind an explicit confirmation naming what the user will gain and lose" | Covered | FR-5 | Rewritten in v2 to add Resolution OD-3 (multi-select showing target set; confirmation computes gained/lost sets; save disabled if unchanged) — a reasonable elaboration of "confirmation naming what the user will gain and lose," not new scope. Full-replacement semantics citation (`docs/designs/api/US-3.2-openapi.yaml`) independently re-verified accurate. |
| AD-AC6 | "Given an admin on a user's detail screen When they deactivate the user with a non-empty reason Then POST /admin/users/{id}/deactivate is called and the returned status is reflected When they resend the invite Then POST /admin/users/{id}/resend-invite is called and a generic confirmation is shown" | Covered | FR-6 | Unchanged from v1. |
| AD-AC7 | "Given any admin screen Then no control anywhere issues DELETE /admin/users/{id}" | Covered | FR-7 | Unchanged from v1. |
| AD-AC8 | "Given an admin holding audit:read on /admin/audit-logs Then GET /admin/audit-logs renders occurred_at, actor_id, actor_role, event, target_id, outcome, request_id, ip and user_agent And null values render an explicit placeholder rather than an empty cell And the actor_id / event / target_id / from / to filters are sent as query parameters, with the start-of-window parameter named \"from\" And a non-null next_cursor drives \"Load more\"; no total count or page number is displayed anywhere" | Covered | FR-8 | Rewritten in v2 to add Resolution OD-1 (default 7-day `from`/`to` window, pre-filled visibly) and Resolution OD-2 (free-text `event` filter). Both citations (`app/modules/audit/service.py`'s `RangeTooWideError`; `docs/designs/api/US-3.3-openapi.yaml`'s unconstrained `event` string) independently re-verified accurate. Row-key gap from v1 review still present — see Missing Edge Cases. |
| XC-AC1 | "Given an authenticated user whose access token carries no admin scopes Then no admin navigation entry is rendered Given they navigate directly to an admin route anyway Then the server's 403 problem+json is rendered as an explicit \"not permitted\" state, never a blank screen or an infinite spinner Given an admin holding users:read but not users:write Then read screens render normally and every write control is disabled" | Covered | FR-9 | Unchanged from v1. Scopes-lifecycle gap from v1 review still present — see Missing Edge Cases. |
| XC-AC2 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | Covered | FR-10 | Unchanged from v1. |
| XC-AC3 | "Given any form in this Story When a required field is empty or malformed (invalid email shape, empty reason, empty role list) Then submission is blocked with a field-level error and no API call is made" | Covered | FR-11 | Unchanged from v1. |
| XC-AC4 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | Covered | FR-12 | Unchanged from v1. |

## Ambiguities & Non-Verifiable Statements

- **[Low] Dangling FR-4 → FR-5 cross-reference for "immutable-field"** — FR-4 says: "An `immutable-field` problem response (see FR-5) renders that problem's own detail." FR-5 (as rewritten in v2) never uses or explains the term `immutable-field`, nor states which field(s) trigger it; that rationale exists only in the story's Assumption #5 ("`roles` is in `ADMIN_USER_IMMUTABLE_FIELD_NAMES` — sending it to `PATCH` is an `immutable-field` error"). A developer following FR-4's pointer into FR-5 finds nothing that explains the term.
- **[Low] Stray trailing tag in the specification file** — The file ends with a literal `</content>` line immediately after the Traceability Matrix's last row, with no corresponding opening tag anywhere in the document. This is a leaked wrapper artifact, not specification content; it does not affect the meaning or testability of any FR but is a defect in the artifact as written.

## Contradictions With Original Story

None found. All four Resolutions (OD-1–OD-4) incorporated into FR-3/FR-5/FR-8 were checked against the story's own text and against the code/contract citations backing each resolution (`docs/designs/api/US-3.1-openapi.yaml`, `docs/designs/api/US-3.2-openapi.yaml`, `docs/designs/api/US-3.3-openapi.yaml`, `app/modules/audit/service.py`, `app/modules/roles/service.py`) and found accurate; none conflicts with an AC or with the story's stated business context.

## Scope Creep

None found. FR-3's catalogue-driven role picker (OD-4), FR-5's multi-select/gained-lost-diff/disable-if-unchanged behavior (OD-3), and FR-8's default date window (OD-1) and free-text event filter (OD-2) are each explicitly traced to a human-supplied Resolution recorded in `docs/decisions/US-5.4-open-decisions.md` (v2) — the sanctioned mechanism this workflow uses to close an Open Decision — not invented requirements. No FR, NFR, or removed Open Question introduces a requirement, field, endpoint, or system the story does not mention.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Unrecognized `status`/`roles` values not addressed in FR-1** — Story's Client State Notes say: "`UserRead.status` and `UserRead.roles` are plain strings — an unrecognized value renders verbatim." FR-1 states what columns render but never states this fallback rule. AD-AC1 doesn't literally require it, so AC coverage is unaffected. (Carried forward unchanged from the v1 review; FR-1 was not one of the three FRs revised in v2.)
- **[Medium] Audit log row-key stability across Load-more pages still not carried into FR-8** — Story's Client State Notes say: "`AuditLogEntry` has no `id` — synthesize a stable row key (e.g. `occurred_at` + `request_id` + index) rather than using the array index alone across appended pages." FR-8 was rewritten in v2 (to add the OD-1/OD-2 resolutions) but the rewrite still does not mention this instruction. AD-AC8's "Load more" appends pages onto an already-rendered list, which is exactly the failure mode the story called out by name. AC coverage is unaffected since AD-AC8 doesn't literally require it, but this is a specific story instruction that had a second opportunity to be folded into FR-8 in this revision and was not.
- **[Medium] Scopes lifecycle (re-derive on refresh / clear on logout / never persist) still not carried into FR-9** — Story's Client State Notes say: "Scopes come from decoding the in-memory access token's `scopes` claim; re-derived on every refresh, cleared on logout, never persisted." FR-9 states navigation is derived from the decoded `scopes` claim but omits this lifecycle. XC-AC1 doesn't literally test it, so AC coverage is unaffected. (Carried forward unchanged from the v1 review; FR-9 was not one of the three FRs revised in v2.)

## Verdict Rationale

PASS: all 12 ACs are Covered (none Missing or Partially Covered), no Contradiction was found, and no Scope Creep was found. The four Open Decisions that blocked `PLAN_REVIEW` (OD-1–OD-4) are now `RESOLVED` in `docs/decisions/US-5.4-open-decisions.md` (v2) and are correctly, accurately incorporated into exactly FR-3, FR-5, and FR-8 as the specification's own revision note claims — no unresolved blocking Open Decision remains against this version. The five findings above (two Ambiguities, three Missing Edge Cases) are non-blocking: none is required by the literal text of any AC, so none forces a loop-back to `SPECIFICATION` or `CLARIFICATION`.
