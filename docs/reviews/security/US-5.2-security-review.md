---
artifact_type: security_review
story: US-5.2
version: 1
status: APPROVED
created_at: "2026-09-08T19:00:00Z"
updated_at: "2026-09-08T14:50:55Z"
produced_by: security-reviewer
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
  - path: docs/reviews/plans/US-5.2-plan-review.md
    version: 1
  - path: docs/evidence/US-5.2-implementation-report.md
    version: 1
  - path: docs/verification/US-5.2-implementation-verification.md
    version: 1
  - path: docs/tests/US-5.2-test-strategy.md
    version: 1
  - path: docs/tests/US-5.2-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: null
---

# Security Review: Account & Profile Self-Service (Frontend)

**Story ID:** US-5.2
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Summary

`track: frontend` (`docs/stories/US-5.2-account-self-service-ui.md:7`), and `API_DESIGN`/`DB_DESIGN`
both recorded `NOT_APPLICABLE` — no backend, Pydantic, or SQL surface exists in this Story's
diff (independently re-confirmed: every changed/added path is under `frontend/`, per
`implementation-verification.md`'s working-tree enumeration). Per this skill's Track rule,
checks 1, 2, 4, and 5 (password hashing, reversible-encryption ban, `extra="forbid"`,
parameterized SQL) are **N/A by construction**. In their place, this review verified the
frontend-specific invariants AGENTS.md §3's Frontend subsection and this Story's own NFRs
state: the access token stays memory-only, the refresh token is never read/stored/logged by
client code, and no password/token/recovery-code value reaches `console.*` or a rendered
error. Check 6 (uniform auth-failure response) was checked in its narrower frontend form.
All checked rows pass, with two Low advisory notes below that do not affect the verdict.

## AGENTS.md §7 Non-Negotiable Checklist (frontend track — see Summary for scope)

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | `track: frontend` (`docs/stories/US-5.2-account-self-service-ui.md:7`); no `models.py`/password-hashing code exists in this Story's diff — confirmed via `implementation-verification.md`'s working-tree enumeration (58/58 touched paths under `frontend/`). |
| No plaintext/reversible encryption for credentials | N/A | Same as above — no server-side credential storage in scope. Client-side: `current_password` is never persisted anywhere (see frontend-invariant rows below); it exists only as a controlled `<input type="password">` value and a request-body field. |
| No tokens/hashes/PII in logs; no `print()` | Pass | `grep -rn "console\.\(log\|warn\|error\|debug\|info\)" frontend/src` → zero matches across the entire tree (re-run independently, confirming `implementation-verification.md`'s finding). `print()` is a Python-only concern, N/A to a TypeScript stack. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A | No Pydantic schema touched — `API_DESIGN`/`DB_DESIGN` are `NOT_APPLICABLE` per the story's own Assumption #7 (`docs/stories/US-5.2-account-self-service-ui.md:37`). |
| Parameterized SQL only, no string interpolation | N/A | No SQL, repository, or migration exists in this Story's diff. |
| Uniform auth-failure response, no differentiation leaked | Pass (narrowed) | See "Uniform response — narrowed check" below. |

## Frontend-Specific Invariants (AGENTS.md §3 Frontend subsection, in place of checks 1/2/4/5)

| Invariant | Result | Evidence |
|---|---|---|
| Access token lives in memory only, never `localStorage`/`sessionStorage` | Pass | `frontend/src/store/authStore.tsx:79-86` (`defaultState`) and its reducer (`:48-77`) hold `accessToken` only in `useReducer` state. `frontend/src/session/sessionBridge.ts` (read in full): a `SessionBridge` interface (`:21-25`) held in one module-level mutable variable (`activeBridge`, `:33`), defaulting to a `noopBridge` (`:27-31`) whose methods are no-ops until `configureSessionBridge` is called — no fetch, no React, no persistence of its own; it is a pure callback registry, never a second copy of the token. `authStore.tsx:126-131` is the only caller of `configureSessionBridge`, wiring `getAccessToken: () => stateRef.current.accessToken` (`:127`, an in-memory closure over the reducer's own state) and `resetSessionBridge()` on unmount (`:131`); `api/httpClient.ts:93` (`getSessionBridge().getAccessToken()`) is the only reader. `grep -rn "localStorage\|sessionStorage" frontend/src` (excluding `.test.`) → the only non-comment hits are `components/MfaEnrollmentBanner.tsx:14,22` (a non-sensitive boolean dismissal flag, pre-existing US-5.1 pattern, unrelated to the access token). No `accessToken`/token value is ever written to either storage API. |
| Refresh token never read, stored, or parsed by client code | Pass | `frontend/src/api/httpClient.ts:78-85` (`performRefreshRequest`) and `:171-204` (`httpPatch`'s own 401→refresh→retry branch, new in this Story) both call `POST /auth/refresh` with `credentials: "include"` and never touch `document.cookie`. `RefreshResponse` (`frontend/src/api/types.ts`) carries no refresh-token field, so no code path can read one even indirectly. The browser's `httpOnly` cookie does the work per AGENTS.md §3's Frontend "Session handling" paragraph. |
| MFA `secret`/`otpauth_uri`/`recovery_codes` and `current_password` never reach `console.*`, storage, or a third party | Pass | `frontend/src/components/QrCode.tsx` renders `otpauth_uri` locally via the bundled `qrcode.react` `QRCodeSVG` — no network call (`frontend/src/components/QrCode.test.tsx:26-38` asserts zero MSW-observed requests during render; `:40-55` spies on `console.log/warn/error` and asserts the secret string never appears in any call). `frontend/src/components/RecoveryCodesDisplay.tsx` holds codes only as a prop from parent `useState`; `handleCopy` uses `navigator.clipboard.writeText` (explicit user action, not persistence) and `handleDownload` builds a local `Blob`/`URL.createObjectURL` (no network). `RecoveryCodesDisplay.test.tsx:67-90` spies on `Storage.prototype.setItem` and `console.log/warn/error`, asserting neither fires with a code value. `SecurityScreen.tsx:45-46` holds `enrollment`/`recoveryCodes` in local component state, cleared by `onRecoveryCodesConfirmed` (`:71-76`); `SecurityScreen.test.tsx:203-236` runs a full enroll→activate flow with the same `setItem`/`console` spies and asserts the secret and both recovery codes never appear in any call. `current_password` (profile email-change, MFA enroll/disable, deactivation forms) is only ever a controlled form value and a request-body field — the same repo-wide `console.*` grep (zero hits) and the error-rendering path below cover it. <!-- pragma: allowlist secret --> |
| No sensitive value reaches a rendered error | Pass | `frontend/src/components/apiErrorHelpers.ts` (read in full) exposes only `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors`, reading a structural `{status, message, fieldErrors, kind}` shape populated by `frontend/src/api/errorNormalization.ts:51-75` — which explicitly falls back to a generic message (`GENERIC_MESSAGE`) for any unrecognized response shape rather than ever rendering the raw body (`errorNormalization.ts:71-74`). Every screen touched by this Story (`ProfileScreen.tsx:203-206`, `SecurityScreen.tsx` all three branches, `DeactivateAccountScreen.tsx:79-80`, `EmailVerificationScreen.tsx:68-93`) routes its error UI through these four helpers only — none interpolates a raw `Error.message`, a stack trace, or an echoed request payload (password/code/secret). |

## Uniform response — narrowed check

The backend's uniform-auth-failure guarantee is out of this Story's scope (no backend
touched); the applicable question is whether the **frontend adds its own differentiation**
on top of whatever the backend already returns. Checked the one endpoint in this Story
shaped like an enumeration risk — `POST /auth/verify-email/resend`
(`frontend/src/screens/EmailVerificationScreen.tsx:48-54,91-93`): on success it renders
`resendMutation.data.message` verbatim (the backend's own generic confirmation text) and on
failure falls through to the same generic `ErrorState`/`apiErrorHelpers` path used
everywhere else in this Story — no client-side branch inspects the response to decide
"address exists" vs. "address doesn't exist" and render a different message. The
current-password-gated flows (MFA enroll/disable, email change, deactivation) likewise
render whatever `fieldErrors`/`message` the server returned without adding a second layer of
interpretation. Pass.

## Independent assessment: `useProfileUpdate.ts`'s unconditional `If-Match` (requested scrutiny)

`frontend/src/hooks/useProfileUpdate.ts:22-23` sends `If-Match: <cached ETag>` when one is
known and the literal string `If-Match: "*"` otherwise, rather than PS-AC2's literal wording
("omitted otherwise"). `implementation-verifier` already flagged this as a non-blocking
AC-wording deviation (OD-1's recorded resolution) and out of its own technical-compliance
scope. Assessed independently here for a security implication: per RFC 7232 §3.1, `If-Match:
*` is satisfied whenever the target resource currently has **any** representation — it does
not compare against a specific version. For an authenticated user's own profile (which
always exists once the account exists), this is behaviourally equivalent to omitting the
header entirely: both let the first write of a session proceed unconditionally, and neither
prevents a lost-update race against a concurrent write from another session. **No
incremental security exposure beyond what PS-AC2's own literal "omitted otherwise" wording
already accepted** — sending `"*"` doesn't create a new unconditional-overwrite path that
omission wouldn't already have; it's the same race window, just spelled differently over the
wire. This is not a §7/frontend-invariant finding.

## Advisory Findings (non-§7, does not force Fail)

- **[Low] Sensitive values pass through TanStack Query's mutation cache, not only "transient
  component state"** — `useMfaActivate.ts`/`useMfaEnroll.ts`/`useProfileUpdate.ts` wrap
  `mfaApi.activateMfa`/`enrollMfa`/`profileApi.patchProfile` in `useMutation`, whose
  `data`/`variables` (recovery codes, `otpauth_uri`, `secret`, `current_password`) are held
  in the shared `QueryClient`'s in-memory mutation cache until garbage-collected or
  overwritten, not only in the screen's own `useState` as the spec's Client State Notes
  literally describe (`docs/stories/US-5.2-account-self-service-ui.md:73`). `queryClient.ts`
  configures no persistence plugin (no `persistQueryClient`, no storage sync — confirmed by
  reading the file in full), so this stays in-heap-memory only, is never written to any
  storage API, and is never logged; functionally it meets the NFR. Worth a mechanical
  follow-up (e.g. `mutation.reset()` after `onRecoveryCodesConfirmed`/on successful email
  change) only for byte-for-byte fidelity to the spec's literal wording, not because a
  storage/log leak exists.
- **[Low] `sessionBridge.ts`'s deliberate categorization call, now with a second reader** —
  the file's own header comment (`frontend/src/session/sessionBridge.ts:18-20`) flags itself
  as a deliberate, plan-approved seam living outside both `api/` and `store/` to avoid
  AGENTS.md §3's bidirectional import ban, and asks that this be repeated in
  `non_blocking_findings` by whoever touches it. This Story adds a second, independent
  reader of that seam: `httpPatch`'s own 401→refresh→retry branch
  (`frontend/src/api/httpClient.ts:191-201`), alongside `performRequest`'s pre-existing one
  (`:115-125`). Both branches were read in full for this review; neither reads, stores, or
  logs a refresh token, and the bridge itself remains a pure in-memory callback registry
  (see the access-token row above). No new finding — carried forward per the file's own
  convention so it isn't silently dropped at this stage.
- **[Low] `ProfileScreen.tsx:14` imports `SUPPORTED_LOCALES`/two types directly from
  `../api/types`** — already caught and adjudicated Minor/non-blocking by
  `implementation-verifier` (`docs/verification/US-5.2-implementation-verification.md:78-94,109`)
  as an AGENTS.md §3 layer-table letter-of-the-rule violation with zero runtime coupling
  into `fetch`/the token layer and no secret involved. Re-confirmed here from a security
  angle: `api/types.ts` has zero imports of its own and no import-time side effect, so this
  does not open a live path to `httpClient`/`fetch` from the component tree. No new finding;
  carried forward for completeness only.

## Verdict Rationale

All six §7 checklist rows are either N/A by construction (frontend-only Story, no backend
surface) or Pass; both frontend-specific invariant rows and the narrowed uniform-response
check are Pass, each with cited file:line evidence and, for the MFA/recovery-code path,
citation to tests that spy on `console.*` and `Storage.prototype.setItem` and assert the
secret values never appear. The two advisory findings are Low and do not touch a §7
non-negotiable. **Overall Verdict: PASS.**
