---
id: US-5.4
epic: EPIC-5
title: Admin Console (Frontend)
slug: admin-console-ui
priority: MEDIUM
track: frontend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: 27
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/27
  last_synced_at: "2026-09-07T00:00:00Z"
---

# Epic 5 — Frontend: Admin Console

**Story ID:** US-5.4
**Project:** Customer Portal
**Depends on:** US-5.1 (auth store, API client, route guards, problem+json rendering) and **US-5.2** (the API client's response-header/ETag support, US-5.2 Assumption #2)
**Split note:** originally drafted as "Slice B" of US-5.2; peeled out because the two share no screens and no permission model.

## User Story
As an administrator,
I want to manage users, assign roles, and review the audit log through a real web UI,
So that EPIC-3 (US-3.1/3.2/3.3) is usable end-to-end, not just through raw API calls.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Stack | Reuses US-5.1's `frontend/` — same API client, auth store, guards | Adds screens, not infrastructure |
| 2 | **Permission gating source** | Scopes are read from the **JWT `scopes` claim, decoded (not verified) client-side** from the in-memory access token | `LoginResponse`/`RefreshResponse` carry only `access_token`/`expires_in`/`mfa_enrollment_deadline` — no user object and no roles list. `app/core/security.py` puts `sub` and `scopes` in the token. This amends US-5.1's "current user from `UserRead`" note |
| 3 | Gating is **cosmetic only** | Hiding an admin nav item never substitutes for handling a 403 — every admin screen renders the server's 403 problem+json | Client-decoded claims are advisory; the backend is the authority |
| 4 | **ETag / If-Match** | `ETag` is captured from `GET /admin/users/{id}` and echoed as `If-Match` on the next `PATCH`; a 412 renders a "changed by someone else — reload" conflict state | `ETag` arrives as a **response header**. The client capability this needs is delivered by US-5.2 Assumption #2 |
| 5 | **Role editing is a second save path** | The user-edit screen has two independent saves: field edits → `PATCH /admin/users/{id}` (`users:write`, requires `reason`), roles → `PUT /admin/users/{id}/roles` (`roles:write`) | `roles` is in `ADMIN_USER_IMMUTABLE_FIELD_NAMES` — sending it to `PATCH` is an `immutable-field` error. Two endpoints, two permissions, one screen |
| 6 | **No delete affordance** | No "delete user" control exists anywhere in the UI | `DELETE /admin/users/{id}` returns **405 for every authenticated caller by design** (FR-17); erasure belongs to the US-1.4 retention job |
| 7 | Pagination | Cursor "Load more" on the user list and the audit log | Both are `items` + `next_cursor` with **no total count** — page numbers are not derivable |
| 8 | No backend changes | `API_DESIGN` / `DB_DESIGN` record `NOT_APPLICABLE` | Purely a frontend consuming an already-delivered contract |

## In Scope
- User list (`GET /admin/users`) with `q` / `status` / `role` filters and cursor "Load more"
- User detail (`GET /admin/users/{id}`, capturing `ETag`)
- Create user (`POST /admin/users`: `email`, `display_name`, `roles` — **no password field**)
- Edit user (`PATCH /admin/users/{id}` with `If-Match` and a **required `reason`**)
- Deactivate user (`POST /admin/users/{id}/deactivate`, required `reason`)
- Resend invite (`POST /admin/users/{id}/resend-invite`)
- Role catalogue (`GET /admin/roles`) and role replacement (`PUT /admin/users/{id}/roles`)
- Audit log viewer (`GET /admin/audit-logs`) with `actor_id` / `event` / `target_id` / `from` / `to` filters and cursor "Load more"
- Scope-derived admin navigation, with server 403 still handled on every screen

## Out of Scope
- Account/profile self-service, MFA enrollment — Story **US-5.2**
- Support Tickets UI — Story **US-5.3**
- User deletion (405 by design), attachments, agent ticket tooling
- Any backend/API/DB change

## API Contract (existing backend — reference only, not designed by this Story)
| Method | Path | Scope | Request | Success |
|---|---|---|---|---|
| GET | `/api/v1/admin/users` | `users:read` | `?q=&status=&role=&cursor=&limit=25` | 200 `UserListResponse` |
| GET | `/api/v1/admin/users/{id}` | `users:read` | — | 200 `UserRead` + **`ETag` header** |
| POST | `/api/v1/admin/users` | `users:write` | `{email, display_name, roles}` | 201 `UserRead` + `ETag` |
| PATCH | `/api/v1/admin/users/{id}` | `users:write` | `{display_name?, locale?, timezone?, avatar_url?, reason}` + `If-Match` | 200 `UserRead` + `ETag` |
| POST | `/api/v1/admin/users/{id}/deactivate` | `users:write` | `{reason}` | 200 `UserRead` |
| POST | `/api/v1/admin/users/{id}/resend-invite` | `users:write` | — | 202 `ResendInviteResponse` |
| DELETE | `/api/v1/admin/users/{id}` | (any) | — | **405 always — never called by the UI** |
| GET | `/api/v1/admin/roles` | `users:read` | — | 200 `{roles: [{name, permissions}]}` |
| PUT | `/api/v1/admin/users/{id}/roles` | `roles:write` | `{roles: [name]}` | 200 `{roles}` |
| GET | `/api/v1/admin/audit-logs` | `audit:read` | `?actor_id=&event=&target_id=&from=&to=&cursor=&limit=50` | 200 `AuditLogListResponse` |

`UserRead`: `id`, `email`, `display_name`, `status`, `roles`, `created_at`, `last_login_at`.
`AuditLogEntry`: `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `request_id`, `ip`, `user_agent`, `outcome` — **no `id` field**.
Audit's start-of-window query parameter is literally **`from`** (aliased in the router), not `from_`.

## Client State Notes
- **Scopes** come from decoding the in-memory access token's `scopes` claim; re-derived on every refresh, cleared on logout, never persisted.
- **ETags** are held per-resource in query cache metadata, keyed by user id.
- `AuditLogEntry` has **no `id`** — synthesize a stable row key (e.g. `occurred_at` + `request_id` + index) rather than using the array index alone across appended pages.
- `event` is free text; `actor_role`, `outcome`, `ip`, `user_agent`, `actor_id`, `target_id` are all nullable — every column renders an explicit placeholder rather than blank.
- `UserRead.status` and `UserRead.roles` are plain strings — an unrecognized value renders verbatim.
- A single admin may hold `users:read` without `users:write` or `roles:write`; each control is gated on its own scope, independently.

## Acceptance Criteria

**AD-AC1 — User list**
```gherkin
Given an authenticated admin holding users:read on /admin/users
Then GET /admin/users renders each user's email, display_name, status, roles, created_at and last_login_at
And q / status / role filters re-request the list and reset the cursor
And a non-null next_cursor drives a "Load more" that appends the next page
And no total count or page number is displayed anywhere
```

**AD-AC2 — User detail captures the ETag**
```gherkin
Given an admin opening a user
Then GET /admin/users/{id} is called and the ETag response header is captured into client state
And that ETag is sent as If-Match on the next PATCH for that user
```

**AD-AC3 — Create user**
```gherkin
Given an admin holding users:write
When they submit email, display_name and roles
Then POST /admin/users is called with exactly those fields and no password field is present anywhere in the form
And on 201 they land on the new user's detail screen
```

**AD-AC4 — Edit user requires a reason**
```gherkin
Given the user-edit form
When any editable field (display_name, locale, timezone, avatar_url) is changed
Then a non-empty reason is required before submission is allowed
And PATCH /admin/users/{id} is called with If-Match and the reason
And a 412 shows a conflict state; an immutable-field problem renders its detail
```

**AD-AC5 — Roles are a separate save path**
```gherkin
Given the user-edit screen
Then roles are never included in the PATCH body
When the admin changes role assignment and saves
Then GET /admin/roles supplies the selectable catalogue and PUT /admin/users/{id}/roles is called with the full replacement list
And an admin lacking roles:write sees the role control disabled, and a server 403 still renders correctly if it is attempted
And role replacement sits behind an explicit confirmation naming what the user will gain and lose
```

**AD-AC6 — Deactivate and resend invite**
```gherkin
Given an admin on a user's detail screen
When they deactivate the user with a non-empty reason
Then POST /admin/users/{id}/deactivate is called and the returned status is reflected
When they resend the invite
Then POST /admin/users/{id}/resend-invite is called and a generic confirmation is shown
```

**AD-AC7 — No delete affordance**
```gherkin
Given any admin screen
Then no control anywhere issues DELETE /admin/users/{id}
```

**AD-AC8 — Audit log**
```gherkin
Given an admin holding audit:read on /admin/audit-logs
Then GET /admin/audit-logs renders occurred_at, actor_id, actor_role, event, target_id, outcome, request_id, ip and user_agent
And null values render an explicit placeholder rather than an empty cell
And the actor_id / event / target_id / from / to filters are sent as query parameters, with the start-of-window parameter named "from"
And a non-null next_cursor drives "Load more"; no total count or page number is displayed anywhere
```

**XC-AC1 — Scope-derived navigation**
```gherkin
Given an authenticated user whose access token carries no admin scopes
Then no admin navigation entry is rendered
Given they navigate directly to an admin route anyway
Then the server's 403 problem+json is rendered as an explicit "not permitted" state, never a blank screen or an infinite spinner
Given an admin holding users:read but not users:write
Then read screens render normally and every write control is disabled
```

**XC-AC2 — problem+json errors**
```gherkin
Given any request in this Story returns a 4xx application/problem+json body
Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace
And a 422 validation-failed maps its errors array onto the matching form fields
```

**XC-AC3 — Client-side validation**
```gherkin
Given any form in this Story
When a required field is empty or malformed (invalid email shape, empty reason, empty role list)
Then submission is blocked with a field-level error and no API call is made
```

**XC-AC4 — Network / server failure**
```gherkin
Given a network error or 5xx from any endpoint in this Story
Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception
```

## Non-Functional / Security Requirements
- Client-side scope decoding is **never** treated as authorization; every privileged screen handles a server 403.
- Destructive/irreversible actions (user deactivation, role replacement) sit behind an explicit confirmation naming the consequence.
- No audit-log row content (`ip`, `user_agent`, `request_id`) is written to the browser console in production builds.
- Full keyboard navigation and visible focus on every form and control; the audit table's cells are associated with their column headers (a11y).
- Responsive from ~375px through desktop; the audit table scrolls horizontally within its own container rather than forcing page-level horizontal scroll.
- Every screen has an explicit loading state and an explicit error state.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| AD-AC1, AD-AC3, AD-AC6, AD-AC8 | Component/integration tests against the mocked API layer (MSW or equivalent) | `[gate]` |
| AD-AC2 | Test asserting the `ETag` **response header** is captured and echoed as `If-Match` | `[gate]` |
| AD-AC4 | Test asserting `reason` is required and that a 412 renders a conflict state | `[gate]` |
| AD-AC5 | Test asserting `roles` never appears in a PATCH body and that role saves hit `PUT .../roles` | `[gate]` |
| AD-AC7 | Static/unit assertion that no code path issues `DELETE /admin/users/{id}` | `[gate]` |
| XC-AC1 | Tests for a scope-less token, a read-only token, and a forced server 403 | `[gate]` |
| XC-AC2–4 | Tests per screen for problem+json, validation, and network/5xx failure | `[gate]` |
| a11y bar | Automated a11y check (e.g. axe) on the user-list, user-edit and audit screens | `[gate]` |

## Open Questions
1. `UserRead.status` has no documented value set anywhere in the codebase (plain `str`). Confirm whether the list filter's `status` options should be hard-coded in the UI or left as free text.
2. The audit log's `event` filter is free text with no discoverable vocabulary. Confirm free-text input, or raise a backend Story to expose an event catalogue.
3. Role replacement is a full **replace**, not a delta. Confirm the UI should present it as a multi-select showing the resulting final set (rather than add/remove actions), so the destructive nature is visible.
