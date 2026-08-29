# Spec Review: Password Reset

**Original Story:** docs/stories/US-2.4-password-reset.md
**Spec Reviewed:** docs/specifications/US-008-password-reset-spec.md
**Story ID:** US-2.4 (backlog) / US-008 (spec)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All six Acceptance Criteria (PR-AC1–PR-AC6) are fully covered by the spec's Functional Requirements (FR-1–FR-6), and no contradictions or scope creep were found — the spec's wording tracks the story's gherkin text and Non-Functional/Out-of-Scope sections closely. The verdict is "Pass with Issues" because one concrete technical decision from the story's Assumptions & Defaults table (the token generation method) was not carried into the spec, and a couple of minor detail gaps and one edge-case question are worth resolving before build.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| PR-AC1 | "Given a registered, active account When POST /v1/auth/password-reset/request is called with that email Then respond 202 with a generic body ('If an account exists, an email has been sent') And a single-use reset token with a 30-minute TTL is created (SHA-256 hash stored only) And any previously issued, unconsumed reset token for that account is invalidated And an email is sent containing the token in the URL fragment, not the query string" | Covered | FR-1 | Token record shape and 202/generic-body/TTL/invalidation/fragment-delivery are all reproduced. See Ambiguities #1 for a related gap (token generation method). |
| PR-AC2 | "Given a valid, unconsumed, unexpired reset token and a new password meeting policy When POST /v1/auth/password-reset/confirm is called with {token, new_password} Then respond 200 And the password hash is replaced (Argon2id) And the token's consumed_at is set And revoke_before:{user_id} is set to now, terminating every existing session and refresh family And a 'your password was changed' notification is sent to the account's email And an auth_audit_log entry is written (event=password_reset_completed)" | Covered | FR-2 | All six sub-clauses reproduced verbatim. |
| PR-AC3 | "Given an email address that is not registered, or belongs to a deactivated account When POST /v1/auth/password-reset/request is called Then respond 202 with the same body, status and comparable timing as PR-AC1 And no email is sent, and this fact is not observable from the response" | Covered | FR-3 | Matches source exactly, including the cross-reference to the FR-1 baseline. |
| PR-AC4 | "Given a reset token that is expired, already consumed, or matches no stored hash When POST /v1/auth/password-reset/confirm is called with it Then respond 400 with type '.../errors/token-expired' or '.../errors/token-invalid' And the existing password remains unchanged And the response offers the option to request a new link" | Covered | FR-4 | See Ambiguities #2: the story itself doesn't specify which of the three states maps to which error slug; the spec inherits this ambiguity and appropriately raises it as an Open Question rather than inventing an answer. |
| PR-AC5 | "Given a valid reset token When the new password is shorter than 12 characters, appears in the breached-password list, or equals the current password Then respond 422 with type '.../errors/password-policy' And the errors array states which rule failed And the token is NOT consumed, so the user can retry with the same link" | Covered | FR-5 | Matches source exactly. |
| PR-AC6 | "Given a reset was requested for the same account less than 60 seconds ago When POST /v1/auth/password-reset/request is called again Then respond 429 with a Retry-After header And the per-account limit is 5 requests/hour and the per-IP limit is 10 requests/hour" | Covered | FR-6 | Matches source exactly. |

## Ambiguities & Non-Verifiable Statements

- **[Medium] Token generation method (length/algorithm) omitted from the spec** — Story's Assumptions & Defaults table, row 2: "Token design | 32 bytes via `secrets.token_urlsafe(32)`, SHA-256 hash stored, single-use | Matches US-1.2". Spec FR-1 says only: "A single-use reset token with a 30-minute TTL is created, with only its SHA-256 hash stored." The specific generation mechanism (32 bytes via `secrets.token_urlsafe(32)`) is a concrete, testable technical decision documented in the story but does not appear anywhere in the spec's Functional or Non-Functional Requirements. A developer building strictly from the spec has no way to know the token must be generated this specific way, and QA has nothing to test against for this detail.

- **[Low] PR-AC4's error-type mapping ambiguity is carried forward, not resolved** — Story: "respond 400 with type '.../errors/token-expired' or '.../errors/token-invalid'" covers three distinct token states (expired, already consumed, matches no stored hash) without saying which state maps to which slug. Spec FR-4 reproduces the same two-option wording without resolving the mapping. This ambiguity originates in the story itself, not the spec — and the spec correctly surfaces it in its own Open Questions section — so this is noted for completeness rather than as an independent defect introduced by the spec.

- **[Low] Error envelope field-level schema not reproduced** — Story's "Error Envelope" section gives a concrete `problem+json` example with fields `type`, `title`, `status`, `detail`, `instance`, and states "Error `type` slugs introduced by this story: `password-policy`." The spec's FR-4 and FR-5 mention "a `problem+json` body of type ..." but never reproduce the field-level shape (title/detail/instance) anywhere in the document, leaving the exact response body to be inferred from the type slug alone.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Malformed or missing `email` field on the request endpoint** — The story's API Contract defines the request body for `/v1/auth/password-reset/request` as `{"email": str}`, but neither the story's ACs nor the spec's FRs state what happens when the field is missing, empty, or not a validly formed email address. Does PR-AC1/PR-AC3's scope intend this case to be covered by this story's error handling (e.g., a `400`), or is basic field validation assumed to be handled elsewhere and out of scope here?

## Verdict Rationale

Pass with Issues: every AC (PR-AC1–PR-AC6) is fully Covered and no contradictions or scope creep were found, so nothing here blocks implementation outright. However, the token-generation detail gap (Ambiguities #1) is a concrete, sourced requirement that did not make it into the spec and should be added before engineering starts building FR-1, and the remaining ambiguity/edge-case notes are worth a quick resolution pass.
