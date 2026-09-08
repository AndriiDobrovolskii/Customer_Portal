---
artifact_type: task_breakdown
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T08:34:53Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: implementation-planner
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: null
---

# Task Breakdown — US-5.2

Track: `frontend` (per `docs/stories/US-5.2-account-self-service-ui.md` front
matter). `API_DESIGN`/`DB_DESIGN` both recorded `NOT_APPLICABLE` — no
backend-track skill appears in this breakdown. The single execution skill on
this track is `frontend-builder`; layers below are `AGENTS.md` §3's Frontend
subsection table (`api/`, `store/`, `components/`, `hooks/`, `screens/`,
`routes/`), not the backend layer table. `frontend/` already exists
(shipped by US-5.1) — no scaffold task is needed.

| Task ID | Skill to Invoke | Layer (AGENTS.md §3) | Depends On | Files Touched | Verification Command |
|---|---|---|---|---|---|
| T1 | frontend-builder | `api/` | — | frontend/src/api/httpClient.ts (add `httpPatch<T>`, Plan Change 1), httpClient.test.ts (new), frontend/src/api/types.ts (new DTOs + `SUPPORTED_LOCALES`, Change 5/7), frontend/src/api/profileApi.ts (new), frontend/src/api/mfaApi.ts (new), frontend/src/api/accountApi.ts (new), frontend/src/api/authApi.ts (add `verifyEmail`/`resendVerificationEmail`), frontend/src/test/mswHandlers.ts (one handler per new endpoint: `PATCH /profile`, `POST /profile/confirm-email-change`, `POST /auth/verify-email`, `POST /auth/verify-email/resend`, `POST /auth/mfa/enroll`, `POST /auth/mfa/activate`, `DELETE /auth/mfa`, `POST /account/deactivate`) | `npx vitest run frontend/src/api/httpClient.test.ts` passes, asserting `httpPatch` resolves `{data,status,headers}` and threads `If-Match` only when `options.ifMatch` is supplied; `npx tsc --noEmit` clean; diff-read confirms `httpGet`/`httpPost`/`httpDelete` signatures are byte-for-byte unchanged (Plan Risk 6); `grep -rl "from \"react\"\|@tanstack/react-query" frontend/src/api/profileApi.ts frontend/src/api/mfaApi.ts frontend/src/api/accountApi.ts frontend/src/api/authApi.ts` returns no matches (AGENTS.md §3 `api/` row) |
| T2 | frontend-builder | `store/` (auth state) | — | frontend/src/store/authStore.tsx (`AuthStateSeed`/`SetSessionPayload` gain required `mfaEnabled: boolean`, new `SET_MFA_ENABLED` reducer case, new `setMfaEnabled` action on `AuthStoreValue` — Plan Change 6) | `grep -n "mfaEnabled" frontend/src/store/authStore.tsx` shows it in `AuthStateSeed`, `SetSessionPayload`, the `SET_SESSION`/`SET_MFA_ENABLED`/`CLEAR_SESSION` reducer cases, and `AuthStoreValue`; `grep -rl "from \"\.\./api\|from \"\.\./hooks" frontend/src/store` returns no matches (AGENTS.md §3 `store/` row). (`npx tsc --noEmit` is not the proof for this task in isolation — `SetSessionPayload.mfaEnabled` is now required, and the two call sites that supply it, `useLogin.ts`/`useMfaVerify.ts`, are T4's edits; the full clean `tsc --noEmit` compile is proven at T4/T13.) |
| T3 | frontend-builder | `components/` (shared helper) | — | frontend/src/components/apiErrorHelpers.ts (add `getErrorStatus`, Plan Change 4), apiErrorHelpers.test.ts | `npx vitest run frontend/src/components/apiErrorHelpers.test.ts` passes for `getErrorStatus` alongside the existing `getErrorKind`/`getErrorMessage` coverage pattern; `grep -n "^import.*api/" frontend/src/components/apiErrorHelpers.ts` returns no match — stays structural/duck-typed, no direct `api/` import (AGENTS.md §3 `screens/`, `components/` row; scoped to actual `import` statements, not the file's explanatory comment, which references `api/httpClient.ts`'s `ApiError` shape by name without importing it) |
| T4 | frontend-builder | `hooks/` | T1, T2 | frontend/src/hooks/useProfileUpdate.ts(+test) [Change 3], useConfirmEmailChange.ts(+test), useVerifyEmail.ts(+test), useResendVerificationEmail.ts(+test), useMfaEnroll.ts(+test), useMfaActivate.ts(+test), useMfaDisable.ts(+test), useAccountDeactivate.ts(+test), useLogin.ts (modify: pass `mfaEnabled: false` into `setSession`, +additive test), useMfaVerify.ts (modify: pass `mfaEnabled: true` into `setSession`, +additive test) | `npx vitest run frontend/src/hooks/useProfileUpdate.test.ts frontend/src/hooks/useConfirmEmailChange.test.ts frontend/src/hooks/useVerifyEmail.test.ts frontend/src/hooks/useResendVerificationEmail.test.ts frontend/src/hooks/useMfaEnroll.test.ts frontend/src/hooks/useMfaActivate.test.ts frontend/src/hooks/useMfaDisable.test.ts frontend/src/hooks/useAccountDeactivate.test.ts frontend/src/hooks/useLogin.test.ts frontend/src/hooks/useMfaVerify.test.ts` passes — including `useProfileUpdate`'s 200/202/412 branch coverage (known-ETag write, no-known-ETag write sending `If-Match: *`, a 202 removing the cached ETag, a 412 setting the conflict flag) and the additive `mfaEnabled` assertions on `useLogin`/`useMfaVerify`; `npx tsc --noEmit` clean (proves T2's now-required `SetSessionPayload.mfaEnabled` field is satisfied at both call sites); diff-read confirms `useMfaActivate`'s/`useMfaDisable`'s `onSuccess` call `authStore.setMfaEnabled`, `useAccountDeactivate`'s calls `authStore.clearSession`, and no store write happens inside a screen |
| T5 | frontend-builder | `components/` (new UI) | — | frontend/src/components/RecoveryCodesDisplay.tsx(+test), frontend/src/components/QrCode.tsx(+test), frontend/package.json (add the QR-rendering dependency, candidate `qrcode.react` — Plan Change 9/Risk 2) | `npx vitest run frontend/src/components/RecoveryCodesDisplay.test.tsx frontend/src/components/QrCode.test.tsx` passes, including the assertion that no storage API, console method, or third-party host ever receives `secret`/`otpauth_uri`/`recovery_codes`, and that `QrCode` fires no unexpected network/MSW call; `grep -rl "qrcode" frontend/src --include=*.ts --include=*.tsx` returns only `QrCode.tsx`/`QrCode.test.tsx` (the new dependency stays isolated to one adapter file). **Blocked until the QR-rendering dependency receives `AGENTS.md` §7.8 human sign-off — see Notes below; this task cannot execute before that approval is recorded.** |
| T6 | frontend-builder | `screens/` | T1, T2, T3, T4 | frontend/src/screens/ProfileScreen.tsx(+test), `/settings/profile` | `npx vitest run frontend/src/screens/ProfileScreen.test.tsx` passes (PS-AC2/FR-2: edit-only submit, first-write `If-Match: *`, second-write echoes captured ETag, 412 renders "changed elsewhere, reload"; PS-AC3/FR-3: 202 shows pending-email state and clears the cached ETag; FR-9: locale membership in `SUPPORTED_LOCALES`, timezone membership in the `Intl.supportedValuesOf("timeZone")`-derived list; XC-AC1/XC-AC2/XC-AC3); no `vi.mock(` in the test file; `grep -l "fetch(\|axios\|api/httpClient\|api/profileApi" frontend/src/screens/ProfileScreen.tsx` returns no matches (AGENTS.md §3 `screens/` row: no direct `api/` import); a `vitest-axe` pass on this screen returns zero violations (spec Enforcement Matrix `[gate]`, includes the timezone combobox's keyboard-navigability) |
| T7 | frontend-builder | `screens/` | T3, T4 | frontend/src/screens/EmailVerificationScreen.tsx(+test), `/verify-email` | `npx vitest run frontend/src/screens/EmailVerificationScreen.test.tsx` passes (PS-AC4/FR-4: success/expired/invalid render distinctly; resend shows one generic confirmation regardless of MSW handler outcome; XC-AC1/XC-AC2/XC-AC3); no `vi.mock(` in the test file; grep confirms no direct `api/` import |
| T8 | frontend-builder | `screens/` | T3, T4 | frontend/src/screens/ConfirmEmailChangeScreen.tsx(+test), `/confirm-email-change` | `npx vitest run frontend/src/screens/ConfirmEmailChangeScreen.test.tsx` passes rendered **both** with an authenticated test-utils wrapper and without one (PS-AC3/FR-3 "works signed-in and signed-out", Plan Risk 9 — two assertions, not one); no `vi.mock(` in the test file; grep confirms no direct `api/` import |
| T9 | frontend-builder | `screens/` | T2, T3, T4, T5 | frontend/src/screens/SecurityScreen.tsx(+test), `/settings/security` | `npx vitest run frontend/src/screens/SecurityScreen.test.tsx` passes rendered with `authStore.mfaEnabled = false` (seeded via `test-utils`'s `AuthProvider` `initialState`) showing the enroll flow (PS-AC5/FR-5: `current_password` required, QR renders from `otpauth_uri` with no network call, recovery codes display exactly once behind an explicit save-confirmation) **and** with `mfaEnabled = true` showing the disable flow directly, not a default-to-enroll (PS-AC6/FR-6: `current_password`+`code` required, session-revocation consequence named, `authStore.setMfaEnabled(false)` verified via the store's own exposed state); no `vi.mock(` in the test file; a `vitest-axe` pass returns zero violations |
| T10 | frontend-builder | `screens/` | T3, T4 | frontend/src/screens/DeactivateAccountScreen.tsx(+test), `/settings/deactivate` | `npx vitest run frontend/src/screens/DeactivateAccountScreen.test.tsx` passes (PS-AC7/FR-7: `current_password` unconditionally required; on 200, `authStore.clearSession()` is called and landing on `/login` with the confirmation message is asserted via the real route tree in a memory router, not a `vi.mock('react-router-dom')` spy); no `vi.mock(` in the test file; a `vitest-axe` pass returns zero violations |
| T11 | frontend-builder | `routes/` (route table) | T6, T7, T8, T9, T10 | frontend/src/routes/AppRoutes.tsx (add `/settings/profile`, `/settings/security`, `/settings/deactivate` inside the existing `ProtectedRoute` group; add `/verify-email`, `/confirm-email-change` outside both `ProtectedRoute` and `GuestOnlyRoute`, Plan Change 10), AppRoutes.test.tsx | `npx vitest run frontend/src/routes/AppRoutes.test.tsx` passes: `/settings/profile`, `/settings/security`, `/settings/deactivate` redirect an unauthenticated visitor to `/login`; `/verify-email` and `/confirm-email-change` each render for **both** an authenticated and an unauthenticated test-utils wrapper (explicitly two assertions per route, Plan Risk 9); `grep -rl "from \"\.\./api" frontend/src/routes` returns no matches (AGENTS.md §3 `routes/` row) |
| T12 | frontend-builder | `components/` (modify) | T11 | frontend/src/components/MfaEnrollmentBanner.tsx (add a link into `/settings/security`, spec Assumption #6), MfaEnrollmentBanner.test.tsx (additive assertion only) | `npx vitest run frontend/src/components/MfaEnrollmentBanner.test.tsx` passes: all existing dismiss-behavior assertions still pass unchanged (Plan Risk 7 — no rewrite dropping existing coverage), plus one new assertion for the link target rendering into `/settings/security` |
| T13 | gate-enforcer | — | T1–T12 | — | `cd frontend && npm run lint && npm run format:check && npm run type-check && npm run test:coverage` all pass; `pre-commit run --all-files` passes (frontend-scoped hooks); diff-read confirms `AGENTS.md` §3 Frontend layer-table import directions across every file touched by T1–T12 (no `lint-imports` equivalent on this stack yet); confirms no sensitive value (`secret`, `otpauth_uri`, `recovery_codes`, `current_password`, access token) reaches `localStorage`/`sessionStorage`/console/a third party (Plan Risk 8) |

`T1`, `T2`, `T3` are parallel-eligible — each has no dependency on the other
two. `T5` is parallel-eligible with `T1`–`T4` (no shared dependency), subject
to its own sign-off gate below. `T6`–`T10` (the five screens) are mutually
parallel-eligible — each depends only on the subset of `T1`–`T5` named in its
row, not on each other.

## Notes (carried forward from the implementation plan, not resolved here)

- **New-dependency sign-off blocks `T5` (`qrcode.react`), and the
  no-network-call portion of `T9`'s `SecurityScreen`/`QrCode` verification
  that depends on it.** Plan Risk 2: per `AGENTS.md` §7.8, this is a
  new-dependency propose/approve human sign-off required before
  `IMPLEMENTATION`, not something `frontend-builder` may add unilaterally.
  This is not modeled as its own Task ID because the sign-off is a human
  gate, not an execution-skill task — but `T5` cannot start, and `T9`'s
  QR-rendering assertions cannot run, until it is recorded.
- **OD-6/OD-7 are gated on content, not existence** (Plan Risk 4): `T1`'s
  `SUPPORTED_LOCALES` constant and `T6`'s `Intl.supportedValuesOf("timeZone")`-
  derived combobox both ship the plan's documented default regardless of
  either OD's eventual resolution; neither blocks scheduling.
- **OD-3 is explicitly not built** (Plan Change 11/Risk 5): `T12`'s banner
  link is the entire integration point per the spec's current scope; no task
  in this breakdown adds a forced-navigation guard to `AppShell.tsx` or any
  route.
- **`T2`/`T4` together are this breakdown's realization of Plan Change
  6/Risk 1** — `impact_analysis` originally scored `authStore.tsx`,
  `useLogin.ts`, and `useMfaVerify.ts` as "not affected"; the plan corrected
  that, and `T2` (store) followed by `T4` (the two hook edits, gated on `T2`)
  is why `T2` alone is not expected to leave `tsc --noEmit` clean — the fix
  spans both tasks by design.
- **`mswHandlers.ts` additions are bundled into `T1`** rather than a separate
  Task ID, following `US-5.1`'s task-breakdown precedent of folding shared
  test-infrastructure amendments into the layer task that introduces the
  endpoints needing them.
- **OD-1's broader-than-literal `If-Match: *` wording** (Plan Risk 3) is
  already reflected in `T4`'s `useProfileUpdate` verification bullet (four
  named branches, not three) — `test-writer`/`reconciliation-reviewer`
  should verify against FR-2's approved (broader) text, not OD-1's narrower
  original phrasing.
