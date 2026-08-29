# Spec Review: Logout

**Original Story:** docs/stories/US-2.2-logout.md
**Spec Reviewed:** docs/specifications/US-006-logout-spec.md
**Story ID:** US-006
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All five Acceptance Criteria (LO-AC1–LO-AC5) are covered by a corresponding Functional Requirement, and no direct contradiction between the spec and the story's stated business context was found. However, the spec surfaces (and correctly does not silently resolve) an internal tension already present in the source story: LO-AC4's expectation of a `204` on a repeat logout with "the same still-valid access token" is difficult to reconcile with LO-AC5's rule that any request bearing a pre-logout, denylisted access token gets `401`. Because that tension makes FR-4/FR-5 non-verifiable as written until the source is clarified, and because the spec silently drops the story's Data Model Notes (specifically the `jti_denylist:{jti}` key-naming convention), the verdict is Pass with Issues rather than a clean Pass.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| LO-AC1 | "Given an authenticated user with a valid access token and refresh cookie When POST /v1/auth/logout is called Then respond 204 And the presented refresh token is marked revoked (its whole rotation family, per US-2.3) And the access token's jti is added to a Valkey denylist with TTL = its remaining lifetime And the refresh cookie is cleared (Set-Cookie with Max-Age=0) And an auth_audit_log entry is written (event=logout, scope=session)" | Covered | FR-1 | — |
| LO-AC2 | "Given an authenticated user with active sessions on three devices When POST /v1/auth/logout-all is called Then respond 204 And revoke_before:{user_id} is set to now in Valkey And every access and refresh token issued before that moment is rejected on next use (401) And an auth_audit_log entry is written (event=logout, scope=all_sessions)" | Covered | FR-2 | — |
| LO-AC3 | "Given a request with no access token, or an expired/invalid one When POST /v1/auth/logout is called Then respond 401 And no session state is modified" | Covered | FR-3 | — |
| LO-AC4 | "Given a refresh token that was already revoked by a previous logout When POST /v1/auth/logout is called again with the same still-valid access token Then respond 204 (identical to LO-AC1) — the operation is idempotent And no additional revocation side effects occur And no error is surfaced that would confirm the token's prior state" | Covered | FR-4 | Text is a faithful reproduction of LO-AC4, but see Ambiguity #1 — as written, LO-AC4 is difficult to reconcile with LO-AC5 |
| LO-AC5 | "Given a user who has just logged out When any authenticated endpoint is called with the pre-logout access token Then respond 401 Because the jti is on the denylist, regardless of the token's exp claim" | Covered | FR-5 | See Ambiguity #1 |

## Ambiguities & Non-Verifiable Statements

- **[High] LO-AC4 vs. LO-AC5: repeat-logout token state is unresolved** — Spec (FR-4) says: "Given a refresh token that was already revoked by a previous logout, when `POST /v1/auth/logout` is called again with the same still-valid access token, the system responds `204`..." Spec (FR-5) says: "Given a user who has just logged out, when any authenticated endpoint is called with the pre-logout access token, the system responds `401` because the token's `jti` is on the denylist..." Per LO-AC1/FR-1, the *first* logout call already adds that same access token's `jti` to the denylist. `POST /v1/auth/logout` is itself an authenticated endpoint, so FR-5's "any authenticated endpoint" would seem to include the repeat logout call in FR-4, which conflicts with FR-4's requirement to return `204`. As written, a developer cannot implement both FR-4 and FR-5 without first knowing which token FR-4's "same still-valid access token" actually refers to (e.g., a second, not-yet-denylisted access token from a separate login, vs. the literal first-call token). This defect originates in the source story itself (LO-AC4 vs. LO-AC5), not something the spec introduced — and the spec's own Open Questions section already flags it accurately, using nearly the same reasoning. It is listed here because it still leaves FR-4 non-verifiable as currently stated, which should block implementation of that specific requirement until the source is clarified.

- **[Low-Medium] Denylist key-naming convention dropped from the spec** — Story (Data Model Notes) says: "Valkey `jti_denylist:{jti}` — value irrelevant, TTL = `exp − now`." Spec (FR-1) says only: "adds the access token's `jti` to a Valkey denylist with TTL equal to its remaining lifetime" — it never names the `jti_denylist:{jti}` key pattern. The spec has no Data Model section at all, whereas the sibling `revoke_before:{user_id}` key name from the same story section *is* carried into FR-2 verbatim. A developer implementing FR-1 from the spec alone would have to invent a key-naming scheme rather than use the one the story specifies, which risks divergence from the schema `revoke_before:{user_id}` (US-1.4) and future code expect to interoperate with.

## Contradictions With Original Story

None found. (The FR-4/FR-5 tension above is an ambiguity inherited from the story's own two ACs, not a case of the spec asserting something the story doesn't — the spec's Traceability Matrix quotes both ACs verbatim and unmodified.)

## Scope Creep

None found. Every Functional Requirement, the Non-Functional Requirements, and the Out of Scope section trace directly to corresponding story content (ACs, the Non-Functional / Security Requirements section, and the Out of Scope section respectively). No new fields, endpoints, or systems were introduced.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Access token valid but refresh cookie absent** — LO-AC1's Given clause presumes "a valid access token and refresh cookie" together; neither the story nor the spec states what happens on `POST /v1/auth/logout` when the access token is valid but no refresh cookie is present (e.g., already cleared, or a non-browser client). Does LO-AC3's "expired/invalid" case apply here, or is this undefined? Since the source story itself doesn't address this combination, it's flagged as an open question rather than a spec defect.

- **[Low] CSRF validation failure behavior** — Story (Non-Functional / Security Requirements) says: "Logout is a state-changing, cookie-authenticated call → CSRF token required." Neither the story nor the spec (which reproduces this NFR verbatim) defines the response when the CSRF token is missing or invalid. This may be intentionally out of scope because it's handled by shared cross-cutting middleware rather than logout-specific logic — flagging as a question rather than asserting a gap, since the story gives no indication this story is meant to define that behavior itself.

## Verdict Rationale

Pass with Issues: AC coverage is complete (5/5 Covered) and no spec-vs-story contradiction was found, so this does not meet the Fail bar. However, one High-severity Ambiguity (FR-4/FR-5's unresolved interaction, inherited from LO-AC4/LO-AC5) leaves a requirement non-verifiable as written, and a Low-Medium completeness gap (the dropped `jti_denylist:{jti}` key convention) plus two Low-severity open questions about edge cases remain. Recommend resolving the LO-AC4/LO-AC5 tension with the story owner before implementation begins, since it affects testable behavior of the logout endpoint's idempotency guarantee.
