# Specification: Logout

**Source:** docs/backlog/US-2.2-logout.md
**Story ID:** US-006
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-006-spec-review.md)

## Summary

This spec covers session termination for authenticated users: ending the session on the current device only, ending every session for the account at once, server-side revocation of both access and refresh tokens for each case, idempotent behavior on a repeat logout, and rejection of unauthenticated logout requests and of requests that present an already-revoked access token.

## Background

As an authenticated user, I want to end my session on this device, or on all devices at once, so that nobody can continue using the portal as me after I walk away or lose a device.

## Functional Requirements

### FR-1: Logout on the Current Device

Given an authenticated user with a valid access token and refresh cookie, when `POST /v1/auth/logout` is called, the system responds `204`; marks the presented refresh token revoked, including its whole rotation family (per US-2.3); adds the access token's `jti` to a Valkey denylist (key `jti_denylist:{jti}`) with TTL equal to its remaining lifetime; clears the refresh cookie (`Set-Cookie` with `Max-Age=0`); and writes an `auth_audit_log` entry (`event=logout`, `scope=session`).

**Derived from:** LO-AC1

### FR-2: Logout Everywhere

Given an authenticated user with active sessions on three devices, when `POST /v1/auth/logout-all` is called, the system responds `204`; sets `revoke_before:{user_id}` to now in Valkey; every access and refresh token issued before that moment is rejected with `401` on its next use; and an `auth_audit_log` entry is written (`event=logout`, `scope=all_sessions`).

**Derived from:** LO-AC2

### FR-3: Unauthenticated Logout Request Is Rejected

Given a request with no access token, or an expired/invalid one, when `POST /v1/auth/logout` is called, the system responds `401` and no session state is modified. This story introduces no new error `type` slugs; the `401` uses the shared unauthenticated `problem+json` envelope.

**Derived from:** LO-AC3

### FR-4: Idempotent Repeat Logout

Given a refresh token that was already revoked by a previous logout, when `POST /v1/auth/logout` is called again with the same still-valid access token, the system responds `204` (identical to the response in FR-1) — the operation is idempotent, no additional revocation side effects occur, and no error is surfaced that would confirm the token's prior state.

**Derived from:** LO-AC4

### FR-5: Revoked Access Token Cannot Be Reused

Given a user who has just logged out, when any authenticated endpoint is called with the pre-logout access token, the system responds `401` because the token's `jti` is on the denylist, regardless of the token's `exp` claim. This story introduces no new error `type` slugs; the `401` uses the shared unauthenticated `problem+json` envelope.

**Derived from:** LO-AC5

## Non-Functional Requirements

- Clearing the cookie client-side is not sufficient; server-side revocation is the acceptance criterion.
- Logout is a state-changing, cookie-authenticated call, so a CSRF token is required.
- Denylist entries (`jti_denylist:{jti}`) must expire on their own (TTL = `exp − now`) so the store stays bounded without a cleanup job.
- The denylist lookup must add no more than 2 ms to the shared auth middleware; it should be combined with the `revoke_before` check in a single Valkey round trip.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Per-device session listing and selective revocation (US-2.6).
- Account deactivation (US-1.4), which has its own revocation trigger.

**Derived from:** Out of Scope section of the source.

## Open Questions

The source's own Open Questions section states "None." The item below is a spec-author finding raised while formalizing LO-AC4 against LO-AC1 and LO-AC5, not something copied from the source.

- LO-AC4 describes a repeat `POST /v1/auth/logout` call authenticated with "the same still-valid access token" used in the prior logout call. But LO-AC1 states that the first logout call already adds that same access token's `jti` to the Valkey denylist, and LO-AC5 states that any request presenting a pre-logout access token is rejected with `401` because its `jti` is on the denylist. It is not clear how LO-AC4's expectation of a `204` response on that same access token is reconciled with LO-AC5's denylist rejection — for example, whether LO-AC4 assumes a different, not-yet-denylisted access token is actually used for the repeat call, or whether the denylist check is meant to be bypassed specifically for the logout endpoint. Please clarify which reading is intended before implementation.
- LO-AC1's Given clause presumes "a valid access token and refresh cookie" together; neither the story nor this spec states what happens on `POST /v1/auth/logout` when the access token is valid but no refresh cookie is present (e.g., already cleared, or a non-browser client). Does LO-AC3's "expired/invalid" case apply here, or is this undefined?
- The Non-Functional / Security Requirements state logout requires a CSRF token, but neither the story nor this spec defines the response when the CSRF token is missing or invalid. This may be handled by shared cross-cutting middleware rather than logout-specific logic; please confirm.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| LO-AC1 | "Given an authenticated user with a valid access token and refresh cookie When POST /v1/auth/logout is called Then respond 204 And the presented refresh token is marked revoked (its whole rotation family, per US-2.3) And the access token's jti is added to a Valkey denylist with TTL = its remaining lifetime And the refresh cookie is cleared (Set-Cookie with Max-Age=0) And an auth_audit_log entry is written (event=logout, scope=session)" | FR-1 |
| LO-AC2 | "Given an authenticated user with active sessions on three devices When POST /v1/auth/logout-all is called Then respond 204 And revoke_before:{user_id} is set to now in Valkey And every access and refresh token issued before that moment is rejected on next use (401) And an auth_audit_log entry is written (event=logout, scope=all_sessions)" | FR-2 |
| LO-AC3 | "Given a request with no access token, or an expired/invalid one When POST /v1/auth/logout is called Then respond 401 And no session state is modified" | FR-3 |
| LO-AC4 | "Given a refresh token that was already revoked by a previous logout When POST /v1/auth/logout is called again with the same still-valid access token Then respond 204 (identical to LO-AC1) — the operation is idempotent And no additional revocation side effects occur And no error is surfaced that would confirm the token's prior state" | FR-4; see Open Question |
| LO-AC5 | "Given a user who has just logged out When any authenticated endpoint is called with the pre-logout access token Then respond 401 Because the jti is on the denylist, regardless of the token's exp claim" | FR-5 |
