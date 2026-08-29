# Spec Review: Refresh Token

**Original Story:** docs/stories/US-2.3-refresh-token.md
**Spec Reviewed:** docs/specifications/US-007-refresh-token-spec.md
**Story ID:** US-2.3 (source) / US-007 (spec)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All six Acceptance Criteria (RT-AC1–RT-AC6) from the original story are covered by the spec's Functional Requirements (FR-1–FR-7), with no contradictions and no scope creep detected. The spec correctly surfaces two genuine story-level gaps (refresh rate-limit behavior, mobile-client token delivery) as Open Questions rather than inventing requirements to fill them, which is the desired behavior. The verdict is "Pass with Issues" because two pieces of testable detail present in the source story — the RFC 7807 error envelope schema and the refresh cookie's `Path=/v1/auth` scoping constraint — were not carried into the spec's requirements, and one AC-inherited ambiguity ("indistinguishable" response) was not clarified.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| RT-AC1 | "Given a valid, unconsumed, unexpired refresh token When POST /v1/auth/refresh is called Then respond 200 with a new access token And a new refresh token is issued and set as the cookie (rotation) And the presented refresh token is marked consumed and can never be used again And the new token keeps the same family_id and the same absolute expiry as the original" | Covered | FR-1 | — |
| RT-AC2 | "Given a refresh token that was already consumed by a previous rotation When POST /v1/auth/refresh is called with it Then respond 401 with type '.../errors/token-invalid' And every token in that family is revoked immediately (the whole session chain is destroyed) And an auth_audit_log entry is written (event=refresh_reuse_detected, severity=high) And a security notification email is sent to the account owner" | Covered | FR-2 | — |
| RT-AC3 | "Given a refresh token that is expired, unknown, or was revoked by logout When POST /v1/auth/refresh is called Then respond 401 with type '.../errors/token-invalid' And no access token is issued And the response is indistinguishable between the three cases" | Covered | FR-3 | "Indistinguishable" is left undefined in both story and spec — see Ambiguities. |
| RT-AC4 | "Given a refresh token last used more than 14 days ago (idle timeout) When POST /v1/auth/refresh is called Then respond 401 and full re-authentication is required Given a token family created more than 30 days ago (absolute cap) When POST /v1/auth/refresh is called with any token in that family Then respond 401 regardless of recent activity" | Covered | FR-4, FR-5 | Story's single AC bundles two Given/When/Then clauses (idle timeout, absolute cap); spec splits them into two FRs, which is a faithful elaboration, not scope creep. |
| RT-AC5 | "Given the account was deactivated, or revoke_before:{user_id} is later than the token's issued-at When POST /v1/auth/refresh is called Then respond 401 and no new access token is issued # per US-1.4 DA-AC5" | Covered | FR-6 | — |
| RT-AC6 | "Given two parallel refresh requests carrying the same token (e.g. two browser tabs) When both reach the server Then exactly one succeeds; the check-and-consume runs as ONE atomic operation (a Valkey Lua script, or a conditional UPDATE ... WHERE consumed_at IS NULL RETURNING) And the loser receives 401 within a 10-second grace window WITHOUT the family being revoked Because a same-family retry inside the grace window is a race, not an attack" | Covered | FR-7 | — |

## Ambiguities & Non-Verifiable Statements

- **[Low] "Indistinguishable" response left undefined** — Spec says (FR-3): "the response is indistinguishable between the three cases (expired, unknown, revoked-by-logout)." This phrasing is carried over verbatim in substance from the story's RT-AC3 ("the response is indistinguishable between the three cases"), so the ambiguity originates in the source, not the spec. Neither document states which dimensions must match (status code only? identical response body bytes? identical response latency, to close a timing side-channel?). A QA engineer cannot write a precise conformance test from this wording alone. The spec had the opportunity to resolve this via an Open Question or a concrete definition and did not.

## Contradictions With Original Story

None found. Every FR's Given/When/Then wording, status codes, error `type` slug, and thresholds (14-day idle, 30-day absolute, 10-second grace window) match the story's ACs and Assumptions & Defaults table without conflict.

## Scope Creep

None found. FR-1–FR-7 map 1:1 (or 2:1 for RT-AC4) onto story ACs with no new fields, systems, or behaviors introduced. The Non-Functional Requirements and Out of Scope sections are direct restatements of the story's own sections. The spec's three Open Questions are gaps genuinely present in the story (grace-window validation, undefined rate-limit response, undefined mobile-client delivery mechanism) surfaced as questions rather than as invented requirements — this is correct handling, not creep.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] RFC 7807 error envelope schema not carried into the spec** — The story's "Error Envelope" section defines the exact `application/problem+json` response shape returned on the `401` paths referenced by RT-AC2, RT-AC3, RT-AC5 (fields `type`, `title`, `status`, `detail`, `instance`, with a concrete example). FR-2, FR-3, and FR-6 each state only the status code and the `type` slug ("respond 401 with type '.../errors/token-invalid'"); no section of the spec states that responses must conform to this envelope or lists its required fields. A developer implementing from the spec alone, without cross-referencing the story, would not know the full response body contract.
- **[Low-Medium] Refresh cookie's `Path=/v1/auth` scoping constraint omitted** — The story's Data Model Notes state: "The refresh endpoint is the only route that accepts the refresh cookie (`Path=/v1/auth`), limiting its exposure surface." This is a security-relevant constraint on how the rotated cookie from FR-1 ("issues a new refresh token and sets it as the cookie") must be scoped. It is not mentioned in FR-1 or in the spec's Non-Functional Requirements section, so nothing in the spec obliges an implementer to restrict the cookie's path, which could widen the token's exposure surface contrary to the story's stated intent.

## Verdict Rationale

Pass with Issues: AC coverage is complete (6/6 Covered) and no contradictions were found, so the spec is not blocked from a scope-fidelity standpoint. However, two testable pieces of the response/security contract documented in the source story (the RFC 7807 error envelope shape and the refresh cookie's path scoping) were not carried into the spec's requirements, and one inherited ambiguity ("indistinguishable" response) remains unresolved — these should be addressed before engineering treats the spec as complete.
