# Spec Review: Verify Email

**Original Story:** docs/backlog/US-1.2-verify-email.md
**Spec Reviewed:** docs/specifications/US-002-verify-email-spec.md
**Story ID:** US-002
**Reviewed:** 2026-08-15
**Overall Verdict:** Pass

## Summary

The spec was re-reviewed after all three prior Missing Edge Case findings and the source's own Open Questions were resolved via an explicit "Clarifications & Decisions" section (concurrent token consumption, malformed/missing resend email, resend email case sensitivity, the expired-vs-invalid response split, the 7-day purge window, out-of-scope hourly/IP rate limits, and the generic resend body shape). All 10 ACs remain fully covered, no contradictions were found, and no requirement is left non-verifiable. The spec now carries seven resolutions that go beyond what the source story literally states — these are disclosed and traceable to documented stakeholder decisions rather than silently invented, so they are noted below as disclosed scope additions rather than defects.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| VE-AC1 | "Given an unverified user with a valid, unconsumed, unexpired token When POST /v1/auth/verify-email is called with the raw token Then respond 200 And users.email_verified is set to true And the token's consumed_at is set (single-use enforced; reuse fails per VE-AC3)" | Covered | FR-1 | Concurrency now addressed — see Clarification #1 |
| VE-AC2 | "Given a token whose expires_at has passed When POST /v1/auth/verify-email is called with that token Then respond 400 with problem+json type '.../errors/token-expired' And email_verified remains false" | Covered | FR-2 | Distinctness confirmed — see Clarification #4 |
| VE-AC3 | "Given a token that was already consumed When POST /v1/auth/verify-email is called with that token again Then respond 400 with problem+json type '.../errors/token-invalid'" | Covered | FR-3 | — |
| VE-AC4 | "Given a token string that does not match any stored hash When POST /v1/auth/verify-email is called with that token Then respond 400 with problem+json type '.../errors/token-invalid'" | Covered | FR-4 | — |
| VE-AC5 | "Given a user whose email_verified is false When POST /v1/auth/login is called with correct credentials Then respond 403 with problem+json type '.../errors/email-not-verified' And no session or JWT is issued" | Covered | FR-5 | — |
| VE-AC6 | "Given a user whose email_verified is true When POST /v1/auth/login is called with correct credentials Then respond 200 with a valid session/JWT" | Covered | FR-6 | — |
| VE-AC7 | "Given a user requested a verification email less than 60 seconds ago When POST /v1/auth/verify-email/resend is called for the same account Then respond 429 with a Retry-After header" | Covered | FR-7 | Case sensitivity now defined — see Clarification #3 |
| VE-AC8 | "Given an email address that is not registered When POST /v1/auth/verify-email/resend is called Then respond 200 with the same generic body, status code, and comparable timing as for a registered, unverified account" | Covered | FR-8 | Body shape and malformed-input handling now defined — see Clarifications #2, #7 |
| VE-AC9 | "Given an email address belonging to an already-verified account When POST /v1/auth/verify-email/resend is called Then respond 200 with the same generic body as VE-AC8 (no email is sent, but the response does not reveal this)" | Covered | FR-9 | — |
| VE-AC10 | "Given a user account created more than 7 days ago with email_verified = false When the scheduled purge job runs Then the account and its verification tokens are deleted And a record is written to the audit log noting an automatic purge" | Covered | FR-10 | 7-day window confirmed — see Clarification #5 |

## Ambiguities & Non-Verifiable Statements

None found. All previously flagged gaps (concurrency, malformed input, case sensitivity, response body shape) are now resolved with concrete, testable definitions in FR-1, FR-3, FR-7, FR-8, and FR-9.

## Contradictions With Original Story

None found.

## Scope Additions (Disclosed)

The spec's "Clarifications & Decisions" section adds behavior not stated in the source story's ACs. These are explicitly disclosed as stakeholder decisions (not presented as if derived from the ACs), so they are noted here for visibility rather than as defects:

- **Data-layer atomicity for token consumption (FR-1)** — VE-AC1/VE-AC3 don't mention concurrent requests; the spec now requires enforcement via an atomic conditional update. Disclosed in Clarification #1.
- **400 response for malformed/missing resend email (FR-8)** — Not addressed by VE-AC7–VE-AC9; the spec now specifies a validation error path. Disclosed in Clarification #2.
- **Case-insensitive email matching on resend (FR-7, FR-8)** — Not addressed by any AC; the spec now requires case-insensitive lookup, consistent with the precedent set for registration in US-001. Disclosed in Clarification #3.
- **Concrete generic resend response body (FR-8, FR-9)** — VE-AC8/VE-AC9 require an identical body but don't define its contents; the spec now specifies a fixed JSON shape. Disclosed in Clarification #7.

None of these contradict the story; they fill gaps the story left open. Recommend confirming with the original story author/product owner that these decisions are acceptable, since they were made outside the story document itself. Clarifications #4, #5, and #6 confirm existing source defaults or explicitly defer out-of-scope items rather than adding new behavior, so they are not scope additions.

## Missing Edge Cases, Boundary Conditions & Error Handling

None remaining. The three edge cases flagged in the prior review (concurrent token consumption, malformed resend input, email case sensitivity) are now addressed in FR-1/FR-3, FR-8, and FR-7/FR-8 respectively.

## Verdict Rationale

Pass: AC coverage is complete (10/10 Covered), no contradictions were found, and no ambiguous or non-verifiable statements remain — the three previously open Missing Edge Case findings, plus the source's own Open Questions, are now resolved with concrete, testable definitions. The disclosed scope additions are transparently documented as stakeholder decisions rather than silent invention, so they do not block the verdict, though confirming them with the story owner before implementation is advisable.
