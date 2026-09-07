---
artifact_type: implementation_plan
story: US-5.1
version: 1
status: APPROVED
created_at: "2026-09-06T15:21:36Z"
updated_at: "2026-09-07T19:15:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.1-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.1-design-review.md
    version: 1
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
supersedes: null
---

# Implementation Plan: Authentication & Session Management — Frontend (US-5.1)

## Goal

Stand up the Customer Portal's first `frontend/` tree (React + Vite +
TypeScript + TanStack Query + React Hook Form, per the spec's Assumption #1
and `AGENTS.md` §2's Frontend stack table) and build the eleven FRs' worth of
screens, forms, routing, and session-handling that let a browser exercise the
already-shipped `/auth/*` backend contract end-to-end: register, login (with
the MFA-challenge branch), MFA verification, silent 401-triggered refresh,
logout/logout-all, active-sessions list+revoke, and password reset
(request+confirm) — plus the client-side validation, RFC 7807 error
rendering, route guards, and the distinct pre-auth layout common to all of
them. This Story changes no backend file (`API_DESIGN`/`DB_DESIGN` both
`NOT_APPLICABLE`, confirmed again by `design_review` v1 and
`impact_analysis` v1). Nine Open Decisions (OD-1..OD-9) remain `OPEN` through
an `APPROVED` spec; none is resolved by this plan — each is either designed
around so implementation can proceed regardless of how it resolves, or named
as a blocking dependency below.

## Architectural Changes

### 1. First-ever `frontend/` project in this repository — scaffold per `frontend-builder`'s own procedure, not invented here

`impact_analysis` confirmed no `frontend/`, `package.json`, `vite.config.*`,
or `tsconfig.json` exists anywhere in the repo today. `frontend-builder`'s
own `SKILL.md` §Workflow-1 already specifies the exact scaffold command
(`npm create vite@latest frontend -- --template react-ts`) and the exact
dependency set to add (TanStack Query, React Hook Form, Vitest, React
Testing Library, MSW, ESLint, Prettier) — this plan does not re-derive that
list, it defers to it, and constrains `frontend/package.json`'s four gate
scripts to the load-bearing names `AGENTS.md` §2 fixes: `lint`,
`format:check`, `type-check`, `test:coverage`.

### 2. Layering follows `AGENTS.md` §3's Frontend table exactly: `screens/` (not `pages/`)

`AGENTS.md` §3 and `frontend-builder`'s own `SKILL.md` both name the
top-of-stack directory `screens/`. `.pre-commit-config.yaml` already has a
frontend hook wired against this exact path
(`frontend-vi-mock-in-integration-tests`, `files: ^frontend/src/screens/.*\.test\.tsx$`,
confirmed by direct read) — this hook enforces "no `vi.mock()` of the unit
under test" specifically under `screens/`. `impact_analysis`'s own
illustrative file list used `frontend/src/pages/*.tsx` naming; this plan
deliberately does **not** follow that naming, because doing so would put
every screen test outside the one path the pre-commit hook already matches,
silently disabling that gate for every screen this Story adds. Directory
layout fixed by this plan:

```
frontend/src/
  api/          # httpClient, authApi, errorNormalization — the only fetch() layer
  store/        # authStore (React Context) — access token + current user, in memory only
  hooks/        # one hook per screen-facing operation, wraps api/ in TanStack Query
  routes/       # ProtectedRoute, GuestOnlyRoute, route table
  layouts/      # AuthLayout (no sidebar/header), AppShell (placeholder authenticated shell)
  screens/      # one screen component (+ its form) per FR, plus its *.test.tsx
  components/   # shared: ErrorState, FieldError, MfaEnrollmentBanner
  test/         # mswServer.ts, mswHandlers.ts, test-utils.tsx (provider-wrapped render)
```

Import direction matches `AGENTS.md` §3's table: `screens/`/`components/` →
`hooks/`, `store/` (read-only) → nothing lower; `api/` never imports React or
TanStack Query; `store/` never imports `api/` or `hooks/`. There is no
`lint-imports` equivalent for this stack yet (confirmed, `AGENTS.md` §3), so
this is checked by reading the diff — `frontend-builder`'s own "Self-check
before finishing" section already greps for exactly these violations
(bare `fetch(`/`axios` in `screens/`, `from "react"` in `api/`,
`localStorage`/`sessionStorage` next to token-shaped values).

### 3. Single-flight 401→refresh coordinator is the architecture regardless of how OD-2 resolves

FR-4 requires "the client calls `POST /auth/refresh` exactly once" on a 401.
`impact_analysis` and `frontend-builder`'s own `SKILL.md` (§4, §Verification
Checklist) already independently converge on the same requirement:
concurrent 401s across multiple in-flight TanStack Query calls must resolve
against **one shared in-flight refresh promise**, never one refresh attempt
per failing request — this is the only design that is safe under BR-008
(refresh-token single-use; a second, superseded cookie value looks like
theft) regardless of which way OD-2 is eventually answered. This plan fixes
`frontend/src/api/refreshCoordinator.ts` (or folded into `httpClient.ts`) as
a module-level singleton promise: the first 401 triggers
`POST /auth/refresh`; every 401 arriving while that promise is unsettled
awaits the same promise instead of issuing its own call; on success, all
waiters retry their original request; on failure, the store is cleared and
the app redirects to `/login` once, not once per waiter. OD-3 (proactive,
timer-based refresh ahead of expiry) is explicitly **not** built — FR-4's
text only requires the reactive, 401-triggered path, and no AC exercises a
timer. If OD-3 later resolves to require it, a `setTimeout` scheduled off
`LoginResponse.expires_in` is an additive hook alongside this coordinator,
not a rewrite of it.

### 4. Auth store: React Context + a custom hook, not a new state-management dependency

The spec's Client State Notes call for `accessToken` (in-memory only),
`isAuthenticated`, current user, and a transient `mfaToken`. The story's own
Assumption #2 names "a store, e.g. Zustand/Context" as illustrative
alternatives, not a fixed choice. This plan selects **React Context**
(`createContext`/`useReducer` or a small `useState`-based provider) over
Zustand: it satisfies `AGENTS.md` §3's `store/` layer contract (imports
neither `api/` nor `hooks/`; exposes actions only) with zero new dependency, and
`frontend-builder`'s own scaffold list (`SKILL.md` §Workflow-1) does not
name Zustand or any other store library — adding one would be an
unreviewed dependency under `AGENTS.md` §7.8 with no requirement forcing it.

### 5. Routing requires a new dependency neither `AGENTS.md` §2 nor `frontend-builder`'s scaffold list names — flagged, not silently added

FR-10's "redirected to `/login`, and back to the original route after a
successful login," and the `routes/` layer `AGENTS.md` §3 names outright,
both require real client-side routing (six distinct routes: `/register`,
`/login`, MFA-verify, `/forgot-password`, `/reset-password`, the sessions
screen, plus the placeholder authenticated home). Neither `AGENTS.md` §2's
Frontend stack table nor `frontend-builder`'s explicit
`npm create vite@latest ... ` + dependency-add list names a router. This
plan names `react-router-dom` (v6, `createBrowserRouter` +
`RouterProvider`) as the only reasonable choice for this need, but treats it
as a **new dependency requiring explicit propose/approve sign-off under
`AGENTS.md` §7.8** before `IMPLEMENTATION` adds it — see Risks. The plan's
file layout below assumes it is approved; if it is rejected, `routes/`'s
internal implementation changes (e.g. a hand-rolled history-based router)
but the guard/layout architecture in Change 2 does not.

### 6. Design system: hand-built, semantic-HTML components — the OD-9-safe default under `AGENTS.md` §7.8

OD-9 (headless-UI kit vs. hand-built) remains `OPEN`. Introducing a
component library (Radix/Headless UI + Tailwind) now would itself be a new,
unreviewed dependency under `AGENTS.md` §7.8, pre-empting a decision the
Story's own author explicitly deferred. This plan's baseline architecture
uses hand-built components with explicit `:focus-visible` styling and native
semantic elements (`<button>`, `<label htmlFor>`, `<fieldset>`) to satisfy
the NFR ("full keyboard navigation and visible focus states on every form
and interactive control") without pre-empting OD-9. If OD-9 later resolves
toward a headless-UI kit, adopting it is an additive follow-up — the
`screens/`/`components/` boundary this plan fixes does not change shape
either way.

### 7. Client-side validation: React Hook Form's native rules, no schema-resolver library; exact rule content stays open pending OD-5

`AGENTS.md` §2 and the story's Assumption #1 name React Hook Form, not a
schema-validation library (`zod`/`yup`). This plan uses RHF's built-in
`register(name, { required, pattern, minLength, validate })` rules rather
than adding a resolver dependency — keeps FR-8 achievable with zero new
dependency, and avoids committing to a validation-schema shape before OD-5
(exact per-screen rule set) resolves. What this plan **does** fix now,
because it is independently confirmed (not the OD-5 ambiguity) directly
from `app/modules/users/service.py` by `impact_analysis`: Register's
password rule (min 8 chars, upper+lower+digit+punctuation) and its email
format are checkable client-side; Reset-Password-Confirm's rule (min 12
chars) is checkable client-side, but its breach-check and differs-from-current
checks are server-only and cannot be pre-validated — those two screens'
forms must fall through to FR-9's server-error rendering for exactly those
two checks, never simulate them client-side. The literal constants (8 vs.
12, the exact punctuation set) are wired into each screen's own
`useForm` rules per screen, not a shared cross-screen policy object — OD-5
is about whether this mirroring is the intended approach at all, so this
plan does not present it as resolved, only as the most literal
currently-defensible default.

### 8. Error normalization architecture absorbs OD-4's two non-uniform Register shapes without deciding OD-4 itself

FR-9 assumes a uniform `application/problem+json` envelope; `RegistrationValidationError`
(400, `{"errors":[...]}`, plain `application/json`) and `DuplicateEmailError`
(409, `{"detail": "..."}`, plain `application/json`) do not carry it.
`frontend/src/api/errorNormalization.ts` defines one internal
`NormalizedApiError` shape (`{ status, message, fieldErrors? }`) that every
screen's error rendering consumes; the normalizer's implementation branches
on response shape (RFC 7807 `type`/`detail`/`errors` vs. Register's two
bespoke shapes) to always produce that one internal type. This means FR-9 is
satisfiable today regardless of how OD-4 is eventually answered: if OD-4
later decides the two Register shapes are a backend defect to fix, the two
branches in this one function become dead code to delete, not a
re-architecture of every screen's error handling.

### 9. Automated accessibility check: a new dependency, also flagged rather than silently added

The story's own Enforcement Matrix names "an automated a11y check (e.g.
axe)" as a `[gate]`-marked mandatory row. No such tool appears in
`AGENTS.md` §2's Frontend stack table or in `frontend-builder`'s explicit
scaffold dependency list. This plan names `vitest-axe` (or `jest-axe` run
under Vitest) as the mechanism, run against each screen's rendered DOM in
its existing RTL integration test — but, like Change 5, treats adding it as
a dependency requiring `AGENTS.md` §7.8 sign-off before `IMPLEMENTATION`,
not something this plan or `frontend-builder` may add unilaterally.

## Files To Create

### Project scaffold / build config
- `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`, `frontend/.eslintrc.cjs` (or `eslint.config.js`), `frontend/.prettierrc` — per `frontend-builder` Workflow-1's exact scaffold/dependency list. `package.json` scripts fixed to exactly `lint`, `format:check`, `type-check`, `test:coverage`.
- `frontend/vite.config.ts` dev-server proxy section — gated by OD-1 (OPEN). Planned default: `server.proxy` mapping `/api` to the backend, keeping the spec's "no backend changes" premise true and letting the browser treat the refresh cookie as same-origin. If OD-1 resolves to a cross-origin/CORS approach instead, this file's shape changes and `app/main.py`'s CORS middleware becomes an affected file after all (already flagged by `impact_analysis`'s Findings Carried Forward) — out of this plan's file list unless OD-1 resolves that way.
- `frontend/.env.example` — new, frontend-scoped (distinct from the repo-root `.env.example`, which stays backend-only per `AGENTS.md` §4). Documents `VITE_API_BASE_URL` or equivalent if the OD-1 proxy needs a target.

### API-client / HTTP layer (`frontend/src/api/`)
- `httpClient.ts` — fetch-based wrapper (no axios — no new dependency needed); attaches the in-memory access token as `Bearer`; the one interception point for 401 handling.
- `refreshCoordinator.ts` + `refreshCoordinator.test.ts` — single-flight `/auth/refresh` coordinator (Architectural Change 3) and its Vitest unit test (concurrent-caller/single-call proof, Risk 3).
- `authApi.ts` — one typed function per backend operation: `register`, `login`, `verifyMfa`, `refresh`, `logout`, `logoutAll`, `listSessions`, `revokeSession`, `requestPasswordReset`, `confirmPasswordReset`. Types mirror the spec's API Contract table exactly.
- `errorNormalization.ts` + `errorNormalization.test.ts` — the `NormalizedApiError` mapper (Architectural Change 8) and its Vitest unit test (RFC 7807 branch plus both Register non-conforming shapes, OD-4).
- `types.ts` — DTOs (`UserRead`, `LoginResponse`, `MfaRequiredResponse`, `MfaVerifyResponse`, `RefreshResponse`, `SessionListResponse`/`SessionEntry`, `PasswordResetRequestResponse`, request bodies) mirrored from the spec's API Contract table.

### Auth state / session layer (`frontend/src/store/`)
- `authStore.tsx` — React Context provider + `useAuthStore()` hook. Holds `accessToken` (memory only), `isAuthenticated`, current user, transient `mfaToken` (cleared after use or navigation away). Actions: `setSession`, `setMfaToken`, `clearSession`.
- `queryClient.ts` — TanStack Query client instance + `<QueryClientProvider>` wiring in `App.tsx`.

### Routing / guards / layout (`frontend/src/routes/`, `frontend/src/layouts/`)
- `routes/ProtectedRoute.tsx` — FR-10: unauthenticated → `/login`, remembers the originally-requested route for post-login return.
- `routes/GuestOnlyRoute.tsx` — FR-10's converse: authenticated visiting `/login`/`/register` → placeholder home.
- `routes/AppRoutes.tsx` — the route table (`react-router-dom`, pending Change 5's sign-off).
- `layouts/AuthLayout.tsx` — no sidebar/header, wraps pre-auth screens (spec NFR; the v1 spec-review Major finding this closes).
- `layouts/AppShell.tsx` — minimal authenticated shell hosting the placeholder home content and the logout/logout-all control (FR-5).

### Screens (`frontend/src/screens/`) — one component + one `*.test.tsx` per entry
- `RegisterScreen.tsx` — FR-1.
- `LoginScreen.tsx` — FR-2, and FR-3's initial submission (branches to MFA-verify on `MfaRequiredResponse`).
- `MfaVerifyScreen.tsx` — FR-3's second step (TOTP or recovery code).
- `ForgotPasswordScreen.tsx` — FR-7's request half.
- `ResetPasswordScreen.tsx` — FR-7's confirm half; reads `?token=...`.
- `SessionsScreen.tsx` — FR-6: list + revoke; revoke-control behavior on the current-session row gated by OD-6 (OPEN) — built so the row component takes an `isCurrent` prop, making either OD-6 answer a prop/branch change, not a re-architecture.
- `PlaceholderHomeScreen.tsx` — FR-2/FR-3's post-login landing target; content gated by OD-8 (OPEN).

### Shared components (`frontend/src/components/`)
- `ErrorState.tsx` — FR-11's generic, retry-capable error state; consumed by every screen.
- `FieldError.tsx` — FR-9's per-field 422 `errors[]` renderer; consumed by every form.
- `MfaEnrollmentBanner.tsx` — surfaces `mfa_enrollment_deadline`; copy/dismissal-persistence gated by OD-7 (OPEN); dismissal state in `sessionStorage` (non-sensitive, per spec's own Client State Notes).

### Hooks (`frontend/src/hooks/`)
- One hook + one `*.test.ts` per screen-facing operation (`useRegister`, `useLogin`, `useMfaVerify`, `useLogout`, `useLogoutAll`, `useSessions`, `useRevokeSession`, `useRequestPasswordReset`, `useConfirmPasswordReset`), each wrapping the matching `api/` function in a TanStack Query `useMutation`/`useQuery`. Mutations that change session state update the store in `onSuccess`, never inside the calling screen (`frontend-builder` SKILL.md §4). Each hook's test exercises its own success/error mapping via MSW, not `vi.mock()` of the hook itself.

### Test infrastructure (`frontend/src/test/`)
- `mswServer.ts` — MSW server setup (Vitest `beforeAll`/`afterEach`/`afterAll` wiring).
- `mswHandlers.ts` — one handler per backend operation, shaped exactly like the real responses, **including** Register's two non-RFC7807 shapes (OD-4) and the RFC 7807 envelope for every other endpoint.
- `test-utils.tsx` — a provider-wrapped `render()` (Query client + auth store + router) for screen tests.

## Files To Modify

None. `impact_analysis` confirmed no `frontend/` tree, `package.json`,
`vite.config.*`, or `tsconfig.json` exists anywhere in the repo — every file
above is new. `.pre-commit-config.yaml` already contains the four
frontend-scoped hooks (`frontend-lint`, `frontend-format`,
`frontend-type-check`, `frontend-vi-mock-in-integration-tests`), confirmed
by direct read — this Story needs no further edit to it. It remains a
protected file under `AGENTS.md` §7.9; if any future task in this Story's
`task_breakdown` discovers it does need a change, that change requires
explicit human sign-off, not a silent edit. `app/modules/users/*` and
`app/main.py` are read-only reference contracts per the spec's own
Background/Out of Scope — no line in either changes.

## Risks

1. **Two new dependencies neither `AGENTS.md` §2 nor `frontend-builder`'s
   explicit scaffold list names, required by structural gaps in this
   Story's own scope: `react-router-dom` (routing/guards, FR-10; Change 5)
   and an automated a11y-check library, e.g. `vitest-axe` (the Enforcement
   Matrix's own `[gate]` "a11y bar" row; Change 9).** Both require explicit
   propose/approve sign-off under `AGENTS.md` §7.8 before `IMPLEMENTATION`
   adds them as dependencies — flagged here rather than silently included in
   `frontend-builder`'s eventual `package.json` diff.
2. **OD-1 (CORS/cross-origin, OPEN) can retroactively invalidate this
   plan's "zero backend file changes" premise.** This plan's default
   (`vite.config.ts` dev-proxy, same-origin) keeps that premise true; if
   OD-1 resolves toward an actual `app/main.py` CORS/`allow_credentials`
   change instead, `design_review`'s `NOT_APPLICABLE` verdict and this
   plan's Files-To-Modify (currently empty for the backend) both need
   reconsideration. Carried forward from `impact_analysis`'s own Findings,
   not re-decided here.
3. **OD-2 (concurrent-401 single-flight) is mitigated architecturally
   (Change 3) but not eliminated as a review question.** The single-flight
   coordinator satisfies FR-4's literal text and BR-008's safety concern
   regardless of OD-2's eventual answer, but `test-writer`/
   `reconciliation-reviewer` should confirm this design decision, not
   assume OD-2 was silently resolved by it.
4. **OD-3 (proactive refresh) is out of this plan's scope by design.**
   If OD-3 later resolves to require a timer-based pre-emptive refresh, it
   is additive to `refreshCoordinator.ts`, not a rewrite — but until then,
   every natural token expiry produces one visible failed-request-then-retry
   stutter, which is expected, not a defect, under the current OD-3 answer
   (silence).
5. **OD-4, OD-5, OD-6, OD-7, OD-8 all bound specific files' exact content,
   not their existence.** `errorNormalization.ts` (OD-4), each screen's
   validation rules (OD-5), `SessionsScreen.tsx`'s revoke-row behavior
   (OD-6), `MfaEnrollmentBanner.tsx`'s copy (OD-7), and
   `PlaceholderHomeScreen.tsx`'s content (OD-8) are all named in Files To
   Create with their structure fixed and their literal content flagged as
   pending. `implementation-planner`'s task breakdown should not schedule
   final content for these without confirming the relevant OD has resolved,
   or explicitly accepting the documented default (Changes 6–8 above)
   named here.
6. **OD-9 (design-system choice) is resolved for planning purposes only
   as "no new dependency, hand-built components" (Change 6), specifically
   because introducing a UI-kit dependency now would itself violate
   `AGENTS.md` §7.8.** This is a planning default under an explicit
   constraint, not OD-9 being answered — a later decision to adopt a
   headless-UI kit remains open and additive.
7. **Directory naming: `screens/`, not `pages/`.** `impact_analysis`'s
   illustrative file list used `frontend/src/pages/*.tsx`; this plan
   deliberately uses `frontend/src/screens/` instead (Architectural Change
   2) because `.pre-commit-config.yaml`'s
   `frontend-vi-mock-in-integration-tests` hook is already scoped to
   `^frontend/src/screens/.*\.test\.tsx$`. Using `pages/` would silently
   disable that gate for every test this Story adds — `frontend-builder`
   and `test-writer` must follow this plan's naming, not
   `impact_analysis`'s illustrative one.
8. **First-ever frontend project in this repository.** No sibling
   `frontend/` config exists to mirror; this plan relies on
   `frontend-builder`'s own explicit scaffold command
   (`npm create vite@latest frontend -- --template react-ts`) as the single
   source of the initial file shape, rather than inventing one here.
9. **Access-token/mfa-token handling is security-sensitive by the spec's
   own NFRs.** Architecture (Context-based store, no persistence, no
   console logging of sensitive fields) is fixed by Changes 3–4; enforcement
   is `frontend-builder`'s self-check grep plus `security-reviewer` at its
   own stage — not re-verified by this plan.

## Validation Strategy

- **Product-level NFRs** (`docs/product/non-functional-requirements.md`):
  read in full — every entry (password/secret handling, anti-enumeration,
  rate limiting, revocation latency, DB invariants, audit, performance
  budgets) is a backend-process or backend-endpoint concern with no
  browser-support matrix, WCAG level, or frontend-specific bar stated. This
  Story's own spec NFRs (access-token-in-memory, no sensitive console
  logging, keyboard/focus, responsiveness, loading/error states) already
  supersede it for frontend purposes; NFR-001's "never in a log line"
  scrubbing rule and NFR-002's anti-enumeration behavior are both already
  backend-enforced and this Story's client code only needs to not
  contradict them (e.g. `errorNormalization.ts`/FR-7 must not surface
  account-existence information the backend's generic message already
  withholds).
- **Gate green**: `npm run lint`, `npm run format:check`, `npm run
  type-check`, `npm run test:coverage` (`AGENTS.md` §2's Frontend
  subsection — these four names are load-bearing and already wired into
  `.pre-commit-config.yaml` scoped to `files: ^frontend/`, confirmed by
  direct read, so a Python-only commit never pays for them). `test:coverage`
  itself runs in CI only, same split as the backend's coverage threshold —
  CI is the authority (`AGENTS.md` §6's Frontend subsection).
- **Contracts intact (no `lint-imports` equivalent yet)**: the `AGENTS.md`
  §3 Frontend layer table (Architectural Change 2) is checked by reading the
  diff — `frontend-builder`'s own "Self-check before finishing" section
  (grep `screens/`/`components/` for bare `fetch(`/`axios`; grep `api/` for
  `from "react"`/TanStack Query imports; grep the whole diff for
  `localStorage`/`sessionStorage` next to token-shaped values) is the
  mechanical proxy for this until a real contract exists.
- **New-dependency sign-off**: `react-router-dom` and the chosen a11y-check
  library (Risk 1) are proposed, not added, until a human explicitly
  approves them per `AGENTS.md` §7.8 — this gate runs before
  `IMPLEMENTATION`, not as part of the automated pre-commit/CI gates above.
- **Migrations / runtime rules**: not applicable to this stack (`AGENTS.md`
  §6's Frontend subsection) — no ORM, cache, or migration exists here.
- **Contract & security**: no sensitive value (password, access token,
  recovery code) ever reaches the browser console or a committed file; the
  access/refresh-token handling fixed in `AGENTS.md` §3's session-handling
  rule and Architectural Changes 3–4 is followed exactly, verified by
  `frontend-builder`'s grep-based self-check and confirmed independently at
  `SECURITY_REVIEW`.

## Testing Strategy

Per `AGENTS.md` §5's Frontend subsection: Vitest unit tests for hooks/pure
functions, React Testing Library + MSW integration tests per screen (the
network boundary is the fake, never the component/hook/store under test —
no `vi.mock()` of the unit under test), 85% coverage floor via
`test:coverage`, CI-enforced.

- **Unit** — `refreshCoordinator.ts`'s single-flight behavior (multiple
  concurrent callers awaiting one shared promise, exactly one `POST
  /auth/refresh` call — the concrete proof for Risk 3/OD-2's mitigation);
  `errorNormalization.ts`'s branch coverage over RFC 7807 shapes **and**
  Register's two non-conforming shapes (OD-4); each screen's RHF validation
  rules that are independently confirmed (Register's email/password
  composition, Reset-Password's length floor) plus an explicit test that
  the two server-only checks (breach, differs-from-current) are **not**
  simulated client-side and instead fall through to server-error rendering.
- **Integration (RTL + MSW)** — one test module per screen per
  `impact_analysis`'s Test-Surface Impact section, reconciled against the
  story's own Enforcement Matrix (every row `[gate]`, mandatory):
  - FE-AC1–3, FE-AC5–7: Register, Login (both branches), MFA-verify,
    Sessions (list+revoke), Forgot-password, Reset-password — each against
    MSW handlers shaped like the real backend responses.
  - FE-AC4: a dedicated test firing two-plus simultaneous authenticated
    requests that both 401, asserting exactly one `/auth/refresh` call and
    both original requests retried on success (the single-flight proof
    `frontend-builder`'s own Verification Checklist already requires).
  - FE-AC6: sessions list+revoke, current-session marker rendered, and
    revoke-affordance behavior per whichever OD-6 default is in force at
    build time (Risk 5) — explicitly asserted, not left implicit.
  - FE-AC8: per-screen blocked-submission tests for every rule that is
    confirmed today (Change 7); rules gated by OD-5 flagged as pending in
    the test file until OD-5 resolves.
  - FE-AC9: problem+json `type`/`errors` → rendered message/field mapping,
    **plus** a dedicated case per Register's two non-uniform shapes (OD-4).
  - FE-AC10: route-guard tests both directions, including
    redirect-to-originally-requested-route after login. `.pre-commit-config.yaml`'s
    `frontend-vi-mock-in-integration-tests` hook bans **any** `vi.mock(` call
    under `frontend/src/screens/*.test.tsx` (not only mocking the unit under
    test) — this test asserts the resulting route by rendering the real
    route tree inside a memory router and reading where it lands, never by
    `vi.mock('react-router-dom')` to spy on `useNavigate`. This restriction
    is scoped to `screens/`; tests under `hooks/`, `api/`, `store/`,
    `routes/` are not matched by the hook and are checked by diff review
    only (Validation Strategy).
  - FE-AC11: a network-error and a 5xx test per screen, asserting
    `ErrorState.tsx` renders (never a blank screen, never an unhandled
    rejection reaching the console).
  - a11y bar: an automated check (Risk 1, pending sign-off) run against
    each screen's rendered DOM in its own integration test file, not a
    separate suite.
- **New test infrastructure** (no existing frontend test file to extend —
  this is the first frontend code in the repo): `mswServer.ts`,
  `mswHandlers.ts`, `test-utils.tsx` (Files To Create, Test infrastructure
  section) — one-time setup, not per-screen.
- **Coverage** — 85% floor via `test:coverage`, `AGENTS.md` §5/§6's
  Frontend subsection; a floor, not a goal — no exclusion for the
  refresh-coordinator's concurrency branch or the error-normalization
  layer's Register-specific special-casing.
