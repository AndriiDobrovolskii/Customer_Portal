# Spec Review: Multi-Factor Authentication (TOTP)

**Original Story:** docs/stories/US-2.5-mfa-totp.md
**Spec Reviewed:** docs/specifications/US-009-mfa-totp-spec.md
**Story ID:** US-009 (source backlog file uses US-2.5)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All 7 Acceptance Criteria (MF-AC1–MF-AC7) are fully covered by FR-1 through FR-7, with faithful, near-verbatim traceability and no contradictions of the source story. The spec also does good hygiene work flagging genuine cross-story gaps (LI-AC1, MR-AC1, enrolment-endpoint scope) as Open Questions rather than inventing answers. The issues found are: one story-stated default (the TOTP algorithm/hash parameters) that never makes it into any FR, two ambiguous behavioral phrases carried through without clarification, and a handful of edge cases implied by the story's own API Contract and AC text that neither the ACs nor the spec's Open Questions address.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| MF-AC1 | "Given an authenticated user without MFA enrolled When POST /v1/auth/mfa/enroll is called with the correct current_password Then respond 200 with a TOTP secret (otpauth:// URI + QR payload) in a PENDING state And the secret is stored encrypted at rest (envelope encryption, KMS-managed key), never in plaintext And MFA is NOT yet active — an unfinished enrolment can never lock the user out" | Covered | FR-1 | — |
| MF-AC2 | "Given a pending enrolment When POST /v1/auth/mfa/activate is called with a valid 6-digit code Then respond 200 with 10 single-use recovery codes, shown exactly once And recovery codes are stored as Argon2id hashes, never in plaintext And users.mfa_enabled becomes true And an auth_audit_log entry is written (event=mfa_enabled)" | Covered | FR-2 | — |
| MF-AC3 | "Given a user with mfa_enabled = true who submits correct credentials When POST /v1/auth/login is called Then respond 200 with {\"mfa_required\": true, \"mfa_token\": \"...\"} and NO access or refresh token And the mfa_token is single-use, scoped to MFA verification only, with a 5-minute TTL And POST /v1/auth/mfa/verify with a valid code then completes the login exactly as LI-AC1" | Covered | FR-3 | LI-AC1's exact payload is out of this source's reach; spec correctly defers it to Open Questions instead of guessing |
| MF-AC4 | "Given a valid mfa_token When POST /v1/auth/mfa/verify is called with an incorrect code Then respond 401 with type \".../errors/mfa-invalid-code\" Given a code that was already accepted within its time step Then respond 401 as well, because each code is single-use (replay protection) And a ±1 time-step (30 s) skew window is accepted, no wider" | Covered | FR-4 | — |
| MF-AC5 | "Given 5 failed verification attempts against the same mfa_token When POST /v1/auth/mfa/verify is called again Then respond 429, the mfa_token is invalidated, and full re-authentication is required Because a 6-digit code has only 10^6 possibilities and must not be guessable online" | Covered | FR-5 | — |
| MF-AC6 | "Given a user holding the admin, auditor or support_agent role When DELETE /v1/auth/mfa is called Then respond 409 with type \".../errors/mfa-required-for-role\" And when such a role is granted to a user without MFA (US-3.2 MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes And during the 14-day rollout grace period login still succeeds, but each login warns the user and records the outstanding enrolment" | Covered | FR-6 | MR-AC1 mechanics and enrolment-token scope correctly deferred to Open Questions |
| MF-AC7 | "Given a user who has lost their authenticator device When POST /v1/auth/mfa/verify is called with a valid recovery code instead of a TOTP code Then login completes, that recovery code is consumed and can never be reused And the user is emailed a security notification and prompted to re-enrol" | Covered | FR-7 | — |

## Ambiguities & Non-Verifiable Statements

- **[Medium] TOTP algorithm parameters never stated in any FR** — Story's Assumptions & Defaults table, row 1: "Algorithm: RFC 6238 TOTP, SHA-1, 6 digits, 30-second step." No MF-AC restates the hash algorithm, and FR-1 only says the response contains "a TOTP secret (`otpauth://` URI + QR payload)" with no mention of SHA-1 or RFC 6238. A developer generating the `otpauth://` URI (which must encode `algorithm=SHA1` and `period=30` as query parameters for compatibility with authenticator apps) or implementing server-side code verification (FR-4/FR-5) cannot act on FR-1/FR-4 alone to know which HMAC hash to use — the digit count (6) and the 30-second step are each individually recoverable from FR-2 ("6-digit code") and FR-4 ("±1 time-step (30 s) skew window"), but the hash algorithm (SHA-1) appears nowhere in the Functional Requirements.
- **[Low] "QR payload" format is undefined** — FR-1 (and MF-AC1 verbatim): "a TOTP secret (`otpauth://` URI + QR payload)." Neither the story nor the spec defines what "QR payload" means as a wire format — a rendered image (PNG/SVG, base64-encoded?) versus simply expecting the client to render the `otpauth://` URI itself as a QR code. A developer implementing the `/v1/auth/mfa/enroll` response body cannot determine the exact JSON shape from this text alone.
- **[Medium] "warns the user" and "records the outstanding enrolment" have no defined mechanism** — FR-6 (and MF-AC6 verbatim): "During the 14-day rollout grace period, login still succeeds, but each login warns the user and records the outstanding enrolment." Neither the story nor the spec specifies the warning's delivery channel (a field in the login response? an email? a banner rendered client-side?) or what "records" means operationally (a log line, a counter, a specific column). A developer could not write a test against this sentence as written without first resolving those questions — and unlike the LI-AC1/MR-AC1/enrolment-scope gaps, the spec does not flag this one as an Open Question.

## Contradictions With Original Story

None found. Every FR's stated behavior, status code, and error type matches the corresponding AC exactly; the Non-Functional Requirements, Out of Scope, and Traceability Matrix sections are also verbatim-consistent with the story.

## Scope Creep

None found. All seven FRs derive directly from their cited MF-AC, the Non-Functional Requirements section reproduces the story's Non-Functional / Security Requirements section verbatim, and the Out of Scope section reproduces the story's Out of Scope list verbatim. No new endpoints, fields, systems, or behaviors are introduced beyond what the story states.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[High] Successful non-privileged MFA disable (`DELETE /v1/auth/mfa` → 204) has no FR** — The story's API Contract table lists `DELETE /v1/auth/mfa` with a `200`/`204` success response, and the Non-Functional Requirements state the auth precondition ("requires the current password and a valid code"), but no MF-AC narrates the success path's behavior (does `users.mfa_enabled` become `false`? is the secret/recovery codes purged? is an `auth_audit_log` event such as `mfa_disabled` — listed in the story's Data Model Notes — written?). Because no AC covers this, the spec has no FR for it either, and — unlike the other cross-references it correctly deferred — does not raise it as an Open Question. Given this is a fully documented endpoint in the story's own API Contract, this looks like a genuine gap worth flagging upstream rather than silently absorbing.
- **[Medium] Recovery code exhaustion is unaddressed** — MF-AC7 describes using one recovery code, but neither the story nor the spec addresses what happens when a user has consumed all 10 recovery codes and still cannot access their authenticator (e.g., is a support-mediated recovery path expected, or does the account become unrecoverable via self-service?). Does the story's scope intend this scenario to be handled by this story, or is it deliberately out of scope alongside WebAuthn/SMS?
- **[Low] Whether recovery-code failures count toward the MF-AC5 lockout counter is unspecified** — MF-AC5/FR-5 describe "5 failed verification attempts against the same mfa_token" without distinguishing TOTP-code attempts from recovery-code attempts submitted to the same `/v1/auth/mfa/verify` endpoint. Does a wrong recovery code increment the same failure counter as a wrong TOTP code?

## Verdict Rationale

Pass with Issues: AC coverage is complete (7/7 Covered) and no contradictions were found, so the spec is not blocked outright. However, one story-stated default (TOTP hash algorithm) is absent from every FR, two behavioral phrases ("warns the user," "records the outstanding enrolment") are carried through without being made verifiable or flagged as open, and the documented `DELETE /v1/auth/mfa` success path has no requirement coverage and no corresponding Open Question. These should be resolved before implementation begins on the enrolment and disable/rollout-warning paths.
