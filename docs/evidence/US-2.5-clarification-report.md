# US-2.5 (MFA/TOTP) — Clarification Report

## Scope, Actors, Business Value

**Actor:** Any user holding (or about to hold) a privileged role — `admin`, `auditor`, `support_agent` — plus any customer who opts in voluntarily. **Trigger:** enrolling a TOTP authenticator, or logging in on an account with MFA already enabled. **Business value:** a stolen or phished password alone no longer reaches the admin console or other customers' data (`docs/product/personas.md`'s Administrator/Support Agent/Auditor personas are all marked "MFA-mandatory").

In scope: enrolment (pending → active), activation with recovery-code issuance, the login-challenge branch and its verification endpoint, brute-force protection on the verify step, and mandatory enforcement for privileged roles including a 14-day rollout grace period. Out of scope: WebAuthn/passkeys, SMS codes, "remember this device" — all explicitly excluded by the story.

## What's Clear

- The TOTP algorithm choice (RFC 6238, SHA-1, 6-digit, 30s step, ±1 step skew) is fully specified and matches `business-glossary.md`'s MFA/TOTP entry.
- Recovery-code count (10), hashing (Argon2id — consistent with project-wide BR-003), and single-use semantics are unambiguous.
- The four endpoints (`enroll`, `activate`, `verify`, `DELETE`) have request/response shapes stated in the API Contract table.
- Brute-force handling (5 failed attempts → 429, token invalidated, full re-auth) is concrete and testable, and follows the same Valkey-counter pattern already established for login (`login_failure_threshold_account/ip` in `app/core/config.py`).
- The replay-protection mechanism (`mfa_used_step:{user_id}:{step}` in Valkey, TTL one time step) is concrete.
- The self-service MFA-disable requirement (current password + valid code) is unambiguous and consistent with the project's "hijacked session can't unilaterally weaken security" pattern (mirrors BR-006's deactivation-revocation discipline).
- Error-type slugs (`mfa-invalid-code`, `mfa-required-for-role`) and the RFC 7807 envelope are given directly.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-2.5-open-decisions.md` for full detail. Summary:

- **OD-1 (blocking):** US-2.5 depends on US-3.2 (Manage Roles) per this project's own `docs/stories/README.md` dependency notes and suggested build order — but US-3.2 has not been implemented. There is no `role` column on `users`, no permission-scope claim in the JWT, no `perm_epoch` mechanism anywhere in the current codebase. MF-AC6 directly cites "US-3.2 MR-AC1" behavior that doesn't exist yet. This is not a guessable detail — it changes whether this story can be built as scoped at all right now.
- **OD-2:** "Envelope encryption with a KMS-managed key" has no existing implementation or precedent in this codebase to follow (no KMS client, no encryption-at-rest utility anywhere in `app/`).
- **OD-3:** MF-AC1's "QR payload" phrase isn't reflected in the API Contract table's two-field response — unclear if a QR image is actually returned.
- **OD-4:** The 14-day grace-period "warning" mechanism (API field vs. email vs. both, and email cadence) is unresolved — the story itself flags the email-cadence half as an open question and doesn't address the API-response half at all.
- **OD-5:** Whether recovery-code consumption (MF-AC7) is a pure notification event or forces an account-level state change is unstated.
- **OD-6:** Whether disabling MFA should set `revoke_before` (matching the precedent set by password reset and deactivation) is unstated.

## Readiness Verdict

**Not Ready — see Open Decisions.**

OD-1 in particular is not a spec-writer-fillable gap: it's a structural dependency on a story that hasn't been built, explicitly documented as a prerequisite by this project's own backlog. Proceeding to `story-spec-writer` before this is resolved risks either quietly absorbing US-3.2's scope into US-2.5 or producing a spec for an acceptance criterion (MF-AC6) that cannot be implemented or tested. The remaining five decisions (OD-2 through OD-6) are ordinary spec-writer-blocking ambiguities of the kind this project has resolved before (e.g. US-2.4's OD-1–OD-3), but OD-1 should be resolved first since its outcome (which of options A/B/C) changes the shape of everything else.
