---
artifact_type: impact_analysis
story: US-5.1
version: 1
status: ARCHIVED
created_at: "2026-09-07T13:30:00Z"
updated_at: "2026-09-07T13:30:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.1-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.1-design-review.md
    version: 1
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
supersedes: null
---

# Impact Analysis: Authentication & Session Management — Frontend (US-5.1)

**Spec:** docs/specifications/US-5.1-spec.md (v2, FR-1..FR-11)
**Spec review:** docs/reviews/specifications/US-5.1-spec-review.md (v2, Pass with Issues — all AC Covered, no Critical/Major open)
**Design review:** docs/reviews/designs/US-5.1-design-review.md (v1, NOT_APPLICABLE — API_DESIGN and DB_DESIGN both recorded NOT_APPLICABLE; confirmed no `US-5.1-*` file exists under `docs/designs/api/` or `docs/designs/database/`)
**Open decisions:** docs/decisions/US-5.1-open-decisions.md (OD-1..OD-9, all OPEN — none resolved by this survey)

This is a **frontend-only** Story. Confirmed by direct directory listing: no `frontend/` directory exists anywhere in this repository today (`Glob frontend/**` → no files found), and the repo root has no `package.json`, `vite.config.*`, or `tsconfig.json` either — only `dev-gui/` (a gitignored static test page, per `app/main.py`'s CORS comment) and the backend's own `app/`, `migrations/`, `scripts/`, `tests/` trees. Every "affected file" below is therefore a **new file in a project that must itself be scaffolded**, not a modification to an existing frontend codebase. `AGENTS.md` §3's layer table (`models.py`/`schemas.py`/`repository.py`/`cache.py`/`service.py`/`router.py`) is a backend-only convention enforced by `lint-imports` against `app/modules/`; it does not apply to a frontend tree and is not force-fit below. Instead, files are grouped by the frontend's own natural layers (build/scaffold, HTTP/api-client, auth state, routing/guards/layout, screens, forms, shared error UI, tests) per the spec's Assumption #1 stack (React + Vite + TypeScript + TanStack Query + React Hook Form).

The existing backend `app/modules/users/` is read here only as a **reference contract** — the request/response shapes this Story's frontend code must match — never as a file this Story modifies. Confirmed by direct read of `app/modules/users/router.py` (all 11 `/auth/*` routes this Story's FRs call) and `app/modules/users/schemas.py` (`LoginResponse`, `MfaRequiredResponse`, `RefreshResponse`, `SessionListResponse`/`SessionEntry`, `PasswordResetRequestResponse`, etc.) and `app/main.py` (CORS middleware, `RegistrationValidationError`/`DuplicateEmailError`/`ProblemError` exception handlers). No line in `app/modules/users/*` or `app/main.py` is listed as "affected" below — this Story changes none of them (spec Background: "does not design or change any API, database schema, or backend behavior"; Out of Scope: "Any backend/API/DB change").

## Affected Files

### Project scaffold / build config (new — no equivalent exists today)

- **`frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`** — wholly new. Confirmed: no such files exist anywhere in the repo. Needed to stand up the React + Vite + TypeScript stack the spec's Assumption #1 names before any of FR-1..FR-11 can be built. `OD-9` (design-system/component-library choice) is a dependency of this layer's exact dependency list (Tailwind/Radix vs. hand-built) but is not resolved here.
- **`frontend/vite.config.ts` dev-server proxy (or its absence)** — directly gated by `OD-1` (CORS/cross-origin). If the frontend runs same-origin via a Vite `server.proxy` (keeping the spec's "no backend changes" assumption true), this file's shape is fixed one way; if instead the backend's CORS policy must change (`app/main.py`, out of this Story's scope per Background/Out of Scope), this file is fixed a different way. Flagged, not resolved — `OD-1` remains OPEN.

### API-client / HTTP layer (new)

- **`frontend/src/api/httpClient.ts`** (or equivalent) — new. Single fetch/axios wrapper every FR's endpoint call goes through: attaches the in-memory access token as a `Bearer` header (FR-2/FR-3), lets the browser handle the `httpOnly` refresh cookie automatically (FR-2's "not read or stored by client code"), and is the one interception point for FR-4's 401→refresh→retry logic and FR-9/FR-11's error normalization.
- **`frontend/src/api/authApi.ts`** (or per-endpoint modules) — new. One typed call per backend route this Story's FRs use: `POST /auth/register`, `POST /auth/login`, `POST /auth/mfa/verify`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/sessions`, `DELETE /auth/sessions/{family_id}`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` — confirmed each exists today in `app/modules/users/router.py` with the exact request/response shapes this Story's frontend types must mirror (`UserCreate`/`UserRead`, `LoginRequest`/`LoginResponse`/`MfaRequiredResponse`, `MfaVerifyRequest`/`MfaVerifyResponse`, `RefreshResponse`, `SessionListResponse`/`SessionEntry`, `PasswordResetRequestRequest`/`Response`, `PasswordResetConfirmRequest`).
- **`frontend/src/api/errorNormalization.ts`** (or equivalent) — new. FR-9's problem+json → UI-message mapping, plus the 422 `errors[]` → form-field mapping. Directly shaped by `OD-4`: confirmed by direct read of `app/main.py` that `RegistrationValidationError` (400, `{"errors":[{field,message,code}]}`, plain `application/json`) and `DuplicateEmailError` (409, `{"detail": "..."}`, plain `application/json`) do **not** carry the RFC 7807 envelope every other endpoint's `ProblemError`/`RequestValidationError` handler produces — this module cannot implement FR-9 uniformly across all 10 endpoints without special-casing Register's two shapes, and `OD-4` (whether that's a client special-case or a backend defect) is unresolved.
- **`frontend/src/api/refreshCoordinator.ts`** (or equivalent, may be folded into `httpClient.ts`) — new, and its exact shape is gated by `OD-2` (single-flight vs. independent concurrent refresh) and `OD-3` (reactive-only vs. also proactive/timer-based). Flagged as a file whose internal logic cannot be finalized until those two Open Decisions resolve; its existence (some 401-handling module) is certain from FR-4 regardless.

### Auth state / session layer (new)

- **`frontend/src/auth/authStore.ts`** (or a TanStack Query–backed equivalent) — new. Holds the access token **in memory only** (spec NFR: "Never `localStorage`/`sessionStorage`/a cookie the client sets itself") and the transient `mfa_token` between FR-3's login and mfa/verify calls (spec: "holding `mfa_token` only in transient state" — never persisted).
- **`frontend/src/auth/queryClient.ts`** — new TanStack Query client setup/provider, consumed by every screen's data-fetching (sessions list, etc.).

### Routing / guards / layout layer (new)

- **`frontend/src/routes/ProtectedRoute.tsx`** (or equivalent guard component) — new. FR-10: redirect unauthenticated visitors to `/login` and back to the originally-requested route after login.
- **`frontend/src/routes/GuestOnlyRoute.tsx`** (or equivalent) — new. FR-10's converse: an authenticated user hitting `/login` or `/register` is redirected to the placeholder authenticated home (content itself gated by `OD-8`, unresolved).
- **`frontend/src/layouts/AuthLayout.tsx`** — new. Spec NFR: "A distinct auth layout — with no main sidebar or header — is used for this Story's pre-authentication screens." Confirmed no such component can exist today since no `frontend/` tree exists; this is the file the v1 spec-review Major finding (now closed) traces to.
- **`frontend/src/layouts/AppShell.tsx`** (placeholder) — new, minimal. Needed as the authenticated-side counterpart to `AuthLayout`, hosting `OD-8`'s (unresolved) placeholder home content.

### Screens / pages layer (new)

- **`frontend/src/pages/RegisterPage.tsx`** — FR-1.
- **`frontend/src/pages/LoginPage.tsx`** — FR-2 and FR-3's initial submission (branches to MFA-verify screen on `MfaRequiredResponse`).
- **`frontend/src/pages/MfaVerifyPage.tsx`** — FR-3's second step.
- **`frontend/src/pages/ForgotPasswordPage.tsx`** — FR-7's request half.
- **`frontend/src/pages/ResetPasswordPage.tsx`** — FR-7's confirm half (reads `?token=...` from the URL).
- **`frontend/src/pages/SessionsPage.tsx`** — FR-6: list + revoke. Its "revoke" control's exact behavior on the current-session row is gated by `OD-6` (unresolved: disable/hide vs. let the `409 CurrentSessionError` surface).
- **`frontend/src/pages/PlaceholderHomePage.tsx`** — FR-2/FR-3's post-login landing target; content gated by `OD-8` (unresolved).
- **A logout/logout-all trigger** — FR-5. Likely a control inside `AppShell.tsx` rather than its own page; exact placement is an `ARCHITECTURE_PLANNING` call, not decided here.
- **An MFA-enrollment-deadline banner component** — surfaces `LoginResponse.mfa_enrollment_deadline`/`RefreshResponse.mfa_enrollment_deadline` (both confirmed present in `app/modules/users/schemas.py` today). Its exact copy/dismissal rule is gated by `OD-7` (unresolved); the component's existence is certain, its content is not.

### Forms / validation layer (new)

- **Per-screen form + validation-schema pairs** (React Hook Form, per spec Assumption #1) for Register, Login, MFA-verify, Forgot-password, Reset-password — FR-8's "blocks submission ... without calling the API" behavior. The **exact rule set** (password composition/length, email-shape regex) is gated by `OD-5`: confirmed by direct read of `app/modules/users/service.py` that Register's `_validate_password` (min 8 chars + upper/lower/digit/punctuation) and password-reset-confirm's policy (min 12 chars + breach-check + differs-from-current, both server-only checks the client cannot mirror) are two different, undocumented policies with no shared length constant — this Story's forms cannot be finalized against a single rule set until `OD-5` resolves.

### Shared / cross-cutting UI layer (new)

- **A generic error-state component** (retry-capable) — FR-11: network error / 5xx → generic retry UI, never a blank screen or unhandled exception. Consumed by every screen above.
- **A field-level error renderer** — FR-9's 422 `errors[]` → per-field message mapping, consumed by every form above.

## Cross-Module / Cross-Repo Ripple

This Story's only "cross-module" edge is a **new cross-repo dependency**: a to-be-created `frontend/` HTTP client calling the existing, already-shipped backend's `/auth/*` API surface as an **external HTTP contract**, not an internal `app/modules/*` service→service call in the `AGENTS.md` §3 sense (that section's router/service import-direction discipline governs backend-internal calls only and does not apply across a network boundary). This is flagged because it is a genuinely new fact for this repository — today nothing in the codebase calls the backend from a browser-based client — but it does not trigger any change to `app/modules/users/*` itself.

| Caller | Callee | New or existing | Reason |
|---|---|---|---|
| `frontend/src/api/authApi.ts` (new) | `POST /auth/register`, `POST /auth/login`, `POST /auth/mfa/verify`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/sessions`, `DELETE /auth/sessions/{family_id}`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm` | **New cross-repo edge** (existing backend endpoints, confirmed present in `app/modules/users/router.py`; new caller) | Every FR (FR-1..FR-7) is a browser-side consumer of an already-delivered backend contract — no backend file changes as a result. |
| Browser (automatic) | Backend's `httpOnly` refresh-token cookie (`Set-Cookie` on `/login`, `/refresh`, `/mfa/verify`; read on `/refresh`, `/logout`, `/sessions`, `DELETE /sessions/{family_id}`) | Existing mechanism, new consumer | FR-2's "refresh cookie is not read or stored by client code — only the browser holds it." Whether this cookie reaches the backend at all in dev depends on `OD-1` (same-origin proxy vs. cross-origin CORS change) — unresolved. |

No new dependency is introduced on any other `app/modules/*` package (`roles`, `support`, `admin_users`, etc.) — this Story's scope is exhaustively the `users` module's `/auth/*` surface per the spec's Out of Scope section ("MFA enrollment/activation UI ... a future Story," "Support Tickets UI — Story 5.2," "Admin UI, profile-editing UI — future Stories").

## Migration / Schema Impact

**None.** Confirmed explicitly: `DB_DESIGN` recorded verdict `NOT_APPLICABLE` for this Story (`docs/reviews/designs/US-5.1-design-review.md`, v1 — "no `database_design`/`entity_model` artifact exists to review; the spec states no persistence change is made"), and the approved specification's own Background/Out of Scope sections state "does not design or change any API, database schema, or backend behavior" / "Any backend/API/DB change" is out of scope. No table, column, index, or Alembic revision is affected by this Story. No existing backend repository query is affected.

## Test-Surface Impact

**No existing frontend test file can change — none exists.** Confirmed: `Glob frontend/**` returns no files, so there is nothing under a `frontend/` tree for this Story to modify; the entirety of this Story's test surface is new. (Existing backend test files under `tests/` are unaffected — this Story touches no backend code.)

**Wholly new test surface**, reconciled against the story's own Enforcement Matrix (`docs/stories/US-5.1-authentication-session-management.md` §Enforcement Matrix — every row there is `[gate]`, i.e. mandatory, not advisory) rather than re-derived from the spec's FRs alone:

- **FE-AC1–3, FE-AC5–7 → component/integration tests against a mocked API layer (MSW or equivalent)**: one test module per screen (Register, Login, MFA-verify, Sessions list, Forgot-password, Reset-password) covering that screen's own FR (FR-1, FR-2/FR-3, FR-3, FR-6, FR-7 x2). The Enforcement Matrix names the mocking tool (MSW) explicitly — a new dev-dependency and test-harness setup file (e.g. `frontend/src/test/mswServer.ts` or equivalent) this survey did not list as its own affected file until reconciling against the story; added here as a new test-infrastructure file, not a screen file.
- **FE-AC6 → a dedicated component test for list + revoke, including the "current session" marker** — called out as its own Matrix row distinct from the general FE-AC1–3/5–7 row; its exact revoke-affordance assertion is pending `OD-6`.
- **FE-AC4 → an integration test simulating a 401 mid-session** — FR-4's silent-refresh-on-401 behavior; single-flight and proactive-refresh assertions are pending `OD-2`/`OD-3`.
- **FE-AC8 → form-level unit tests (React Hook Form + validation schema)** — FR-8's per-screen blocked-submission behavior; the exact rule set is pending `OD-5`.
- **FE-AC9 → a test asserting problem+json `type`/`errors` map to rendered messages/fields** — FR-9's error-normalization layer; Register's two non-uniform shapes are pending `OD-4`.
- **FE-AC10 → route-guard unit/integration tests for both directions** — unauthenticated→login redirect-and-return; authenticated→placeholder-home redirect.
- **FE-AC11 → a test forcing a network/5xx failure per screen** — FR-11's generic retry-capable error state.
- **"a11y bar" → an automated accessibility check (e.g. axe) in CI on key screens** — a Matrix row with no corresponding FE-AC or FR at all (it traces instead to the spec's own NFR "full keyboard navigation and visible focus states on every form and interactive control"). This is a wholly distinct, CI-wired test category the FR-by-FR list above would have missed entirely; flagged here specifically because it is gated by `OD-9` (design-system choice) — a headless-UI primitive layer (Radix/Headless UI) versus hand-built components changes what this check can assume is already accessible by construction versus must be asserted per screen.
- An end-to-end or integration-level test path (tooling not yet chosen — no `frontend/` test runner exists today) exercising at least one full FR-2 login→placeholder-home flow and one FR-3 MFA-challenge→verify flow against a running or mocked backend — beyond the Matrix's per-AC rows, but implied by their combination (a login that both succeeds and redirects).

No test file for `app/modules/users/*` (`tests/unit/modules/users/`, `tests/integration/modules/users/`) is affected — this Story adds no backend behavior for those suites to cover.

## Findings Carried Forward (not resolved here — flagged for `planner`/upstream reconsideration)

- **OD-1 (CORS/cross-origin, OPEN) is a blast-radius-altering fact, not merely an implementation detail.** If OD-1 resolves toward an actual backend CORS/`allow_credentials` change rather than a same-origin Vite dev-proxy, this survey's "no backend file is affected" framing becomes false: `app/main.py`'s `CORSMiddleware` configuration would become an affected file after all, and the design-review's `NOT_APPLICABLE` verdict (predicated on "no backend/API/DB change") would need reconsideration. `API_DESIGN`'s own recorded non-blocking finding (`docs/workflow/workflow-state.yaml`) already flags this same conditional-invalidation risk. This survey does not resolve OD-1 and does not escalate to `changes_required_specification` on this basis — the spec correctly carries it as an open question rather than asserting a resolution — but `planner` should not have to rediscover that the "zero backend impact" premise is conditional on how OD-1 resolves.
- **OD-4 (Register's two non-RFC-7807 error shapes, OPEN) means FR-9 cannot be implemented uniformly across this Story's ten endpoints as literally written.** Confirmed by direct read of `app/main.py`/`app/modules/users/exceptions.py`: `RegistrationValidationError` and `DuplicateEmailError` are the only two response shapes among this Story's endpoints that do not carry the `application/problem+json` envelope FR-9 assumes for "any request in this Story." The `frontend/src/api/errorNormalization.ts` file listed above must special-case Register specifically regardless of how OD-4 resolves (client special-case vs. backend defect) — an upstream-artifact incompleteness `planner` should not have to re-derive from scratch.
