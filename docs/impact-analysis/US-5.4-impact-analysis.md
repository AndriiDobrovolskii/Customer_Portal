---
artifact_type: impact_analysis
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T11:00:00Z"
updated_at: "2026-09-13T16:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.4-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.4-design-review.md
    version: 2
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: docs/impact-analysis/US-5.4-impact-analysis.md (v1)
---

# Impact Analysis: Admin Console (Frontend)

**Story ID:** US-5.4
**Track:** frontend (per `docs/stories/US-5.4-admin-console-ui.md` front matter)

> **Revision (v2):** `version: 1` of this artifact was produced against
> specification v1 (`status: APPROVED` at the time, now `SUPERSEDED`), whose
> Open Questions still carried OD-1–OD-4 as `OPEN`. `PLAN_REVIEW` returned
> `BLOCKED` over those same four items and `story-orchestrator` redirected
> the story to `CLARIFICATION`
> (`docs/workflow/history.jsonl`, `2026-09-13T12:45:00Z`), where a human
> stakeholder resolved all four (`docs/decisions/US-5.4-open-decisions.md`,
> v2). Specification v2 incorporates those resolutions into FR-3, FR-5, and
> FR-8 only; every other FR, and the spec's Out of Scope section, is
> unchanged from v1 — confirmed against the spec's own revision note and
> independently against specification review v2
> (`docs/reviews/specifications/US-5.4-spec-review.md`, v2, verdict `PASS`,
> "Scope Creep: None found"). `API_DESIGN`/`DB_DESIGN` were re-run against
> spec v2 and again recorded `NOT_APPLICABLE`
> (`docs/reviews/designs/US-5.4-design-review.md`, v2, verdict
> `NOT_APPLICABLE`). Re-surveying the current `frontend/src/` tree for this
> revision (confirmed: still no `admin`-prefixed file exists anywhere) found
> **no change to the affected-file set itself** — every file identified in
> v1 remains affected for the same structural reason (new screen, new hook,
> new API function, the `authStore`/`AppShell` scope-navigation change, the
> `httpClient.ts` `PUT` wrapper). What changed is that four behaviors
> previously recorded as *pending an Open Decision* are now recorded as
> *resolved, specific requirements* against the same files: the Create User
> role picker (§1, `api/` and `screens/` rows, OD-4), the role-replacement
> multi-select and its gained/lost/disable-when-unchanged confirmation
> logic (§1, `screens/` row, OD-3), the Audit Log default `from`/`to` window
> (§1, `hooks/`/`screens/` rows, OD-1), and the `event` filter's input type
> (§1, `screens/` row, OD-2). Section 5 below itemizes each delta from v1
> explicitly. All other sections (§2 Cross-Module Ripple, §3
> Migration/Schema Impact, §4 Test-Surface Impact) are unchanged in
> substance from v1; §3 in particular is reconfirmed unchanged since none of
> the four resolutions adds, modifies, or implies any backend/API/DB change.

**Scope note:** `API_DESIGN` and `DB_DESIGN` both returned `NOT_APPLICABLE`, confirmed by
`docs/reviews/designs/US-5.4-design-review.md` (v2, `NOT_APPLICABLE`) — this is a
frontend-only story consuming nine already-shipped `/api/v1/admin/*` endpoints (designed
and shipped under US-3.1/US-3.2/US-3.3). This survey covers the `frontend/` blast radius
against `AGENTS.md` §3's "Frontend (`frontend/`)" layer table (`screens/`, `components/`,
`hooks/`, `store/`, `api/`, `routes/`, `layouts/`). Backend files (`app/modules/roles/service.py`,
`app/modules/audit/service.py`) are named below only as the (unmodified) contract this
story's frontend code must call correctly — confirmed directly by reading them, per
`docs/decisions/US-5.4-open-decisions.md`'s own citations — they are not affected files.
Confirmed directly against the current `frontend/src/` tree: no `admin`-prefixed file
exists anywhere today, and none of `api/types.ts`, `store/authStore.tsx`, `routes/AppRoutes.tsx`,
or `layouts/AppShell.tsx` contains any admin/role/audit/scope-decoding reference. Every
file below is either wholly new or an additive change to an existing file; nothing in this
Story's scope requires deleting or replacing an existing screen/route/hook the way US-5.3's
FR-15 home-route move did.

## 1. Affected Files / Modules / Layers

### `api/` layer

| File | Reason |
|---|---|
| `frontend/src/api/types.ts` (modify) | New DTOs for all nine endpoints this Story consumes, none of which exist today (confirmed: the current file's newest block is US-5.3's `TicketRead`/etc.). Needed: an admin-scoped user shape distinct from the existing bare `UserRead` (`{id, email}`, line 6) — `AdminUserRead` (`id`, `email`, `display_name`, `status: string`, `roles: string[]`, `created_at`, `last_login_at`, FR-1/FR-2), `AdminUserListResponse` (`items`/`next_cursor`, FR-1), `CreateAdminUserRequest` (`email`/`display_name`/`roles`, FR-3 — `roles` is now definitively catalogue-sourced per Resolution OD-4, not free text), `UpdateAdminUserRequest` (`display_name?`/`locale?`/`timezone?`/`avatar_url?`/`reason`, FR-4), `DeactivateUserRequest` (`reason`, FR-6), `ResendInviteResponse` (FR-6), `RoleRead`/`RoleListResponse` (`{roles: [{name, permissions}]}`, FR-5), `ReplaceUserRolesRequest`/`ReplaceUserRolesResponse` (`{roles: [name]}`, FR-5), `AuditLogEntry` (`occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `request_id`, `ip`, `user_agent`, `outcome` — explicitly **no `id`**, FR-8) and `AuditLogListResponse` (`items`/`next_cursor`, FR-8). `AdminUserRead.status`/`.roles` stay plain `string`/`string[]` (never a union), per the story's own "an unrecognized value renders verbatim" rule — the filter's separate fixed `invited`/`active`/`deactivated` set (FR-1) is a UI-only constant for the `<select>`, not a change to this field's type, the same DTO-field-stays-`string`-vs-filter-union split `types.ts` already has today between `TicketRead.status: string` (line 180) and the separate `TicketStatus` union (line 173) used only by `TicketListScreen.tsx`'s filter. |
| `frontend/src/api/adminApi.ts` (new) | No file for the `/admin/*` path family exists today (`authApi.ts`, `profileApi.ts`, `mfaApi.ts`, `accountApi.ts`, `supportApi.ts` each cover only their own prefix — confirmed by reading `supportApi.ts` in full). Needs one typed function per operation: `listUsers` (`GET /admin/users` with `q`/`status`/`role`/`cursor`/`limit`, FR-1), `getUser` (`GET /admin/users/{id}`, returning the `ETag` header — must use `httpClient.ts`'s header-carrying path rather than plain `httpGet<T>`, FR-2), `createUser` (`POST /admin/users`, FR-3), `updateUser` (`PATCH /admin/users/{id}` with `If-Match`, FR-4 — reuses the existing `httpPatch` verb), `deactivateUser` (`POST /admin/users/{id}/deactivate`, FR-6), `resendInvite` (`POST /admin/users/{id}/resend-invite`, FR-6), `listRoles` (`GET /admin/roles`, FR-3/FR-5 — now a definite, unconditional dependency of both create-user and role-replacement per Resolutions OD-4/OD-3), `replaceUserRoles` (`PUT /admin/users/{id}/roles`, FR-5 — see the `httpClient.ts` row below, no PUT wrapper exists), `listAuditLogs` (`GET /admin/audit-logs` with `actor_id`/`event`/`target_id`/`from`/`to`/`cursor`/`limit`, FR-8, and the parameter object's key must literally be `from`, not `from_`, per the story's own note; the `from`/`to` values on first call are the Resolution OD-1 default — see the `hooks/` row below). |
| `frontend/src/api/httpClient.ts` (modify) | **Definite, not contingent on any Open Decision.** FR-5's `PUT /admin/users/{id}/roles` needs a `PUT` verb wrapper. Confirmed by reading the full file: `HttpMethod` already includes `"PUT"` in its union (line 16), but no `httpPut<T>()` function is exported — only `httpGet`, `httpPost`, `httpDelete`, `httpPatch` (lines 148-231) exist. This is a same-shape additive extension to the pattern `httpPatch` itself established in US-5.2 (its own header comment, lines 172-178, calls out `performRequest`/`parseResponse` as untouched by that addition) — no existing exported function's signature changes. |
| `frontend/src/api/errorNormalization.ts` (checked, not modified) | AD-AC4's "an immutable-field problem renders its detail" and FR-10's generic problem+json handling are both already satisfied by the existing `detail`-first branch in `normalizeApiError()` (lines 51-75) — confirmed no admin endpoint's error shape deviates from the RFC 7807 envelope already handled (unlike US-5.1's Register endpoint, which needed the two bespoke non-RFC7807 branches this file also carries). No admin-specific field-error array shape beyond the existing `errors: [{field, message}]` extraction (FR-10's 422 mapping) is implied by any FR. |

### `store/` layer

| File | Reason |
|---|---|
| `frontend/src/store/authStore.tsx` (modify) | FR-9's "net-new infrastructure" note in the approved spec's Background section is explicit and independently confirmed here: no `scopes`/decoding logic exists in `frontend/src/store` today (confirmed by reading the full file — `AuthStateSeed`, line 15, has `accessToken`/`isAuthenticated`/`user`/`mfaToken`/`mfaEnrollmentDeadline`/`mfaEnabled` only, no `scopes`). Needs a `scopes: string[]` field on `AuthStateSeed`, derived by decoding the `scopes` claim out of `accessToken`'s JWT payload (decode-only, never verified client-side per Assumption #2/#3) on `SET_SESSION` and `TOKEN_REFRESHED` (the two actions that change `accessToken`, per the reducer at lines 48-77), and reset to `[]` on `CLEAR_SESSION` — matching the story's Client State Notes ("re-derived on every refresh, cleared on logout, never persisted"), which spec review (v1 and v2, Missing Edge Cases, Medium) flags as absent from FR-9's own prose but not from the story's own binding text. FR-9 itself is unchanged between spec v1 and v2. |
| `frontend/src/store/decodeTokenScopes.ts` (new; exact filename is a `planner`/`frontend-builder` naming call) | A pure, dependency-light JWT-claims decoder (base64url-decode the payload segment, `JSON.parse`, read `scopes`) has no home in the existing `store/` file structure and is exactly the kind of pure logic this codebase already separates out for independent unit testing (parallel to `errorNormalization.ts` sitting apart from `httpClient.ts`). Colocated under `store/` rather than `api/` because it never performs I/O and `authStore.tsx`'s own header comment states `store/` "imports neither `api/` nor `hooks/` directly." |
| `frontend/package.json` (flagged, not necessarily modified) | **Decision point, not resolved here — not one of OD-1–OD-4 and not affected by their resolution.** No `jwt-decode`/`jose`/similar dependency exists today (confirmed: `dependencies` lists only `@tanstack/react-query`, `qrcode.react`, `react`, `react-dom`, `react-hook-form`, `react-router-dom`). Decoding a JWT payload can be done with a two-line hand-rolled `atob`/base64url helper (no new dependency) or with a small library. Either choice satisfies FR-9; only the library choice touches this file. Flagged per this Story's own US-5.3 precedent (that story's impact analysis flagged and then closed an analogous `package.json` question against OD-5) so `planner` does not have to rediscover that no such dependency exists yet. |

### `routes/` layer

| File | Reason |
|---|---|
| `frontend/src/routes/AppRoutes.tsx` (modify) | FR-1 through FR-6, FR-8 need four new routes registered inside the existing `<ProtectedRoute><AppShell /></ProtectedRoute>` group (same shape as `/tickets`, `/sessions`, `/settings/*`, lines 71-89 today): a list route (`/admin/users`), a create route (`/admin/users/new`), a detail route (`/admin/users/:id` — the second dynamic-segment route in this file, after `/tickets/:id`), and an audit route (`/admin/audit-logs`). Per Assumption #3/XC-AC1, these routes are **not** wrapped in any additional scope-gating guard beyond the existing auth-only `ProtectedRoute` — XC-AC1's second clause requires a scope-less user who navigates directly to render the server's 403, not a client-side redirect, so no new route-guard component is implied by any AC. |
| `frontend/src/routes/ProtectedRoute.tsx` (checked, not modified) | Confirmed by reading the full file: gates on `isAuthenticated` only (line 43), no scope awareness. Per the row above, this Story's ACs require exactly that — an authenticated non-admin still reaches the route and receives the server's 403 (rendered by the screen, FR-9/FR-10), not a client-side block. No change needed. |

### `layouts/` layer

| File | Reason |
|---|---|
| `frontend/src/layouts/AppShell.tsx` (modify) | FR-9: "Admin navigation entries are derived from the `scopes` claim." Today this file's `<nav>` (line 30) has exactly one static link (`/tickets`, added by US-5.3). Needs two new conditionally-rendered links (Users, Audit Log) gated on the presence of the relevant scope(s) read off `useAuthStore()` — the same store-read-only pattern this file already uses for `mfaEnrollmentDeadline` (line 25), extended to read the new `scopes` field from the `store/authStore.tsx` row above. |

### `hooks/` layer (all new — no existing hook covers any admin/audit operation)

| File | Reason |
|---|---|
| `frontend/src/hooks/useAdminUsers.ts` (new) | FR-1: wraps `adminApi.listUsers` in a cursor-paginated query, parameterized by `q`/`status`/`role`, following `useTickets.ts`'s `useInfiniteQuery` shape (that file's full 13 lines) — the closest existing precedent for "filters reset the cursor" (AD-AC1). |
| `frontend/src/hooks/useAdminUser.ts` (new) | FR-2: wraps `GET /admin/users/{id}`, capturing the response's `ETag` header into TanStack Query cache metadata keyed by user id — the same `ETAG_QUERY_KEY`-in-cache pattern `useProfileUpdate.ts` already established for US-5.2's single-resource ETag (that file's full 49 lines), generalized here to be keyed per user id rather than a single fixed key. |
| `frontend/src/hooks/useCreateAdminUser.ts` (new) | FR-3: wraps `adminApi.createUser`; on `201` the caller (screen) navigates to the new user's detail route using the response body's `id` — no password field anywhere in this hook's payload type (`CreateAdminUserRequest` above already excludes it). |
| `frontend/src/hooks/useUpdateAdminUser.ts` (new) | FR-4: wraps `adminApi.updateUser`, reading the cached `ETag` from `useAdminUser.ts`'s query key as the outgoing `If-Match`, and setting a `conflict` flag on a `412` — directly mirrors `useProfileUpdate.ts`'s `onError`/`conflict` state shape (lines 39-44 of that file). Also owns rendering the `immutable-field` problem's `detail` on submission of a `roles`-bearing body — moot here, since FR-5 guarantees `roles` is never in this hook's payload. |
| `frontend/src/hooks/useAdminRoles.ts` (new) | FR-3 (per Resolution OD-4, now definite) and FR-5 (per Resolution OD-3, unconditional): wraps `GET /admin/roles`, the shared role-catalogue query both the create-user form and the role-replacement control read unconditionally — a `useQuery`, not paginated (no cursor in the story's API Contract table for this endpoint). |
| `frontend/src/hooks/useReplaceUserRoles.ts` (new) | FR-5: wraps `adminApi.replaceUserRoles` (`PUT`, full replacement); must invalidate or update `useAdminUser.ts`'s query so the detail screen reflects the new role set without a manual reload — the same "one hook invalidates another hook's query key" shape `useReplyToTicket.ts` already established against `useTicketDetail.ts` in US-5.3. |
| `frontend/src/hooks/useDeactivateAdminUser.ts` (new) | FR-6: wraps `adminApi.deactivateUser`; the returned `UserRead.status` must update the detail screen's displayed status without a full refetch, matching FR-6's "the returned status is reflected." |
| `frontend/src/hooks/useResendInvite.ts` (new) | FR-6: wraps `adminApi.resendInvite`; success renders a generic confirmation only (the endpoint's `202` body per the story's API Contract table is not itself displayed). |
| `frontend/src/hooks/useAuditLogs.ts` (new) | FR-8: wraps `adminApi.listAuditLogs` in a cursor-paginated query parameterized by `actor_id`/`event`/`target_id`/`from`/`to`, same `useInfiniteQuery` shape as `useAdminUsers.ts`/`useTickets.ts`. **Resolution OD-1 (resolved in this revision):** on initial mount, before any filter is chosen, this hook's default `from`/`to` must be `now − 7 days`/`now`, ISO 8601 UTC — required because `GET /admin/audit-logs` 422s (`range-too-wide`) if either bound is missing (`app/modules/audit/service.py:124-129`, per OD-1's own citation). This default must be computed once and handed to `AdminAuditLogScreen.tsx` for visible pre-fill (see that row below) rather than applied silently inside the hook only. |

### `screens/` layer (all new)

| File | Reason |
|---|---|
| `frontend/src/screens/AdminUserListScreen.tsx` (new; exact name is a `planner`/`frontend-builder` naming call) | AD-AC1/FR-1: `/admin/users` — `q`/`status`/`role` filters (status as the fixed `invited`/`active`/`deactivated` set per the approved spec's FR-1, not free text), cursor "Load more," no total count anywhere, an unrecognized `status`/`roles` value rendered verbatim (the story's Client State Notes; flagged by spec review as not literally required by any AC, but present in binding Client State Notes this screen must still honor). |
| `frontend/src/screens/AdminUserCreateScreen.tsx` (new) | AD-AC3/FR-3: `/admin/users/new` — `email`/`display_name`/`roles` fields, no password field anywhere. **Resolution OD-4 (resolved in this revision):** the `roles` field's selectable options are sourced from `useAdminRoles.ts`'s catalogue (`GET /admin/roles`) unconditionally, not free text — this is now the spec's own FR-3 text, not a pending choice, because the create-user backend path silently drops any unrecognized role name (`app/modules/roles/service.py:231-236`) rather than rejecting the request, so a catalogue-only picker is required to prevent an under-permissioned account via typo. Lands on the new user's detail screen on `201`. |
| `frontend/src/screens/AdminUserDetailScreen.tsx` (new) | AD-AC2/AD-AC4/AD-AC5/AD-AC6/AD-AC7/FR-2/FR-4/FR-5/FR-6/FR-7: `/admin/users/:id` — the single largest surface in this Story. Hosts: the field-edit form (`display_name`/`locale`/`timezone`/`avatar_url`, required non-empty `reason`, `If-Match`, 412 conflict state, immutable-field detail rendering — same two-form-on-one-screen shape `ProfileScreen.tsx` already established for US-5.2's field-edit-vs.-email-change split, here split as field-edit-vs.-role-replacement instead); the independent role-replacement control (disabled without `roles:write`). **Resolution OD-3 (resolved in this revision):** the role control is a multi-select displaying the target *replacement* role set (matching `PUT`'s full-replacement semantics, not an add/remove interaction), and the required confirmation dialog must compute and display **Gained roles** (`selected − current`) and **Lost roles** (`current − selected`) against the roles as currently loaded, with Save disabled whenever the selected set equals the current set — this is new, specific state-comparison logic this screen owns (reusing the in-screen `confirming`-boolean-toggle pattern `DeactivateAccountScreen.tsx` already established rather than a new shared dialog component, confirmed no `ConfirmDialog`-shaped component exists in `components/` today; the gained/lost diff itself is plain set arithmetic, not a new component). An empty role selection remains a separate, always-blocking case per FR-11 (client-side validation), independent of the gained/lost diff. Also hosts deactivate (reason required, same confirm-toggle pattern) and resend-invite controls; and, by omission, **no delete control anywhere** (AD-AC7 — a negative requirement satisfied by never adding one, not by a file to touch). |
| `frontend/src/screens/AdminAuditLogScreen.tsx` (new) | AD-AC8/FR-8: `/admin/audit-logs` — renders all nine `AuditLogEntry` columns, an explicit placeholder for each nullable column (`actor_role`, `outcome`, `ip`, `user_agent`, `actor_id`, `target_id`), `event` verbatim, filters sent as literal query parameters including `from` (not `from_`), cursor "Load more," no total count. **Resolution OD-1 (resolved in this revision):** on first load, before the admin changes anything, this screen's `from`/`to` date-picker inputs must be **visibly pre-filled** with the last-7-days default computed by `useAuditLogs.ts` (not applied silently behind the scenes) — a rendering obligation this screen owns in addition to that hook's default-value computation. **Resolution OD-2 (resolved in this revision):** the `event` filter is a plain free-text `<input>` carrying an illustrative placeholder (e.g. "e.g. user_created, authz_denied"), not a `<select>`/combobox against any enumerated list — no catalogue endpoint exists for event names the way `GET /admin/roles` exists for role names. Must also synthesize a stable per-row key (`occurred_at` + `request_id` + index, per the story's Client State Notes, flagged by spec review v1 and v2 as not carried into FR-8's prose but binding via the story) since `AuditLogEntry` has no `id` and rows accumulate across "Load more" pages — using the array index alone across appended pages is the exact failure mode the story calls out by name. |

## 1a. Checked — Not Affected (reference only)

| File | Why it was checked | Why it is not affected |
|---|---|---|
| `frontend/src/components/ErrorState.tsx`, `frontend/src/components/FieldError.tsx` | FR-10/FR-11/FR-12 apply to every new screen in this Story, same as every prior Story's screens. | Both are already generic (`kind`-based / field-message-based, confirmed by reading both files in full) and reusable as-is by all four new screens with no new props or variants required — the same conclusion US-5.3's impact analysis reached for its own three new screens. |
| `frontend/src/components/apiErrorHelpers.ts` | Every new screen/hook needs `getErrorKind`/`getErrorMessage`/`getErrorStatus`/`getFieldErrors` to read a `412` (FR-4) and a `403` (FR-9) without importing `api/httpClient.ts` directly. | Confirmed by reading the full file: `getErrorStatus` (lines 26-29, added for US-5.2's own 412 detection) already returns the numeric status generically — no admin-specific status code needs a new helper. |
| `frontend/src/store/queryClient.ts` | Every new `hooks/` query/mutation above shares this client. | Existing defaults are generic; no FR asks for a per-query override, same conclusion as US-5.3. |
| `frontend/src/session/sessionBridge.ts` | `store/authStore.tsx`'s changes (scopes field) are adjacent to the session bridge this file defines. | Confirmed by cross-reference: the bridge's contract (`getAccessToken`/`onTokenRefreshed`/`onSessionExpired`) is consumed only by `api/httpClient.ts` for the Bearer header and 401-refresh flow — it never needs to know about scopes, which are read directly off `useAuthStore()` by `screens/`/`layouts/` per FR-9. No change. |
| Any `*.css` file / a styling layer | NFR bar requires responsive layout (~375px through desktop, audit table scrolling within its own container) and visible focus/keyboard navigation across four new screens. | Confirmed no styling layer exists anywhere in `frontend/src` today (same gap US-5.3's impact analysis already recorded and closed as pre-existing, not introduced by that Story). This Story inherits the same gap; it is recorded here rather than rediscovered mid-`IMPLEMENTATION`. |

## 2. Cross-Module Ripple

This is a frontend-only story; "cross-module" here means cross-layer calls within
`frontend/`, per `AGENTS.md` §3's Frontend layer table — there is no backend
service→service ripple to trace, because no backend `app/modules/*` file is modified.

Within `frontend/`:
- `screens/AdminUserListScreen.tsx` → `hooks/useAdminUsers.ts` → `api/adminApi.ts` (list)
  → `api/httpClient.ts` → backend `GET /admin/users` (unmodified, `users:read`-scoped
  server-side).
- `screens/AdminUserCreateScreen.tsx` → `hooks/useCreateAdminUser.ts` +
  `hooks/useAdminRoles.ts` → `api/adminApi.ts` (create, list roles) → `api/httpClient.ts`
  → backend `POST /admin/users`, `GET /admin/roles` (unmodified).
- `screens/AdminUserDetailScreen.tsx` → `hooks/useAdminUser.ts`, `useUpdateAdminUser.ts`,
  `useAdminRoles.ts`, `useReplaceUserRoles.ts`, `useDeactivateAdminUser.ts`,
  `useResendInvite.ts` → `api/adminApi.ts` → `api/httpClient.ts` (using the new `httpPut`
  wrapper for role replacement) → backend `GET/PATCH /admin/users/{id}`,
  `GET /admin/roles`, `PUT /admin/users/{id}/roles`, `POST /admin/users/{id}/deactivate`,
  `POST /admin/users/{id}/resend-invite` (all unmodified — confirmed the create-user and
  role-replacement backend paths behave differently for an unknown role name, per
  `docs/decisions/US-5.4-open-decisions.md` OD-4's citation of
  `app/modules/roles/service.py:137-142` vs. `:231-236` — a fact this Story's frontend
  must not paper over, not a file this Story's frontend can fix).
- `screens/AdminAuditLogScreen.tsx` → `hooks/useAuditLogs.ts` → `api/adminApi.ts` → backend
  `GET /admin/audit-logs` (unmodified — confirmed this endpoint rejects a request missing
  *either* `from` or `to` with a `422 range-too-wide`, per OD-1's citation of
  `app/modules/audit/service.py:124-129`; this Story's frontend must supply both bounds on
  every request, including the first, now satisfied by Resolution OD-1's default window).
- `hooks/useReplaceUserRoles.ts` → `hooks/useAdminUser.ts`'s query key (invalidation) — an
  intra-`hooks/` dependency, the same shape US-5.3's `useReplyToTicket.ts` →
  `useTicketDetail.ts` and US-5.1's `useRevokeSession.ts` → `useSessions.ts` already
  established.
- `hooks/useDeactivateAdminUser.ts` → `hooks/useAdminUser.ts`'s query key (update, per
  FR-6's "returned status is reflected") — same intra-`hooks/` shape.
- `layouts/AppShell.tsx` and every new `screens/` file → `store/authStore.tsx`'s new
  `scopes` field (read-only) — this is the **one new cross-layer dependency this Story
  introduces that did not exist before it**, flagged per the skill's instruction to call
  out a new dependency explicitly: today no `layouts/` or `screens/` file reads anything
  off `authStore` beyond `isAuthenticated`, `user`, and `mfaEnrollmentDeadline`; after this
  Story, `scopes` becomes a second, independently-read field feeding both navigation
  visibility (FR-9) and per-control disabling (`users:write`/`roles:write`/`audit:read`
  gating) across every new screen.
- `store/authStore.tsx` → `store/decodeTokenScopes.ts` (new intra-`store/` dependency,
  invoked from the reducer's `SET_SESSION`/`TOKEN_REFRESHED` handling) — a pure function
  call, not a new external I/O boundary.

No new dependency from `hooks/`/`api/` back into `screens/`/`components/` is introduced
(would violate `AGENTS.md` §3's downward-only import direction) and none was found
necessary. Unchanged from v1: none of the four OD resolutions adds a new cross-module or
cross-layer edge beyond what v1 already identified — Resolutions OD-1/OD-2 affect
`AdminAuditLogScreen.tsx`/`useAuditLogs.ts` behavior only, and OD-3/OD-4 affect
`AdminUserDetailScreen.tsx`/`AdminUserCreateScreen.tsx` behavior only, all against the same
already-identified `useAdminRoles.ts` dependency.

## 3. Migration/Schema Impact

**None.** Confirmed explicitly, per the skill's requirement not to omit this section
silently, and reconfirmed unchanged for this revision — none of Resolutions OD-1–OD-4 adds,
modifies, or implies a backend/API/DB change; each is a client-side presentation or
default-value decision layered on an already-shipped, unmodified endpoint:
- `API_DESIGN` and `DB_DESIGN` both recorded `NOT_APPLICABLE` for this Story, re-run
  specifically against specification v2 (corroborated directly by
  `docs/reviews/designs/US-5.4-design-review.md`, v2, `NOT_APPLICABLE`).
- The approved spec's (v2) Out of Scope section states this explicitly, unchanged from v1:
  "Any backend/API/DB change. This Story implements only against already-shipped backend
  endpoints; it does not add, modify, or design any API route, request/response contract,
  or database schema/table/column."
- Confirmed by direct inspection of the two backend service files this Story's Open
  Decisions cite (`app/modules/roles/service.py`, `app/modules/audit/service.py`): both
  already implement the exact behaviors (full-replace role semantics, silent-drop of
  unknown role names at creation, the 90-day/either-bound-missing audit window rejection)
  this Story's screens must merely surface correctly — no new column, table, index, or
  migration is implied by any FR, including the three FRs (FR-3, FR-5, FR-8) revised in v2.
- No existing backend repository query is affected — every one of the nine endpoints this
  Story calls is already shipped and unmodified.
- FR-2/FR-4's `ETag`/`If-Match` handling and FR-9's scope decoding are exclusively
  client-side (TanStack Query cache metadata / in-memory JWT-claim decoding), not a
  persistence-layer decision, matching this Story's design review's own (v2) conclusion.

## 4. Test-Surface Impact

Unchanged in substance from v1 — resolving OD-1–OD-4 adds specific assertions *within* the
new test files already identified below (e.g. the role-replacement gained/lost diff and
disable-when-unchanged behavior belongs in `AdminUserDetailScreen.test.tsx`; the default
7-day window and free-text `event` filter belong in `AdminAuditLogScreen.test.tsx`/
`useAuditLogs.test.ts`), not a new test file — consistent with this skill's scope, which
surveys affected files rather than enumerating individual test cases.

### Existing test files that must change

| File | Reason |
|---|---|
| `frontend/src/layouts/AppShell.test.tsx` | Currently exercises only `LogoutControls` and the `/tickets` nav link plus the MFA banner (confirmed by reading the full file — its two `describe` blocks cover exactly those, both via `renderWithProviders(<AppShell />, { route: ..., isAuthenticated: true })` with no `scopes` option). Must gain assertions for the new Users/Audit Log nav entries appearing when the seeded token carries the relevant scopes and being absent when it does not (FR-9's first two `Given`s), which requires the `test-utils.tsx` change below first. |
| `frontend/src/routes/AppRoutes.test.tsx` | Currently has no route-table entries for anything under `/admin/*` (confirmed by reading the full file's route-by-route test list). Must gain entries for the four new routes, including their unauthenticated-redirects-to-`/login` case (same shape as every other `ProtectedRoute`-wrapped route already tested in this file, e.g. lines 113-135 for `/settings/*`). |
| `frontend/src/test/test-utils.tsx` | `RenderWithProvidersOptions`/`buildAuthSeed()` (lines 26-72) seed every `AuthStateSeed` field this codebase's tests exercise today (`isAuthenticated`, `user`, `mfaToken`, `mfaEnrollmentDeadline`, `mfaEnabled`) but have no `scopes` option — confirmed by reading the full file. XC-AC1's three `Given`s (no admin scopes, direct navigation forced-403, `users:read`-only with write controls disabled) each require a test to seed a token/derived-scopes value this harness cannot express today. This file is `test-writer`'s own harness contract (per its header comment) but sits inside the blast radius regardless of ownership, same as it did for US-5.3. |
| `frontend/src/test/mswHandlers.ts` | Must gain baseline handlers for all nine endpoints this Story calls (`GET /admin/users`, `GET /admin/users/:id` — carrying an `ETag` response header, the same mechanism the existing `PATCH /profile` handler already demonstrates at line 76, needed for AD-AC2's capture-on-GET behavior — `POST /admin/users`, `PATCH /admin/users/:id`, `POST /admin/users/:id/deactivate`, `POST /admin/users/:id/resend-invite`, `GET /admin/roles`, `PUT /admin/users/:id/roles`, `GET /admin/audit-logs`), following the existing one-handler-per-operation convention (confirmed by reading the full file's US-5.3 block, lines 115-174). Not a new file — shared baseline infrastructure every new screen's tests will import. Required directly by `AGENTS.md` §3's testing-discipline quote this skill's own required reading names: "an `api/authApi.ts` function requires an MSW handler covering both its success and its documented error shapes" — nine new `adminApi.ts` functions imply nine handlers. |
| `frontend/src/api/httpClient.test.ts` | Existing file (not new). Must gain coverage for the new `httpPut` wrapper (section 1's `api/` row) — unconditional, not contingent on any Open Decision, since FR-5's `PUT /admin/users/{id}/roles` call is unconditional in the approved spec. |

### New test files (net-new screens/hooks/store logic have no existing coverage to update)

- `frontend/src/screens/AdminUserListScreen.test.tsx`
- `frontend/src/screens/AdminUserCreateScreen.test.tsx` (now including a catalogue-only role picker case per Resolution OD-4)
- `frontend/src/screens/AdminUserDetailScreen.test.tsx` (now including the gained/lost confirmation diff and disable-when-unchanged case per Resolution OD-3)
- `frontend/src/screens/AdminAuditLogScreen.test.tsx` (now including the visible default 7-day pre-fill and free-text `event` input cases per Resolutions OD-1/OD-2)
- `frontend/src/hooks/useAdminUsers.test.ts`
- `frontend/src/hooks/useAdminUser.test.ts`
- `frontend/src/hooks/useCreateAdminUser.test.ts`
- `frontend/src/hooks/useUpdateAdminUser.test.ts`
- `frontend/src/hooks/useAdminRoles.test.ts`
- `frontend/src/hooks/useReplaceUserRoles.test.ts`
- `frontend/src/hooks/useDeactivateAdminUser.test.ts`
- `frontend/src/hooks/useResendInvite.test.ts`
- `frontend/src/hooks/useAuditLogs.test.ts` (now including the default `from`/`to` computation per Resolution OD-1)
- `frontend/src/store/decodeTokenScopes.test.ts` (new pure-function unit test — no
  equivalent exists today since no scope-decoding logic exists today)
- An a11y test pass (axe, per the existing `vitest-axe` devDependency, same mechanism
  US-5.3 already used) on `AdminUserListScreen`, `AdminUserDetailScreen`, and
  `AdminAuditLogScreen` specifically — the story's own Enforcement Matrix names exactly
  these three for the automated a11y check; no existing a11y test covers them since they
  don't exist yet.
- A test asserting no code path issues `DELETE /admin/users/{id}` (AD-AC7) — a static/unit
  assertion per the story's own Enforcement Matrix, likely a repo-wide grep-style check or
  an MSW-handler-absence assertion rather than a per-screen test; naming and mechanism
  left to `planner`/`test-writer`.

## 5. Delta From v1 (superseded)

Explicit summary of what changed in this revision, since v1's affected-file set is fully
carried forward unchanged:

| Item | v1 status | v2 status |
|---|---|---|
| Create User role picker source (FR-3) | Flagged in Non-Blocking Findings as OD-4, `OPEN` — `AdminUserCreateScreen.tsx`'s reason said "pending OD-4's resolution of whether that source is mandatory or one option." | Resolved: catalogue-driven from `GET /admin/roles` via `useAdminRoles.ts`, unconditionally. `api/`, `hooks/`, and `screens/` rows in §1 updated accordingly. |
| Role-replacement control interaction model (FR-5) | AD-AC5's "explicit confirmation naming what the user will gain and lose" was already anticipated generically in `AdminUserDetailScreen.tsx`'s v1 reason, but flagged in Non-Blocking Findings as OD-3, `OPEN` — the exact interaction (multi-select vs. add/remove) was undecided. | Resolved: multi-select target-set control; confirmation computes `selected − current` (Gained) / `current − selected` (Lost); Save disabled when the sets are equal. `screens/` row in §1 updated with this specific state-comparison logic. |
| Audit Log default `from`/`to` window (FR-8) | Flagged in Non-Blocking Findings as OD-1, `OPEN` — `useAuditLogs.ts`'s v1 reason said "OD-1 (still OPEN...) determines what this hook sends on first mount... flagged, not resolved, here." | Resolved: last 7 days (`now − 7 days` to `now`, ISO 8601 UTC), computed once by the hook and rendered as a **visible** pre-fill by the screen (not applied silently). `hooks/` and `screens/` rows in §1 updated accordingly. |
| Audit Log `event` filter input type (FR-8) | Flagged in Non-Blocking Findings as OD-2, `OPEN`. | Resolved: free-text `<input>` with an illustrative placeholder; no enumerated/discoverable list. `screens/` row in §1 updated accordingly. |
| Affected-file set (§1 rows/files) | — | **No file added or removed.** All four resolutions land as behavior changes within files v1 already identified. |
| Cross-module ripple (§2) | — | Unchanged in substance; reconfirmed no new edge introduced by the four resolutions. |
| Migration/schema impact (§3) | None. | Reconfirmed **None** — none of the four resolutions is a backend/API/DB change. |
| Test-surface impact (§4) | — | Same file list; the four already-planned new test files now carry specific case obligations per the table above, not new files. |

## Non-Blocking Findings

- `frontend/package.json`'s dependency list is a genuine open decision point (whether a
  JWT-decoding library is added) with a real, if small, file-scope consequence — flagged
  in section 1, not resolved here. Not one of OD-1–OD-4 and unaffected by their resolution.
- `frontend/src/api/httpClient.ts` needs a new `httpPut` wrapper — this is **not**
  contingent on any Open Decision (unlike US-5.3's analogous `Retry-After` extension,
  which was gated on that story's OD-1); FR-5's `PUT /admin/users/{id}/roles` call is
  unconditional in the approved spec.
- Specification review v2 carries forward three non-blocking Missing-Edge-Case findings
  (unrecognized `status`/`roles` rendering in FR-1; audit row-key stability in FR-8;
  scopes lifecycle in FR-9) that were not folded into their respective FRs' own prose even
  on this second revision pass. This impact analysis already routes each into the correct
  file (§1: `AdminUserListScreen.tsx`'s verbatim-render note; `AdminAuditLogScreen.tsx`'s
  row-key synthesis; `store/authStore.tsx`'s re-derive/clear/never-persist note) since each
  is binding via the story's own Client State Notes regardless of whether the spec's FR
  prose states it.

## Notes for Downstream Stages

- Exact file names for the four new screens, `store/decodeTokenScopes.ts`, and the
  AD-AC7 no-delete static assertion are `planner`/`frontend-builder`/`test-writer` naming
  calls, not resolved here, consistent with how US-5.3's own impact analysis treated
  analogous naming choices (e.g. `NewTicketScreen.tsx`).
- The role-catalogue query (`useAdminRoles.ts`) is a single shared dependency of both
  `AdminUserCreateScreen.tsx` (FR-3, per Resolution OD-4, now unconditional) and
  `AdminUserDetailScreen.tsx`'s role-replacement control (FR-5, per Resolution OD-3, also
  unconditional).
- `useAdminUser.ts`'s per-user-id ETag cache key and `useUpdateAdminUser.ts`'s `If-Match`
  read from it is the same shape `useProfileUpdate.ts` established for a single fixed key,
  generalized to a per-id key rather than a second, differently-shaped cache mechanism.
- The gained/lost role diff (Resolution OD-3) and the default 7-day audit window
  (Resolution OD-1) are both plain client-side computations (set arithmetic; date
  arithmetic) with no new dependency implied — distinct from the `package.json` flag above,
  which concerns JWT decoding only.
