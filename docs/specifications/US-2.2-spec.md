# Specification: Logout

**Source:** docs/stories/US-2.2-logout.md
**Story ID:** US-2.2
**Generated:** 2026-08-22
**Revised:** 2026-08-31 (incorporates resolved Open Decisions OD-1–OD-6, `docs/decisions/US-2.2-open-decisions.md`, following us-clarifier's clarification pass against the now-implemented US-2.1 codebase); further revised 2026-08-31 for the spec review's lookup-miss finding (FR-1 refresh-cookie branch)
**Status:** Draft (SPEC_REVIEW Pass with Issues, accepted by user 2026-08-31 — see `docs/reviews/specifications/US-2.2-spec-review.md`)

## Summary

This spec covers session termination for authenticated users: ending the session on the current device only, ending every session for the account at once, server-side revocation of both access and refresh tokens for each case, idempotent behavior on a repeat logout, and rejection of unauthenticated logout requests and of requests that present an already-revoked access token.

## Background

As an authenticated user, I want to end my session on this device, or on all devices at once, so that nobody can continue using the portal as me after I walk away or lose a device.

## Open Decision Resolutions (OD-1–OD-6)

The 2026-08-22 version of this spec followed the story's literal design (a Valkey `jti_denylist:{jti}` key) and left two ambiguities open (LO-AC4/LO-AC5's contradiction, and the missing-refresh-cookie case). Clarification against the now-implemented US-2.1 codebase found the actual architecture already diverges from that design, and surfaced further gaps. All six were resolved by the user on 2026-08-31 and apply to every FR below:

- **Access-token revocation mechanism:** superseded. US-2.1 already built a Postgres `user_sessions` table (`jti` primary key, `issued_at`, `expires_at`, `revoked_at`), already checked by `UserService.get_authenticated_user` on every authenticated request. This story revokes by setting `revoked_at = now()` on that jti's row — no Valkey `jti_denylist` key is introduced. **Resolution source:** OD-1.
- **LO-AC4 vs. LO-AC5 (repeat-logout idempotency):** resolved as a logout-only carve-out. `POST /v1/auth/logout` specifically accepts a request whose jti is already revoked and still returns `204`; every other endpoint, including `POST /v1/auth/logout-all`, continues to reject a revoked jti with `401` per LO-AC5. **Resolution source:** OD-2.
- **`refresh_tokens` revocation:** the table has no `revoked_at` column and no lookup-by-hash method today (US-2.3, which would normally add this, has not been built yet). This story adds a minimal `revoked_at` column plus a token-hash lookup and family-revoke repository method, scoped only to what logout needs; single-use consumption tracking (`consumed_at`, rotation) remains US-2.3's responsibility. **Resolution source:** OD-3.
- **CSRF protection:** descoped from this story. No CSRF mechanism exists anywhere in the codebase (login was explicitly exempted and never needed to build one); building generic CSRF middleware is materially bigger than this story and is tracked as a separate follow-up. The story's CSRF requirement is not enforced by this implementation. **Resolution source:** OD-4.
- **`auth_audit_log` scope field:** the existing table has no `scope` column. This story adds a dedicated nullable `scope: String(32)` column, populated only on logout events (`session` / `all_sessions`) and left `null` on every other event type. **Resolution source:** OD-5.
- **Access token valid, refresh cookie absent:** treated as the happy path minus the cookie-specific side effects — the jti is still revoked, the audit entry (`scope=session`) is still written, and `204` is still returned; only the cookie-clear and refresh-family-revoke steps are skipped since there is no cookie to act on. **Resolution source:** OD-6.

## Functional Requirements

### FR-1: Logout on the Current Device

Given an authenticated user with a valid access token, when `POST /v1/auth/logout` is called, the system responds `204`; sets `revoked_at = now()` on the `user_sessions` row matching the access token's `jti` (per resolved OD-1); if a refresh cookie is present, resolves it to its `refresh_tokens` row by `token_hash`, and if a matching row is found, sets `revoked_at = now()` on every row sharing that row's `family_id` (per resolved OD-3); the refresh cookie is always cleared whenever it was present (`Set-Cookie` with `Max-Age=0`), regardless of whether its `token_hash` matched a row; and an `auth_audit_log` entry is written (`event=logout`, `scope=session`, per resolved OD-5).

If no refresh cookie is present, the cookie-clear and refresh-family-revocation steps are skipped; the jti is still revoked and the audit entry and `204` still occur (per resolved OD-6).

If a refresh cookie is present but its `token_hash` matches no `refresh_tokens` row (stale, tampered, or already-deleted), the family-revocation step is silently skipped — there is nothing to revoke — but the jti revocation, cookie-clear, audit entry, and `204` response all still occur exactly as in the matched case, so no response-level signal distinguishes a matched from an unmatched cookie (spec-review finding, resolved by the user 2026-08-31: preserves the story's anti-enumeration/idempotency intent).

**Derived from:** LO-AC1; revocation mechanism per resolved OD-1, OD-3; audit schema per resolved OD-5; missing-cookie branch per resolved OD-6; lookup-miss branch per spec-review finding, resolved 2026-08-31

### FR-2: Logout Everywhere

Given an authenticated user with active sessions on three devices, when `POST /v1/auth/logout-all` is called, the system responds `204`; sets `revoke_before:{user_id}` to now in Valkey (the existing `RevocationCache` mechanism from US-1.4/US-2.1); every access and refresh token issued before that moment is rejected with `401` on its next use; and an `auth_audit_log` entry is written (`event=logout`, `scope=all_sessions`, per resolved OD-5).

**Derived from:** LO-AC2; audit schema per resolved OD-5

### FR-3: Unauthenticated Logout Request Is Rejected

Given a request with no access token, or an expired/invalid one, when `POST /v1/auth/logout` is called, the system responds `401` and no session state is modified. This story introduces no new error `type` slugs; the `401` uses the shared unauthenticated `problem+json` envelope.

**Derived from:** LO-AC3

### FR-4: Idempotent Repeat Logout

Given an access token whose `user_sessions.revoked_at` was already set by a previous `POST /v1/auth/logout` call, when `POST /v1/auth/logout` is called again with that same access token, the system responds `204` (identical to the response in FR-1) — the operation is idempotent, no additional revocation side effects occur (the row is already revoked; the refresh cookie, if present, was already cleared), and no error is surfaced that would confirm the token's prior state. This leniency applies only to `POST /v1/auth/logout`; per resolved OD-2, no other endpoint — including `POST /v1/auth/logout-all` — accepts a revoked jti.

**Derived from:** LO-AC4; idempotency mechanism per resolved OD-2

### FR-5: Revoked Access Token Cannot Be Reused

Given a user who has just logged out, when any authenticated endpoint other than `POST /v1/auth/logout` is called with the pre-logout access token, the system responds `401` because the token's `user_sessions` row has `revoked_at` set (per resolved OD-1), regardless of the token's `exp` claim. This story introduces no new error `type` slugs; the `401` uses the shared unauthenticated `problem+json` envelope.

**Derived from:** LO-AC5; revocation mechanism per resolved OD-1; scope of the FR-4 carve-out per resolved OD-2

## Non-Functional Requirements

- Clearing the cookie client-side is not sufficient; server-side revocation is the acceptance criterion.
- Denylist entries must expire on their own so the store stays bounded without a cleanup job. Per resolved OD-1, this applies to the `revoke_before:{user_id}` Valkey key (already TTL-bounded, unchanged from US-1.4/US-2.1); `user_sessions.revoked_at` is a Postgres row and is not a self-expiring key, since the row already carries its own `expires_at`.
- The revocation check must add no more than 2 ms to the shared auth middleware. Per resolved OD-1, this is already satisfied: `user_sessions` lookup by `jti` is already an unconditional step in `get_authenticated_user` on every authenticated request today.
- CSRF protection is not enforced by this story. Per resolved OD-4, the story's original CSRF requirement is descoped — see Out of Scope.

**Derived from:** Non-Functional / Security Requirements section of the source; revocation-mechanism substitutions per resolved OD-1, OD-4.

## Out of Scope

- Per-device session listing and selective revocation (US-2.6).
- Account deactivation (US-1.4), which has its own revocation trigger.
- CSRF protection for this and other cookie-authenticated state-changing endpoints — no CSRF mechanism exists in the codebase today; tracked as a separate follow-up story rather than built here. Per resolved OD-4.
- Refresh-token single-use consumption tracking (`consumed_at`) and rotation — remains US-2.3's responsibility; this story adds only the minimal `revoked_at`/family-revoke capability it needs (OD-3).

**Derived from:** Out of Scope section of the source; CSRF and refresh-token-scope additions per resolved OD-4, OD-3.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| LO-AC1 | "Given an authenticated user with a valid access token and refresh cookie When POST /v1/auth/logout is called Then respond 204 And the presented refresh token is marked revoked (its whole rotation family, per US-2.3) And the access token's jti is added to a Valkey denylist with TTL = its remaining lifetime And the refresh cookie is cleared (Set-Cookie with Max-Age=0) And an auth_audit_log entry is written (event=logout, scope=session)" | FR-1 |
| LO-AC2 | "Given an authenticated user with active sessions on three devices When POST /v1/auth/logout-all is called Then respond 204 And revoke_before:{user_id} is set to now in Valkey And every access and refresh token issued before that moment is rejected on next use (401) And an auth_audit_log entry is written (event=logout, scope=all_sessions)" | FR-2 |
| LO-AC3 | "Given a request with no access token, or an expired/invalid one When POST /v1/auth/logout is called Then respond 401 And no session state is modified" | FR-3 |
| LO-AC4 | "Given a refresh token that was already revoked by a previous logout When POST /v1/auth/logout is called again with the same still-valid access token Then respond 204 (identical to LO-AC1) — the operation is idempotent And no additional revocation side effects occur And no error is surfaced that would confirm the token's prior state" | FR-4 |
| LO-AC5 | "Given a user who has just logged out When any authenticated endpoint is called with the pre-logout access token Then respond 401 Because the jti is on the denylist, regardless of the token's exp claim" | FR-5 |
