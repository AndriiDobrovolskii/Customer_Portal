# Specification: Active Session Management

**Source:** docs/stories/US-2.6-active-sessions.md
**Story ID:** US-010
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/specifications/US-010-spec-review.md)

## Summary

This spec covers self-service management of a user's active login sessions: listing every live session (refresh-token family) with recognisable, privacy-safe metadata, and revoking an individual session by its `family_id`, including the ownership, idempotency, and authentication rules that govern revocation.

## Background

As an authenticated user, I want to see every device currently signed in to my account and sign any of them out individually, so that I can spot and cut off access I do not recognise without logging myself out everywhere.

## Functional Requirements

### FR-1: Listing Active Sessions

Given an authenticated user, when `GET /v1/auth/sessions` is called, the system responds `200` with one entry per live refresh-token family, each entry containing `family_id`, `created_at`, `last_used_at`, an approximate location (city/country derived from IP), and a parsed device/browser label, plus an `is_current` flag. Exactly one entry is flagged `is_current`, matching the caller's own family. The response contains no token value, token hash, or full IP address.

**Derived from:** SM-AC1

### FR-2: Revoking One Session

Given an authenticated user and a `family_id` belonging to another of their own devices, when `DELETE /v1/auth/sessions/{family_id}` is called, the system responds `204`, revokes every token in that family (as in US-2.2's LO-AC1), leaves the caller's own session unaffected, and writes an `auth_audit_log` entry (`event=session_revoked`, `target_family=<family_id>`).

**Derived from:** SM-AC2

### FR-3: Revoking Another User's Session Returns 404

Given a `family_id` that belongs to a different user, when `DELETE /v1/auth/sessions/{family_id}` is called, the system responds `404` with a `problem+json` body of type `.../errors/not-found`, rather than `403`, because a `403` would confirm that the `family_id` exists.

**Derived from:** SM-AC3

### FR-4: Revoking an Already-Revoked or Expired Session Is Idempotent

Given a `family_id` that is already revoked or has expired, when `DELETE /v1/auth/sessions/{family_id}` is called, the system responds `204`. This operation is idempotent, mirroring US-2.2's LO-AC4 behavior.

**Derived from:** SM-AC4

### FR-5: Unauthenticated Requests Are Rejected

Given a request with no valid access token, when `GET /v1/auth/sessions` is called, the system responds `401` and discloses no session metadata.

**Derived from:** SM-AC5

## Non-Functional Requirements

- IP address and user-agent are personal data: they must be documented in the privacy notice, the location must be displayed coarsened (city/country, not street-level), and session metadata must be purged 90 days after the session ends.
- Revoking a session must reuse US-2.2's revocation path, so exactly one code path ends a session.
- `last_used_at` should be written asynchronously, or throttled to once per minute, to keep the refresh path fast.
- Performance: p95 latency ≤ 200 ms; sessions per user are bounded at 20 live families.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Logout of the current session and logout-everywhere (covered by US-2.2).
- Admin-facing visibility into another user's sessions (not currently required; would need its own permission and audit story).

**Derived from:** Out of Scope section of the source.

## Open Questions

- The Assumptions & Defaults table sets a live-session cap of "20 families per user, oldest evicted," and the Non-Functional Requirements repeat the 20-family bound, but no Acceptance Criterion describes what happens when the cap is exceeded (e.g., is the oldest family's session revoked the same way as manual revocation, is an `auth_audit_log` entry written for it, does the evicted device receive any signal). Should eviction behavior be specified as its own Acceptance Criterion?
- The In Scope section lists "Capture and update of session metadata during rotation" as part of this story, but no Acceptance Criterion describes the expected behavior for it (which fields are captured or updated, on what trigger, and how errors are handled). Is this fully specified elsewhere (e.g., in US-2.3), or does it need its own Acceptance Criterion here?
- SM-AC1 requires "a parsed device/browser label" in the session listing but does not define how the label is derived from the user-agent string or what value (if any) is returned when the user-agent cannot be parsed. What is the expected format and fallback behavior for the device/browser label?
- SM-AC2/FR-2 scope the happy path to "a `family_id` belonging to another of their own devices," and the Out of Scope section excludes "Logout of the current session." No Acceptance Criterion states what `DELETE /v1/auth/sessions/{family_id}` should do when the caller passes their own current `family_id` — does it fall through to FR-2's 204/revoke behavior, get rejected with a distinct error, or something else?
- The Non-Functional Requirements state `last_used_at` "should be written asynchronously, or throttled to once per minute" — two divergent strategies offered without specifying which governs, or what the throttle window (if used) is scoped to (per family, per user, globally). Which strategy is intended?
- SM-AC3 and SM-AC4 cover a `family_id` belonging to a different user, and one that is already revoked or expired, respectively. Neither states the response for a syntactically invalid `family_id` that matches no record at all — does this fall under the same `404` path as SM-AC3, or does it warrant separate handling (e.g. `400`)?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| SM-AC1 | "Given an authenticated user with three live refresh-token families When GET /v1/auth/sessions is called Then respond 200 with one entry per family: family_id, created_at, last_used_at, approximate location (city/country from IP), a parsed device/browser label, and is_current And exactly one entry is flagged is_current, matching the caller's own family And no token value, hash or full IP address is returned" | FR-1 |
| SM-AC2 | "Given an authenticated user and a family_id belonging to another of their devices When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 and every token in that family is revoked (as in US-2.2 LO-AC1) And the caller's own session is unaffected And an auth_audit_log entry is written (event=session_revoked, target_family=…)" | FR-2 |
| SM-AC3 | "Given a family_id that belongs to a different user When DELETE /v1/auth/sessions/{family_id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm that the family_id exists" | FR-3 |
| SM-AC4 | "Given a family_id that is already revoked or has expired When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 — the operation is idempotent, mirroring LO-AC4" | FR-4 |
| SM-AC5 | "Given a request with no valid access token When GET /v1/auth/sessions is called Then respond 401 and no session metadata is disclosed" | FR-5 |
