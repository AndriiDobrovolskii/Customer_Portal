---
artifact_type: implementation_plan
story: US-5.2
version: 1
status: APPROVED
created_at: "2026-09-08T09:05:00Z"
updated_at: "2026-09-08T09:15:00Z"
produced_by: planner
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.2-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.2-design-review.md
    version: 1
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
supersedes: null
---

# Implementation Plan: Account & Profile Self-Service — Frontend (US-5.2)

## Goal

Extend US-5.1's `frontend/` tree with the ten FRs' worth of self-service
screens the approved spec (v2, `APPROVED`) requires: profile edit
(write-only interim, FR-1/FR-2), email change and confirmation (FR-3), email
verification landing and resend (FR-4), MFA enrollment and disable (FR-5,
FR-6), and account deactivation (FR-7) — plus the client-side validation
(FR-9), problem+json rendering (FR-8), and network/server-failure handling
(FR-10) common to all of them. Several already-shipped US-5.1 files change: the shared `api/httpClient.ts`
gains a header-exposing `httpPatch<T>` (Assumption #2), `MfaEnrollmentBanner.tsx`
gains a link into the new enrollment flow (Assumption #6), and — a finding
this plan surfaces itself, beyond `impact_analysis`'s original survey —
`authStore.tsx`/`useLogin.ts`/`useMfaVerify.ts` gain a `mfaEnabled` signal so
`SecurityScreen.tsx` has a safe, real basis for choosing between its enroll
and disable flows (Change 6). No backend/API/DB file changes — confirmed again by
`design_review` v1 (`NOT_APPLICABLE`) and `impact_analysis` v1 (`PASS`).
OD-1, OD-2, and OD-4 are resolved and already reflected in FR-2/FR-5/FR-6/FR-7;
OD-3, OD-5, OD-6, and OD-7 remain `OPEN` through an `APPROVED` spec — none is
resolved by this plan; each is either designed around so build can proceed
regardless of how it resolves, or named as a dependency below.

## Architectural Changes

### 1. `httpClient.ts`: an additive `httpPatch<T>` that exposes status + headers, existing verbs untouched

FR-2 needs the `ETag` response header from a `200 PATCH /profile` and needs
to tell a `200` (edit succeeded) apart from a `202` (email-change pending)
apart from a `412` (conflict) — none of which the current
`httpGet`/`httpPost`/`httpDelete` (`Promise<T>`, body only) can express.
Rather than reshaping every existing export (which every US-5.1 call site
depends on, per `impact_analysis`), this plan adds one new, additive export:

```ts
export function httpPatch<T>(
  path: string,
  body: unknown,
  options: { auth?: boolean; ifMatch?: string } = {},
): Promise<{ data: T; status: number; headers: Headers }>
```

`performRequest`'s internals (401→refresh→retry, network/5xx normalization)
are reused unchanged; only the PATCH path threads an `If-Match` header (when
`options.ifMatch` is supplied) and resolves with `{ data, status, headers }`
instead of bare `T`. `httpGet`/`httpPost`/`httpDelete` keep their existing
`Promise<T>` signatures — no US-5.1 call site changes. `httpPatch` is generic
(any caller may use it); the policy of "always send `If-Match`, using `*`
when no ETag is known" (OD-1) is enforced by `profileApi.ts`/
`useProfileUpdate.ts`, not by `httpClient.ts` itself, which stays a
transport-only layer.

### 2. ETag held in TanStack Query's cache, not a new store slice

The spec's Client State Notes say the ETag is "held per-resource in query
cache metadata." There is no real `GET /profile` query to attach that
metadata to (FR-1 is deferred), so this plan uses a dedicated, non-fetching
query key purely as a cache slot: `queryClient.setQueryData(["profile",
"etag"], etag)` after a `200`, `queryClient.getQueryData(["profile",
"etag"])` read before the next write, and `queryClient.removeQueries(["profile",
"etag"])` after a `202` (per FR-3: "invalidates rather than reusing" a stale
value) or a `412`. This avoids adding a new `store/` file for one string, and
keeps the value in memory only (the app's `QueryClient` has no persister
configured — confirmed in `store/queryClient.ts` — so this is exactly as
non-durable as the NFR requires). The ETag itself is not a secret value; it
is not subject to the NFR's "never written to storage" list (that list names
`secret`/`otpauth_uri`/`recovery_codes`/`current_password` specifically), but
it is still never placed in `localStorage`/`sessionStorage`.

### 3. `useProfileUpdate.ts` owns both `PATCH /profile` variants; disambiguates 200/202/412 by status, not by shape

Both the field-edit payload and the email-change payload hit the same
endpoint (`profileApi.patchProfile`). One hook, one `useMutation`, because
the spec's Client State Notes tie their ETag/pending-email handling together
(a `202` invalidates the ETag the next edit would otherwise reuse). On
`onSuccess`, the hook reads `response.status`:
- `200` → writes the returned `ProfileRead` back into the form, caches the
  new `ETag` (Change 2), clears any conflict state.
- `202` → removes the cached ETag, and the caller (`ProfileScreen.tsx`) reads
  `pending_email` off the returned `ProfileRead` to show the "confirm the
  link sent to `<pending_email>`" state (FR-3).
- A `412` surfaces as a thrown `ApiError` (status 412); `onError` sets a
  conflict flag the screen renders as "changed elsewhere, reload" (FR-2),
  read via the new `apiErrorHelpers.getErrorStatus` (Change 4) so
  `ProfileScreen.tsx` never imports `api/httpClient.ts`'s `ApiError` class
  directly (`AGENTS.md` §3 Frontend table).
- Per OD-1's resolution, the hook — not the screen — decides the outgoing
  `If-Match`: the cached ETag if `queryClient.getQueryData(["profile",
  "etag"])` returns one, else the literal string `"*"`, on every write,
  including the session's first.

### 4. `apiErrorHelpers.ts` gains `getErrorStatus`, the one addition beyond `impact_analysis`'s literal wording

`impact_analysis` flagged this file needs *some* status-exposing helper for
FR-2's 412 detection without `ProfileScreen.tsx` importing `api/` directly.
`PresentableApiError` already declares `status?: number` (unused today);
this plan adds one function, `getErrorStatus(error: unknown): number |
undefined`, mirroring `getErrorKind`/`getErrorMessage`'s existing structural
pattern exactly — no new interface, no new file.

### 5. New `api/` files split by domain, not one grab-bag extension

- `profileApi.ts` (new) — `patchProfile` (both payload shapes, threading
  `ifMatch`), `confirmEmailChange`. FR-2/FR-3.
- `mfaApi.ts` (new) — `enrollMfa`, `activateMfa`, `disableMfa`. FR-5/FR-6.
  Kept separate from `authApi.ts`'s existing `verifyMfa` (the *challenge*
  flow, already shipped, untouched) because enroll/activate/disable are a
  distinct sub-domain: enroll/activate accept an enrollment-scoped access
  token (not the login-challenge `mfa_token`), while disable is a normal
  Bearer call re-verified by password+code (`service.py:1515-1554`, no
  token-scope check) — mixing any of these into `authApi.ts`'s
  login/session-lifecycle grab-bag would blur that distinction.
- `accountApi.ts` (new) — `deactivateAccount`. FR-7.
- `authApi.ts` (modified, additive only) — `verifyEmail`,
  `resendVerificationEmail` added alongside the existing `/auth/*`
  functions, since both new endpoints are `/auth/*` paths and this file is
  already the home for every `/auth/*` operation that isn't login/session
  (register, refresh, logout, password reset). FR-4.
- `types.ts` (modified, additive only) — one interface/type per new DTO
  (`ProfileRead`, `ProfileUpdateRequest`, `EmailChangeRequest`,
  `ConfirmEmailChangeRequest/Response`, `VerifyEmailRequest/Response`,
  `ResendVerificationRequest/Response`, `MfaEnrollRequest/Response`,
  `MfaActivateRequest/Response`, `MfaDisableRequest`,
  `AccountDeactivateRequest/Response`), plus `SUPPORTED_LOCALES` (Change 7).

### 6. `SecurityScreen.tsx`'s enroll/disable branch: derived from the login response shape already in `authStore`, not a blind default

No response schema anywhere in this Story's contract exposes an
`mfa_enabled`-shaped field to the client (confirmed by reading
`app/modules/users/schemas.py`/`service.py` directly, not only the spec's
own table) — the same root cause as FR-1's missing `GET /profile`/`GET
/users/me` (OD-5, `OPEN`). A blind "always default to enroll" design was
considered and rejected: `app/modules/users/service.py`'s `enroll_mfa`
(line 1295) has **no** already-enabled guard — it unconditionally
overwrites `mfa_secret_encrypted`, the single column that serves both the
*pending* and the *active* secret (`models.py:38`; the overwrite itself is
`repository.py:215-225`'s `update_mfa_pending_secret`) — so an already-enrolled user
who is shown, and acts on, an "enroll" default would have their real,
working TOTP secret silently invalidated by the interim UI itself, not by
a rejected API call. This is not an acceptable default for a `[gate]`-marked
AC (PS-AC6).

Instead, this plan reuses a signal already present in already-shipped
US-5.1 code: `POST /auth/login`'s response shape itself (`LoginResponse` vs
`MfaRequiredResponse`, `isMfaRequiredResponse()` in `api/types.ts`) reveals
whether the account has MFA enabled at the moment of login — a
plain `LoginResponse` means MFA is **not** enabled; reaching
`useMfaVerify`'s success path (which only occurs after an
`MfaRequiredResponse` challenge) means it **is**.

Concretely, this requires four specific changes to `authStore.tsx`'s
existing shape — named explicitly here so `frontend-builder` is not left to
guess how a `boolean` fits a reducer whose other four fields are all
nullable/optional:
- `AuthStateSeed` gains `mfaEnabled: boolean`. `defaultState` and the
  `CLEAR_SESSION` case both set it `false` — not because "no MFA" is known
  pre-login, but because it is unreachable in that state: `/settings/security`
  sits behind `ProtectedRoute`, so `SecurityScreen` never renders while
  `isAuthenticated` is false. This is stated explicitly so it is a documented
  default, not an implied fact about an unauthenticated caller's MFA status.
- `SetSessionPayload` gains `mfaEnabled: boolean` as a **required** field
  (unlike `mfaEnrollmentDeadline`'s optional-with-`?? null` pattern) — this
  is deliberate: strict mode's `tsc --noEmit` (already this Story's gate,
  Validation Strategy) then fails a build where either `setSession` call
  site (`useLogin.ts`'s direct branch, `useMfaVerify.ts`) forgets to pass
  it, rather than silently defaulting.
- The `SET_SESSION` reducer case copies `action.payload.mfaEnabled` through
  verbatim (no `?? null` fallback, since it is now required).
- `TOKEN_REFRESHED` already spreads `...state`, so a silent 401→refresh
  (US-5.1's existing coordinator) leaves `mfaEnabled` untouched — this is
  the specific mechanism that makes the signal durable for the lifetime of
  an authenticated tab, not just at the instant of login.
- A new action, `setMfaEnabled(enabled: boolean)`, dispatching a new
  `{ type: "SET_MFA_ENABLED"; enabled: boolean }` action mirroring
  `setMfaToken`'s existing shape exactly, is added to `AuthStoreValue`.
  `useMfaActivate.ts`'s `onSuccess` calls `setMfaEnabled(true)`;
  `useMfaDisable.ts`'s `onSuccess` calls `setMfaEnabled(false)`. Neither
  hook has the full `accessToken`/`user` payload `setSession` requires, so
  this dedicated action — not `setSession` — is their only legal path to
  updating this piece of state, the same reason `setMfaToken` exists
  alongside `setSession` today.

`SecurityScreen.tsx` reads `authStore.mfaEnabled` to decide which flow to
render — a real signal kept current for the lifetime of the session, not a
guess. This is sound because the app has no session-restore-on-mount path
(confirmed: `App.tsx` wires providers only, no bootstrap silent-refresh;
`isAuthenticated` is only ever true after this tab's own login/verify call)
— every authenticated moment in this app is reachable only through a login
this Story's signal already observes. Residual gap: if MFA is
enabled/disabled from a *different* session while this tab stays open, this
tab's `mfaEnabled` goes stale until the next login — the same class of
staleness OD-5 already accepts for profile data, not a new one.

**This extends `impact_analysis`'s survey**, which recorded `store/authStore.tsx`
as "not affected" for a different reason (FR-7's `clearSession` reuse only)
and did not examine FR-5/FR-6's need for an enroll/disable signal.
`authStore.tsx`, `useLogin.ts`, and `useMfaVerify.ts` — all already-shipped
US-5.1 files — move from "not affected" to "modified" for this reason; see
Files To Modify and Risk 1.

### 7. Locale list: one shared constant, not hard-coded twice — a forward-compatible default pending OD-6

OD-6 (`OPEN`) asks whether `SupportedLocale`'s two-item placeholder list
should ship as-is or be structured for extension. This plan does not resolve
OD-6, but avoids the concrete risk OD-6 names (the list "duplicated by hand"
in two places): `types.ts` exports one `SUPPORTED_LOCALES = ["en-US",
"en-GB"] as const` array (plus the derived union type), and both the form's
`<select>` options and its client-side validation rule (FR-9) read from that
one constant. If OD-6 later expands the list, this is a one-line change, not
a find-and-replace across the form and its validator.

### 8. Timezone input: native `Intl.supportedValuesOf("timeZone")`, no hard-coded list, no new dependency — a pragmatic default pending OD-7

OD-7 (`OPEN`) asks full IANA set vs. a curated subset. This plan takes a
third option neither OD-7 branch names, to avoid inventing a curated list
with no product source (none exists anywhere in the repo, per
`us-clarifier`'s own finding) and to avoid hand-maintaining ~600 entries
client-side: the timezone field's option list is derived at runtime from
`Intl.supportedValuesOf("timeZone")` (native ES2022 API, already available in
every browser this Story's NFRs target — zero new dependency). This is
rendered as a hand-built, keyboard-navigable searchable combobox (typeahead
filtering the same in-memory list), consistent with US-5.1's own OD-9
resolution (no UI-kit dependency). The browser's ICU timezone set and the
backend's `zoneinfo.available_timezones()` are expected to match for the
overwhelming majority of values; a rare mismatch surfaces as a normal 422
mapped onto the field by the already-planned FR-8/FR-9 machinery, not a new
error path. If OD-7 later resolves toward a curated subset, swapping the
source list is a one-line change to this combobox's data source, not a
re-architecture.

### 9. QR rendering: a new dependency, flagged for sign-off, not silently added

Assumption #5/FR-5 require the `otpauth_uri` QR to be rendered locally,
never via an external service. No QR library exists in
`frontend/package.json` today (confirmed by `impact_analysis`). This plan
names `qrcode.react` (a thin, no-network SVG/canvas renderer) as the
candidate, wrapped in one adapter component (`components/QrCode.tsx`) so the
third-party import is isolated to a single file — if a different library is
approved instead, only that one file's internals change. Per `AGENTS.md`
§7.8, this is a **new dependency requiring explicit propose/approve
sign-off before `IMPLEMENTATION`**, exactly like US-5.1's own
`react-router-dom`/`vitest-axe` additions — not something this plan or
`frontend-builder` may add unilaterally.

### 10. Routing: the confirm-email-change *and* verify-email routes both sit outside both existing guards

`impact_analysis` flagged that FR-3's confirm-email-change route ("works
signed-in and signed-out") fits neither `ProtectedRoute` (blocks signed-out)
nor `GuestOnlyRoute` (blocks signed-in). This plan extends the same
reasoning to FR-4's verify-email route: PS-AC4 says "a visitor opens a
verification link," with no stated constraint on that visitor's current
auth state, so wrapping it in `GuestOnlyRoute` would incorrectly redirect an
already-signed-in visitor away from a link they explicitly followed. Both
`/verify-email` and `/confirm-email-change` are added to `AppRoutes.tsx` as
bare routes, outside `AuthLayout`'s `GuestOnlyRoute` group and outside the
`ProtectedRoute`-wrapped group — no new guard component is introduced;
"outside both" is achieved by simply not wrapping them, which is sufficient
for this Story's two cases. `/settings/profile`, `/settings/security`, and
`/settings/deactivate` are added inside the existing `ProtectedRoute` group
(same shape as `/sessions`).

### 11. OD-3 (enrollment-scoped-token 403 navigation) is explicitly *not* built — banner link only, per the spec's own scope

OD-3 remains `OPEN` and non-blocking. The spec's own scope treats US-5.1's
dismissible banner-plus-link (Assumption #6) as the entire integration
point; this plan does not add a force-navigate guard to `AppShell.tsx` or
any route, because doing so would resolve OD-3 unilaterally rather than
leaving it for a human decision. If OD-3 later resolves toward forced
navigation, that is an additive guard on top of `AppShell.tsx` /
`ProtectedRoute.tsx`, not a rewrite of anything this plan fixes.

### 12. Confirmation UI for MFA-disable and deactivation: inline per-screen, no new shared component

FR-6 and FR-7 both need an "explicit, non-accidental confirmation step
naming the consequence." `impact_analysis` did not flag a shared
confirmation-dialog file as part of this Story's blast radius, and no such
component exists today to extend. Rather than introduce a new shared file
not named by the survey, each screen implements its own inline
confirm-then-submit step (e.g., a checkbox or a second "Yes, disable
MFA"/"Yes, deactivate my account" button that only appears after the
consequence text is shown) using the same `react-hook-form` + native
semantic elements this stack already uses elsewhere. If a third
consumer of this pattern appears in a future Story, extracting a shared
component then is a safe refactor; inventing one now for two call sites,
neither in the survey, is not.

## Files To Create

### `api/`
- `frontend/src/api/profileApi.ts` — `patchProfile`, `confirmEmailChange`. FR-2/FR-3.
- `frontend/src/api/mfaApi.ts` — `enrollMfa`, `activateMfa`, `disableMfa`. FR-5/FR-6.
- `frontend/src/api/accountApi.ts` — `deactivateAccount`. FR-7.

### `hooks/`
- `frontend/src/hooks/useProfileUpdate.ts` — Change 3. FR-2/FR-3.
- `frontend/src/hooks/useConfirmEmailChange.ts` — FR-3; callable signed-in or signed-out, does not assume an authenticated hook context.
- `frontend/src/hooks/useVerifyEmail.ts` — FR-4.
- `frontend/src/hooks/useResendVerificationEmail.ts` — FR-4.
- `frontend/src/hooks/useMfaEnroll.ts` — FR-5, with `current_password` per OD-2.
- `frontend/src/hooks/useMfaActivate.ts` — FR-5; `recovery_codes` flow to the screen for display only, never persisted by the hook; `onSuccess` calls the new `authStore.setMfaEnabled(true)` action (Change 6).
- `frontend/src/hooks/useMfaDisable.ts` — FR-6, with `current_password` + `code` per OD-2; `onSuccess` calls `authStore.setMfaEnabled(false)` (Change 6).
- `frontend/src/hooks/useAccountDeactivate.ts` — FR-7; `onSuccess` calls `authStore.clearSession()`, same pattern as `useLogout.ts`.

### `screens/`
- `frontend/src/screens/ProfileScreen.tsx` — FR-2/FR-3, `/settings/profile`.
- `frontend/src/screens/EmailVerificationScreen.tsx` — FR-4, `/verify-email`.
- `frontend/src/screens/ConfirmEmailChangeScreen.tsx` — FR-3's confirmation-link landing target, `/confirm-email-change`. **Addition beyond `impact_analysis`'s illustrative screens list** — justified because `useConfirmEmailChange.ts` (already in that survey) needs a rendering target, and the survey's own routing section already names the guard gap this screen's route fills (Change 10).
- `frontend/src/screens/SecurityScreen.tsx` — FR-5/FR-6, `/settings/security` (Change 6).
- `frontend/src/screens/DeactivateAccountScreen.tsx` — FR-7, `/settings/deactivate`.

### `components/`
- `frontend/src/components/RecoveryCodesDisplay.tsx` — FR-5's one-time display: copy (`navigator.clipboard`) and download (local `Blob`/object-URL, no network) support, plus the explicit "I have saved these" confirmation gate. Never writes to any storage API.
- `frontend/src/components/QrCode.tsx` — Change 9; thin adapter isolating the new QR-rendering dependency to one file.

## Files To Modify

- `frontend/src/api/httpClient.ts` — add `httpPatch<T>` (Change 1). Existing `httpGet`/`httpPost`/`httpDelete` signatures unchanged.
- `frontend/src/api/types.ts` — additive new DTOs + `SUPPORTED_LOCALES` (Change 5, 7).
- `frontend/src/api/authApi.ts` — additive `verifyEmail`, `resendVerificationEmail` (Change 5). FR-4.
- `frontend/src/components/apiErrorHelpers.ts` — additive `getErrorStatus` (Change 4).
- `frontend/src/components/MfaEnrollmentBanner.tsx` — add a link into `/settings/security` (spec Assumption #6). Existing dismiss behavior and `sessionStorage` persistence untouched.
- `frontend/src/routes/AppRoutes.tsx` — add `/settings/profile`, `/settings/security`, `/settings/deactivate` (inside the existing `ProtectedRoute` group) and `/verify-email`, `/confirm-email-change` (unguarded, Change 10).
- `frontend/package.json` — add the QR-rendering dependency (Change 9), pending sign-off.
- `frontend/src/store/authStore.tsx` — additive `mfaEnabled: boolean` on `AuthStateSeed`/`SetSessionPayload` (required, not optional), a new `SET_MFA_ENABLED` reducer case, and a new `setMfaEnabled(enabled: boolean)` action on `AuthStoreValue` mirroring `setMfaToken`'s existing shape (Change 6, four sub-changes spelled out there). **Correction to `impact_analysis`'s "not affected" finding for this file** — that finding was scoped to FR-7's `clearSession` reuse only and did not examine FR-5/FR-6's enroll/disable signal need; see Change 6 and Risk 1.
- `frontend/src/hooks/useLogin.ts` — additive: pass `mfaEnabled: false` into `setSession` on the direct-login branch (Change 6, now a required `SetSessionPayload` field). Existing `setMfaToken`/challenge-branch behavior unchanged.
- `frontend/src/hooks/useMfaVerify.ts` — additive: pass `mfaEnabled: true` into `setSession` on its (challenge-completing) branch (Change 6).

**Not modified, confirmed by `impact_analysis`'s "Checked — Not Affected" section and independently re-confirmed while reading these files for this plan:** `errorNormalization.ts`, `ErrorState.tsx`, `FieldError.tsx`, `useLogout.ts`, `ProtectedRoute.tsx`, `GuestOnlyRoute.tsx`, `AppShell.tsx`. No protected file under `AGENTS.md` §7.9 (`pyproject.toml`, `migrations/env.py`, `.pre-commit-config.yaml`) is touched by this plan.

## Risks

1. **OD-5 (`OPEN`) is also the root cause of a second gap this plan found while reading the actual backend code, beyond what `impact_analysis` scoped: `enroll_mfa`/`disable_mfa` (`app/modules/users/service.py`) give the client no safe way to guess current MFA status.** A naive "always default to enroll" design would let an already-enrolled user's real TOTP secret be silently overwritten by the interim UI itself (`enroll_mfa` has no already-enabled guard). Change 6's fix — deriving `authStore.mfaEnabled` from the already-shipped login-response shape (`LoginResponse` vs `MfaRequiredResponse`) and keeping it current via this Story's own `useMfaActivate`/`useMfaDisable` — avoids that outcome using a real signal, not a guess, but it is still session-scoped (stale if MFA changes from another session concurrently) and should be revisited once a backend read endpoint exists. This also means `authStore.tsx`, `useLogin.ts`, and `useMfaVerify.ts` move from `impact_analysis`'s "not affected" to "modified" — see Files To Modify.
2. **One new dependency requires `AGENTS.md` §7.8 sign-off before `IMPLEMENTATION`: the QR-rendering library (Change 9, candidate `qrcode.react`).** Unlike US-5.1, this Story adds no router or a11y-library dependency — `react-router-dom` and `vitest-axe` are already present in `frontend/package.json` (confirmed by direct read).
3. **OD-1's resolution ("first write" wording) was flagged Low by `spec_review` as broader in FR-2 than OD-1's literal text** — FR-2 (and this plan's Change 3) applies `If-Match: *` "whenever no ETag is known," which also covers the post-`202` case, not only the literal first write. This plan follows the approved spec's (broader) wording, per `spec_review`'s own conclusion that the generalization is "a necessary, reasoned extension." Flagged here so `test-writer`/`reconciliation-reviewer` verify against FR-2's actual text, not OD-1's narrower original phrasing.
4. **OD-6 and OD-7 (`OPEN`) each bound a specific field's exact content, not its existence.** The locale constant (Change 7) and the `Intl`-derived timezone list (Change 8) are both structured so either OD's eventual answer is a small follow-up, not a re-architecture — but `implementation-planner`'s task breakdown should not treat either as fully settled. Change 8's runtime dependency was verified before committing to it, not assumed: `frontend/tsconfig.app.json` already sets `"target": "ES2022"`/`"lib": ["ES2022", ...]` (so `tsc --noEmit` accepts `Intl.supportedValuesOf`), and the local Node runtime (`v24.15.0`, full-ICU by default) resolves `Intl.supportedValuesOf("timeZone")` to 418 entries — Vitest/jsdom run under this same Node `Intl`, so no fallback list is needed.
5. **OD-3 (`OPEN`) means every authenticated route remains a raw `403 mfa-enrollment-required` dead-end for a privileged account mid-grace-period beyond the banner link (Change 11).** This is the spec's own current scope, not a gap this plan introduces, but it is a real UX gap until OD-3 resolves.
6. **`httpClient.ts` is shared, load-bearing infrastructure for every US-5.1 screen already shipped.** Change 1 is additive-only specifically to avoid regressing any existing call site; `frontend-builder` must not touch `performRequest`'s existing behavior for `GET`/`POST`/`DELETE` while adding `httpPatch`.
7. **`MfaEnrollmentBanner.tsx` is already-shipped US-5.1 code with an existing test.** The new link assertion must be additive to `MfaEnrollmentBanner.test.tsx`, not a rewrite that could silently drop existing dismiss-behavior coverage.
8. **Security-sensitive values (`secret`, `otpauth_uri`, `recovery_codes`, `current_password`) must never reach `localStorage`/`sessionStorage`/the console/any third party (NFR, PS-AC5).** All four are held only in transient React state (RHF form state or component state), cleared on navigation away — no hook or store persists them. Verified by `frontend-builder`'s grep-based self-check (per US-5.1 precedent) and independently at `SECURITY_REVIEW`.
9. **Confirm-email-change and verify-email routes sit outside both existing guards (Change 10) — a routing shape this codebase has no prior example of.** A mistaken wrap in either guard would silently break PS-AC3's "works signed-in and signed-out" requirement or PS-AC4's visitor-reachability requirement; `AppRoutes.test.tsx` must assert both directions explicitly for both routes, not just one.

## Validation Strategy

- **Gate green**: `npm run lint`, `npm run format:check`, `npm run
  type-check`, `npm run test:coverage` (`AGENTS.md` §2's Frontend
  subsection — load-bearing names, already wired into
  `.pre-commit-config.yaml` scoped to `files: ^frontend/`). `test:coverage`
  runs in CI only, same as the backend's coverage threshold.
- **Contracts intact (no `lint-imports` equivalent yet)**: the `AGENTS.md`
  §3 Frontend layer table is checked by reading the diff.
  Specifically for this Story: `ProfileScreen.tsx`/`SecurityScreen.tsx`/
  `DeactivateAccountScreen.tsx`/`EmailVerificationScreen.tsx`/
  `ConfirmEmailChangeScreen.tsx` must import only `hooks/`, `store/`
  (read-only), and shared components — never `api/` directly (this is
  exactly why Change 4 adds `getErrorStatus` to `apiErrorHelpers.ts` rather
  than having screens read `ApiError.status`). `api/profileApi.ts`,
  `mfaApi.ts`, `accountApi.ts` must import only `httpClient`/`types` — no
  React, no TanStack Query.
- **New-dependency sign-off**: the QR-rendering library (Risk 2) is
  proposed, not added, until a human explicitly approves it per `AGENTS.md`
  §7.8 — before `IMPLEMENTATION`, not as part of the automated gates above.
- **Migrations / runtime rules**: not applicable to this stack (`AGENTS.md`
  §6's Frontend subsection) — no ORM, cache, or migration exists here, and
  this Story adds none.
- **Contract & security**: no sensitive value (`secret`, `otpauth_uri`,
  `recovery_codes`, `current_password`, access token) ever reaches the
  browser console or a committed file; the existing access/refresh-token
  handling (`AGENTS.md` §3's session-handling rule) is unchanged by this
  Story and must not be touched while adding `httpPatch` (Change 1/Risk 6).
  Verified by `frontend-builder`'s grep-based self-check and independently
  at `SECURITY_REVIEW`.

## Testing Strategy

Per `AGENTS.md` §5's Frontend subsection: Vitest unit tests for hooks/pure
functions, React Testing Library + MSW integration tests per screen, 85%
coverage floor via `test:coverage`, CI-enforced. No `vi.mock()` of the unit
under test anywhere; MSW is the network boundary.

- **Unit**:
  - `httpPatch`'s status/headers-exposing shape and its `If-Match` header
    threading (Change 1) — a new `httpClient.test.ts` (flagged missing by
    `impact_analysis`; this Story is the first to need it).
  - `getErrorStatus` (Change 4) alongside the existing
    `getErrorKind`/`getErrorMessage` coverage pattern.
  - Each new hook's success/error mapping via MSW (`useProfileUpdate`'s
    200/202/412 branches per Change 3 is the one requiring the most
    branch coverage: known-ETag write, no-known-ETag write sending
    `If-Match: *`, a 202 removing the cached ETag, a 412 setting the
    conflict flag).
  - FR-9's client-side validation rules per form: email shape, 6-digit MFA
    code, locale membership in `SUPPORTED_LOCALES` (Change 7), timezone
    membership in the `Intl.supportedValuesOf("timeZone")`-derived list
    (Change 8) — each asserted to block submission with no API call, per
    `apiErrorHelpers`'s existing pattern of never calling the network layer
    for a client-caught error.
- **Integration (RTL + MSW)**, one module per screen, per
  `impact_analysis`'s Test-Surface Impact section plus the two additions
  this plan makes (`ConfirmEmailChangeScreen`, the two guard-shape tests):
  - **PS-AC2/FR-2** (`ProfileScreen.test.tsx`): edit-only submit sends only
    changed fields; first-ever write in a fresh session sends `If-Match:
    *`; a second write in the same session echoes the captured `ETag`; a
    412 response renders the "changed elsewhere, reload" state instead of
    silently overwriting.
  - **PS-AC3/FR-3** (`ProfileScreen.test.tsx` + `ConfirmEmailChangeScreen.test.tsx`):
    a 202 shows the pending-email state and stores no ETag (asserted via
    the next-write test sending `If-Match: *` again, proving the cache was
    cleared); `ConfirmEmailChangeScreen` succeeds both rendered with an
    authenticated test-utils wrapper and rendered without one.
  - **PS-AC4/FR-4** (`EmailVerificationScreen.test.tsx`): success/expired/invalid
    each render distinctly; the resend control shows one generic
    confirmation regardless of MSW handler outcome (address-exists vs. not).
  - **PS-AC5/FR-5** (`SecurityScreen.test.tsx`, `RecoveryCodesDisplay.test.tsx`,
    `QrCode.test.tsx`): rendered with `authStore.mfaEnabled = false`
    (seeded via `test-utils`'s `AuthProvider` `initialState`, Change 6) shows
    the enroll flow; enroll requires `current_password`; QR renders from
    `otpauth_uri` with no network request (assert no unexpected MSW/network
    call fires from the QR renderer itself); recovery codes display exactly
    once, cannot be dismissed without the explicit save-confirmation, and a
    grep-style assertion across the test's rendered output/mock storage
    confirms no storage API, console method, or third-party host receives
    `secret`/`otpauth_uri`/`recovery_codes`.
  - **PS-AC6/FR-6** (`SecurityScreen.test.tsx`): rendered with
    `authStore.mfaEnabled = true` shows the disable flow directly (proving
    the screen does not default to enroll for an already-enrolled session,
    the defect Change 6 exists to avoid); disable requires `current_password`
    + `code`; the confirmation step's copy names the session-revocation
    consequence; a successful disable calls `authStore.setMfaEnabled(false)`,
    verified via the store's own exposed state, not a spy on the hook.
  - **`useLogin.test.ts`/`useMfaVerify.test.ts`** (Change 6, additive
    assertions on already-existing test files): a plain `LoginResponse`
    sets `authStore.mfaEnabled = false`; completing `useMfaVerify` sets it
    `true` — the two branches `SecurityScreen`'s initial state depends on.
  - **PS-AC7/FR-7** (`DeactivateAccountScreen.test.tsx`): `current_password`
    is unconditionally required; on 200, `authStore.clearSession()` is
    called and the test asserts landing on `/login` with the confirmation
    message, via the real route tree in a memory router (not a
    `vi.mock('react-router-dom')` spy, consistent with
    `.pre-commit-config.yaml`'s screens-directory ban).
  - **XC-AC1/FR-8**: a problem+json 4xx and a 422-with-`errors[]` case per
    screen, reusing the existing `errorNormalization.ts`/`FieldError.tsx`
    infrastructure — no new normalization logic needed (per
    `impact_analysis`'s own "Checked — Not Affected" finding).
  - **XC-AC2/FR-9**: a blocked-submission test per form/field named above.
  - **XC-AC3/FR-10**: a network-error and a 5xx test per screen, asserting
    `ErrorState.tsx` renders, never a blank screen or an unhandled rejection.
  - **Routing (`AppRoutes.test.tsx`)**: `/settings/profile`,
    `/settings/security`, `/settings/deactivate` redirect an unauthenticated
    visitor to `/login` (existing `ProtectedRoute` behavior, new routes);
    `/verify-email` and `/confirm-email-change` render for **both** an
    authenticated and an unauthenticated test-utils wrapper (Risk 9) —
    explicitly two assertions per route, not one.
  - **MfaEnrollmentBanner.test.tsx**: existing dismiss-behavior assertions
    kept; one new assertion added for the link target into
    `/settings/security`.
  - **a11y bar**: an automated `vitest-axe` pass (existing devDependency) on
    `ProfileScreen`, `SecurityScreen`, and `DeactivateAccountScreen`
    specifically, per the Enforcement Matrix's `[gate]` row — including the
    timezone combobox's keyboard-navigability (Change 8) and the recovery-code
    list's copy/selectability by keyboard (PS-AC5's NFR).
- **New test infrastructure**: `frontend/src/test/mswHandlers.ts` gains one
  handler per new endpoint (`impact_analysis`'s list), following the
  existing one-handler-per-operation convention — not a new file.
- **Coverage** — 85% floor via `test:coverage`, a floor not a goal; no
  exclusion for the 200/202/412 branch in `useProfileUpdate.ts` or the
  guard-shape routes in `AppRoutes.tsx`.
