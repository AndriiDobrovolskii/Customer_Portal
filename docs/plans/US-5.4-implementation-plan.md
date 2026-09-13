---
artifact_type: implementation_plan
story: US-5.4
version: 2
status: DRAFT
created_at: "2026-09-13T07:49:37Z"
updated_at: "2026-09-13T17:05:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.4-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.4-design-review.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
supersedes: docs/plans/US-5.4-implementation-plan.md (v1)
---

# Implementation Plan: Admin Console (Frontend)

**Story ID:** US-5.4
**Track:** frontend (`docs/stories/US-5.4-admin-console-ui.md` front matter)
**API/DB design:** `NOT_APPLICABLE` (confirmed by `docs/reviews/designs/US-5.4-design-review.md`, v2) — this Story
consumes nine already-shipped `/api/v1/admin/*` endpoints (US-3.1/US-3.2/US-3.3) with no backend change.
**Built on:** `docs/impact-analysis/US-5.4-impact-analysis.md` (v2) — this plan does not re-derive the blast
radius; it decides *what* changes architecturally, files, risks, and validation strategy for the files that
survey already named. Execution order and which execution skill runs each task are `implementation-planner`'s
job, not this document's.

> **Revision (v2):** `version: 1` of this plan (`status: DRAFT`) was built against specification v1 and impact
> analysis v1, both now `SUPERSEDED`, and carried OD-1–OD-4 forward as unresolved placeholders (its own Risk 1,
> and bracketed "pending OD-x" notes on `useAdminRoles.ts`/`useAuditLogs.ts`/`AdminUserCreateScreen.tsx`/
> `AdminUserDetailScreen.tsx`/`AdminAuditLogScreen.tsx`). `PLAN_REVIEW` returned `BLOCKED` against v1 of this
> plan and v1 of the task breakdown specifically because task-breakdown tasks T16/T19/T20/T21 were tied to those
> still-`OPEN` decisions. `story-orchestrator` redirected the story to `CLARIFICATION`, where a human stakeholder
> resolved all four (`docs/decisions/US-5.4-open-decisions.md`, v2), and specification v2 incorporated the
> resolutions into FR-3, FR-5, and FR-8. This revision removes every OD-placeholder and states the resolved
> behavior directly, against the same affected-file set impact analysis v2 confirms is unchanged from v1 (no
> file added or removed — see that document's §5 "Delta From v1"). This revision also closes the one remaining
> non-OD decision point v1 left conditional (the JWT-decoding dependency choice, Risk 2 below) rather than
> carrying a second conditional row forward. It does not touch `docs/plans/US-5.4-task-breakdown.md`, owned by
> `implementation-planner`.

## Goal

Deliver a frontend-only admin console inside the existing `frontend/` app (built by US-5.1/US-5.2) that lets an
authenticated admin, gated purely by scopes decoded from their in-memory access token: list and filter users
with cursor pagination (FR-1), open a user's detail and capture its `ETag` (FR-2), create a user with no password
field and a catalogue-driven role picker (FR-3), edit a user's non-role fields behind a required `reason` and
`If-Match` (FR-4), manage roles as an independent full-replacement save path via a target-set multi-select with a
gained/lost confirmation diff (FR-5), deactivate a user and resend their invite (FR-6), never expose a delete
affordance (FR-7), view the audit log with a visibly-prefilled default 7-day window and free-text `event` filter
(FR-8), and have all of the above governed by scope-derived navigation (FR-9), uniform problem+json rendering
(FR-10), client-side validation before any request fires (FR-11), and a retry-capable network/5xx failure state
(FR-12) — with client-side scope decoding treated everywhere as advisory only, never as authorization.

## Architectural Changes

All changes are additive within the existing frontend layer table (`AGENTS.md` §3 Frontend subsection:
`screens/`,`components/` → `hooks/` → `api/`, with `store/` read-only by `hooks/`/`screens/`/`layouts/`/`routes/`).
No new layer, no new top-level directory, no restructuring of `frontend/src/`.

1. **New client-side authorization surface: scope decoding.** Today `store/authStore.tsx` carries no `scopes`
   field and no JWT-claims decoding exists anywhere in `frontend/src`. This Story adds a pure, dependency-light
   decoder (`store/decodeTokenScopes.ts`) that base64url-decodes the access token's payload segment and reads its
   `scopes` claim — decode-only, **never verified client-side** (Story Assumption #2/#3). `authStore.tsx`'s
   reducer calls it on the two actions that already change `accessToken` (`SET_SESSION`, `TOKEN_REFRESHED`,
   confirmed at that file's lines 48-77 by the impact analysis) and resets `scopes` to `[]` on `CLEAR_SESSION`,
   so the field is always re-derived from the current token, never independently mutated, and never persisted —
   matching the story's Client State Notes ("re-derived on every refresh, cleared on logout, never persisted").
   This is the one genuinely new architectural capability this Story introduces; everything else is applying
   the existing screen → hook → api pattern to a new resource family. The decoder is a two-line hand-rolled
   `atob`/base64url helper — **no new `package.json` dependency** (Risk 2 below closes this decision).
2. **A new resource family in the existing API/hooks pattern.** `api/adminApi.ts` (new) holds one typed function
   per operation, following the existing per-prefix file convention (`authApi.ts`, `profileApi.ts`, `supportApi.ts`
   each cover one path family). `api/httpClient.ts` gains an `httpPut<T>()` wrapper — `HttpMethod` already
   includes `"PUT"` in its union but no wrapper is exported today; this is a same-shape additive extension to the
   pattern `httpPatch` already established, touching no existing exported signature. One new hook per operation
   under `hooks/` mirrors `useTickets.ts` (`useInfiniteQuery` for the two cursor-paginated lists) and
   `useProfileUpdate.ts` (the ETag-cache-then-`If-Match` shape, generalized here from a single fixed key to a
   per-user-id key). `useAdminRoles.ts` (`GET /admin/roles`) is a single shared, unconditional dependency of both
   the create-user screen (Resolution OD-4) and the role-replacement control (Resolution OD-3) — not a
   conditional dependency of either.
3. **Cross-hook cache invalidation, no new mechanism.** `useReplaceUserRoles.ts` and `useDeactivateAdminUser.ts`
   each update or invalidate `useAdminUser.ts`'s query key after a successful mutation, the same intra-`hooks/`
   dependency shape `useReplyToTicket.ts` → `useTicketDetail.ts` (US-5.3) and `useRevokeSession.ts` →
   `useSessions.ts` (US-5.1) already established. No new cross-hook coordination primitive is introduced.
4. **Scope-gated, not route-guarded, navigation and controls.** Per Assumption #3 and XC-AC1's literal second
   `Given` (a scope-less user navigating directly must see the server's 403, not a client redirect),
   `routes/ProtectedRoute.tsx` is **not** modified and no new route-guard component is added. The four new routes
   register inside the existing `<ProtectedRoute><AppShell /></ProtectedRoute>` group exactly like `/tickets`,
   `/sessions`, `/settings/*` today. Gating happens entirely at the presentation layer: `layouts/AppShell.tsx`
   conditionally renders the two new nav entries off `scopes`, and each screen's write controls (edit save,
   role save, deactivate, resend-invite) are individually `disabled` based on the specific scope each requires
   (`users:write`, `roles:write`) — matching the story's "a single admin may hold `users:read` without
   `users:write` or `roles:write`; each control is gated on its own scope, independently." Every privileged
   screen still renders the server's 403 problem+json via the existing `apiErrorHelpers.ts`/`ErrorState.tsx`
   pair — client gating is cosmetic, the server 403 path is the enforced one, in both directions.
5. **No new shared confirmation-dialog component.** `AdminUserDetailScreen.tsx`'s two destructive actions
   (deactivate, role replacement) reuse the in-screen `confirming`-boolean-toggle pattern
   `DeactivateAccountScreen.tsx` already established, rather than introducing a new shared `ConfirmDialog`
   component — confirmed no such component exists in `components/` today. This keeps the change additive to an
   existing pattern instead of adding a new shared UI primitive speculatively. Per Resolution OD-3, the
   role-replacement confirmation is not a generic "are you sure" toggle — it must compute and display
   **Gained roles** (`selected − current`) and **Lost roles** (`current − selected`) as two explicit sets, using
   order-insensitive set comparison (see Risk 5 below).
6. **DTO/type split preserved, not reinvented.** `AdminUserRead.status`/`.roles` stay plain `string`/`string[]`
   in `api/types.ts` (never a union), consistent with the story's own "an unrecognized value renders verbatim"
   rule; the fixed `invited`/`active`/`deactivated` set for FR-1's filter `<select>` is a UI-only constant, not a
   DTO type — the same DTO-stays-`string`-vs-filter-union split `types.ts` already has today between
   `TicketRead.status: string` and the separate `TicketStatus` union consumed only by `TicketListScreen.tsx`.

## Files To Create

| File | Purpose |
|---|---|
| `frontend/src/store/decodeTokenScopes.ts` | Pure JWT-payload decoder returning the `scopes` claim (decode-only, unverified). Architectural Change 1. |
| `frontend/src/api/adminApi.ts` | Typed functions for all nine `/admin/*` operations: `listUsers`, `getUser` (ETag-carrying), `createUser`, `updateUser`, `deactivateUser`, `resendInvite`, `listRoles`, `replaceUserRoles`, `listAuditLogs` (audit's start-of-window param sent literally as `from`). |
| `frontend/src/hooks/useAdminUsers.ts` | FR-1: cursor-paginated user list, `q`/`status`/`role` filters reset the cursor. |
| `frontend/src/hooks/useAdminUser.ts` | FR-2: single-user query capturing the `ETag` response header into query-cache metadata keyed by user id. |
| `frontend/src/hooks/useCreateAdminUser.ts` | FR-3: create-user mutation; payload's `roles` values are drawn only from `useAdminRoles.ts`'s catalogue (Resolution OD-4). |
| `frontend/src/hooks/useUpdateAdminUser.ts` | FR-4: field-edit mutation reading the cached `ETag` as outgoing `If-Match`; surfaces `412` conflict and `immutable-field` detail. |
| `frontend/src/hooks/useAdminRoles.ts` | FR-3/FR-5: shared role-catalogue query (`GET /admin/roles`), built once and consumed **unconditionally** by both the create-user form (Resolution OD-4) and the role-replacement control (Resolution OD-3) — not an optional/fallback source for either. |
| `frontend/src/hooks/useReplaceUserRoles.ts` | FR-5: full-replacement role mutation (`PUT`); invalidates/updates `useAdminUser.ts`'s query key. |
| `frontend/src/hooks/useDeactivateAdminUser.ts` | FR-6: deactivate mutation; updates `useAdminUser.ts`'s cached status without a full refetch. |
| `frontend/src/hooks/useResendInvite.ts` | FR-6: resend-invite mutation (generic confirmation only; the `202` body is not displayed). |
| `frontend/src/hooks/useAuditLogs.ts` | FR-8: cursor-paginated audit log query, `actor_id`/`event`/`target_id`/`from`/`to` filters. **Resolution OD-1:** on first mount, before any filter is chosen, computes the default window `from = now − 7 days`, `to = now` (ISO 8601 UTC) exactly once and hands both values to `AdminAuditLogScreen.tsx` for a visible pre-fill — the default must never be applied silently inside the hook only (see Risk 4's testability note on freezing the clock). |
| `frontend/src/screens/AdminUserListScreen.tsx` | AD-AC1/FR-1: `/admin/users`. |
| `frontend/src/screens/AdminUserCreateScreen.tsx` | AD-AC3/FR-3: `/admin/users/new`. `roles` field is a catalogue-driven multi-select sourced from `useAdminRoles.ts` (Resolution OD-4) — no free-text role entry anywhere on this screen. |
| `frontend/src/screens/AdminUserDetailScreen.tsx` | AD-AC2/AD-AC4/AD-AC5/AD-AC6/AD-AC7/FR-2/FR-4/FR-5/FR-6/FR-7: `/admin/users/:id` — largest surface in this Story; hosts field-edit, role-replacement, deactivate, and resend-invite, and by omission never adds a delete control. Role control is a multi-select displaying the target *replacement* role set (Resolution OD-3), not add/remove actions; its confirmation dialog computes and renders Gained (`selected − current`) / Lost (`current − selected`) role sets against order-insensitive set comparison, and Save is disabled whenever the selected set equals the current set. |
| `frontend/src/screens/AdminAuditLogScreen.tsx` | AD-AC8/FR-8: `/admin/audit-logs`. `from`/`to` date-picker inputs are **visibly pre-filled** on first render with `useAuditLogs.ts`'s computed 7-day default (Resolution OD-1, not applied silently). `event` filter is a plain free-text `<input>` with an illustrative placeholder, e.g. "e.g. user_created, authz_denied" (Resolution OD-2) — no `<select>`/combobox/enumerated list. |
| Test files paired 1:1 with every file above (`*.test.ts(x)`), per `AGENTS.md` §5 Frontend subsection's "a new `screens/LoginScreen.tsx` requires `LoginScreen.test.tsx`" rule. | See Testing Strategy. |
| `frontend/src/store/decodeTokenScopes.test.ts` | Pure-function unit coverage for the new decoder — no equivalent test exists today. |

Exact screen/hook file names above match `docs/impact-analysis/US-5.4-impact-analysis.md`'s naming, which that
document flagged as a "planner/frontend-builder naming call" — this plan adopts them as final rather than
re-opening the naming question, since they already follow the codebase's existing `use<Resource><Verb>.ts` /
`<Resource><Screen>.tsx` conventions exactly.

## Files To Modify

| File | Change |
|---|---|
| `frontend/src/api/types.ts` | Add `AdminUserRead`, `AdminUserListResponse`, `CreateAdminUserRequest`, `UpdateAdminUserRequest`, `DeactivateUserRequest`, `ResendInviteResponse`, `RoleRead`/`RoleListResponse`, `ReplaceUserRolesRequest`/`ReplaceUserRolesResponse`, `AuditLogEntry`, `AuditLogListResponse`. Purely additive; no existing type's shape changes. |
| `frontend/src/api/httpClient.ts` | Add `httpPut<T>()`, following `httpPatch`'s existing shape. `HttpMethod` already includes `"PUT"`; `performRequest`/`parseResponse` stay untouched, mirroring how `httpPatch` itself was added in US-5.2 without touching those two functions. |
| `frontend/src/store/authStore.tsx` | Add `scopes: string[]` to `AuthStateSeed`; derive it via `decodeTokenScopes.ts` on `SET_SESSION`/`TOKEN_REFRESHED`; reset to `[]` on `CLEAR_SESSION`. No existing field's shape or the reducer's existing action handling changes. |
| `frontend/src/routes/AppRoutes.tsx` | Register four new routes inside the existing `<ProtectedRoute><AppShell /></ProtectedRoute>` group: `/admin/users`, `/admin/users/new`, `/admin/users/:id`, `/admin/audit-logs`. Same registration shape as every existing route in this file; no new guard wrapper. |
| `frontend/src/layouts/AppShell.tsx` | Add two conditionally-rendered nav links (Users, Audit Log) gated on `scopes` read from `useAuthStore()`, alongside the existing `/tickets` link and the `mfaEnrollmentDeadline` read this file already performs. |
| `frontend/src/layouts/AppShell.test.tsx` | Add assertions for the two new nav entries appearing/absent based on seeded `scopes` (depends on the `test-utils.tsx` change below landing first). |
| `frontend/src/routes/AppRoutes.test.tsx` | Add route-table entries for the four new routes, including their unauthenticated-redirect-to-`/login` case, matching every other `ProtectedRoute`-wrapped route already tested in this file. |
| `frontend/src/test/test-utils.tsx` | Add a `scopes` option to `RenderWithProvidersOptions`/`buildAuthSeed()` so tests can seed a token/derived-scopes value — required by XC-AC1's three `Given`s (no admin scopes / direct-navigation forced-403 / `users:read`-only). |
| `frontend/src/test/mswHandlers.ts` | Add baseline handlers for all nine `/admin/*` endpoints, including one demonstrating the `ETag` response header on `GET /admin/users/:id` (same mechanism the existing `PATCH /profile` handler already uses). |
| `frontend/src/api/httpClient.test.ts` | Add coverage for the new `httpPut` wrapper — unconditional, since FR-5's `PUT` call is unconditional in the approved spec. |

`frontend/package.json` is **not** expected to change (decision closed — see Risk 2): scope decoding uses a
hand-rolled two-line `atob`/base64url helper rather than a `jwt-decode`/`jose`-class dependency, so no new
dependency is added by this Story. `frontend/src/api/errorNormalization.ts` and `routes/ProtectedRoute.tsx` were
checked by the impact analysis and require no change; this plan concurs — no FR implies a new problem+json shape
or a new guard mechanism.

## Protected-File Check (AGENTS.md §7.9)

None of the files above are protected. `pyproject.toml`, `migrations/env.py`, and `.pre-commit-config.yaml` are
untouched by this Story — this is a `frontend/`-only change with no backend/migration/CI-enforcement-config
surface. No explicit user sign-off is required on that basis. `frontend/package.json` is not modified by this
plan (Risk 2 closes the dependency question against a hand-rolled helper), so no §7.8 new-dependency sign-off is
triggered either.

## Risks

1. **A dependency choice for JWT-claims decoding — closed.** No `jwt-decode`/`jose`-class dependency exists in
   `frontend/package.json` today. This plan decides in favor of a hand-rolled two-line `atob`/base64url helper:
   it avoids a new dependency entirely (lowest risk, smallest surface), and is sufficient since this Story only
   reads one claim and never verifies the signature (verification and expiry checks are already handled
   elsewhere in the session-refresh flow). Per `AGENTS.md` §7.8 ("propose, never execute unilaterally: new...
   dependencies"), this decision is recorded here explicitly rather than left to `implementation-planner`/
   `frontend-builder` to rediscover or default silently; no `package.json` change is expected.
2. **Client-decoded scopes must never become a real authorization boundary — a plausible implementation drift.**
   Because `ProtectedRoute.tsx` deliberately stays auth-only (Architectural Change 4), it is tempting for an
   implementer to "helpfully" add scope checks there instead of at the presentation layer, which would silently
   convert cosmetic gating into a client-side authorization gate and violate Assumption #3/the spec's own NFR
   ("Client-side scope decoding is never treated as authorization"). Mitigated by explicitly *not* modifying
   `ProtectedRoute.tsx` in this plan and requiring every privileged screen to independently render the server's
   403 (FR-9's second `Given`) regardless of what the decoded scopes say.
3. **Cross-hook cache invalidation ordering (role replacement / deactivation vs. the detail query).** If
   `useReplaceUserRoles.ts` or `useDeactivateAdminUser.ts` update the `useAdminUser.ts` cache entry with a stale
   or partial shape (e.g. writing only `roles` without preserving the rest of `AdminUserRead`, or vice versa),
   the detail screen can render an inconsistent user object without any network error being raised — a silent
   correctness bug, not a crash. Mitigated by preferring targeted query invalidation (`invalidateQueries` +
   refetch) over a hand-merged cache patch, the same choice `useReplyToTicket.ts` made against `useTicketDetail.ts`.
4. **`ETag` capture must generalize correctly from a single fixed cache key (`useProfileUpdate.ts`, one profile
   per session) to a per-user-id key (many users, one admin session).** A key collision or a stale `ETag` read
   for the wrong user id would cause every `PATCH` to send an incorrect `If-Match`, always failing with `412`
   regardless of actual staleness — an availability bug for every edit, not just concurrent-edit conflicts. This
   is the direct frontend analogue of a migration hazard: get the keying wrong and every write breaks, not just
   the edge case it was meant to guard. Mitigated by keying explicitly on user id (not a fixed constant) from
   the start, verified by a dedicated test asserting the `ETag` for user A is never sent as `If-Match` for user B.
5. **Resolution OD-1's default audit window is computed from `now`, making `useAuditLogs.ts` time-dependent.**
   A test that asserts "the default window is the last 7 days" without controlling the clock is flaky by
   construction (it will intermittently disagree with itself across a UTC day boundary, and any date-math bug
   only shows up at that boundary). Mitigated by requiring `useAuditLogs.test.ts`/`AdminAuditLogScreen.test.tsx`
   to freeze/mock the clock (e.g. `vi.setSystemTime`) before asserting the computed `from`/`to` values, rather
   than asserting against a live `Date.now()` computed independently in the test.
6. **Resolution OD-3's Save-disabled check compares the selected role set against the current role set, but
   `GET /admin/roles` order and the user's stored `roles` order need not match.** A naive stringify-and-compare
   or index-wise comparison would spuriously enable Save when nothing actually changed (both sets equal, order
   differs) or spuriously disable it when the user actually did change roles but the resulting set happens to
   restringify identically under a buggy comparison. Mitigated by requiring order-insensitive set comparison
   (e.g. compare sorted arrays, or `Set` equality) for both the gained/lost diff computation and the
   Save-disabled-when-unchanged check, verified by a dedicated test seeding the current roles in a different
   order than the catalogue returns them.
7. **No AC literally requires the "unrecognized `status`/`roles` value renders verbatim" and "stable synthetic
   audit row key" rules** (per specification review v2's own Missing Edge Cases, Medium/Low, carried forward
   unchanged from v1), but both are explicit, binding instructions in the story's Client State Notes that the
   impact analysis carried into `AdminUserListScreen.tsx` and `AdminAuditLogScreen.tsx` respectively. Risk: an
   implementer treats the spec's FR text as the complete contract and drops these two behaviors since no FR/AC
   literally names them. Mitigated by naming both explicitly in Files To Create above and in the Testing Strategy
   below, rather than leaving them to be rediscovered (or missed) during coding. Separately, specification
   review v2 flags (Low, v2-only) that FR-4's "(see FR-5)" pointer for the `immutable-field` problem dead-ends —
   FR-5 never explains the term. This plan resolves that ambiguity directly rather than carrying it forward:
   per the story's own Assumption #5, `roles` is the field in `ADMIN_USER_IMMUTABLE_FIELD_NAMES`, so
   `useUpdateAdminUser.ts`/`AdminUserDetailScreen.tsx` render the `immutable-field` problem's `detail` only in
   the (should-be-unreachable, since FR-5 guarantees `roles` is never sent to `PATCH`) case of that field name
   appearing in a `422`/`409`-class response.
8. **A11y and responsive bar apply to four entirely new screens with no existing styling layer to build on**
   (confirmed by the impact analysis: no CSS/styling layer exists anywhere in `frontend/src` today — a
   pre-existing gap, not introduced by this Story). The audit table specifically needs its own horizontally-
   scrolling container per the NFR, and the Enforcement Matrix names exactly three screens (user-list, user-edit,
   audit) for an automated axe check. Risk is under-scoping this to "just render the data" and missing the
   keyboard-navigation/focus-visibility/column-header-association bar. No new architectural component is
   proposed to close this gap (would be scope creep against this Story, which inherits — not introduces — the
   missing styling layer); it is flagged here so `IMPLEMENTATION_PLANNING`/`frontend-builder` budget for it
   explicitly rather than treating it as free.

## Dependencies on Other Stories / Open Decisions

- **Depends on US-5.1** (auth store, API client, route guards, problem+json rendering) and **US-5.2** (the
  API client's response-header/`ETag` support) — both already delivered; this Story extends their infrastructure,
  it does not wait on new work from either.
- **OD-1–OD-4 are `RESOLVED`** (`docs/decisions/US-5.4-open-decisions.md`, v2) and incorporated directly into
  this plan's Files To Create and Risks above; they are no longer a dependency or blocker for any downstream
  stage. This closes the specific gap that caused `PLAN_REVIEW` to return `BLOCKED` against v1 of this plan and
  v1 of the task breakdown (task-breakdown tasks T16/T19/T20/T21 were tied to these four items while they were
  still `OPEN`) — `implementation-planner`'s re-run of the task breakdown against this v2 plan should tie those
  tasks to the resolved behavior stated here rather than to an Open Decision reference.
- **No dependency on any concurrently in-flight Story.** Confirmed by the impact analysis: every backend endpoint
  this Story calls is already shipped and unmodified (US-3.1/US-3.2/US-3.3), and no other `US-5.x` frontend
  Story shares a screen, route, or hook with this one.

## Validation Strategy

Per `AGENTS.md` §2/§6 Frontend subsections, the exact four gate scripts are load-bearing and must stay green
throughout implementation:

- `npm run lint` (ESLint) — zero findings, including on the two new `store/` files and all new `hooks/`/`screens/`
  files; no new `any` (TypeScript strict mode, §2's Frontend row).
- `npm run format:check` (Prettier, check-only) — clean on every new and modified file.
- `npm run type-check` (`tsc --noEmit`) — the layering discipline in Architectural Change 4 (screens/layouts read
  `scopes` off the store; no screen imports `api/` directly) is largely self-enforcing here because `hooks/`
  is the only layer that imports `api/`, and TypeScript will fail to compile a screen that tries to call
  `adminApi.ts` directly without going through a hook's typed return shape — this is not `lint-imports`-mechanical
  the way the backend is (§3 Frontend subsection: "no `lint-imports`-equivalent contract enforcing this
  mechanically yet"), so the diff must still be read layer-by-layer at `PLAN_REVIEW`/`QUALITY_GATE` rather than
  trusted to the type-checker alone.
- `npm run test:coverage` (Vitest, coverage gate) — 85% floor per §5's Frontend subsection, same floor as the
  backend, enforced the same way (a floor, not a target).
- Because this Story touches no backend file, none of the backend gates (`pytest`, `mypy strict`,
  `lint-imports`, the Alembic cycle) apply — confirmed by the Migration/Schema Impact section of the impact
  analysis (none, reconfirmed unchanged in v2) and the design review's `NOT_APPLICABLE` verdict (v2) for both
  `API_DESIGN`/`DB_DESIGN`.
- §6's frontend "contract & security" Definition-of-Done item applies directly: no sensitive value (access
  token, any decoded claim beyond `scopes`) reaches the browser console or a committed file, and the access
  token stays in-memory-only per §3's session-handling rule — this Story's new `decodeTokenScopes.ts` reads the
  in-memory token only, never persists its output, and the store's `scopes` field must not be logged.
- **Spec NFR — no audit-log row content in production console output.** `AdminAuditLogScreen.tsx` (and any
  hook/error-handling path it uses) must not `console.*` a row's `ip`, `user_agent`, or `request_id` — verified
  by code review of the diff (no mechanical gate catches this on the frontend today, same limitation as the
  layering check above) plus a unit assertion described in Testing Strategy.
- **Spec NFR — every screen has an explicit loading state, not only an explicit error state.** Each of the four
  new screens must render a distinct loading indicator while its initial query is pending, separate from and in
  addition to its error state (XC-AC4) and its empty-result state — checked by diff review at `PLAN_REVIEW`/
  `QUALITY_GATE` and asserted per screen in Testing Strategy.

## Testing Strategy

Per `AGENTS.md` §5's Frontend subsection (Vitest unit vs. React-Testing-Library-plus-MSW integration split) and
this Story's own Enforcement Matrix:

**Unit (Vitest, no network, no DOM beyond RTL's minimum):**
- `store/decodeTokenScopes.test.ts` — pure-function coverage: a well-formed token with a `scopes` claim, a
  token with an empty/absent `scopes` claim, and a malformed token payload (must not throw and must degrade to
  no scopes, since a scope-decoding failure must never crash the app or silently grant access).
- Each new hook (`useAdminUsers`, `useAdminUser`, `useCreateAdminUser`, `useUpdateAdminUser`, `useAdminRoles`,
  `useReplaceUserRoles`, `useDeactivateAdminUser`, `useResendInvite`, `useAuditLogs`) gets its own
  `*.test.ts`, using a real MSW handler rather than a hand-mocked `fetch` (§5's explicit preference), following
  `useTickets.test.ts`/`useProfileUpdate.test.ts`'s existing shape. `useAuditLogs.test.ts` freezes the system
  clock (Risk 5) before asserting the computed default `from`/`to` values.
- `api/httpClient.test.ts` gains coverage for the new `httpPut` wrapper.

**Integration (React Testing Library + MSW, full screen + hooks + store tree):**
- One `*.test.tsx` per new screen (`AdminUserListScreen`, `AdminUserCreateScreen`, `AdminUserDetailScreen`,
  `AdminAuditLogScreen`), each driven by `mswHandlers.ts`'s new baseline handlers, covering:
  - AD-AC1/FR-1: filters re-request and reset cursor; "Load more" appends; no total count rendered anywhere;
    an unrecognized `status`/`roles` value renders verbatim (Risk 7).
  - AD-AC2/FR-2 `[gate]`: the `ETag` response header on `GET /admin/users/{id}` is captured and echoed as
    `If-Match` on the next `PATCH` for the *same* user id, and explicitly **not** echoed for a different user id
    (Risk 4's mitigation, made concrete as a test).
  - AD-AC3/FR-3 `[gate]`: exactly `email`/`display_name`/`roles` in the `POST` body, no password field rendered
    anywhere in the DOM, navigation to the new user's detail screen on `201`, and the `roles` multi-select's
    options are populated from `GET /admin/roles` only — no free-text role entry exists anywhere on this screen
    (Resolution OD-4).
  - AD-AC4/FR-4 `[gate]`: `reason` required before submit is enabled; `If-Match` present on `PATCH`; a `412`
    renders the conflict state; an `immutable-field` problem renders its own `detail`.
  - AD-AC5/FR-5 `[gate]`: `roles` never appears in any `PATCH` body (assert on every captured `PATCH` request in
    this screen's tests, not just the happy path); role save hits `PUT .../roles` with the full replacement
    list; the role control is `disabled` for a `roles:write`-less seed, and a forced server `403` on that path
    still renders correctly; the confirmation dialog computes and displays the correct Gained/Lost role sets
    (Resolution OD-3) using seed data whose current-role order differs from the catalogue's order (Risk 6); Save
    stays disabled when the selected set equals the current set, and becomes enabled the moment either set
    differs.
  - AD-AC6/FR-6 `[gate]`: deactivate requires a non-empty reason, sits behind an explicit confirmation naming
    the consequence (spec NFR — destructive/irreversible actions), and reflects the returned status; resend-invite
    shows a generic confirmation and never displays the `202` body.
  - AD-AC7/FR-7 `[gate]`: a static/unit assertion (repo-wide search or an MSW-handler-absence assertion — exact
    mechanism is `test-writer`'s call, not resolved here) that no code path in this Story issues
    `DELETE /admin/users/{id}`.
  - AD-AC8/FR-8 `[gate]`: all nine columns render; each nullable column renders an explicit placeholder, never
    an empty cell; the `from`/`to` date-picker inputs are **visibly pre-filled** with the last-7-days default on
    first render, with the system clock frozen for a deterministic assertion (Resolution OD-1, Risk 5); the
    `event` filter is a free-text `<input>` carrying an illustrative placeholder, never a `<select>`/combobox
    (Resolution OD-2); filters (including the literal `from` parameter name) are sent as query parameters;
    "Load more" appends without duplicate or unstable row keys across pages (Risk 7's synthetic-key requirement,
    made concrete as a test asserting row identity survives an appended page).
  - XC-AC1/FR-9 `[gate]`: three seeded-token scenarios via the new `test-utils.tsx` `scopes` option — no admin
    scopes (no nav entry rendered, forced direct navigation renders the server's `403`, never a blank screen or
    infinite spinner), and `users:read`-only (read screens render, every write control disabled).
  - XC-AC2/FR-10 `[gate]`: a problem+json 4xx renders its `detail`/mapped message with no raw JSON or stack
    trace visible in the DOM; a `422` maps its `errors` array onto the matching form fields, tested per screen.
  - XC-AC3/FR-11 `[gate]`: per form, an empty/malformed required field blocks submission with a field-level
    error and asserts **no** MSW request was recorded.
  - XC-AC4/FR-12 `[gate]`: a simulated network error and a `5xx` each render a retry-capable error state, never
    a blank screen, indefinite spinner, or unhandled exception (assert no uncaught error surfaces to the test
    runner).
- `layouts/AppShell.test.tsx` and `routes/AppRoutes.test.tsx` gain the new nav/route assertions described in
  Files To Modify.
- Each new screen's test asserts a distinct loading state renders before its query resolves (spec NFR, distinct
  from its error state) and, for `AdminAuditLogScreen.test.tsx` specifically, a spied `console.log`/`console.warn`/
  `console.error` records no call containing a row's `ip`, `user_agent`, or `request_id` value (spec NFR on
  console hygiene).
- `[gate]` **a11y pass** (axe, existing `vitest-axe` devDependency) on exactly the three screens the Enforcement
  Matrix names: `AdminUserListScreen`, `AdminUserDetailScreen` (the story's "user-edit" screen), and
  `AdminAuditLogScreen`.

No `vi.mock()` on the component/hook/store under test in any of the above (§5's explicit prohibition) — MSW is
the only network boundary substituted, matching how every prior US-5.x Story's tests are structured.
