---
artifact_type: traceability
story: US-5.2
version: 1
status: APPROVED
created_at: "2026-09-08T14:44:55Z"
updated_at: "2026-09-08T14:50:55Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/designs/US-5.2-design-review.md
    version: 1
  - path: docs/tests/US-5.2-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.2-implementation-report.md
    version: 1
  - path: docs/verification/US-5.2-implementation-verification.md
    version: 1
supersedes: null
---

# Traceability: Account & Profile Self-Service (Frontend) — US-5.2

End-to-end AC → specification → design → test → code mapping. Design is
`NOT_APPLICABLE` for every row: this Story is frontend-only and makes no
API/DB change (`API_DESIGN` and `DB_DESIGN` both returned `NOT_APPLICABLE`;
`design_review` recorded `NOT_APPLICABLE` for the same reason).

| AC ID | Spec FR | Design | Test File(s) | Source Code |
|---|---|---|---|---|
| PS-AC1 | FR-1 (deferred) | NOT_APPLICABLE — no backend read endpoint exists this Story (OD-5) | `screens/ProfileScreen.test.tsx` (no dedicated test; positive companion: `test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values`) | `frontend/src/screens/ProfileScreen.tsx` |
| PS-AC2 | FR-2 (per OD-1's resolution) | NOT_APPLICABLE | `screens/ProfileScreen.test.tsx`, `hooks/useProfileUpdate.test.ts`, `api/httpClient.test.ts` | `frontend/src/screens/ProfileScreen.tsx`, `frontend/src/hooks/useProfileUpdate.ts`, `frontend/src/api/httpClient.ts`, `frontend/src/api/profileApi.ts` |
| PS-AC3 | FR-3 | NOT_APPLICABLE | `screens/ProfileScreen.test.tsx`, `screens/ConfirmEmailChangeScreen.test.tsx`, `routes/AppRoutes.test.tsx`, `hooks/useProfileUpdate.test.ts`, `hooks/useConfirmEmailChange.test.ts`, `api/httpClient.test.ts` | `frontend/src/screens/ProfileScreen.tsx`, `frontend/src/screens/ConfirmEmailChangeScreen.tsx`, `frontend/src/hooks/useProfileUpdate.ts`, `frontend/src/hooks/useConfirmEmailChange.ts`, `frontend/src/api/profileApi.ts`, `frontend/src/routes/AppRoutes.tsx` |
| PS-AC4 | FR-4 | NOT_APPLICABLE | `screens/EmailVerificationScreen.test.tsx`, `routes/AppRoutes.test.tsx`, `hooks/useVerifyEmail.test.ts`, `hooks/useResendVerificationEmail.test.ts` | `frontend/src/screens/EmailVerificationScreen.tsx`, `frontend/src/hooks/useVerifyEmail.ts`, `frontend/src/hooks/useResendVerificationEmail.ts`, `frontend/src/api/authApi.ts`, `frontend/src/routes/AppRoutes.tsx` |
| PS-AC5 | FR-5 (per OD-2's resolution) | NOT_APPLICABLE | `screens/SecurityScreen.test.tsx`, `components/RecoveryCodesDisplay.test.tsx`, `components/QrCode.test.tsx`, `hooks/useMfaEnroll.test.ts`, `hooks/useMfaActivate.test.ts` | `frontend/src/screens/SecurityScreen.tsx`, `frontend/src/components/RecoveryCodesDisplay.tsx`, `frontend/src/components/QrCode.tsx`, `frontend/src/hooks/useMfaEnroll.ts`, `frontend/src/hooks/useMfaActivate.ts`, `frontend/src/api/mfaApi.ts` |
| PS-AC6 | FR-6 (per OD-2's resolution) | NOT_APPLICABLE | `screens/SecurityScreen.test.tsx`, `hooks/useMfaDisable.test.ts`, `hooks/useLogin.test.ts`, `hooks/useMfaVerify.test.ts` | `frontend/src/screens/SecurityScreen.tsx`, `frontend/src/hooks/useMfaDisable.ts`, `frontend/src/api/mfaApi.ts`, `frontend/src/store/authStore.tsx` |
| PS-AC7 | FR-7 (per OD-4's resolution) | NOT_APPLICABLE | `screens/DeactivateAccountScreen.test.tsx`, `routes/AppRoutes.test.tsx`, `hooks/useAccountDeactivate.test.ts` | `frontend/src/screens/DeactivateAccountScreen.tsx`, `frontend/src/screens/LoginScreen.tsx` (additive — confirmation-message rendering), `frontend/src/hooks/useAccountDeactivate.ts`, `frontend/src/api/accountApi.ts` |
| XC-AC1 | FR-8 | NOT_APPLICABLE | `screens/ProfileScreen.test.tsx`, `screens/EmailVerificationScreen.test.tsx`, `screens/ConfirmEmailChangeScreen.test.tsx`, `screens/SecurityScreen.test.tsx`, `screens/DeactivateAccountScreen.test.tsx`, `components/apiErrorHelpers.test.ts` | `frontend/src/components/apiErrorHelpers.ts`, `frontend/src/api/errorNormalization.ts`, `frontend/src/screens/ProfileScreen.tsx`, `frontend/src/screens/EmailVerificationScreen.tsx`, `frontend/src/screens/ConfirmEmailChangeScreen.tsx`, `frontend/src/screens/SecurityScreen.tsx`, `frontend/src/screens/DeactivateAccountScreen.tsx` |
| XC-AC2 | FR-9 | NOT_APPLICABLE | `screens/ProfileScreen.test.tsx`, `screens/EmailVerificationScreen.test.tsx`, `screens/SecurityScreen.test.tsx`, `screens/DeactivateAccountScreen.test.tsx` | Form validation inline in `frontend/src/screens/ProfileScreen.tsx`, `frontend/src/screens/EmailVerificationScreen.tsx`, `frontend/src/screens/SecurityScreen.tsx`, `frontend/src/screens/DeactivateAccountScreen.tsx` |
| XC-AC3 | FR-10 | NOT_APPLICABLE | `screens/ProfileScreen.test.tsx`, `screens/EmailVerificationScreen.test.tsx`, `screens/ConfirmEmailChangeScreen.test.tsx`, `screens/SecurityScreen.test.tsx`, `screens/DeactivateAccountScreen.test.tsx`, `hooks/useResendVerificationEmail.test.ts` | `frontend/src/components/apiErrorHelpers.ts`, `frontend/src/api/httpClient.ts`, `frontend/src/screens/ProfileScreen.tsx`, `frontend/src/screens/EmailVerificationScreen.tsx`, `frontend/src/screens/ConfirmEmailChangeScreen.tsx`, `frontend/src/screens/SecurityScreen.tsx`, `frontend/src/screens/DeactivateAccountScreen.tsx` |

## Supporting / non-AC-mapped tests

- `api/httpClient.test.ts` — transport-layer primitive (`httpPatch`) tests underlying PS-AC2/PS-AC3; one row (`test_http_patch_omits_if_match_header_when_option_not_supplied`) proves conditional header threading at the transport layer, not `useProfileUpdate`'s always-send-`If-Match` policy — see the reconciliation report's Spec Drift section.
- `components/apiErrorHelpers.test.ts` — remaining branch coverage for `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors` underlying every screen's XC-AC1 rendering.
- `components/MfaEnrollmentBanner.test.tsx` — spec Assumption #6's banner-link-into-enrollment integration point; not itself a numbered AC.

## Open Decisions carried into shipped behavior

| OD | Status | Disposition in shipped code |
|---|---|---|
| OD-1 | RESOLVED (`HUMAN_SPEC_APPROVAL`) | `If-Match: *` sent whenever no ETag is known (PS-AC2 deviation, spec v2 FR-2) |
| OD-2 | RESOLVED (`HUMAN_SPEC_APPROVAL`) | `current_password` required on MFA enroll/disable; disable also requires TOTP `code` and warns of session revocation (PS-AC5/PS-AC6 deviations, spec v2 FR-5/FR-6) |
| OD-4 | RESOLVED (`HUMAN_SPEC_APPROVAL`) | `current_password` unconditionally required on deactivation; password-less accounts out of scope (PS-AC7 deviation, spec v2 FR-7) |
| OD-3 | OPEN | No forced navigation for enrollment-scoped tokens; banner-link-only per spec's own scope. No test (matches spec scope, not a gap). |
| OD-5 | OPEN | PS-AC1 (profile view) untestable/unimplemented this Story — no `GET /profile`/`GET /users/me`; deferred to a future backend Story. |
| OD-6 | OPEN | Locale set (`en-US`, `en-GB`) shipped as this pass's recorded default, tested against that default, not a resolved OD. |
| OD-7 | OPEN | Timezone input scope shipped as this pass's recorded default, tested against that default, not a resolved OD. |

Reconciliation does not resolve any Open Decision; this table records where
each one's current state landed in the shipped, tested code.
