# Spec Review: Login

**Original Story:** docs/backlog/US-2.1-login.md
**Spec Reviewed:** docs/specifications/US-005-login-spec.md
**Story ID:** US-005 (spec's own Story ID field; the backlog story itself is filed as US-2.1)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All six Acceptance Criteria in US-2.1 (LI-AC1–LI-AC6) are fully and accurately covered by FR-1–FR-6 in the spec, with no contradictions and no scope creep — the FRs are faithful prose renderings of the Gherkin ACs. The spec's own Open Questions section is notably thorough, correctly flagging real inconsistencies (e.g. the mobile refresh-token transport, RS256/JWKS, and several audit-logging gaps) instead of silently resolving them. The issues found here are narrower: the spec never reproduces the concrete response/error JSON shapes or the `auth_audit_log` field list that the source defines elsewhere (API Contract table, Error Envelope section, Data Model Notes), leaving two requirements less precisely testable than the source material supports.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| LI-AC1 | "Given an active user whose email is verified When POST /v1/auth/login is called with the correct email and password Then respond 200 with an access token (JWT, 15-minute TTL) in the body And set a refresh token as an HttpOnly, Secure, SameSite=Strict cookie (Path=/v1/auth) And an auth_audit_log entry is written (event=login_succeeded) And users.last_login_at is updated" | Covered | FR-1 | Matches verbatim in substance. |
| LI-AC2 | "Given an active, verified user When POST /v1/auth/login is called with an incorrect password Then respond 401 with problem+json type \".../errors/invalid-credentials\" And no token of any kind is issued And an auth_audit_log entry is written (event=login_failed, reason=bad_password)" | Covered | FR-2 | Matches verbatim in substance. |
| LI-AC3 | "Given an email address that is not registered When POST /v1/auth/login is called with that email and any password Then respond 401 with the same body, status and comparable timing as LI-AC2 Because a dummy Argon2id verification is performed so response time does not reveal account existence" | Covered | FR-3 | Matches verbatim in substance. |
| LI-AC4 | "Given correct credentials are supplied When the account is unverified Then respond 403 with type \".../errors/email-not-verified\" ... When the account is deactivated Then respond 403 with type \".../errors/account-deactivated\" ... And in both cases credential verification runs first, so an attacker without the password only ever sees 401" | Covered | FR-4 | Both branches and the ordering guarantee are preserved. |
| LI-AC5 | "Given 10 failed login attempts for the same account within 15 minutes When POST /v1/auth/login is called again for that account Then respond 429 with a Retry-After header and type \".../errors/too-many-attempts\" And the same limit applies independently per source IP (20 attempts / 15 minutes) And a successful login resets the account counter" | Covered | FR-5 | Matches verbatim in substance. |
| LI-AC6 | "Given a request body missing \"password\", or containing an unknown field When POST /v1/auth/login is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names the offending field(s) And no login attempt is recorded against the rate-limit counter" | Covered | FR-6 | Matches verbatim in substance. |

## Ambiguities & Non-Verifiable Statements

- **[Medium] Concrete response/error JSON shapes not reproduced** — Spec says (FR-1): "the system responds `200` with an access token (JWT, 15-minute TTL) in the body" and (FR-2, similarly FR-3/FR-5/FR-6): "the system responds `401` with a `problem+json` body of type `.../errors/invalid-credentials`." The source's API Contract table states the exact success shape: `` `{"access_token": str, "token_type": "Bearer", "expires_in": 900}` `` (US-2.1-login.md, line 36), and the source's Error Envelope section (lines 104–113) states the full RFC 7807 shape (`type`, `title`, `status`, `detail`, `instance`) with a worked example. Neither the `token_type`/`expires_in` fields nor the full problem+json field set is carried into any FR or a dedicated schema section of the spec. A developer or QA engineer could not write an exact contract/schema test directly against the spec text as written — they would need to cross-reference the original story for the concrete field list.
- **[Low] `auth_audit_log` field composition not specified** — Spec says (FR-1): "writes an `auth_audit_log` entry (`event=login_succeeded`)"; FR-2 similarly specifies only `event=login_failed, reason=bad_password`. The source's Data Model Notes (line 40) define the full `auth_audit_log` schema as `event`, `reason`, `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at`, but the spec never states that these additional fields must be populated on each audit write. As worded, the spec is verifiable only on the `event`/`reason` values, not on the completeness of the audit record.

## Verdict Rationale

Pass with Issues: all six ACs are fully covered with no contradictions and no unsupported scope additions, so this does not rise to Fail. However, the two Ambiguity findings above mean a developer building strictly from this spec would need to go back to the original story to get exact response and audit-log schemas — worth tightening before implementation begins, though not blocking.
