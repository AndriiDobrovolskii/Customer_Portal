# Spec Review: Register User

**Original Story:** docs/specifications/US-001 Register User.md
**Spec Reviewed:** docs/specifications/US-001-register-user.md
**Story ID:** US-001
**Reviewed:** 2026-08-15
**Overall Verdict:** Pass

## Summary

The spec was re-reviewed after all five prior Open Questions were resolved via an explicit "Clarifications & Decisions" section (validation error schema, password special-character set, the AC-1/AC-5 cross-reference mislabel, concurrent duplicate registration, and email whitespace trimming). All six ACs remain fully covered, no contradictions were found, and no requirement is left non-verifiable. The spec now carries five resolutions that go beyond what the source story literally states — these are disclosed and traceable to documented stakeholder decisions rather than silently invented, so they are noted below as disclosed scope additions rather than defects.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AC-1  | "Given a Visitor submits a valid, unregistered email and password, When the registration request is processed, Then the system creates the user account and returns `HTTP 201 Created` with: - A `Location` header pointing to the created user resource (e.g., `/api/v1/users/{id}`). - A JSON response body containing non-sensitive user metadata: ... - The response payload **must never** contain the password or password hash (per AC-5)." | Covered | FR-1, FR-6 | AC-1's "(per AC-5)" reference is addressed — see FR-6 note and Clarification #1 |
| AC-2  | "Given an email address is already registered in the system (e.g., `user@example.com`), When a Visitor attempts to register using the same email with any combination of letter cases (e.g., `User@Example.com` or `USER@EXAMPLE.COM`), Then the system treats the emails as identical, rejects the request, and returns `HTTP 409 Conflict`." | Covered | FR-2 | — |
| AC-3  | "Given an email address that is missing, empty, or does not conform to standard RFC 5322 format, When a Visitor submits the registration request, Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details." | Covered | FR-3 | Error schema now defined — see Validation Error Schema section |
| AC-4  | "Given a password that does not meet the password policy (minimum 8 characters, containing at least 1 uppercase, 1 lowercase, 1 digit, and 1 special character (e.g., @, #, $, %, !)), When a Visitor submits the registration request, Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details." | Covered | FR-4 | Special-character set now defined — see below |
| AC-5  | "Given a registration request where the password field is missing or empty, When a Visitor submits the request, Then the system rejects the request and returns `HTTP 400 Bad Request`." | Covered | FR-5 | — |
| AC-6  | "Given any registration attempt (successful or failed), When the API response is generated, Then the response payload must never contain the plaintext password or password hash." | Covered | FR-6 | — |

## Ambiguities & Non-Verifiable Statements

None found. All previously flagged ambiguities (validation error schema, special-character set) are now resolved with concrete, testable definitions in FR-3, FR-4, and the Validation Error Schema section.

## Contradictions With Original Story

None found. The password special-character set decision ("any ASCII printable, non-alphanumeric character") extends the story's example list (`@, #, $, %, !`) but does not conflict with it — the story's own wording ("e.g.") signals the list is non-exhaustive, so a superset is a valid interpretation rather than a contradiction.

## Scope Additions (Disclosed)

The spec's "Clarifications & Decisions" section adds behavior not stated in the source story's ACs. These are explicitly disclosed as stakeholder decisions (not presented as if derived from the ACs), so they are noted here for visibility rather than as defects:

- **Data-layer atomicity for duplicate-email detection (FR-2)** — The story's AC-2 does not mention concurrent requests; the spec now requires enforcement via a data-layer unique constraint. Disclosed in Clarification #4.
- **Whitespace trimming (FR-2, FR-3)** — Not addressed by AC-2 or AC-3; the spec now requires trimming before validation. Disclosed in Clarification #5.
- **Validation error schema (FR-3, FR-4)** — Not defined by AC-3 or AC-4; the spec now specifies a concrete `errors[]` JSON shape. Disclosed in Clarification #3.

None of these contradict the story; they fill gaps the story left open. Recommend confirming with the original story author/product owner that these decisions are acceptable, since they were made outside the story document itself.

## Missing Edge Cases, Boundary Conditions & Error Handling

None remaining. The two edge cases flagged in the prior review (concurrent duplicate registration, email whitespace handling) are now addressed in FR-2 and FR-3.

## Verdict Rationale

Pass: AC coverage is complete (6/6 Covered), no contradictions were found, and no ambiguous or non-verifiable statements remain — the five previously open items are now resolved with concrete, testable definitions. The disclosed scope additions are transparently documented as stakeholder decisions rather than silent invention, so they do not block the verdict, though confirming them with the story owner before implementation is advisable.
