---
artifact_type: security_review
story: US-5.1
version: 1
status: DRAFT
created_at: "2026-09-07T23:30:00Z"
updated_at: "2026-09-07T23:30:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.1-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/reviews/plans/US-5.1-plan-review.md
    version: 1
  - path: docs/evidence/US-5.1-implementation-report.md
    version: 1
  - path: docs/verification/US-5.1-implementation-verification.md
    version: 1
  - path: docs/tests/US-5.1-test-strategy.md
    version: 1
  - path: docs/tests/US-5.1-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
  - path: docs/catalog/US-5.1-pipeline-status.md
    version: 2
supersedes: null
---

# Security Review: Authentication & Session Management (Frontend)

**Story ID:** US-5.1
**Reviewed:** 2026-09-07
**Overall Verdict:** Pass

## Summary

Track is `frontend` (`docs/stories/US-5.1-authentication-session-management.md:7`), so per this skill's own "Track first" note, checks 1/2/4/5 (Argon2id password storage, no reversible credential encryption, `extra="forbid"`+privilege exclusion, parameterized SQL) are N/A by construction — no password hashing, credential-at-rest storage, Pydantic schema, or SQL exists anywhere in `frontend/`. In their place I independently verified the frontend-specific invariants AGENTS.md §3's Frontend subsection states: the access token is held in memory only and never persisted; the refresh token is never read, parsed, or stored by any client-side code at all (only `credentials: "include"` is used, letting the browser manage the `httpOnly` cookie); and no password, token, or recovery-code value reaches a `console.*` call or a rendered error message anywhere in `frontend/src`. Check 6 (uniform auth-failure response), read narrowly per this Story's own instructions, is also clean: no screen adds its own differentiation on top of whatever message the backend already returned. All checks were verified by direct reading of the actual source files and repo-wide greps I ran myself, not by trusting prior stage reports' prose (though they independently reached the same conclusion — see `docs/verification/US-5.1-implementation-verification.md`). **Verdict: Pass.**

## AGENTS.md §7 / §3-Frontend Non-Negotiable Checklist (frontend track — checks 1/2/4/5 N/A by construction)

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | `track: frontend` (`docs/stories/US-5.1-authentication-session-management.md:7`) — no password hashing exists anywhere under `frontend/`; Argon2id hashing is backend-only (`app/modules/users/service.py`), untouched by this Story (confirmed: entire diff is under `frontend/`, per `docs/verification/US-5.1-implementation-verification.md` §6.5). |
| No plaintext/reversible encryption for credentials | N/A | No credential-at-rest storage exists in this stack — this Story's own NFR requires the *opposite*: the access token is memory-only and the refresh token is never held by client code at all (see the two frontend-specific rows below, which supersede this check for this track). |
| No sensitive value in logs; no `print()` | Pass | Repo-wide `grep -rn "console\.(log\|error\|warn\|debug\|info\|trace)" frontend/src` → **zero matches** across all 65 `.ts`/`.tsx` files (production and test code alike). There is no `print()` equivalent risk in a browser bundle; no `console.*` call of any kind exists in the diff. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A | No Pydantic schema (or any inbound-schema equivalent) exists under `frontend/` — this is a backend-only construct. `frontend/src/api/types.ts` (read in full) defines plain TypeScript DTO interfaces with no runtime validation layer of this kind; none carries a privilege field (`UserRead` is `{id, email}` — `frontend/src/api/types.ts:6-9`). |
| Parameterized SQL only, no string interpolation | N/A | No SQL, ORM, or database access exists anywhere in `frontend/` — this Story makes zero backend/DB changes (confirmed by `impact_analysis` v1's Migration/Schema Impact section: "None"). |
| Uniform auth-failure response, no differentiation leaked | Pass | `frontend/src/api/errorNormalization.ts:51-75` (`normalizeApiError`) derives its rendered message solely from the backend's own `detail`/`errors[].message` text, or a fixed `GENERIC_MESSAGE` fallback (line 22, 74) for any unrecognized shape — it performs no branching on HTTP status or response shape that would add a *new* distinction the backend didn't already draw. `frontend/src/screens/LoginScreen.tsx:44-45,76` renders `getErrorMessage(apiError)` uniformly regardless of whether the underlying failure was wrong-password or unknown-email — both arrive from the backend as the same generic message and the screen adds no `if (status === X)` branch to differentiate them. `frontend/src/screens/ForgotPasswordScreen.tsx:36-37` renders the backend's own `requestMutation.data.message` verbatim (the "if an account exists..." anti-enumeration text) rather than composing its own conditional copy. |

## Frontend-Specific Invariants (AGENTS.md §3's Frontend subsection, in place of checks 1/2/4/5 for `track: frontend`)

| Rule | Result | Evidence |
|---|---|---|
| Access token lives in memory only — never `localStorage`/`sessionStorage`/a client-set cookie | Pass | `frontend/src/store/authStore.tsx:15-68` — `AuthStateSeed.accessToken` is plain `useReducer` state with no persistence side effect anywhere in the file (read in full, 127 lines). Repo-wide `grep -rn "localStorage\|sessionStorage" frontend/src` → the only production-code hit is `frontend/src/components/MfaEnrollmentBanner.tsx:14,22` (`sessionStorage` for a non-sensitive dismissal boolean, sanctioned by the story's own Client State Notes at `docs/stories/US-5.1-authentication-session-management.md:72`); the two other hits are test files (`LoginScreen.test.tsx:57-58`) that *assert the absence* of `mfaToken`/`accessToken` from either storage mechanism, not a violation. |
| Refresh token never read, parsed, or stored by client code — the browser handles the `httpOnly` cookie automatically | Pass | `frontend/src/api/httpClient.ts:78-85` (`performRefreshRequest`) calls `POST /auth/refresh` with `credentials: "include"` and reads only `access_token`/`expires_in`/`mfa_enrollment_deadline` off the response (`RefreshResponse`, `frontend/src/api/types.ts:48-52`) — that interface has **no refresh-token field at all**, so there is nothing to read even by mistake. No file under `frontend/src` sets, reads, or references a `Set-Cookie`/`document.cookie` value, and no line ever names a "refresh token" variable holding a string pulled from the cookie — confirmed by reading every file in `frontend/src/api/` and `frontend/src/session/` (`sessionBridge.ts`, 46 lines, holds only the in-memory access token accessor/callbacks, no cookie logic). `refreshCoordinator.ts:1-25` is a pure single-flight promise wrapper around `refreshFn`; it never inspects the response body for anything cookie-shaped. |
| No password/token/recovery-code value reaches `console.*` or a rendered error message | Pass | Confirmed above: zero `console.*` calls anywhere in `frontend/src`. For rendered errors: `errorNormalization.ts:51-75` only ever surfaces server-supplied `detail`/`errors[].message` *text* (never a request body, which this module never receives — it only processes responses) or the fixed `GENERIC_MESSAGE` constant. Screens that collect a password (`RegisterScreen.tsx:84-96`, `LoginScreen.tsx:61-70`, `ResetPasswordScreen.tsx:54-66`) render only RHF's own static validation-rule strings (e.g. `"Password must contain at least 8 characters..."`, `frontend/src/screens/RegisterScreen.tsx:30`) or the field's server-mapped `message` string via `FieldError`/`getFieldErrors` (`errorNormalization.ts:38-49`, which extracts only `.message`, never `.value`/the submitted password) — no code path echoes the actual password value back into the DOM. `MfaVerifyScreen.tsx` (recovery-code/TOTP entry) follows the identical pattern: `errors.code.message` is a static required-field string, and the API error path never surfaces the submitted `code`. `mfaToken` (the transient MFA challenge token) is read from the store only to build the outbound `verifyMfa` request body (`MfaVerifyScreen.tsx:31`) and never rendered. |

## Verdict Rationale

All items that apply to this `track: frontend` Story are Pass; the four checks this skill's own Track-first note declares N/A by construction (password hashing, credential-at-rest, Pydantic `extra="forbid"`, SQL parameterization) have no applicable code to violate them, confirmed by reading the actual `frontend/` diff rather than assuming the N/A. No password, access token, refresh token, or recovery-code value was found reaching `localStorage`/`sessionStorage`, the browser console, or a rendered error message anywhere in `frontend/src`, and the refresh cookie is never read or parsed by any client-side code — verified by direct file:line evidence, not by trusting `implementation-verifier`'s prior PASS. No differentiation beyond what the backend already returns is added by any screen's error rendering. **Overall Verdict: Pass.**
