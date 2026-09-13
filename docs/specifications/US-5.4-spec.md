---
artifact_type: specification
story: US-5.4
version: 2
status: APPROVED
created_at: "2026-09-13T07:12:38Z"
updated_at: "2026-09-13T13:30:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/evidence/US-5.4-clarification-report.md
    version: 2
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: docs/specifications/US-5.4-spec.md (v1)
---

# Specification: Admin Console (Frontend)

**Source:** docs/stories/US-5.4-admin-console-ui.md
**Story ID:** US-5.4
**Generated:** 2026-09-13
**Status:** Draft

> **Revision (v2):** `version: 1` of this specification (`status: APPROVED`)
> still carried four Open Decisions (OD-1–OD-4) as unresolved Open Questions.
> `PLAN_REVIEW` returned `BLOCKED` (`docs/reviews/plans/US-5.4-plan-review.md`)
> because the task breakdown tied OD-1–OD-4 directly to tasks T16, T19, T20,
> and T21, and `story-orchestrator` recorded a `HUMAN_REDIRECTED` transition
> back to `CLARIFICATION` (`docs/workflow/history.jsonl`,
> `2026-09-13T12:45:00Z`). A human stakeholder supplied an explicit
> resolution for each of the four items in that same session. Those
> resolutions are formalized in `docs/decisions/US-5.4-open-decisions.md`
> (version 2) and `docs/evidence/US-5.4-clarification-report.md` (version 2),
> and are incorporated directly into FR-3, FR-5, and FR-8 below, replacing
> the four bracketed forward-references those FRs carried in v1. Open
> Questions no longer carries OD-1–OD-4; see
> [Decisions Resolved by Human (2026-09-13)](#decisions-resolved-by-human-2026-09-13).
> FR-3, FR-5, and FR-8 are the only Functional Requirements whose text
> changed; all other sections are otherwise unchanged from v1.

## Summary

This spec covers the frontend admin console for the Customer Portal: a user list with filters and cursor pagination, user detail with `ETag` capture, create user, edit user (reason-gated, `If-Match`-protected), role management as an independent save path, user deactivation and invite resend, an audit log viewer with filters and cursor pagination, and scope-derived admin navigation — plus the client-side validation, problem+json error rendering, and network/server-failure handling common to every screen in this Story. It makes no backend, API, or database change; it consumes only already-shipped EPIC-3 endpoints.

## Background

As an administrator, the actor wants to manage users, assign roles, and review the audit log through a real web UI, so that EPIC-3's backend admin/audit capabilities (US-3.1 manage users, US-3.2 manage roles, US-3.3 view audit information) are usable end-to-end, not just through raw API calls. This Story reuses US-5.1's shared frontend infrastructure (API client, auth store, route guards) and US-5.2's response-header/`ETag` capability, and was originally drafted as "Slice B" of US-5.2 before being split out because the two share no screens and no permission model. Per the source's own Assumption #8, `API_DESIGN` and `DB_DESIGN` are `NOT_APPLICABLE` — this Story is a pure frontend consumer of an already-delivered backend contract.

**Net-new infrastructure note (not a reuse):** per the clarification report's Dependency Check, decoding the access token's `scopes` claim client-side (FR-9) is new work this Story adds, not an existing US-5.1 pattern being reused — no JWT-decoding dependency exists yet in `frontend/package.json`, no scopes/decoding logic exists yet in `frontend/src/store`, and `ProtectedRoute.tsx` currently gates on authentication only, with no scope awareness. A spec-writer/planner should treat FR-9 as new client-side infrastructure to build, not a call into something already shipped.

## Functional Requirements

### FR-1: User List

On the user list screen, an admin holding `users:read` sees `GET /admin/users` rendered as a list of each returned user's `email`, `display_name`, `status`, `roles`, `created_at`, and `last_login_at`. The `q`, `status`, and `role` filters each re-issue the request and reset the cursor. Per the clarification report's resolution of the source's own Open Question 1 (the value set is documented at `docs/designs/api/US-3.1-openapi.yaml:402-404`), the `status` filter's options are the fixed set `invited`, `active`, `deactivated` — this is not a free-text field. A non-null `next_cursor` in the response drives a "Load more" control that appends the next page to the list already shown; no total count or page number is displayed anywhere on this screen.

**Derived from:** AD-AC1

### FR-2: User Detail Captures the ETag

Opening a user calls `GET /admin/users/{id}`. The response's `ETag` header is captured into client state, keyed by user id per the source's Client State Notes. That captured `ETag` is sent as the `If-Match` header on the next `PATCH /admin/users/{id}` request for the same user (FR-4).

**Derived from:** AD-AC2

### FR-3: Create User

An admin holding `users:write` submits a create-user form collecting exactly `email`, `display_name`, and `roles`; no password field is present anywhere in the form. The `roles` field's selectable options are sourced from `GET /admin/roles` — the same role catalogue, and the same query, that FR-5's role-replacement control uses — rather than free text (Resolution OD-4); this prevents an admin from creating an under-permissioned account via a typo, since the create-user backend path silently drops any role name it does not recognize rather than rejecting the request. Submitting calls `POST /admin/users` with exactly those three fields. On `201`, the admin lands on the new user's detail screen.

**Derived from:** AD-AC3; role-picker source per Resolution OD-4

### FR-4: Edit User Requires a Reason

On the user-edit form, changing any editable field (`display_name`, `locale`, `timezone`, `avatar_url`) requires a non-empty `reason` before submission is allowed. Submitting calls `PATCH /admin/users/{id}` with the `If-Match` header carrying the `ETag` captured per FR-2 and the `reason`. A `412` response renders a conflict state rather than silently overwriting. An `immutable-field` problem response (see FR-5) renders that problem's own detail.

**Derived from:** AD-AC4

### FR-5: Roles Are a Separate Save Path

On the user-edit screen, `roles` is never included in the body of a `PATCH /admin/users/{id}` request. `GET /admin/roles` supplies the selectable catalogue for this screen's role control, which is a **multi-select showing the target replacement role set** — the full set of roles the user will hold if the save proceeds, matching `PUT /admin/users/{id}/roles`'s full-replacement semantics rather than an add/remove interaction (Resolution OD-3). Saving a role change calls `PUT /admin/users/{id}/roles` with the full replacement `roles` list. An admin lacking `roles:write` sees the role control disabled, and a server `403` still renders correctly if a role save is attempted anyway.

Role replacement sits behind an explicit confirmation dialog that computes, against the user's roles as currently loaded, and displays:
- **Gained roles** = `selected_roles − current_roles`
- **Lost roles** = `current_roles − selected_roles`

Save is disabled whenever neither set changed — i.e. whenever the selected role set is identical to the current role set (Resolution OD-3). An empty role selection is a separate, always-blocking case handled by FR-11's client-side validation (empty role list), independent of the gained/lost diff.

**Derived from:** AD-AC5; role-control interaction model and confirmation-dialog diff per Resolution OD-3

### FR-6: Deactivate and Resend Invite

From a user's detail screen, an admin deactivates the user by supplying a non-empty `reason`; this calls `POST /admin/users/{id}/deactivate`, and the returned status is reflected on the screen. Separately, a resend-invite control calls `POST /admin/users/{id}/resend-invite` and shows a generic confirmation.

**Derived from:** AD-AC6

### FR-7: No Delete Affordance

No control anywhere in the admin console issues `DELETE /admin/users/{id}`.

**Derived from:** AD-AC7

### FR-8: Audit Log Viewer

An admin holding `audit:read` sees `GET /admin/audit-logs` rendered with `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `outcome`, `request_id`, `ip`, and `user_agent` for each entry. Null values (`actor_role`, `outcome`, `ip`, `user_agent`, `actor_id`, `target_id` are all nullable per the source's Client State Notes) render an explicit placeholder rather than an empty cell; `event` renders verbatim as free text.

The `event` filter is a **free-text input** carrying an illustrative placeholder (e.g. "e.g. user_created, authz_denied") rather than a discoverable or enumerated list, since no catalogue endpoint exists for event names the way `GET /admin/roles` exists for role names (Resolution OD-2). The `actor_id`, `event`, `target_id`, `from`, and `to` filters are sent as query parameters, with the start-of-window parameter named literally `from`.

On first load, before the admin has changed anything, the `from`/`to` filters default to **the last 7 days** — `from = now − 7 days`, `to = now`, both in ISO 8601 UTC — and both values are pre-filled **visibly** in the date-picker inputs rather than applied silently behind the scenes (Resolution OD-1); this also satisfies `GET /admin/audit-logs` rejecting a request that is missing either bound. A non-null `next_cursor` drives "Load more"; no total count or page number is displayed anywhere on this screen.

**Derived from:** AD-AC8; default date-range window per Resolution OD-1; `event` filter input type per Resolution OD-2

### FR-9: Scope-Derived Admin Navigation

Admin navigation entries are derived from the `scopes` claim decoded client-side from the in-memory access token; an authenticated user whose token carries no admin scopes sees no admin navigation entry rendered. If such a user navigates directly to an admin route anyway, the server's `403` problem+json response is rendered as an explicit "not permitted" state — never a blank screen or an infinite spinner. An admin holding `users:read` but not `users:write` sees read screens render normally, with every write control rendered disabled.

**Derived from:** XC-AC1

### FR-10: problem+json Error Rendering

For any request in this Story that returns a 4xx `application/problem+json` response, the UI renders that response's detail (or a mapped, user-friendly message keyed by `type`) — with no raw JSON or stack trace. A `422` validation-failure response's `errors` array is mapped onto the matching form fields.

**Derived from:** XC-AC2

### FR-11: Client-Side Validation Before Submission

For any form in this Story, when a required field is empty or malformed (an invalid email shape, an empty `reason`, an empty role list), submission is blocked with a field-level error and no API call is made.

**Derived from:** XC-AC3

### FR-12: Network / Server Failure Handling

For any endpoint in this Story, a network error or a `5xx` response results in a retry-capable error state — never a blank screen, an indefinite spinner, or an unhandled exception.

**Derived from:** XC-AC4

## Non-Functional Requirements

- Client-side scope decoding is never treated as authorization; every privileged screen handles a server `403`.
- Destructive/irreversible actions (user deactivation, role replacement) sit behind an explicit confirmation naming the consequence.
- No audit-log row content (`ip`, `user_agent`, `request_id`) is written to the browser console in production builds.
- Full keyboard navigation and visible focus on every form and control; the audit table's cells are associated with their column headers (accessibility).
- Responsive from ~375px through desktop; the audit table scrolls horizontally within its own container rather than forcing page-level horizontal scroll.
- Every screen has an explicit loading state and an explicit error state.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Account/profile self-service, MFA enrollment — Story US-5.2.
- Support Tickets UI — Story US-5.3.
- User deletion (405 by design), attachments, agent ticket tooling.
- Any backend/API/DB change. This Story implements only against already-shipped backend endpoints; it does not add, modify, or design any API route, request/response contract, or database schema/table/column. `API_DESIGN` and `DB_DESIGN` are `NOT_APPLICABLE` for US-5.4, per Assumption #8.

**Derived from:** Out of Scope section of the source (backend-change bullet expanded per Assumption #8: "`API_DESIGN` / `DB_DESIGN` record `NOT_APPLICABLE`").

## Open Questions

None. All four Open Decisions raised by `us-clarifier` (`docs/decisions/US-5.4-open-decisions.md`, OD-1–OD-4) have been resolved by explicit human decision on 2026-09-13. See [Decisions Resolved by Human (2026-09-13)](#decisions-resolved-by-human-2026-09-13) below for the resolution text and where each lands in this specification.

## Decisions Resolved by Human (2026-09-13)

`version: 1` of this specification carried OD-1–OD-4 as unresolved Open Questions. `PLAN_REVIEW` returned `BLOCKED` because the task breakdown depended on them, and `story-orchestrator` redirected the story to `CLARIFICATION` (`docs/workflow/history.jsonl`, `2026-09-13T12:45:00Z`), where a human stakeholder supplied the following resolutions, each now incorporated into the FR named:

| OD | Resolution | Incorporated in |
|----|------------|------------------|
| OD-1 | Audit Log screen's default `from`/`to` window on first load: `from = now − 7 days`, `to = now`, ISO 8601 UTC, both pre-filled visibly in the date-picker inputs (not applied silently). | FR-8 |
| OD-2 | The `event` filter is a free-text input with an illustrative placeholder; no enumerated or discoverable list. | FR-8 |
| OD-3 | The role control is a multi-select showing the target replacement role set; the confirmation dialog computes and displays Gained roles (`selected − current`) and Lost roles (`current − selected`); save is disabled if neither set changed. | FR-5 |
| OD-4 | The Create User role picker is catalogue-driven, sourced from `GET /admin/roles` — the same source and query FR-5 uses for role replacement. | FR-3 |

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AD-AC1 | "Given an authenticated admin holding users:read on /admin/users Then GET /admin/users renders each user's email, display_name, status, roles, created_at and last_login_at And q / status / role filters re-request the list and reset the cursor And a non-null next_cursor drives a \"Load more\" that appends the next page And no total count or page number is displayed anywhere" | FR-1 |
| AD-AC2 | "Given an admin opening a user Then GET /admin/users/{id} is called and the ETag response header is captured into client state And that ETag is sent as If-Match on the next PATCH for that user" | FR-2 |
| AD-AC3 | "Given an admin holding users:write When they submit email, display_name and roles Then POST /admin/users is called with exactly those fields and no password field is present anywhere in the form And on 201 they land on the new user's detail screen" | FR-3 |
| AD-AC4 | "Given the user-edit form When any editable field (display_name, locale, timezone, avatar_url) is changed Then a non-empty reason is required before submission is allowed And PATCH /admin/users/{id} is called with If-Match and the reason And a 412 shows a conflict state; an immutable-field problem renders its detail" | FR-4 |
| AD-AC5 | "Given the user-edit screen Then roles are never included in the PATCH body When the admin changes role assignment and saves Then GET /admin/roles supplies the selectable catalogue and PUT /admin/users/{id}/roles is called with the full replacement list And an admin lacking roles:write sees the role control disabled, and a server 403 still renders correctly if it is attempted And role replacement sits behind an explicit confirmation naming what the user will gain and lose" | FR-5 |
| AD-AC6 | "Given an admin on a user's detail screen When they deactivate the user with a non-empty reason Then POST /admin/users/{id}/deactivate is called and the returned status is reflected When they resend the invite Then POST /admin/users/{id}/resend-invite is called and a generic confirmation is shown" | FR-6 |
| AD-AC7 | "Given any admin screen Then no control anywhere issues DELETE /admin/users/{id}" | FR-7 |
| AD-AC8 | "Given an admin holding audit:read on /admin/audit-logs Then GET /admin/audit-logs renders occurred_at, actor_id, actor_role, event, target_id, outcome, request_id, ip and user_agent And null values render an explicit placeholder rather than an empty cell And the actor_id / event / target_id / from / to filters are sent as query parameters, with the start-of-window parameter named \"from\" And a non-null next_cursor drives \"Load more\"; no total count or page number is displayed anywhere" | FR-8 |
| XC-AC1 | "Given an authenticated user whose access token carries no admin scopes Then no admin navigation entry is rendered Given they navigate directly to an admin route anyway Then the server's 403 problem+json is rendered as an explicit \"not permitted\" state, never a blank screen or an infinite spinner Given an admin holding users:read but not users:write Then read screens render normally and every write control is disabled" | FR-9 |
| XC-AC2 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | FR-10 |
| XC-AC3 | "Given any form in this Story When a required field is empty or malformed (invalid email shape, empty reason, empty role list) Then submission is blocked with a field-level error and no API call is made" | FR-11 |
| XC-AC4 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | FR-12 |
</content>
