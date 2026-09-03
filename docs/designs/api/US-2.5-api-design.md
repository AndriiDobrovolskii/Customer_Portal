# API Design: Multi-Factor Authentication / TOTP (US-2.5 / spec US-2.5)

**Source spec:** docs/specifications/US-2.5-spec.md
**Spec review:** docs/reviews/specifications/US-2.5-spec-review.md (Pass with Issues, resolved 2026-09-01)
**OpenAPI fragment:** docs/designs/api/US-2.5-openapi.yaml

## New Endpoints

### `POST /v1/auth/mfa/enroll`

Begins (or restarts — OD-11) a PENDING TOTP enrolment (FR-1). Requires a valid access token plus re-proving `current_password` in the body. Returns `{"secret", "otpauth_uri"}` — no third QR-image field (OD-3). The secret is AES-GCM-encrypted at rest (OD-2) and never returned again after this call.

### `POST /v1/auth/mfa/activate`

Completes enrolment with a valid 6-digit code (FR-2). Returns 10 recovery codes shown exactly once. This is also the exit point for both enrolment-scoped-token triggers (FR-6's privileged-role grant, FR-7's recovery-code use): if either condition put the account in a scoped state, activation clears it and sets `perm_epoch:{user_id}`, so the next authenticated call responds `401 token-stale` until the caller refreshes.

### `POST /v1/auth/mfa/verify`

Completes a login challenge (FR-3/FR-4/FR-5/FR-7). Uses a distinct auth scheme (`mfaTokenAuth`) from every other authenticated endpoint in this project — the `mfa_token` from `POST /v1/auth/login`'s challenge branch, not a normal bearer access token; a normal access token must not be accepted here. Accepts either a 6-digit TOTP code or a recovery code in the same `code` field (FR-7); both count toward the same 5-attempt lockout (OD-10). Success returns the identical shape `POST /v1/auth/login` returns on a non-MFA login (LI-AC1), including the `refresh_token` cookie.

### `DELETE /v1/auth/mfa`

Self-service disable, requiring both `current_password` and a valid code (constant-time comparison, per the spec's Non-Functional Requirements). Two outcomes: `409 mfa-required-for-role` for `admin`/`auditor`/`support_agent` (FR-6), or `204` for everyone else (FR-8) — `mfa_enabled → false`, secret nulled, recovery codes deleted, `mfa_disabled` audited, `revoke_before` set (every other session ends).

## Extension to Existing Endpoints (not redefined here — see their own story's contract)

- **`POST /v1/auth/login`** (US-2.1/US-2.1): gains the `mfa_required`/`mfa_token` branch (FR-3) as an alternate `200` body shape, and — independently — the enrolment-scoped-token behavior (FR-6): if the account holds a privileged role with `mfa_enabled = false`, the issued access token is enrolment-scoped, and a login response field carries the outstanding-enrolment deadline during the 14-day grace period (OD-4). This is additive to `LoginResponse`, not a breaking change to its existing fields.
- **`POST /v1/auth/refresh`** (US-2.3/US-2.3): re-evaluates the same enrolment-scoping condition on every call (per the spec-review resolution), so a refreshed access token stays scoped if the underlying condition still holds. Additive to `RefreshResponse`.

## Cross-Cutting Patterns Reused, Not Invented

- `401 unauthorized` for a missing/invalid access token is the same pattern every authenticated endpoint in this project uses.
- `429 too-many-attempts` (FR-5) reuses the slug US-2.1's login lockout already established — not a new one.
- The enrolment-scoped-token rejection reuses US-3.2's `token-stale` slug (already the response for a `perm_epoch`-invalidated access token), since both describe the same underlying situation: an access token whose claims no longer reflect the account's current state.
- `revoke_before`/`perm_epoch` writes (FR-8, FR-2) follow the exact same Valkey-key mechanics US-3.2 and password-reset/deactivation already use — no new revocation primitive.

## Open Questions Not Resolved by the Spec (deferred to PLANNING, not decided here)

1. **`POST /v1/auth/mfa/activate`'s `401` doesn't distinguish "wrong code" from "no PENDING enrolment exists at all."** The spec's FR-2 only describes the success path; whether calling `activate` with no prior `enroll` call should be a distinct error (e.g. `404`/`409`) or fold into the same generic `401` is not stated. The contract currently uses one shape for both.
2. **Does `DELETE /v1/auth/mfa` accept a recovery code in place of a TOTP code?** FR-8/the source's Non-Functional Requirements say "current password and a valid code" without specifying whether "code" here means TOTP-only or also accepts a recovery code, the way `verify` does (FR-7).
3. **Check-precedence on `DELETE /v1/auth/mfa` when a privileged-role caller also submits a wrong password/code.** The contract lists `401` and `409` as independent branches but doesn't state which check runs first — does an incorrect password on a privileged account return `401` (normal auth failure) or does the `409` role-block short-circuit before password verification even happens? This has a security dimension (whether an unauthenticated-but-role-aware caller can learn role-privilege status without proving the password first) worth resolving explicitly at PLANNING.
4. **Exact field name and shape for the grace-period warning** (OD-4) on `LoginResponse`/`RefreshResponse` — the spec says "a field recording the outstanding-enrolment deadline" but doesn't name it; this design assumes something like `mfa_enrollment_deadline` but the exact name/type is a PLANNING/schema-builder decision, not fixed here.
