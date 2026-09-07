---
artifact_type: task_breakdown
story: US-5.1
version: 1
status: APPROVED
created_at: "2026-09-07T18:30:00Z"
updated_at: "2026-09-07T19:15:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
supersedes: null
---

# Task Breakdown — US-5.1

Track: `frontend` (per `docs/stories/US-5.1-authentication-session-management.md`
front matter). `API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE` — no
backend-track skill appears in this breakdown. The single execution skill on
this track is `frontend-builder`; layers below are `AGENTS.md` §3's Frontend
subsection table, not the backend layer table.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | scaffold/build config (AGENTS.md §2 Frontend stack) | — | frontend/package.json, vite.config.ts, tsconfig.json, tsconfig.node.json, index.html, src/main.tsx, src/App.tsx, src/vite-env.d.ts, .eslintrc.cjs (or eslint.config.js), .prettierrc, frontend/.env.example | `cd frontend && npm run lint && npm run format:check && npm run type-check` all exit 0 on the scaffold-only tree; `package.json` `scripts` are exactly `lint`, `format:check`, `type-check`, `test:coverage` (no others, no renames) |
| T2 | frontend-builder | `api/` | T1 | frontend/src/api/httpClient.ts, refreshCoordinator.ts, refreshCoordinator.test.ts, authApi.ts, errorNormalization.ts, errorNormalization.test.ts, types.ts | `npx vitest run frontend/src/api/refreshCoordinator.test.ts frontend/src/api/errorNormalization.test.ts` passes, including the concurrent-401 single-call proof and both Register non-RFC7807 branches; `grep -rl "from \"react\"\|@tanstack/react-query" frontend/src/api` returns no matches (AGENTS.md §3 `api/` row: must not import React/TanStack Query) |
| T3 | frontend-builder | `store/` (auth state) | T1 | frontend/src/store/authStore.tsx, frontend/src/store/queryClient.ts | `npx tsc --noEmit` clean; `grep -rl "from \"\.\./api\|from \"\.\./hooks" frontend/src/store` returns no matches (AGENTS.md §3 `store/` row: must not import `api/` or `hooks/`) |
| T4 | frontend-builder | test/ (test infrastructure) | T2, T3 | frontend/src/test/mswServer.ts, mswHandlers.ts, test-utils.tsx | `npx vitest run frontend/src/api/errorNormalization.test.ts` still passes once wired through `mswServer.ts`'s `beforeAll`/`afterEach`/`afterAll` (proves the harness boots — `frontend/src/test` itself holds no test files, so running it directly reports zero tests, not a pass); `grep -c "http\.\(get\|post\|delete\)" frontend/src/test/mswHandlers.ts` shows a handler for each of the 10 `/auth/*` operations plus Register's two non-RFC7807 shapes (`RegistrationValidationError`, `DuplicateEmailError`) |
| T5 | frontend-builder | `hooks/` | T2, T3, T4 | frontend/src/hooks/useRegister.ts(+.test.ts), useLogin, useMfaVerify, useLogout, useLogoutAll, useSessions, useRevokeSession, useRequestPasswordReset, useConfirmPasswordReset (each +.test.ts) | `npx vitest run frontend/src/hooks` passes for every hook's success/error mapping against MSW; `grep -rl "from \"react-router-dom\"" frontend/src/hooks` returns no matches; diff-read confirms session-mutating hooks update the store only in `onSuccess`, never inside a calling screen |
| T6 | frontend-builder | `hooks/`/`api/` boundary (integration) | T2, T3, T4, T5 | frontend/src/api/refreshCoordinator.integration.test.tsx | `npx vitest run frontend/src/api/refreshCoordinator.integration.test.tsx` passes (FE-AC4/Plan Testing Strategy: two-plus simultaneous authenticated hook calls both 401 via MSW, asserts exactly one `POST /auth/refresh` call and both original requests retried on success — the RTL+MSW integration proof distinct from `T2`'s unit-level single-flight test) |
| T7 | frontend-builder | `routes/` (guards) + `layouts/` | T3, T5 | frontend/src/routes/ProtectedRoute.tsx, GuestOnlyRoute.tsx, frontend/src/layouts/AuthLayout.tsx, AppShell.tsx | `npx vitest run frontend/src/routes/ProtectedRoute.test.tsx frontend/src/routes/GuestOnlyRoute.test.tsx frontend/src/layouts/AppShell.test.tsx` passes for both redirect directions **and** FE-AC5/FR-5 (Log out calls `useLogout`/`POST /auth/logout`, clears in-memory state, lands on `/login`; Log out everywhere calls `useLogoutAll`/`POST /auth/logout-all` with the same effect); `grep -rl "from \"\.\./api" frontend/src/routes` returns no matches (AGENTS.md §3 `routes/` row: must not import `api/` directly) — **gated on the `react-router-dom` dependency sign-off, see Notes** |
| T8 | frontend-builder | `components/` (shared UI) | T1 | frontend/src/components/ErrorState.tsx, FieldError.tsx, MfaEnrollmentBanner.tsx (+ tests) | `npx vitest run frontend/src/components` passes; `grep -rl "fetch(\|axios" frontend/src/components` returns no matches |
| T9 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/RegisterScreen.tsx, RegisterScreen.test.tsx | `npx vitest run frontend/src/screens/RegisterScreen.test.tsx` passes (FE-AC1, FE-AC8 email/password rules, FE-AC9, FE-AC11); no `vi.mock(` in the test file (pre-commit `frontend-vi-mock-in-integration-tests`); `grep -l "fetch(\|axios" frontend/src/screens/RegisterScreen.tsx` returns no matches |
| T10 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/LoginScreen.tsx, LoginScreen.test.tsx | `npx vitest run frontend/src/screens/LoginScreen.test.tsx` passes (FE-AC2, FE-AC3's initial branch to MFA-verify, FE-AC9, FE-AC11); no `vi.mock(` in the test file; grep confirms no bare `fetch`/`axios` |
| T11 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/MfaVerifyScreen.tsx, MfaVerifyScreen.test.tsx | `npx vitest run frontend/src/screens/MfaVerifyScreen.test.tsx` passes (FE-AC3's second step, TOTP + recovery code, FE-AC9, FE-AC11); no `vi.mock(` in the test file |
| T12 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/ForgotPasswordScreen.tsx, ForgotPasswordScreen.test.tsx | `npx vitest run frontend/src/screens/ForgotPasswordScreen.test.tsx` passes (FE-AC7's request half, FE-AC9, FE-AC11); no `vi.mock(` in the test file |
| T13 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/ResetPasswordScreen.tsx, ResetPasswordScreen.test.tsx | `npx vitest run frontend/src/screens/ResetPasswordScreen.test.tsx` passes (FE-AC7's confirm half, FE-AC8's 12-char client rule plus an explicit test that breach-check/differs-from-current are NOT simulated client-side, FE-AC9, FE-AC11); no `vi.mock(` in the test file |
| T14 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/SessionsScreen.tsx, SessionsScreen.test.tsx | `npx vitest run frontend/src/screens/SessionsScreen.test.tsx` passes (FE-AC6: list+revoke, current-session marker, revoke-affordance per the OD-6 default in force, FE-AC11); no `vi.mock(` in the test file |
| T15 | frontend-builder | `screens/` | T5, T7, T8, T4 | frontend/src/screens/PlaceholderHomeScreen.tsx, PlaceholderHomeScreen.test.tsx | `npx vitest run frontend/src/screens/PlaceholderHomeScreen.test.tsx` passes (post-login landing render, MfaEnrollmentBanner surfaced when `mfa_enrollment_deadline` present); no `vi.mock(` in the test file |
| T16 | frontend-builder | `routes/` (route table) | T7, T9, T10, T11, T12, T13, T14, T15 | frontend/src/routes/AppRoutes.tsx, AppRoutes.test.tsx | `npx vitest run frontend/src/routes/AppRoutes.test.tsx` passes for FE-AC10 both directions (unauthenticated→`/login`-and-back, authenticated→placeholder-home), rendering the real route tree in a memory router with no `vi.mock('react-router-dom')` — **gated on the `react-router-dom` dependency sign-off, see Notes** |
| T17 | gate-enforcer | — | T1–T16 | — | `cd frontend && npm run lint && npm run format:check && npm run type-check && npm run test:coverage` all pass; `pre-commit run --all-files` passes (frontend-scoped hooks: `frontend-lint`, `frontend-format`, `frontend-type-check`, `frontend-vi-mock-in-integration-tests`); diff-read confirms AGENTS.md §3 Frontend layer-table import directions (no `lint-imports` equivalent on this stack yet) |

`T2`/`T3` and `T6`/`T8` are parallel-eligible: `T2` and `T3` share only `T1`
as a dependency; `T8` shares only `T1` and can run alongside `T2`–`T7`; `T6`
(FE-AC4 integration proof) only needs `T2`/`T3`/`T4`/`T5` and can run
alongside `T7`. `T9`–`T15` (the seven screens) are mutually
parallel-eligible — each depends on `T5`/`T7`/`T8`/`T4` only, not on each
other.

## Notes (carried forward from the implementation plan, not resolved here)

- **New-dependency sign-off blocks `T7` and `T16` (`react-router-dom`), and
  the a11y-check portion of every screen task `T9`–`T15` (`vitest-axe` or
  equivalent).** Plan Risk 1: neither dependency appears in `AGENTS.md` §2's
  Frontend stack table or `frontend-builder`'s own scaffold list; both
  require explicit `AGENTS.md` §7.8 human propose/approve sign-off before
  `IMPLEMENTATION` adds them. This is not modeled as its own Task ID because
  the sign-off is a human gate, not an execution-skill task — but `T7`/`T16`
  cannot start, and the a11y assertion inside `T9`–`T15`'s verification
  cannot run, until it is recorded.
- **OD-gated content, not OD-gated existence** (Plan Risk 5): `T2`'s
  `errorNormalization.ts` implements the Register-special-case branch per
  Plan Change 8 regardless of OD-4; `T9`/`T13`'s validation rules use the
  literal constants Plan Change 7 already fixed (8-char Register, 12-char
  Reset-Password) pending OD-5; `T14`'s revoke-row uses an `isCurrent` prop
  per the OD-6 default; `T8`'s `MfaEnrollmentBanner` uses a plain dismissible
  banner per the OD-7 default; `T15`'s `PlaceholderHomeScreen` content is
  minimal/placeholder pending OD-8. None of these block scheduling — each
  task applies the plan's documented default unless a newer OD resolution is
  recorded before that task executes.
- **OD-1 (CORS) only affects `T1`'s `vite.config.ts` dev-proxy shape** (Plan
  Risk 2). If OD-1 later resolves toward an actual backend CORS change
  instead of a same-origin proxy, `T1` needs revisiting together with a
  backend task this breakdown does not contain (out of this Story's
  currently-approved zero-backend-file-change scope).
- **FE-AC4's integration proof (`T6`) has no path named in the plan's Files
  To Create** — the plan's Testing Strategy names the assertion (two-plus
  simultaneous authenticated calls, one refresh, both retried) but not a
  file. `T6`'s path (`frontend/src/api/refreshCoordinator.integration.test.tsx`)
  is this breakdown's placement, not a plan-fixed one; `test-writer`/
  `plan-reviewer` should confirm the location rather than assume it is
  settled.
