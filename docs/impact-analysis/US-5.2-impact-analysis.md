---
artifact_type: impact_analysis
story: US-5.2
version: 1
status: DRAFT
created_at: "2026-09-08T08:15:26Z"
updated_at: "2026-09-08T08:15:26Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.2-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.2-design-review.md
    version: 1
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: null
---

# Impact Analysis: Account & Profile Self-Service (Frontend)

**Story ID:** US-5.2
**Track:** frontend (per `docs/stories/US-5.2-account-self-service-ui.md` front matter)
**Scope note:** `API_DESIGN` and `DB_DESIGN` both returned `NOT_APPLICABLE` (no backend/API/DB change; frontend-only story consuming already-shipped endpoints), confirmed by `docs/reviews/designs/US-5.2-design-review.md` (v1, `NOT_APPLICABLE`). This survey therefore covers the `frontend/` blast radius against the layer table in `AGENTS.md` §3 "Frontend (`frontend/`)" (`screens/`, `components/`, `hooks/`, `store/`, `api/`, `routes/`), not backend `app/modules/` layering. Backend files are named only where the spec's FRs cite them as the (unmodified) contract this story's frontend code must call correctly — they are not affected files.

## 1. Affected Files / Modules / Layers

### `api/` layer

| File | Reason |
|---|---|
| `frontend/src/api/httpClient.ts` | FR-2 (Assumption #2) requires the shared client to expose response **headers**, not only JSON bodies, so the `ETag` header from a `200 PATCH /profile` can be captured. Current `parseResponse<T>`/`performRequest<T>` (lines 57-128) return only the parsed body; every `httpGet`/`httpPost`/`httpDelete` call site depends on this shape. Also needs a `httpPatch<T>` export — no PATCH verb exists today (only `GET`/`POST`/`DELETE`; `HttpMethod` already includes `"PATCH"` but no wrapper function does). |
| `frontend/src/api/types.ts` | New DTOs needed for every endpoint this story calls that has no existing type: `ProfileRead`, `ProfileUpdateRequest`/`EmailChangeRequest` (`PATCH /profile`'s two payload shapes), `ConfirmEmailChangeRequest`/`ConfirmEmailChangeResponse`, `VerifyEmailRequest`/`VerifyEmailResponse`, `ResendVerificationRequest`/`ResendResponse`, `MfaEnrollRequest`/`MfaEnrollResponse` (`{secret, otpauth_uri}`), `MfaActivateRequest`/`MfaActivateResponse` (`{recovery_codes}`), `MfaDisableRequest`, `AccountDeactivateRequest`/`AccountDeactivateResponse`. None of these exist in the current file (which only has auth/session/password-reset DTOs from US-5.1). |
| `frontend/src/api/profileApi.ts` (new) | No `profileApi.ts` exists today. Needs one function per `PATCH /profile` (edit and email-change variants) and `POST /profile/confirm-email-change`. |
| `frontend/src/api/mfaApi.ts` or an extension of an existing file (new) | `POST /auth/mfa/enroll`, `POST /auth/mfa/activate`, `DELETE /auth/mfa` have no typed wrapper yet (only `verifyMfa` for the *challenge* flow exists in `authApi.ts`, which this story does not otherwise touch — only additive new functions are needed). |
| `frontend/src/api/accountApi.ts` or an extension (new) | `POST /account/deactivate` has no typed wrapper yet. |
| `frontend/src/components/apiErrorHelpers.ts` | FR-2's `412` "changed elsewhere, reload" state must be detected in `screens/`, but `screens/`/`components/` must not import `api/` directly (`AGENTS.md` §3 Frontend table) and this file's current exports (`getErrorKind`, `getErrorMessage`, `getFieldErrors`) expose no status code — confirmed against `LoginScreen.tsx`, which reads mutation errors only through these structural helpers, never `error.status` directly. A status-exposing helper (or an equivalent conflict-detecting helper) is needed here for `ProfileScreen.tsx` to render the 412 state without violating that layering rule. |

### `hooks/` layer

| File | Reason |
|---|---|
| `frontend/src/hooks/useProfileUpdate.ts` (new) | FR-2/FR-3: owns the `PATCH /profile` mutation, the "only the changed fields" diffing, `If-Match`/`If-Match: *` selection per OD-1's resolution, capturing the returned `ETag` into session-scoped state on `200`, invalidating (not reusing) on `202`, and surfacing the `412` conflict distinctly. Session-affecting/ETag-affecting store writes belong in this hook's `onSuccess`/`onError`, per the existing `useLogin.ts` convention of keeping such writes out of the screen. |
| `frontend/src/hooks/useConfirmEmailChange.ts` (new) | FR-3's `POST /profile/confirm-email-change`, callable both signed-in and signed-out (must not assume an authenticated hook context the way `useSessions.ts` etc. do). |
| `frontend/src/hooks/useVerifyEmail.ts` (new) | FR-4's `POST /auth/verify-email`. |
| `frontend/src/hooks/useResendVerificationEmail.ts` (new) | FR-4's `POST /auth/verify-email/resend`. |
| `frontend/src/hooks/useMfaEnroll.ts` (new) | FR-5's `POST /auth/mfa/enroll` (with `current_password` per OD-2). |
| `frontend/src/hooks/useMfaActivate.ts` (new) | FR-5's `POST /auth/mfa/activate`; on success the one-time `recovery_codes` flow through to the screen for display, never persisted by the hook. |
| `frontend/src/hooks/useMfaDisable.ts` (new) | FR-6's `DELETE /auth/mfa` (with `current_password` + `code` per OD-2); `onSuccess` should reflect the disabled state back into whatever local MFA-status signal the security screen reads. |
| `frontend/src/hooks/useAccountDeactivate.ts` (new) | FR-7's `POST /account/deactivate`; `onSuccess` must call `authStore.clearSession()` (all in-memory auth state cleared) and the screen navigates to `/login`. This is the one new hook that writes to the store on success, same pattern as `useLogout.ts`. |

### `store/` layer

| File | Reason |
|---|---|
| `frontend/src/store/queryClient.ts` | Candidate location for the ETag-per-resource metadata the spec's Client State Notes describe ("held per-resource in query cache metadata"). No `queryClient.setQueryData`/`meta` convention exists yet in this file. Whether the ETag is held here or elsewhere in component/hook state is a placement decision for `planner`, not settled by this survey — see Notes for Downstream Stages. |

### `screens/` layer (new screens — none of these exist today)

| File | Reason |
|---|---|
| `frontend/src/screens/ProfileScreen.tsx` (new) | FR-2/FR-3: the `/settings/profile` form (edit; email-change sub-flow), write-only per FR-1's deferral. |
| `frontend/src/screens/EmailVerificationScreen.tsx` (new) | FR-4: the `/verify-email` (or similar) landing page reading a token from the URL, rendering success/expired/invalid distinctly, plus the resend control. |
| `frontend/src/screens/SecurityScreen.tsx` (new) | FR-5/FR-6: `/settings/security` — MFA enroll (QR + secret + 6-digit activate + one-time recovery codes) and MFA disable. |
| `frontend/src/screens/DeactivateAccountScreen.tsx` (new) | FR-7: the deactivation confirmation screen. |

### `components/` layer

| File | Reason |
|---|---|
| `frontend/src/components/MfaEnrollmentBanner.tsx` | **Changes US-5.1's shipped code** (spec Assumption #6 / In Scope bullet): the banner currently renders a dismiss-only message with no link (lines 40-53). Needs a link/navigation action into the new MFA enrollment flow (`SecurityScreen.tsx` or a dedicated enrollment route). Its existing test `MfaEnrollmentBanner.test.tsx` will need a new assertion for the link target. |
| `frontend/src/components/RecoveryCodesDisplay.tsx` or similar (new) | FR-5's one-time recovery-code display: copy/download support plus the explicit "I have saved these" confirmation gate, and the NFR constraint that the codes are never written to `localStorage`/`sessionStorage`/a cookie/the console/any third party. |
| A bundled QR-rendering component (new) | Assumption #5/FR-5: the `otpauth_uri` QR must be rendered **locally in the browser** via a bundled library, never an external QR service. No QR library exists in `frontend/package.json` today (checked: dependencies list has no `qrcode`/`qrcode.react`/similar). |

### `routes/` layer

| File | Reason |
|---|---|
| `frontend/src/routes/AppRoutes.tsx` | New routes must be added for `/settings/profile`, `/settings/security`, the deactivation screen, and an email-verification landing route (signed-out reachable, unlike the existing `ProtectedRoute`-wrapped block). Current file (lines 19-69) has no `/settings/*` routes and only one signed-out-reachable route group (`AuthLayout`'s children) plus one `ProtectedRoute`-wrapped group. The email-verification route needs to be reachable **without** authentication (like `/reset-password`) since FR-4 applies to "a visitor," while `/settings/profile` and `/settings/security` need `ProtectedRoute` (like `/sessions`). The confirm-email-change route (FR-3, "works signed-in and signed-out") cannot use either existing guard as-is — `ProtectedRoute` would block a signed-out visitor and `GuestOnlyRoute` would block a signed-in one; it needs to sit outside both, a routing shape the current file has no precedent for. |

### `package.json`

| File | Reason |
|---|---|
| `frontend/package.json` | A new dependency for locally-rendered QR generation must be added (Assumption #5/FR-5) — none exists today. No other dependency addition is implied by any other FR. |

## 1a. Checked — Not Affected (reference only)

Read while tracing the above, and confirmed to need **no** change for this story. Recorded so `planner` does not need to re-derive that these were checked, and so none of them is mistaken for a change target:

| File | Why it was checked | Why it is not affected |
|---|---|---|
| `frontend/src/api/errorNormalization.ts` | XC-AC1 (FR-8) spans every screen in this story. | The existing `detail`-first branch (lines 58-62) already satisfies "detail, or a mapped message keyed by type"; no new shape appears among this story's endpoints that the current logic mishandles. |
| `frontend/src/components/ErrorState.tsx`, `frontend/src/components/FieldError.tsx` | FR-8/FR-9/FR-10 apply to every new screen. | Both are already generic (kind-based / field-message-based) and reusable as-is by `ProfileScreen`, `EmailVerificationScreen`, `SecurityScreen`, and `DeactivateAccountScreen` with no new props or variants required. |
| `frontend/src/hooks/useLogout.ts` | FR-7's `useAccountDeactivate.ts` needs the same "`clearSession` on success" shape. | Confirms the pattern to replicate; the file itself is not touched. |
| `frontend/src/store/authStore.tsx` | FR-7 clears in-memory auth state on deactivation success. | Reuses the existing `clearSession` action unchanged; no new action is needed. |
| `frontend/src/routes/ProtectedRoute.tsx`, `frontend/src/routes/GuestOnlyRoute.tsx` | New routes need a guard shape check (section 1, `AppRoutes.tsx`). | Neither guard is modified — the new "either state" route sits outside both rather than requiring either to change. |
| `frontend/src/layouts/AppShell.tsx` | The three new authenticated screens need a layout. | Fits the existing `AppShell` + `Outlet` pattern already used by `/` and `/sessions` with no structural change. |

## 2. Cross-Module Ripple

This is a frontend-only story; "cross-module" here means cross-layer calls within `frontend/`, since there is no second backend module this story's (nonexistent) service layer would call. No backend `app/modules/*` file is modified, so there is no backend service→service ripple to trace.

Within `frontend/`, the ripple is:
- `screens/ProfileScreen.tsx` → `hooks/useProfileUpdate.ts`, `hooks/useConfirmEmailChange.ts` → `api/profileApi.ts` → `api/httpClient.ts` (extended for header capture) → backend `PATCH /profile`, `POST /profile/confirm-email-change` (already-shipped, `app/modules/profile/router.py` — unmodified).
- `screens/EmailVerificationScreen.tsx` → `hooks/useVerifyEmail.ts`, `hooks/useResendVerificationEmail.ts` → new `api/` functions (likely added to `authApi.ts`, since these are `/auth/*` paths, not `/profile/*`) → `api/httpClient.ts` → backend `POST /auth/verify-email`, `POST /auth/verify-email/resend` (unmodified).
- `screens/SecurityScreen.tsx` → `hooks/useMfaEnroll.ts`, `useMfaActivate.ts`, `useMfaDisable.ts` → new `api/mfaApi.ts` (or `authApi.ts` extension) → `api/httpClient.ts` → backend `POST /auth/mfa/enroll`, `POST /auth/mfa/activate`, `DELETE /auth/mfa` (unmodified — `app/modules/users/service.py`, `schemas.py`).
- `screens/DeactivateAccountScreen.tsx` → `hooks/useAccountDeactivate.ts` → `hooks/useAccountDeactivate.ts`'s `onSuccess` → `store/authStore.tsx`'s `clearSession()` (existing action, same as `useLogout.ts`'s pattern) → `routes/` navigates to `/login` → backend `POST /account/deactivate` (unmodified — `app/modules/account/service.py`).
- `components/MfaEnrollmentBanner.tsx` (rendered from `screens/PlaceholderHomeScreen.tsx`) → new link target → `routes/AppRoutes.tsx`'s new `/settings/security` route → `screens/SecurityScreen.tsx`. This is the one **new** intra-frontend dependency this story introduces: today `MfaEnrollmentBanner` has no navigation/link behavior at all (it only dismisses); after this story it links into a screen that does not yet exist. Flagged per the skill's instruction to call out a new cross-boundary dependency explicitly.

No new dependency from `hooks/`/`api/` back into `screens/`/`components/` is introduced (would violate the `AGENTS.md` §3 Frontend layer table's downward-only import direction) and none was found necessary.

## 3. Migration/Schema Impact

**None.** Confirmed explicitly, per the skill's requirement not to omit this section silently:
- `API_DESIGN` and `DB_DESIGN` both recorded `NOT_APPLICABLE` for this story (`docs/workflow` stage history; corroborated by `docs/reviews/designs/US-5.2-design-review.md` v1).
- The approved spec's own Out of Scope section states: "Any backend/API/DB change. This Story implements only against already-shipped backend endpoints; it does not add, modify, or design any API route, request/response contract, or database schema/table/column."
- No Alembic migration, no `models.py`/`schemas.py`/`repository.py` change, and no existing backend repository query is affected — every endpoint this story calls (`app/modules/profile/router.py`, `app/modules/users/service.py`'s MFA operations, `app/modules/account/service.py`) is already shipped and unmodified.
- The one item that could be mistaken for a schema impact — FR-2's `ETag`/`If-Match` handling and FR-5's `secret`/`otpauth_uri`/`recovery_codes`/`current_password` handling — is explicitly client-side session/transient-component state, not persistence, per the spec's Client State Notes and NFR section.

## 4. Test-Surface Impact

### Existing test files that must change

| File | Reason |
|---|---|
| `frontend/src/components/MfaEnrollmentBanner.test.tsx` | Must gain a new assertion for the link into the enrollment flow, since `MfaEnrollmentBanner.tsx` itself changes (section 1). |
| `frontend/src/routes/AppRoutes.test.tsx` | Must gain route-table assertions for the new `/settings/profile`, `/settings/security`, deactivation, and email-verification routes, and for the new "reachable both signed-in and signed-out" guard shape the confirm-email-change route needs. |
| `frontend/src/test/mswHandlers.ts` | Must gain baseline handlers for every new endpoint this story calls (`PATCH /profile`, `POST /profile/confirm-email-change`, `POST /auth/verify-email`, `POST /auth/verify-email/resend`, `POST /auth/mfa/enroll`, `POST /auth/mfa/activate`, `DELETE /auth/mfa`, `POST /account/deactivate`), following the existing one-handler-per-operation convention. Not a new file — this file is shared baseline infrastructure every screen's tests import. |
| `frontend/src/api/httpClient.ts`'s own test file, if one is added under this story (none currently exists for `httpClient.ts` itself — only `refreshCoordinator.test.ts` and `errorNormalization.test.ts` exist under `api/`) — a new `httpClient.test.ts` is effectively new-file territory, but flagged here because it tests a file section 1 already lists as changed, so a gap in existing coverage becomes directly relevant to this story's own change. |

### New test files (net-new screens/hooks/components have no existing coverage to update)

- `frontend/src/screens/ProfileScreen.test.tsx`
- `frontend/src/screens/EmailVerificationScreen.test.tsx`
- `frontend/src/screens/SecurityScreen.test.tsx`
- `frontend/src/screens/DeactivateAccountScreen.test.tsx`
- `frontend/src/hooks/useProfileUpdate.test.ts`
- `frontend/src/hooks/useConfirmEmailChange.test.ts`
- `frontend/src/hooks/useVerifyEmail.test.ts`
- `frontend/src/hooks/useResendVerificationEmail.test.ts`
- `frontend/src/hooks/useMfaEnroll.test.ts`
- `frontend/src/hooks/useMfaActivate.test.ts`
- `frontend/src/hooks/useMfaDisable.test.ts`
- `frontend/src/hooks/useAccountDeactivate.test.ts`
- A test file for the new recovery-codes display component (naming depends on the component name `planner`/`frontend-builder` settles on in section 1).
- A test file for the new QR-rendering component (same naming caveat).
- An a11y test pass (axe, per the existing `vitest-axe` devDependency and `test/vitest-axe.d.ts`) on `ProfileScreen`, `SecurityScreen`, and `DeactivateAccountScreen` specifically — the spec's Enforcement Matrix names these three screens for the automated a11y check; no existing a11y test file covers them since they don't exist yet.

## Notes for Downstream Stages

- Two placement decisions are flagged as undecided in section 1 rather than resolved here (ETag storage location: `queryClient.ts`/TanStack Query `meta` vs. a dedicated module; new `api/` file boundaries for MFA/account vs. extending `authApi.ts`) — this is a survey, not a plan; `planner`/`implementation-planner` make that call.
- OD-3, OD-6, and OD-7 (still `OPEN` per `docs/decisions/US-5.2-open-decisions.md` v2) each affect the *behavior* of a file already listed above, not which files are in scope: OD-3's forced-navigation question affects `routes/AppRoutes.tsx` (and, only if resolved toward a force-navigate guard, could newly bring `layouts/AppShell.tsx` into scope from today's "not affected" status); OD-6 affects the profile form's locale field in `screens/ProfileScreen.tsx`; OD-7 affects the same screen's timezone field. No additional file beyond those already listed is implied by any of the three.
