# Specification: Multi-Factor Authentication (TOTP)

**Source:** docs/backlog/US-2.5-mfa-totp.md
**Story ID:** US-009
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-009-spec-review.md)

## Summary

This spec covers TOTP-based multi-factor authentication: secret enrolment and activation with recovery-code issuance, the login-time MFA challenge and its verification (including wrong/replayed-code handling, skew tolerance, and brute-force lockout), mandatory enforcement for privileged roles with a 14-day rollout grace period, and recovery-code-based login when an authenticator device is lost.

## Background

As an administrator or support agent, the user wants to protect their account with a time-based one-time code, so that a stolen or phished password alone is not enough to reach the admin console or other customers' data.

## Functional Requirements

### FR-1: Enrolment

Given an authenticated user without MFA enrolled, when `POST /v1/auth/mfa/enroll` is called with the correct `current_password`, the system responds `200` with a TOTP secret (`otpauth://` URI + QR payload) in a PENDING state, per RFC 6238 TOTP using SHA-1, 6 digits, and a 30-second step. The secret is stored encrypted at rest (envelope encryption, KMS-managed key), never in plaintext. MFA is not yet active at this point, so an unfinished enrolment can never lock the user out.

**Derived from:** MF-AC1; algorithm parameters per source Assumptions & Defaults table. The wire format of the "QR payload" (e.g. a rendered image vs. the client rendering the `otpauth://` URI itself) is not defined by either document — see Open Questions.

### FR-2: Activation and Recovery Code Issuance

Given a pending enrolment, when `POST /v1/auth/mfa/activate` is called with a valid 6-digit code, the system responds `200` with 10 single-use recovery codes, shown exactly once. Recovery codes are stored as Argon2id hashes, never in plaintext. `users.mfa_enabled` becomes true, and an `auth_audit_log` entry is written (`event=mfa_enabled`).

**Derived from:** MF-AC2

### FR-3: Login Challenge for MFA-Enabled Users

Given a user with `mfa_enabled = true` who submits correct credentials, when `POST /v1/auth/login` is called, the system responds `200` with `{"mfa_required": true, "mfa_token": "..."}` and issues no access or refresh token. The `mfa_token` is single-use, scoped to MFA verification only, with a 5-minute TTL. Calling `POST /v1/auth/mfa/verify` with a valid code then completes the login exactly as described by US-2.1's LI-AC1 (see Open Questions — LI-AC1 is not defined in this source).

**Derived from:** MF-AC3

### FR-4: Incorrect or Replayed Verification Code

Given a valid `mfa_token`, when `POST /v1/auth/mfa/verify` is called with an incorrect code, the system responds `401` with type `.../errors/mfa-invalid-code`. Given a code that was already accepted within its time step, the system also responds `401`, because each code is single-use (replay protection). A ±1 time-step (30 second) skew window is accepted, and no wider.

**Derived from:** MF-AC4

### FR-5: Verification Brute-Force Lockout

Given 5 failed verification attempts against the same `mfa_token`, when `POST /v1/auth/mfa/verify` is called again, the system responds `429`, the `mfa_token` is invalidated, and full re-authentication is required, because a 6-digit code has only 10^6 possibilities and must not be guessable online.

**Derived from:** MF-AC5

### FR-6: Mandatory MFA Enforcement for Privileged Roles

Given a user holding the `admin`, `auditor`, or `support_agent` role, when `DELETE /v1/auth/mfa` is called, the system responds `409` with type `.../errors/mfa-required-for-role`. When such a role is granted to a user without MFA (per US-3.2's MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes (the specific endpoints included in that scope, and US-3.2's role-granting mechanics, are not defined in this source — see Open Questions). During the 14-day rollout grace period, login still succeeds, but each login warns the user and records the outstanding enrolment.

**Derived from:** MF-AC6

### FR-7: Recovery Code Use

Given a user who has lost their authenticator device, when `POST /v1/auth/mfa/verify` is called with a valid recovery code instead of a TOTP code, login completes, that recovery code is consumed and can never be reused. The user is emailed a security notification and prompted to re-enrol.

**Derived from:** MF-AC7

## Non-Functional Requirements

- Enforcement for privileged roles lives in the shared permission middleware (the same one US-3.2 uses), never in the UI.
- Disabling MFA for a non-privileged user requires the current password **and** a valid code, so a hijacked session cannot strip the second factor.
- Code comparison MUST be constant-time; the secret MUST never be returned again after enrolment.
- The rollout deadline is a configuration value, and its expiry is itself an audited event.
- Performance: verification is a local HMAC computation — p95 ≤ 50 ms, no external service on the login path.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- WebAuthn / passkeys (the natural follow-up story)
- SMS codes — deliberately excluded (SIM-swap risk)
- "Remember this device"

**Derived from:** Out of Scope section of the source.

## Open Questions

- What are the exact endpoints included in the "enrolment-scoped token" issued to a privileged-role user who lacks MFA (MF-AC6)? The source states such a token is "scoped only to the enrolment endpoints" but does not enumerate which endpoints that covers.
- MF-AC3 states that MFA verification "completes the login exactly as LI-AC1," and MF-AC6 references "US-3.2 MR-AC1" for how privileged roles are granted — both are defined in separate story files (US-2.1 Login and US-3.2 Manage Roles respectively) not included in this source. What do LI-AC1's exact response payload and MR-AC1's role-granting mechanics specify, so this story's dependent behavior can be implemented consistently with them?
- What is the communication plan for the 14-day rollout — who sends the warning emails, and on what schedule within the window? (Carried over verbatim from the source's own Open Questions section.)
- The source does not specify what happens when `POST /v1/auth/mfa/enroll` is called again for a user who already has a PENDING enrolment — e.g., whether it re-issues a new secret, returns the existing pending secret, or errors.
- What wire format does the "QR payload" in FR-1's `200` response use — a rendered image (e.g. base64-encoded PNG/SVG), or does the client render the `otpauth://` URI itself as a QR code? The source's API Contract table lists only `{"secret": str, "otpauth_uri": str}` for this response, with no field for a QR payload.
- FR-6 states that during the 14-day rollout grace period "each login warns the user and records the outstanding enrolment," but neither the source nor this spec defines the warning's delivery channel (a login-response field, an email, a client-rendered banner) or what "records" means operationally (a log line, a counter, a specific column).
- The source's API Contract table lists `DELETE /v1/auth/mfa` with a `204` success response for a non-privileged user disabling MFA, but no Acceptance Criterion describes this success path's behavior — does `users.mfa_enabled` become `false`? Are the secret and recovery codes purged? Is the `mfa_disabled` event (listed in the source's Data Model Notes) written to `auth_audit_log`? This story's only AC for `DELETE /v1/auth/mfa` (MF-AC6) covers just the privileged-role-blocked case.
- MF-AC7 describes consuming one recovery code, but neither the source nor this spec addresses what happens once a user has consumed all 10 recovery codes and still cannot access their authenticator — is a support-mediated recovery path expected, or is that deliberately out of scope?
- MF-AC5/FR-5 count "5 failed verification attempts against the same `mfa_token`" without distinguishing TOTP-code attempts from recovery-code attempts submitted to the same `/v1/auth/mfa/verify` endpoint. Does a wrong recovery code increment the same failure counter as a wrong TOTP code?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| MF-AC1 | "Given an authenticated user without MFA enrolled When POST /v1/auth/mfa/enroll is called with the correct current_password Then respond 200 with a TOTP secret (otpauth:// URI + QR payload) in a PENDING state And the secret is stored encrypted at rest (envelope encryption, KMS-managed key), never in plaintext And MFA is NOT yet active — an unfinished enrolment can never lock the user out" | FR-1 |
| MF-AC2 | "Given a pending enrolment When POST /v1/auth/mfa/activate is called with a valid 6-digit code Then respond 200 with 10 single-use recovery codes, shown exactly once And recovery codes are stored as Argon2id hashes, never in plaintext And users.mfa_enabled becomes true And an auth_audit_log entry is written (event=mfa_enabled)" | FR-2 |
| MF-AC3 | "Given a user with mfa_enabled = true who submits correct credentials When POST /v1/auth/login is called Then respond 200 with {\"mfa_required\": true, \"mfa_token\": \"...\"} and NO access or refresh token And the mfa_token is single-use, scoped to MFA verification only, with a 5-minute TTL And POST /v1/auth/mfa/verify with a valid code then completes the login exactly as LI-AC1" | FR-3 (LI-AC1 reference: Open Questions) |
| MF-AC4 | "Given a valid mfa_token When POST /v1/auth/mfa/verify is called with an incorrect code Then respond 401 with type \".../errors/mfa-invalid-code\" Given a code that was already accepted within its time step Then respond 401 as well, because each code is single-use (replay protection) And a ±1 time-step (30 s) skew window is accepted, no wider" | FR-4 |
| MF-AC5 | "Given 5 failed verification attempts against the same mfa_token When POST /v1/auth/mfa/verify is called again Then respond 429, the mfa_token is invalidated, and full re-authentication is required Because a 6-digit code has only 10^6 possibilities and must not be guessable online" | FR-5 |
| MF-AC6 | "Given a user holding the admin, auditor or support_agent role When DELETE /v1/auth/mfa is called Then respond 409 with type \".../errors/mfa-required-for-role\" And when such a role is granted to a user without MFA (US-3.2 MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes And during the 14-day rollout grace period login still succeeds, but each login warns the user and records the outstanding enrolment" | FR-6 (enrolment-scope and MR-AC1 details: Open Questions) |
| MF-AC7 | "Given a user who has lost their authenticator device When POST /v1/auth/mfa/verify is called with a valid recovery code instead of a TOTP code Then login completes, that recovery code is consumed and can never be reused And the user is emailed a security notification and prompted to re-enrol" | FR-7 |
