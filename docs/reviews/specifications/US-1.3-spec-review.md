# Spec Review: Update Profile

**Original Story:** docs/stories/US-1.3-update-profile.md
**Spec Reviewed:** docs/specifications/US-1.3-spec.md
**Story ID:** US-1.3
**Reviewed:** 2026-08-15
**Overall Verdict:** Pass

## Summary

The spec was re-reviewed after all prior findings — the audit-log granularity ambiguity, four Missing Edge Case gaps, and the source's own three Open Questions — were resolved via an explicit "Clarifications & Decisions" section. All 12 ACs remain fully covered, no contradictions were found, and no requirement is left non-verifiable. The spec now carries five resolutions that go beyond what the source story literally states — these are disclosed and traceable to documented stakeholder decisions rather than silently invented, so they are noted below as disclosed scope additions rather than defects.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| UP-AC1 | "Given an authenticated user and a current ETag for their profile When PATCH /v1/profile is called with If-Match: <etag> and {\"display_name\": \"New Name\"} Then respond 200 with the updated resource and a new ETag And a profile_audit_log entry is written with old/new value, actor, and timestamp" | Covered | FR-1 | Multi-field granularity now defined — see Clarification #5 |
| UP-AC2 | "Given an authenticated user When PATCH /v1/profile is called without an If-Match header Then respond 400 with problem+json type '.../errors/precondition-required' And no fields are changed" | Covered | FR-2 | — |
| UP-AC3 | "Given the profile resource changed since the client last read its ETag When PATCH /v1/profile is called with the stale If-Match value Then respond 412 And no fields are changed" | Covered | FR-3 | — |
| UP-AC4 | "Given an authenticated user and a valid ETag When PATCH /v1/profile is called with an invalid value (e.g. locale not in the supported list) Then respond 422 with problem+json type '.../errors/validation-failed' And the errors array names the offending field(s)" | Covered | FR-4 | — |
| UP-AC5 | "When PATCH /v1/profile is called with {\"role\": \"admin\"} or any other immutable field Then respond 422 with problem+json type '.../errors/immutable-field' And no fields are changed" | Covered | FR-5 | — |
| UP-AC6 | "When PATCH /v1/profile is called with a field not in the editable whitelist (e.g. {\"is_super_user\": true}) Then respond 422 with problem+json type '.../errors/validation-failed' And no fields are changed" | Covered | FR-6 | current_password whitelist status now defined — see Clarification #3 |
| UP-AC7 | "Given user A is authenticated When PATCH /v1/profile is scoped/targeted at user B's resource (e.g. via a mismatched path or resource id) Then respond 403" | Covered | FR-7 | Status code confirmed — see Clarification #7 |
| UP-AC8 | "When PATCH /v1/profile is called without a valid session/JWT Then respond 401" | Covered | FR-8 | — |
| UP-AC9 | "Given an authenticated user and a valid ETag When PATCH /v1/profile is called with {\"email\": \"new@example.com\"} and a missing or incorrect current_password Then respond 401 with problem+json type '.../errors/reauthentication-required' And the primary email and pending_email remain unchanged" | Covered | FR-9 | — |
| UP-AC10 | "Given an authenticated user, a valid ETag, and the correct current_password When PATCH /v1/profile is called with {\"email\": \"new@example.com\", \"current_password\": \"...\"} Then respond 202 And users.email remains unchanged; users.pending_email is set to \"new@example.com\" And a confirmation link is sent to new@example.com And a notification (not a confirmation link) is sent to the current, still-active email address And a profile_audit_log entry records the change request" | Covered | FR-10 | Duplicate-email handling now defined — see Clarification #1 |
| UP-AC11 | "Given a valid, unconsumed, unexpired email_change_token When POST /v1/profile/confirm-email-change is called with the raw token Then respond 200 And users.email is set to the value of pending_email; pending_email is cleared And all active sessions/tokens for this user except the confirming one are revoked (requires re-login elsewhere) And a profile_audit_log entry records the completed change" | Covered | FR-11 | Concurrency now addressed — see Clarification #2 |
| UP-AC12 | "Given an expired, already-consumed, or unknown token When POST /v1/profile/confirm-email-change is called with that token Then respond 400 with problem+json type '.../errors/token-expired' or '.../errors/token-invalid' as appropriate And users.email and pending_email remain unchanged" | Covered | FR-12 | — |

## Ambiguities & Non-Verifiable Statements

None found. The audit-log granularity question is now resolved with a concrete, testable rule in FR-1.

## Contradictions With Original Story

None found.

## Scope Additions (Disclosed)

The spec's "Clarifications & Decisions" section adds behavior not stated in the source story's ACs. These are explicitly disclosed as stakeholder decisions (not presented as if derived from the ACs), so they are noted here for visibility rather than as defects:

- **Duplicate-email uniqueness check on email change (FR-9, FR-10)** — Not addressed by UP-AC9/UP-AC10; the spec now requires a case-insensitive check with `409 Conflict` on collision. Disclosed in Clarification #1.
- **Data-layer atomicity for email-change token consumption (FR-11)** — Not addressed by UP-AC11/UP-AC12; the spec now requires atomic enforcement. Disclosed in Clarification #2.
- **`current_password` whitelist scoping (FR-6)** — Not addressed by UP-AC6; the spec now specifies it's only valid alongside `email`. Disclosed in Clarification #3.
- **Combined field-update + email-change handling (FR-1, FR-10)** — Not addressed by any AC; the spec now permits it with atomic commit and a `202` response. Disclosed in Clarification #4.
- **Per-field audit log rows (FR-1)** — UP-AC1's singular phrasing doesn't resolve multi-field behavior; the spec now specifies one row per changed field, matching the source's Data Model Notes. Disclosed in Clarification #5.

None of these contradict the story; they fill gaps the story left open. Recommend confirming with the original story author/product owner that these decisions are acceptable, since they were made outside the story document itself. Clarifications #6, #7, and #8 confirm existing source defaults or explicitly defer out-of-scope items rather than adding new behavior, so they are not scope additions.

## Missing Edge Cases, Boundary Conditions & Error Handling

None remaining. The four edge cases flagged in the prior review (duplicate new-email, concurrent token consumption, current_password whitelist status, combined update handling) are now addressed in FR-9/FR-10, FR-11, FR-6, and FR-1/FR-10 respectively.

## Verdict Rationale

Pass: AC coverage is complete (12/12 Covered), no contradictions were found, and no ambiguous or non-verifiable statements remain — the prior ambiguity and four Missing Edge Case findings, plus the source's own Open Questions, are now resolved with concrete, testable definitions. The disclosed scope additions are transparently documented as stakeholder decisions rather than silent invention, so they do not block the verdict, though confirming them with the story owner before implementation is advisable.
