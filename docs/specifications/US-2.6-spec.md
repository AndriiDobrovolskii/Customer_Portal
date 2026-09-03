# Specification: Active Session Management

**Source:** docs/stories/US-2.6-active-sessions.md
**Story ID:** US-2.6
**Generated:** 2026-08-22
**Revised:** 2026-09-02 — incorporates OD-1–OD-4 (`docs/decisions/US-2.6-open-decisions.md`), the 3 precedent-resolved items from `docs/evidence/US-2.6-clarification-report.md`, and 2 findings from `docs/reviews/specifications/US-2.6-spec-review.md` (current-session identification mechanism, concurrent cap-eviction race), both resolved by the user 2026-09-02.
**Status:** Draft (revised)

## Summary

This spec covers self-service management of a user's active login sessions: listing every live session (refresh-token family) with recognisable, privacy-safe metadata, and revoking an individual session by its `family_id`, including the ownership, idempotency, and authentication rules that govern revocation.

## Background

As an authenticated user, I want to see every device currently signed in to my account and sign any of them out individually, so that I can spot and cut off access I do not recognise without logging myself out everywhere.

## Open Decision Resolutions (2026-09-02)

- **OD-1 (revoking the caller's own current session):** `DELETE /v1/auth/sessions/{family_id}` rejects with `409 Conflict` (type `.../errors/current-session`) when `family_id` matches the caller's own current family, rather than revoking it. Ending your only active session through this endpoint has no described use case — logout (US-2.2) already owns that.
- **OD-2 (live-session cap eviction):** When a new login would push a user's live-family count past 20, the system revokes the single oldest family (by its earliest surviving token's `issued_at`) via the same revocation write US-2.2's logout path uses, and writes an `auth_audit_log` entry (`event=session_evicted`, `target_family=<family_id>`) — distinct from `session_revoked` so an automatic eviction is distinguishable from an explicit user action. No notification email is sent.
- **OD-3 (device/browser label derivation):** The label is derived from the `User-Agent` header via the `user-agents` library, formatted as `"{browser family} on {OS family}"` (e.g. `"Chrome on Windows"`). When the header is missing or yields no recognizable browser/OS, the label is `"Unknown device"`.
- **OD-4 (geo-IP location mechanism):** Location is resolved via a locally bundled MaxMind GeoLite2-City database queried in-process — no live third-party network call. When the IP is private/loopback or has no database entry, the location fields are omitted/`null`; the request does not fail.
- **Precedent (metadata capture during rotation):** already implemented by US-2.3 — `RefreshToken` already carries `family_id`, `ip`, `user_agent`, `last_used_at`, `revoked_at`, and the refresh/rotation path already writes them on every rotation. This story adds no new capture logic or migration for these fields.
- **Precedent (`last_used_at` write strategy):** moot — it is written once per rotation (not per request), synchronously, in the same call as the existing rotation write. No separate async/throttle mechanism is needed.
- **Precedent (malformed/nonexistent `family_id` on DELETE):** treated identically to "belongs to a different user" (FR-3) — any `family_id` that doesn't resolve to a token the caller can act on, whether malformed or simply unknown, responds `404`.
- **Spec-review finding (current-session identification), accepted by user 2026-09-02:** the caller's "current" family (FR-1's `is_current`, FR-6's rejection) is identified by reading the optional `refresh_token` httponly cookie — the same cookie `/v1/auth/refresh` and `/v1/auth/logout` already read — hashing it, and matching it to a live `RefreshToken` row's `family_id`. No access-token JWT claim carries this today, and none is added. If the cookie is absent, expired, or matches no live token, no family is treated as "current" for that request: every entry's `is_current` is `false`, and FR-6 does not trigger (a `DELETE` against any of the caller's own families proceeds as FR-2's ordinary revoke). Not stated by the source story; resolved per `docs/reviews/specifications/US-2.6-spec-review.md`'s Ambiguities finding.
- **Spec-review finding (concurrent cap-eviction race), accepted by user 2026-09-02:** FR-7's family-count check and the eviction it triggers must be done under a row lock (`SELECT...FOR UPDATE`, or equivalent) on the user's live `RefreshToken` rows, so two logins racing concurrently cannot both observe a count of 20 and both skip eviction — mirroring the identical concurrency fix already applied for US-3.2's role-assignment race. Not stated by the source story; resolved per the same spec-review's Missing Edge Cases finding.

## Functional Requirements

### FR-1: Listing Active Sessions

Given an authenticated user, when `GET /v1/auth/sessions` is called, the system responds `200` with one entry per live refresh-token family, each entry containing `family_id`, `created_at`, `last_used_at`, an approximate location (city/country derived from IP via a local GeoLite2 database per OD-4, omitted when unresolvable), and a device/browser label (derived via the `user-agents` library per OD-3, formatted `"{browser} on {OS}"`, falling back to `"Unknown device"`), plus an `is_current` flag. The caller's current family is identified by reading the optional `refresh_token` cookie and matching its hash to a live token (per the spec-review resolution above); at most one entry is flagged `is_current` when that cookie identifies one of the returned families, and none is flagged when it doesn't. The response contains no token value, token hash, or full IP address.

**Derived from:** SM-AC1; label/location mechanism per OD-3/OD-4; current-session identification per spec-review resolution.

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

### FR-6: Revoking the Caller's Own Current Session Is Rejected

Given an authenticated user and a `family_id` matching the family identified via their `refresh_token` cookie (per FR-1's current-session mechanism), when `DELETE /v1/auth/sessions/{family_id}` is called, the system responds `409` with a `problem+json` body of type `.../errors/current-session`, rather than revoking it. No token in the caller's own family is affected. If no cookie is present or it identifies no live family, this rejection never triggers and the request is handled as an ordinary revoke (FR-2).

**Derived from:** Open Decision OD-1 (no AC; the story's Out of Scope section excludes "logout of the current session" but no AC states this endpoint's own behavior for that case); cookie-absent fallback per spec-review resolution.

### FR-7: Oldest Session Evicted Past the 20-Family Cap

Given a user who already has 20 live refresh-token families, when a new login creates a 21st family, the system revokes the single oldest pre-existing family (by its earliest surviving token's `issued_at`; the newly-created family is never itself eligible) via the same revocation path FR-2 uses, and writes an `auth_audit_log` entry (`event=session_evicted`, `target_family=<family_id>`). No notification email is sent for an eviction. The family count-and-evict check runs under a row lock on the user's live `RefreshToken` rows (per the spec-review resolution above), so concurrent logins for the same user cannot both bypass eviction and leave the cap transiently exceeded.

**Derived from:** Open Decision OD-2 (no AC; the story's Assumptions & Defaults table and Non-Functional Requirements state the 20-family cap but no AC describes eviction behavior); concurrency handling per spec-review resolution.

## Non-Functional Requirements

- IP address and user-agent are personal data: they must be documented in the privacy notice, the location must be displayed coarsened (city/country, not street-level), and session metadata must be purged 90 days after the session ends.
- Revoking a session must reuse US-2.2's revocation path, so exactly one code path ends a session.
- `last_used_at` is written synchronously at token rotation time (once per refresh, not per request) — already implemented by US-2.3; see Open Decision Resolutions.
- Performance: p95 latency ≤ 200 ms; sessions per user are bounded at 20 live families (eviction behavior per FR-7/OD-2).

**Derived from:** Non-Functional / Security Requirements section of the source; eviction mechanism per OD-2; `last_used_at` clarification per precedent.

## Out of Scope

- Logout of the current session and logout-everywhere (covered by US-2.2).
- Admin-facing visibility into another user's sessions (not currently required; would need its own permission and audit story).

**Derived from:** Out of Scope section of the source.

## Open Questions

None — all six items raised by the prior draft are resolved: three by the Open Decision Resolutions above (OD-1 own-session revocation, OD-2 cap eviction, OD-3 device/browser label), one by OD-4 (geo-IP mechanism, not raised by the prior draft but resolved alongside it), and two by precedent (metadata capture during rotation; the `last_used_at` write strategy). The malformed-`family_id` question is resolved by precedent (folds into FR-3's `404` path).

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| SM-AC1 | "Given an authenticated user with three live refresh-token families When GET /v1/auth/sessions is called Then respond 200 with one entry per family: family_id, created_at, last_used_at, approximate location (city/country from IP), a parsed device/browser label, and is_current And exactly one entry is flagged is_current, matching the caller's own family And no token value, hash or full IP address is returned" | FR-1 |
| SM-AC2 | "Given an authenticated user and a family_id belonging to another of their devices When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 and every token in that family is revoked (as in US-2.2 LO-AC1) And the caller's own session is unaffected And an auth_audit_log entry is written (event=session_revoked, target_family=…)" | FR-2 |
| SM-AC3 | "Given a family_id that belongs to a different user When DELETE /v1/auth/sessions/{family_id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm that the family_id exists" | FR-3 |
| SM-AC4 | "Given a family_id that is already revoked or has expired When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 — the operation is idempotent, mirroring LO-AC4" | FR-4 |
| SM-AC5 | "Given a request with no valid access token When GET /v1/auth/sessions is called Then respond 401 and no session metadata is disclosed" | FR-5 |

FR-6 and FR-7 have no source AC — both are wholly derived from Open Decisions (OD-1, OD-2) per this template's rule that a gap the source never specified is logged, not invented, until the user resolves it.
