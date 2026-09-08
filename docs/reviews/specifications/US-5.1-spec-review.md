---
artifact_type: specification_review
story: US-5.1
version: 2
status: ARCHIVED
created_at: "2026-09-06T14:45:00Z"
updated_at: "2026-09-07T16:00:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
supersedes: 1
---

# Spec Review: Authentication & Session Management (Frontend)

**Original Story:** docs/stories/US-5.1-authentication-session-management.md
**Spec Reviewed:** docs/specifications/US-5.1-spec.md (v2)
**Story ID:** US-5.1
**Reviewed:** 2026-09-06
**Overall Verdict:** Pass with Issues

*This review replaces the prior v1 review (Pass with Issues, one Major finding).*

## Summary

The spec's 11 Functional Requirements (FR-1..FR-11) still map cleanly one-to-one onto the story's 11 Acceptance Criteria (FE-AC1..FE-AC11); all Covered, no contradictions, no scope creep. The v1 review's single Major finding — the story's "Auth layout (no main sidebar/header) distinct from the authenticated app shell" In Scope item having zero footprint in the spec — is now closed: the spec's Non-Functional Requirements section adds a new bullet stating this explicitly, with a "Derived from" citation to the same In Scope bullet. No new Major/Critical finding emerged. All nine Open Decisions remain correctly carried forward as OPEN, matching `docs/decisions/US-5.1-open-decisions.md` verbatim.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| FE-AC1 | "Given a visitor on /register When they submit a valid email and password Then POST /auth/register is called and, on 201, they land on /login with a success message" | Covered | FR-1 | — |
| FE-AC2 | "Given a registered user without MFA enabled When they submit valid credentials on /login Then POST /auth/login returns LoginResponse And the access token is held in memory, the user is redirected to the authenticated placeholder home And the refresh cookie is not read or stored by client code (only the browser holds it)" | Covered | FR-2 | — |
| FE-AC3 | "Given a registered user with MFA enabled When they submit valid credentials on /login Then POST /auth/login returns MfaRequiredResponse (mfa_token, no tokens issued) And the UI navigates to an MFA-verify screen, holding mfa_token only in transient state When they submit a valid 6-digit TOTP code (or a valid recovery code) Then POST /auth/mfa/verify completes the login exactly as FE-AC2's success path" | Covered | FR-3 | — |
| FE-AC4 | "Given an authenticated session whose access token has expired or is rejected with 401 When any authenticated request fails with 401 Then the client calls POST /auth/refresh exactly once, retries the original request on success And on refresh failure, the client clears in-memory state and redirects to /login" | Covered | FR-4 | Concurrent-401 and proactive-refresh cases correctly deferred to OD-2/OD-3 |
| FE-AC5 | "Given an authenticated user When they choose \"Log out\" Then POST /auth/logout is called, in-memory state is cleared, and they land on /login When they instead choose \"Log out everywhere\" Then POST /auth/logout-all is called with the same client-side effect" | Covered | FR-5 | — |
| FE-AC6 | "Given an authenticated user on the sessions screen Then GET /auth/sessions renders each session's device label, location (if present), last-used time, and marks the current one When they revoke a non-current session Then DELETE /auth/sessions/{family_id} is called and that row disappears from the list without affecting their own session" | Covered | FR-6 | Current-session revoke affordance correctly deferred to OD-6 |
| FE-AC7 | "Given a visitor on /forgot-password When they submit an email Then POST /auth/password-reset/request is called and a generic \"if an account exists...\" message is shown regardless of whether the account exists Given a visitor on /reset-password?token=... with a valid token When they submit a new password meeting the policy Then POST /auth/password-reset/confirm succeeds and they land on /login with a success message" | Covered | FR-7 | — |
| FE-AC8 | "Given any form in this Story When required fields are empty or malformed (e.g. invalid email shape) Then the form blocks submission and shows field-level errors without calling the API" | Covered | FR-8 | Exact per-screen rule set correctly deferred to OD-5 |
| FE-AC9 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its `detail` (or a mapped, user-friendly message keyed by `type`) without a raw stack trace or JSON dump And a 422 validation-failed response maps its `errors` array to the matching form fields" | Covered | FR-9 | Register's two non-conforming error shapes correctly deferred to OD-4 |
| FE-AC10 | "Given an unauthenticated visitor When they navigate to any authenticated route Then they are redirected to /login, and back to the original route after a successful login Given an authenticated user When they navigate to /login or /register Then they are redirected to the authenticated placeholder home instead" | Covered | FR-10 | — |
| FE-AC11 | "Given a network error or a 5xx response from any endpoint in this Story Then the UI shows a generic retry-capable error state, never a blank screen or an unhandled exception" | Covered | FR-11 | — |

## Ambiguities & Non-Verifiable Statements

None found beyond ambiguity already present in the source story and already logged as Open Decisions OD-1..OD-9, which this spec correctly carries forward rather than resolving. The new NFR bullet ("A distinct auth layout — with no main sidebar or header — is used for this Story's pre-authentication screens, kept separate from the layout used by the authenticated app shell after login") is at the same level of verifiable specificity as the story's own wording it derives from — a developer/QA engineer can test for the absence of the shared sidebar/header component on auth routes.

## Contradictions With Original Story

None found. Every FR's stated behavior, the NFR section (including the new auth-layout bullet), and the Out of Scope section match the story's corresponding language without conflict.

## Scope Creep

None found. The newly added NFR bullet is traceable directly to the story's In Scope list — "Auth layout (no main sidebar/header) distinct from the authenticated app shell" (`docs/stories/US-5.1-authentication-session-management.md`) — and the spec's own "Derived from" line cites this correctly. No FR, NFR, or Open Question introduces a requirement, field, or system not traceable to the story.

## Missing Edge Cases, Boundary Conditions & Error Handling

None found. The v1 Major finding (auth-layout requirement untraced anywhere in the spec) is resolved: the new NFR bullet in `docs/specifications/US-5.1-spec.md` §Non-Functional Requirements now gives it an explicit, cited trace, matching the treatment every other In Scope item already received.

## Verdict Rationale

Pass with Issues: all 11 Acceptance Criteria remain fully Covered with no contradictions or scope creep, and the v1 review's one Major finding (untraced auth-layout requirement) is now closed by the new NFR bullet. No Critical or Major finding remains open, so this stage's harness verdict maps to PASS.
