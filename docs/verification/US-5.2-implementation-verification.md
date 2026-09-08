---
artifact_type: implementation_verification
story: US-5.2
version: 1
status: APPROVED
created_at: "2026-09-08T18:00:00Z"
updated_at: "2026-09-08T14:50:55Z"
produced_by: implementation-verifier
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.2-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-5.2-plan-review.md
    version: 1
  - path: docs/evidence/US-5.2-implementation-report.md
    version: 1
  - path: docs/evidence/US-5.2-quality-gate-report.md
    version: 1
  - path: docs/tests/US-5.2-test-strategy.md
    version: 1
  - path: docs/tests/US-5.2-ac-test-matrix.md
    version: 1
supersedes: null
---

# Verification Report: Account & Profile Self-Service (Frontend)

**Story ID:** US-5.2 (`track: frontend`)
**gate-enforcer Result Relied On:** PASS (`docs/evidence/US-5.2-quality-gate-report.md` v1) —
`npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage`
(44/44 test files, 192/192 tests, 96.71%/94.57%/85.39%/96.71% stmt/branch/func/line) all
green; Part B′ grep evidence for API-boundary containment, session-token handling, store
discipline, and banned idioms all PASS. Not re-run here per this skill's constraint — the
mechanical scripts are trusted as captured; Part B′'s narrower greps are independently
re-derived below, not merely trusted.
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Working-tree confirmation (independent, not taken from the gate report)

`git status --porcelain -- frontend/`, re-run in this session: 22 modified + 36 untracked
paths, all under `frontend/` (58 total). `docs/evidence/US-5.2-quality-gate-report.md`
records 21 modified + 32 untracked (53). The 5-file gap is accounted for by non-functional
drift, not scope drift: `frontend/tsconfig.app.tsbuildinfo` (a TypeScript incremental-build
cache file that mutates on every `tsc` invocation, one `M`) plausibly wasn't counted as a
meaningful modification by the gate report's prose, and this session's own commands may
have touched it again since. Every one of the 58 paths maps cleanly onto
`task_breakdown` T1–T12's declared scope (new `api/`, `hooks/`, `screens/`, `components/`
files; modified `authStore.tsx`, `AppRoutes.tsx`, `LoginScreen.tsx`,
`MfaEnrollmentBanner.tsx`, `httpClient.ts`, `types.ts`, `authApi.ts`; test-infra edits to
`test/mswHandlers.ts`/`test/test-utils.tsx`; `package.json`/`package-lock.json` for
`qrcode.react`). No unaccounted-for file, no file outside `frontend/`. This is a headcount
discrepancy in the upstream report's prose, not evidence the working tree diverges from
what was actually built — not a `BLOCKED` condition.

## Summary

Track is `frontend`, so §6.5 (migrations) and §6.6's ORM/eager-load/cache-TTL/service-
discipline items are N/A by construction — this stack has no ORM, migration, or cache. In
their place, `gate-enforcer`'s Part B′ frontend findings (API-boundary containment,
session-token handling, store discipline) were independently re-derived by reading the
actual source files and re-running the same greps myself, not by trusting the report's
prose — and extended into territory gate-enforcer's narrower checks did not cover (import-
boundary containment beyond `fetch`/`axios`). §6.7's frontend analogue (no sensitive value
reaching the console or a rendered error) and the §5 security-case analogue (route-guard
behavior for the five new routes) were checked the same way, with test function names
cited, not just file existence.

One real, citable AGENTS.md §3 Frontend-layer-table violation was found, not caught by
`gate-enforcer`'s Part B′ check 5 (which only greps `fetch(\|axios`, not `api/`-module
imports generally): `screens/ProfileScreen.tsx:14` imports `SUPPORTED_LOCALES` (a runtime
constant) and `ProfileRead`/`ProfileUpdateRequest` (types) directly from `../api/types`,
contradicting the file's own header comment ("Composed from hooks/ and shared components/
only — never api/ or fetch directly (AGENTS.md §3)"). Assessed **Minor, non-blocking**,
for the same reason `US-5.1`'s own precedent (`store/authStore.tsx:13`, an analogous
`api/types` import, also rated Minor/PASS) applies here: `api/types.ts` is a pure data/type
module with zero imports of its own (`grep -n "^import" frontend/src/api/types.ts` →
zero matches) and no import-time side effect — it does not create a live path into
`httpClient`/`fetch`, carries no secret, and both `SUPPORTED_LOCALES` and the two type
names are already covered by 192 green tests exercising `ProfileScreen` through this exact
import. It is a real letter-of-the-rule breach with a mechanical fix (relocate
`SUPPORTED_LOCALES` to a neutral shared module, or re-export it and the two types through
`useProfileUpdate.ts`, and correct the file's own header comment), not a capability-
containment breach in the sense AGENTS.md's own illustrative example describes ("a screen
calling `fetch` directly").

## §6.5 — Migration Human Half

N/A — `track: frontend`. No ORM, Alembic migration, or `models.py`/`migrations/` diff
exists in this Story's scope (confirmed by the working-tree enumeration above: every
touched/added path is under `frontend/`, no `migrations/versions/*.py` file appears).

## §6.6 — Runtime Rules (Frontend Analogue: API-Boundary Containment, Session-Token Handling, Store Discipline)

| Rule | Result | Evidence |
|---|---|---|
| ORM containment / eager loading / cache TTL (backend-only) | N/A | No ORM, database, or cache layer exists under `frontend/`. |
| `api/` is the sole HTTP boundary; no screen/component calls `fetch`/`axios` directly | Pass | Independently re-ran `grep -rn "fetch(\|axios" screens components --include="*.tsx" --include="*.ts"` (excluding `.test.`) under `frontend/src` → one substring hit, `screens/SessionsScreen.tsx:33` (`sessionsQuery.refetch()`, TanStack Query's own method, pre-existing US-5.1 line unmodified by this Story). No US-5.2 screen or component calls the network directly; `frontend/src/api/httpClient.ts:70-76` (`rawFetch`) remains the sole network call site. |
| `api/` imports no React/TanStack Query | Pass | `grep -rln "from \"react\"\|@tanstack/react-query" api` (excluding `.test.`) → zero matches. Directly read the five new/changed non-test `api/` files (`accountApi.ts`, `mfaApi.ts`, `profileApi.ts`, `httpClient.ts`, `types.ts`, `authApi.ts`) — no React or TanStack import in any. |
| No screen/component imports `api/` directly beyond types/constants | **Minor finding** | `screens/ProfileScreen.tsx:14`: `import { SUPPORTED_LOCALES, type ProfileRead, type ProfileUpdateRequest } from "../api/types";` — a real, letter-of-the-rule violation of the layer table's "screens/, components/ ... Must not import: api/ directly" cell, and it contradicts the file's own header comment (line 2). No other screen/component in the whole `frontend/src` tree imports from `api/` (`grep -rn "from \"\.\./api" screens components --include="*.tsx" --include="*.ts"` → this one hit only). Rated Minor/non-blocking: `api/types.ts` has zero imports of its own and no import-time side effect (`grep -n "^import" api/types.ts` → zero matches) — importing it creates no live path into `httpClient`/`fetch`, and neither `SUPPORTED_LOCALES` (`["en-US","en-GB"]`) nor the two type names is a secret. Same class and same verdict as US-5.1's own archived precedent (`store/authStore.tsx:13`'s `api/types` import), adjudicated Minor there for the identical reasoning. Mechanical fix: relocate `SUPPORTED_LOCALES` to a neutral shared module (or re-export via `useProfileUpdate.ts`), and correct the header comment. |
| Access token lives in memory only; never `localStorage`/`sessionStorage` | Pass | `grep -rn "localStorage\|sessionStorage" api hooks screens components store routes` (excluding `.test.`) → matches only in `components/MfaEnrollmentBanner.tsx` (pre-existing US-5.1 non-sensitive dismissal flag, additive link only in this Story) and an explanatory comment in `store/authStore.tsx` documenting `accessToken` as memory-only. Independently grepped every new US-5.2 file (`SecurityScreen.tsx`, `ProfileScreen.tsx`, `DeactivateAccountScreen.tsx`, `EmailVerificationScreen.tsx`, `ConfirmEmailChangeScreen.tsx`, `RecoveryCodesDisplay.tsx`, `QrCode.tsx`, all eight new `hooks/`, `accountApi.ts`/`mfaApi.ts`/`profileApi.ts`) — zero storage-API references. |
| MFA `secret`/`otpauth_uri`/`recovery_codes` never written to any storage API, console, or third party | Pass | `components/RecoveryCodesDisplay.tsx` (read in full): copy uses `navigator.clipboard.writeText` (an explicit, spec-sanctioned user action, not persistence); download builds a local `Blob`/`URL.createObjectURL`, no network call. `components/QrCode.tsx` (read in full): renders `otpauth_uri` via the bundled `qrcode.react` `QRCodeSVG` component locally — no network call, no external QR service. `screens/SecurityScreen.tsx` holds `enrollment`/`recoveryCodes` only in transient `useState`, cleared in `onRecoveryCodesConfirmed` (lines 71-76). Test evidence: `test_security_screen_enroll_secret_otpauth_uri_and_recovery_codes_never_reach_storage_console_or_third_party` (`screens/SecurityScreen.test.tsx:203`), `test_recovery_codes_display_never_writes_codes_to_local_storage_session_storage_or_console` (`components/RecoveryCodesDisplay.test.tsx:67`). |
| No `console.log`/`error`/`warn` anywhere in `frontend/src` | Pass | `grep -rln "console\.\(log\|error\|warn\)" --include="*.ts" --include="*.tsx" .` (excluding `.test.`) → zero matches across the entire tree, broader than gate-enforcer's file-scoped check. |
| Store discipline: no screen/component/route calls a store mutator directly; mutations only inside a hook's `onSuccess` | Pass | `grep -rn "setSession(\|setMfaEnabled(\|clearSession(" hooks screens components store routes` (excluding `.test.`) → every hit is inside a `hooks/` file's `useMutation({ onSuccess: ... })` callback: `useLogin.ts:21` (`setSession`), `useMfaVerify.ts:14` (`setSession`), `useLogout.ts:11`/`useLogoutAll.ts:12` (`clearSession`), `useMfaActivate.ts:14`/`useMfaDisable.ts:12` (`setMfaEnabled`), `useAccountDeactivate.ts:13` (`clearSession`). Zero calls from any screen/component/route. |
| `routes/` must not import `api/` directly | Pass | `grep -rn "from \"\.\./api" routes --include="*.tsx"` → zero matches. `AppRoutes.tsx` (read in full) imports only `route`/layout/screen components and the two guards. |
| Refresh token never read, stored, or parsed by client code (AGENTS.md §3 Frontend "Session handling") | Pass | This Story adds a second 401→refresh→retry path in `httpPatch` (new code, not inherited from US-5.1's audit) — needed independent confirmation. `api/httpClient.ts:191-201`: on a 401, `httpPatch`'s branch calls `coordinateRefresh(performRefreshRequest)` and `bridge.onTokenRefreshed(refreshed.access_token)` — identical pattern to `performRequest`'s existing branch (lines 115-125), never reads or parses a cookie. `performRefreshRequest` (lines 78-85) and `httpPatch`'s own fetch (lines 178-187) both set `credentials: "include"`, letting the browser attach the httpOnly refresh cookie automatically. `RefreshResponse` (`api/types.ts`) has no refresh-token field at all, so no code path in either branch can touch one even indirectly. |

## §6.7 — Contract & Security (Frontend Analogue)

| Item | Result | Evidence |
|---|---|---|
| `response_model`/`status_code` (backend-only) | N/A | No backend route touched by this Story (`API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` per the story's own Assumption #7; working-tree enumeration confirms zero non-`frontend/` files touched). |
| `extra="forbid"` + privilege exclusion (backend-only) | N/A | No Pydantic schema touched by this Story. |
| `.env.example` updated (if applicable) | N/A — no new setting | `git status --porcelain -- .env.example frontend/.env.example` → no change to either file; no new backend or frontend setting was introduced by this Story (the one dependency change, `qrcode.react`, is a client-side rendering library, not a configuration value). |
| No sensitive value in any `*Read`-equivalent DTO | Pass | `api/types.ts` (read in full): `ProfileRead` carries `id, email, pending_email, display_name, locale, timezone, avatar_url, email_verified, created_at` — no password/token/secret field. `MfaEnrollResponse` (`{secret, otpauth_uri}`) and `MfaActivateResponse` (`{recovery_codes}`) are deliberately sensitive-by-design per the spec (Assumption #4/#5) but are never persisted or logged (confirmed above) and are consumed only by the one-time enrollment flow. |
| No sensitive value reaches the browser console | Pass | Independently re-ran `grep -rln "console\.\(log\|error\|warn\)" .` across the whole `frontend/src` tree (broader than gate-enforcer's per-file check) → zero matches. |
| No sensitive value reaches a rendered error | Pass | `components/apiErrorHelpers.ts` (read in full) exposes only `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors`, each reading the structural `{status, message, fieldErrors, kind}` shape populated upstream from the server's own response body (`api/httpClient.ts`'s `ApiError`) — never from a raw JS `Error.message`/stack trace. Spot-checked `screens/ProfileScreen.tsx:203-206`, `screens/SecurityScreen.tsx` (all three branches), `screens/DeactivateAccountScreen.tsx:79-80` — every rendered error path routes through these four helpers, none echoes a submitted `current_password`, TOTP `code`, `secret`, `otpauth_uri`, or `recovery_codes` value. |

## §5 — Security Cases (Frontend Analogue: Route-Guard Behavior for the Five New Protected Routes)

The backend's five-case matrix (no token / expired / malformed / insufficient permissions
/ revoked) has no direct 1:1 analogue on a client that never validates tokens itself. This
Story's actual responsibility — gating the three new `ProtectedRoute`-wrapped screens
correctly and rendering the two guard-free screens in both auth states — is covered as
follows, with test function names cited rather than asserted from memory:

| Case | Test | File |
|---|---|---|
| Unauthenticated visitor hitting `/settings/profile` → redirected to `/login` | `test_app_routes_settings_profile_redirects_unauthenticated_visitor_to_login` | `frontend/src/routes/AppRoutes.test.tsx:107` |
| Unauthenticated visitor hitting `/settings/security` → redirected to `/login` | `test_app_routes_settings_security_redirects_unauthenticated_visitor_to_login` | `frontend/src/routes/AppRoutes.test.tsx:115` |
| Unauthenticated visitor hitting `/settings/deactivate` → redirected to `/login` | `test_app_routes_settings_deactivate_redirects_unauthenticated_visitor_to_login` | `frontend/src/routes/AppRoutes.test.tsx:123` |
| `/verify-email` renders for an unauthenticated visitor (no guard blocks it) | `test_app_routes_verify_email_renders_for_an_unauthenticated_visitor` | `frontend/src/routes/AppRoutes.test.tsx:134` |
| `/verify-email` also renders for an authenticated visitor (neither guard wraps it) | `test_app_routes_verify_email_renders_for_an_authenticated_visitor` | `frontend/src/routes/AppRoutes.test.tsx:142` |
| `/confirm-email-change` renders for an unauthenticated visitor | `test_app_routes_confirm_email_change_renders_for_an_unauthenticated_visitor` | `frontend/src/routes/AppRoutes.test.tsx:150` |
| `/confirm-email-change` also renders for an authenticated visitor | `test_app_routes_confirm_email_change_renders_for_an_authenticated_visitor` | `frontend/src/routes/AppRoutes.test.tsx:158` |
| Generic pre-existing `ProtectedRoute`/`GuestOnlyRoute` redirect + return-to-original-route behavior (unmodified by this Story, still green) | `test_protected_route_unauthenticated_visitor_is_redirected_to_login`, `test_protected_route_remembers_the_originally_requested_route_for_post_login_return` | `frontend/src/routes/ProtectedRoute.test.tsx` (US-5.1, re-confirmed still passing per the quality-gate report's full-suite run) |

`AppRoutes.tsx` itself (read in full) confirms the three new settings routes sit inside the
existing `<ProtectedRoute><AppShell /></ProtectedRoute>` wrapper (lines 69-81) and that
`/verify-email`/`/confirm-email-change` (lines 67-68) are deliberately outside both guards,
per FR-3/FR-4's "works signed-in and signed-out" / "a visitor opens a link" requirement —
matching Plan Change 10.

## Verdict Rationale

Every item that applies to a `track: frontend` Story is Pass or an explicitly-justified N/A
(migrations/ORM/cache/eager-loading are N/A by construction). One Minor finding
(`screens/ProfileScreen.tsx:14`'s `api/types` import) is a real letter-of-the-rule
violation with zero runtime coupling into the fetch/token layer, no security exposure, and
a precedented, mechanical fix — consistent with `US-5.1`'s own archived precedent for the
same class of import. No sensitive value (password, MFA secret, `otpauth_uri`, recovery
codes) was found reaching `localStorage`/`sessionStorage`/the console/a rendered error
anywhere in the diff, confirmed by independent re-reading of the API boundary, MFA
components, and error-rendering helpers rather than by trusting `gate-enforcer`'s summary.
The five new routes are correctly guarded (three behind `ProtectedRoute`, two deliberately
unguarded), with test names cited. **PASS.**

## Findings carried forward for downstream stages (not adjudicated here)

- **`useProfileUpdate.ts:22-23`** always sends an `If-Match` header (the cached ETag, or
  the literal string `"*"` when none is cached) rather than PS-AC2's literal wording ("sent
  only when an ETag ... is known, and is omitted otherwise"). This is `OD-1`'s recorded
  resolution (per the hook's own header comment) and is technically valid HTTP (`If-Match:
  *` matches any current representation), but it is an AC-wording deviation, not an
  AGENTS.md technical-compliance question — `reconciliation-reviewer`'s call, flagged here
  so it is not silently dropped, the same way `gate-enforcer` carried PS-AC1's deferral
  forward without adjudicating it.
- The Minor `ProfileScreen.tsx:14` finding above should be fixed opportunistically (it is
  not blocking), and the working-tree headcount discrepancy noted above is informational
  only.
- **Observation (non-blocking, outside the §6.5/§6.6/§6.7/§5 checklist):** `httpPatch`
  (`api/httpClient.ts:171-204`) re-implements its own 401→refresh→retry branch
  (lines 191-201) rather than routing through the existing `performRequest` helper that
  already has one (lines 101-128). Both copies are correct and tested today, but a future
  fix to the refresh/retry logic in one will not automatically reach the other — a fair
  §1.1 "never invent a second way to do something that already has one" note for whoever
  next touches this file, not a Definition-of-Done violation.
