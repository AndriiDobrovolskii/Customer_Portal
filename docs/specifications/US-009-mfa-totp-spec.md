# Specification: Multi-Factor Authentication (TOTP)

**Source:** docs/stories/US-2.5-mfa-totp.md
**Story ID:** US-009
**Generated:** 2026-08-22
**Revised:** 2026-09-01 — incorporates OD-1–OD-11 (`docs/decisions/US-2.5-open-decisions.md`), all resolved by the user after US-3.2 (Manage Roles) reached PR (#9, merged), and the 6 findings independently surfaced by the pre-existing `docs/reviews/specifications/US-009-spec-review.md` (algorithm parameters omitted from FR-1, QR-payload format, grace-period warning mechanism, the undocumented disable-success path, recovery-code exhaustion, recovery-vs-lockout counter sharing). Further revised 2026-09-01 to resolve 3 findings from this same review's re-run (grace-period timestamp source, recovery-trigger grace-period scope, refresh-while-scoped behavior) — all resolved by the user, recommended options accepted throughout.
**Status:** Draft (revised)

## Summary

This spec covers TOTP-based multi-factor authentication: secret enrolment and activation with recovery-code issuance, the login-time MFA challenge and its verification (including wrong/replayed-code handling, skew tolerance, and brute-force lockout), mandatory enforcement for privileged roles with a 14-day rollout grace period, an enrolment-scoped-token mechanism shared by two distinct triggers, and recovery-code-based login when an authenticator device is lost.

## Background

As an administrator or support agent, the user wants to protect their account with a time-based one-time code, so that a stolen or phished password alone is not enough to reach the admin console or other customers' data.

## Open Decision Resolutions (2026-09-01)

- **OD-1 (US-3.2 dependency — BLOCKING, resolved):** US-3.2 (Manage Roles) reached PR (#9, merged to `main`). The role/permission-scope system this story depends on is live: a fixed role catalogue (`customer`, `support_agent`, `admin`, `auditor`), a JWT `scopes` claim, and a `perm_epoch:{user_id}` mechanism (`app/core/revocation_cache.py::PermissionEpochCache`) that invalidates access tokens only, distinct from `revoke_before`.
- **OD-2 (secret-at-rest encryption):** Follows the `jwt_secret_key` precedent — a local symmetric key (AES-GCM) read from a settings field, documented as a dev-only stand-in for a real KMS-managed key in production. No cloud KMS client is introduced.
- **OD-3 ("QR payload" wire format):** No third response field. `otpauth_uri` is the payload; the client is responsible for rendering it into a QR code. The enroll response stays exactly the two fields the source's API Contract table states (`secret`, `otpauth_uri`).
- **OD-4 + OD-7 (privileged-role grace-period warning, and what the "US-3.2 MR-AC1" citation actually resolves to):** Re-reading US-3.2's actual shipped spec (`docs/specifications/US-012-manage-roles-spec.md`) confirmed MF-AC6's "MR-AC1" citation describes a behavior — an enrolment-scoped token issued on a privileged-role grant — that MR-AC1, as specified and built, does not contain. This is net-new US-2.5 logic, not a hand-off from US-3.2: on every successful login (password verification), the system looks up the user's role names via a new read-only `roles.service` method and, if any held role is `admin`, `auditor`, or `support_agent` and `mfa_enabled` is `false`, applies the enrolment-scoped-token behavior described in FR-6. The grace-period warning is delivered as a field in the login response (not email); the rollout deadline is a configuration value.
- **OD-5 (recovery-code consumption — overrides the recommended advisory-only default):** Consuming a recovery code (FR-7) sets a new flag, `users.mfa_reenrollment_required`, rather than leaving `mfa_enabled` and enforcement untouched. The next successful login is issued the same enrolment-scoped token described in FR-6 — the mechanism now has two independent triggers (a privileged-role grant without MFA, and a recovery-code use by anyone), not one.
- **OD-6 + OD-8 (`DELETE /v1/auth/mfa` success path — not covered by any AC in the source):** On a successful, non-privileged disable: `users.mfa_enabled → false`, `mfa_secret_encrypted → NULL`, all recovery codes for the account deleted, `auth_audit_log` event `mfa_disabled` written, and `revoke_before:{user_id}` set — revoking every other active session, matching the precedent set by password reset and deactivation.
- **OD-9 (recovery-code exhaustion):** Out of scope for this story, on the same footing as WebAuthn/SMS/remember-device. A user who has consumed all 10 recovery codes and lost their authenticator must go through an out-of-band support process; a self-service or admin-mediated recovery path is deferred to a future story.
- **OD-10 (recovery-code attempts vs. the brute-force counter):** A wrong recovery code increments the same failure counter as a wrong TOTP code — both are guesses against the same `mfa_token`.
- **OD-11 (re-enrolling into an existing PENDING enrolment):** `POST /v1/auth/mfa/enroll` always issues a fresh secret, overwriting any existing PENDING one. Nothing is lost, since an unactivated secret was never in use.
- **Spec-review gap (grace-period clock has no data source), resolved 2026-09-01:** `user_roles` (US-3.2) gains a `granted_at` timestamp column (additive migration, nullable, backfilled to `now()` for existing rows). `PUT /v1/admin/users/{id}/roles` (US-012 FR-1) sets it on every full-replacement write that results in a role being held, so the 14-day grace-period clock in FR-6 has an unambiguous data source. This is a small, additive change to the already-merged US-3.2 schema, not a behavior change to US-3.2's endpoints.
- **Spec-review gap (grace period scope for the recovery-code trigger), resolved 2026-09-01:** No grace period applies when the enrolment-scoped token is triggered by recovery-code consumption (FR-7/OD-5) — it scopes the very next login unconditionally. The 14-day grace period (FR-6) applies only to the privileged-role-grant trigger, since that trigger represents someone newly needing to enrol, while a recovery-code trigger means MFA was already active and something went wrong.
- **Spec-review gap (refresh-token behavior while enrolment-scoped), resolved 2026-09-01:** `POST /v1/auth/refresh` re-evaluates the same enrolment-scoping condition login does (privileged role + `mfa_enabled = false`, or `mfa_reenrollment_required = true`) and mints an equally-scoped access token if the condition still holds — closing the bypass of calling refresh instead of logging in again while enrolment-scoped.

## Functional Requirements

### FR-1: Enrolment

Given an authenticated user without MFA enrolled, when `POST /v1/auth/mfa/enroll` is called with the correct `current_password`, the system responds `200` with a TOTP secret and its `otpauth://` URI (`{"secret": str, "otpauth_uri": str}`, no separate QR field — OD-3) in a PENDING state, per RFC 6238 TOTP using SHA-1, 6 digits, and a 30-second step. The secret is stored encrypted at rest using a local symmetric key (AES-GCM), documented as a dev-only stand-in for a real KMS-managed key in production (OD-2) — never in plaintext. MFA is not yet active at this point, so an unfinished enrolment can never lock the user out. If the user already has a PENDING enrolment, this call replaces it with a freshly generated secret (OD-11).

**Derived from:** MF-AC1; algorithm parameters per source Assumptions & Defaults table; secret storage per OD-2; QR-payload format per OD-3; re-enrolment behavior per OD-11.

### FR-2: Activation and Recovery Code Issuance

Given a pending enrolment, when `POST /v1/auth/mfa/activate` is called with a valid 6-digit code, the system responds `200` with 10 single-use recovery codes, shown exactly once. Recovery codes are stored as Argon2id hashes, never in plaintext. `users.mfa_enabled` becomes `true`, and an `auth_audit_log` entry is written (`event=mfa_enabled`). If `users.mfa_reenrollment_required` was `true` (FR-7/OD-5) or the account was holding an enrolment-scoped token (FR-6/OD-7), activation clears that flag and sets `perm_epoch:{user_id}` — the next call with the old scoped token responds `401 token-stale`, and `POST /v1/auth/refresh` then issues a normal, fully-scoped token.

**Derived from:** MF-AC2; exit condition for the enrolment-scoped-token mechanism per OD-7, extended to the OD-5 trigger.

### FR-3: Login Challenge for MFA-Enabled Users

Given a user with `mfa_enabled = true` who submits correct credentials, when `POST /v1/auth/login` is called, the system responds `200` with `{"mfa_required": true, "mfa_token": "..."}` and issues no access or refresh token. The `mfa_token` is single-use, scoped to MFA verification only, with a 5-minute TTL. Calling `POST /v1/auth/mfa/verify` with a valid code then completes the login exactly as described by US-2.1's LI-AC1.

**Derived from:** MF-AC3.

### FR-4: Incorrect or Replayed Verification Code

Given a valid `mfa_token`, when `POST /v1/auth/mfa/verify` is called with an incorrect code, the system responds `401` with type `.../errors/mfa-invalid-code`. Given a code that was already accepted within its time step, the system also responds `401`, because each code is single-use (replay protection). A ±1 time-step (30 second) skew window is accepted, and no wider.

**Derived from:** MF-AC4.

### FR-5: Verification Brute-Force Lockout

Given 5 failed verification attempts against the same `mfa_token`, when `POST /v1/auth/mfa/verify` is called again, the system responds `429`, the `mfa_token` is invalidated, and full re-authentication is required, because a 6-digit code has only 10^6 possibilities and must not be guessable online. A failed attempt counts toward this same limit regardless of whether it was a wrong TOTP code or a wrong recovery code (OD-10) — both are guesses against the same `mfa_token`.

**Derived from:** MF-AC5; shared counter per OD-10.

### FR-6: Mandatory MFA Enforcement for Privileged Roles, and the Enrolment-Scoped Token

Given a user holding the `admin`, `auditor`, or `support_agent` role, when `DELETE /v1/auth/mfa` is called, the system responds `409` with type `.../errors/mfa-required-for-role`.

On every successful login (password verification) and on every `POST /v1/auth/refresh` call, the system resolves the user's role names via a new read-only `roles.service` method (a sibling to the existing `resolve_scopes_for_user`, which US-3.2 already established as a cross-module dependency `users/service.py` uses). If the account holds `admin`, `auditor`, or `support_agent` and `mfa_enabled` is `false`, the call issues an **enrolment-scoped token** — valid only against the MFA enrolment endpoints (`POST /v1/auth/mfa/enroll`, `POST /v1/auth/mfa/activate`) — instead of a normal access token, until enrolment completes (FR-2's exit condition). Re-evaluating the condition on refresh (not just login) closes the bypass of holding a live refresh token to avoid re-scoping.

The 14-day rollout grace period is timed from `user_roles.granted_at` (a new column on the already-merged US-3.2 table, backfilled to `now()` for existing rows and set by `PUT /v1/admin/users/{id}/roles` on every write). During the grace period, login still succeeds and returns a normal token, but the response carries a field recording the outstanding-enrolment deadline (OD-4); after the grace period expires, the enrolment-scoped-token behavior applies unconditionally. The rollout deadline is a configuration value, and its expiry is itself an audited event. This condition only applies while `mfa_enabled` is `false` — an already-enrolled privileged user follows the normal MFA login challenge (FR-3) instead, since the two conditions (`mfa_enabled = false` vs. `mfa_enabled = true`) are mutually exclusive.

This enrolment-scoped-token mechanism has a second, independent trigger — recovery-code consumption (FR-7/OD-5) — which carries no grace period of its own (it scopes the very next login unconditionally) and shares FR-2's exit condition.

**Derived from:** MF-AC6; enrolment-scoped-token mechanism, role lookup, and its exit condition per OD-7; grace-period warning delivery per OD-4; `granted_at` timestamp source and refresh-time re-evaluation per the spec-review resolutions above.

### FR-7: Recovery Code Use

Given a user who has lost their authenticator device, when `POST /v1/auth/mfa/verify` is called with a valid recovery code instead of a TOTP code, login completes and that recovery code is consumed and can never be reused. The user is emailed a security notification and prompted to re-enrol. Consuming the code also sets `users.mfa_reenrollment_required = true` and writes an `auth_audit_log` entry (`event=mfa_recovery_used`); `mfa_enabled` and the existing secret/remaining recovery codes are left untouched. The next successful login (by any means — password + TOTP, or another recovery code) then issues the enrolment-scoped token described in FR-6, using the same exit condition (FR-2: activation clears the flag and sets `perm_epoch`).

**Derived from:** MF-AC7; degraded re-enrolment-required state per OD-5 (overrides the advisory-only default).

### FR-8: Non-Privileged MFA Disable

Given a non-privileged user (not holding `admin`, `auditor`, or `support_agent`) with MFA enabled, when `DELETE /v1/auth/mfa` is called with the correct `current_password` and a valid code, the system responds `204`. `users.mfa_enabled` becomes `false`, `mfa_secret_encrypted` is set to `NULL`, all of the account's recovery codes are deleted, an `auth_audit_log` entry is written (`event=mfa_disabled`), and `revoke_before:{user_id}` is set to now — revoking every other active session for the account, matching the precedent set by password reset and deactivation.

**Derived from:** Not covered by any Acceptance Criterion in the source (the source's API Contract table documents the `204` response with no accompanying Gherkin); resolved per OD-6/OD-8, both flagged independently by `docs/reviews/specifications/US-009-spec-review.md`.

## Non-Functional Requirements

- Enforcement for privileged roles lives in the shared permission middleware (the same one US-3.2 uses), never in the UI.
- Disabling MFA for a non-privileged user requires the current password **and** a valid code, so a hijacked session cannot strip the second factor.
- Code comparison MUST be constant-time; the secret MUST never be returned again after enrolment.
- The rollout deadline is a configuration value, and its expiry is itself an audited event.
- Performance: verification is a local HMAC computation — p95 ≤ 50 ms, no external service on the login path.
- The MFA secret is encrypted at rest using a local symmetric key (AES-GCM) read from settings, documented as a dev-only stand-in for a real KMS-managed key in production (OD-2).

**Derived from:** Non-Functional / Security Requirements section of the source; encryption mechanism per OD-2.

## Out of Scope

- WebAuthn / passkeys (the natural follow-up story)
- SMS codes — deliberately excluded (SIM-swap risk)
- "Remember this device"
- Recovery-code exhaustion (a user who has consumed all 10 codes and lost their authenticator) — deferred to a future support-mediated recovery story (OD-9)

**Derived from:** Out of Scope section of the source; recovery-code exhaustion per OD-9.

## Error Envelope (RFC 7807 `application/problem+json`)

```json
{
  "type": "https://portal.internal/errors/mfa-required-for-role",
  "title": "MFA Required For This Role",
  "status": 409,
  "detail": "Accounts with administrative access must keep multi-factor authentication enabled.",
  "instance": "/v1/auth/mfa"
}
```

Error `type` slugs introduced by this story: `mfa-invalid-code`, `mfa-required-for-role`. The enrolment-scoped-token rejection (FR-6) reuses the existing `token-stale` slug introduced by US-3.2, since both describe an access token whose claims no longer reflect the account's current state.

**Derived from:** Error Envelope section of the source; `token-stale` reuse per OD-7.

## Open Questions

None — all 11 Open Decisions raised by `us-clarifier` are resolved above (Open Decision Resolutions). The source's own Open Question about the grace-period warning email cadence is moot under OD-4's resolution (a login-response field, not an email).

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| MF-AC1 | "Given an authenticated user without MFA enrolled When POST /v1/auth/mfa/enroll is called with the correct current_password Then respond 200 with a TOTP secret (otpauth:// URI + QR payload) in a PENDING state And the secret is stored encrypted at rest (envelope encryption, KMS-managed key), never in plaintext And MFA is NOT yet active — an unfinished enrolment can never lock the user out" | FR-1 |
| MF-AC2 | "Given a pending enrolment When POST /v1/auth/mfa/activate is called with a valid 6-digit code Then respond 200 with 10 single-use recovery codes, shown exactly once And recovery codes are stored as Argon2id hashes, never in plaintext And users.mfa_enabled becomes true And an auth_audit_log entry is written (event=mfa_enabled)" | FR-2 |
| MF-AC3 | "Given a user with mfa_enabled = true who submits correct credentials When POST /v1/auth/login is called Then respond 200 with {\"mfa_required\": true, \"mfa_token\": \"...\"} and NO access or refresh token And the mfa_token is single-use, scoped to MFA verification only, with a 5-minute TTL And POST /v1/auth/mfa/verify with a valid code then completes the login exactly as LI-AC1" | FR-3 |
| MF-AC4 | "Given a valid mfa_token When POST /v1/auth/mfa/verify is called with an incorrect code Then respond 401 with type \".../errors/mfa-invalid-code\" Given a code that was already accepted within its time step Then respond 401 as well, because each code is single-use (replay protection) And a ±1 time-step (30 s) skew window is accepted, no wider" | FR-4 |
| MF-AC5 | "Given 5 failed verification attempts against the same mfa_token When POST /v1/auth/mfa/verify is called again Then respond 429, the mfa_token is invalidated, and full re-authentication is required Because a 6-digit code has only 10^6 possibilities and must not be guessable online" | FR-5 |
| MF-AC6 | "Given a user holding the admin, auditor or support_agent role When DELETE /v1/auth/mfa is called Then respond 409 with type \".../errors/mfa-required-for-role\" And when such a role is granted to a user without MFA (US-3.2 MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes And during the 14-day rollout grace period login still succeeds, but each login warns the user and records the outstanding enrolment" | FR-6 |
| MF-AC7 | "Given a user who has lost their authenticator device When POST /v1/auth/mfa/verify is called with a valid recovery code instead of a TOTP code Then login completes, that recovery code is consumed and can never be reused And the user is emailed a security notification and prompted to re-enrol" | FR-7 |
