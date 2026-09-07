---
artifact_type: specification
story: US-5.1
version: 2
status: APPROVED
created_at: "2026-09-06T14:20:15Z"
updated_at: "2026-09-07T16:00:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/evidence/US-5.1-clarification-report.md
    version: null
  - path: docs/decisions/US-5.1-open-decisions.md
    version: null
supersedes: null
---

# Specification: Authentication & Session Management (Frontend)

**Source:** docs/stories/US-5.1-authentication-session-management.md
**Story ID:** US-5.1
**Generated:** 2026-09-06
**Status:** Draft

## Summary

This spec covers the frontend authentication and session-management surface for the Customer Portal: register, login (including the MFA-challenge branch), MFA verification, silent access-token refresh, logout and "log out everywhere", viewing and revoking active sessions, and password reset (request and confirm) — plus the client-side validation, route guarding, distinct auth layout, and error-rendering behavior common to all of these screens.

## Background

As a customer, the user wants to register, log in, manage active sessions, and reset a password through a real web UI, so that the Customer Portal backend (EPIC-1..4) is usable and demonstrable end-to-end, not just through raw API calls. This Story is a frontend consumer of the already-delivered `/auth/*` backend contract; it does not design or change any API, database schema, or backend behavior.

## Functional Requirements

### FR-1: Registration

A visitor on the registration screen submits an email and password. The client calls `POST /auth/register`; on a `201` response, the visitor lands on the login screen with a success message.

**Derived from:** FE-AC1

### FR-2: Login Without MFA

A registered user without MFA enabled submits valid credentials on the login screen. The client calls `POST /auth/login`, which returns a `LoginResponse`. The access token is held in memory, the user is redirected to the authenticated placeholder home, and the refresh cookie is not read or stored by client code — only the browser holds it.

**Derived from:** FE-AC2

### FR-3: Login With MFA Challenge

A registered user with MFA enabled submits valid credentials on the login screen. The client calls `POST /auth/login`, which instead returns an `MfaRequiredResponse` (an `mfa_token`, no tokens issued). The UI navigates to an MFA-verify screen, holding `mfa_token` only in transient state. When the user submits a valid 6-digit TOTP code (or a valid recovery code), the client calls `POST /auth/mfa/verify`, which completes the login exactly as FR-2's success path.

**Derived from:** FE-AC3

### FR-4: Silent Refresh on 401

Given an authenticated session whose access token has expired or is rejected with `401`: when any authenticated request fails with `401`, the client calls `POST /auth/refresh` exactly once and retries the original request on success. On refresh failure, the client clears in-memory state and redirects to the login screen.

**Derived from:** FE-AC4 (see Open Questions 2–3 for the concurrent-request and proactive-refresh cases this AC's wording raises but does not specify behavior for)

### FR-5: Logout and Logout Everywhere

An authenticated user who chooses "Log out" triggers `POST /auth/logout`, clears in-memory state, and lands on the login screen. Choosing "Log out everywhere" instead triggers `POST /auth/logout-all` with the same client-side effect.

**Derived from:** FE-AC5

### FR-6: Active Sessions — List and Revoke

An authenticated user on the sessions screen sees, per session, its device label, location (if present), and last-used time, with the current session marked. Revoking a non-current session calls `DELETE /auth/sessions/{family_id}`; on success, that row disappears from the list without affecting the user's own session.

**Derived from:** FE-AC6 (see Open Question 6 for the current-session case, which this AC does not exercise)

### FR-7: Password Reset — Request and Confirm

A visitor on the "forgot password" screen submits an email; the client calls `POST /auth/password-reset/request`, and a generic "if an account exists..." message is shown regardless of whether the account exists. A visitor on the "reset password" screen with a valid token submits a new password meeting the applicable policy; the client calls `POST /auth/password-reset/confirm`, and on success the visitor lands on the login screen with a success message.

**Derived from:** FE-AC7

### FR-8: Client-Side Validation Before Submission

For any form in this Story, when a required field is empty or malformed (e.g., an invalid email shape), the form blocks submission and shows field-level errors without calling the API.

**Derived from:** FE-AC8 (see Open Question 5 for the exact per-screen rule set, which this AC does not specify)

### FR-9: Server-Side (problem+json) Error Rendering

When a request in this Story returns a 4xx `application/problem+json` response, the UI renders the response's `detail` (or a mapped, user-friendly message keyed by `type`), never a raw stack trace or JSON dump. A `422` validation-failure response's `errors` array is mapped to the matching form fields.

**Derived from:** FE-AC9 (see Open Question 4 for the two response shapes on this Story's own Register endpoint that this AC's "any request" wording does not actually cover)

### FR-10: Route Guards

An unauthenticated visitor who navigates to any authenticated route is redirected to the login screen, and is returned to the originally requested route after a successful login. An authenticated user who navigates to the login or registration screen is instead redirected to the authenticated placeholder home.

**Derived from:** FE-AC10

### FR-11: Network / Server Failure Handling

When a request in this Story encounters a network error or a 5xx response, the UI shows a generic, retry-capable error state — never a blank screen or an unhandled exception.

**Derived from:** FE-AC11

## Non-Functional Requirements

- Access token: memory only. Never `localStorage`/`sessionStorage`/a cookie the client sets itself.
- Refresh token: never read, logged, or stored by client code.
- No sensitive field (password, token, recovery code) is ever logged to the browser console in production builds.
- Full keyboard navigation and visible focus states on every form and interactive control (accessibility).
- Responsive: usable at common mobile widths (~375px) through desktop.
- Every screen has a loading state for its in-flight request(s) and an explicit error state — no indefinite spinners.
- A distinct auth layout — with no main sidebar or header — is used for this Story's pre-authentication screens, kept separate from the layout used by the authenticated app shell after login.

**Derived from:** Non-Functional / Security Requirements section of the source (first six bullets); the story's In Scope list — "Auth layout (no main sidebar/header) distinct from the authenticated app shell" (`docs/stories/US-5.1-authentication-session-management.md`) — for the last bullet.

## Out of Scope

- MFA enrollment/activation UI (`/auth/mfa/enroll`, `/auth/mfa/activate`, `DELETE /auth/mfa`) — a future "Profile / Settings" Story.
- Support Tickets UI — Story 5.2.
- Admin UI, profile-editing UI — future Stories.
- Any backend/API/DB change.

**Derived from:** Out of Scope section of the source.

## Open Questions

The following nine items are carried forward, unresolved, from `docs/decisions/US-5.1-open-decisions.md` (all entries there are logged `OPEN`). None is resolved in this spec; each is phrased so a reviewer can answer it directly.

1. **(OD-1) Cross-origin / CORS configuration.** The backend's current CORS policy (`app/main.py`) only allowlists a `dev-gui/` static-page origin and does not set `allow_credentials=True`. Will the frontend reach the backend same-origin (e.g., via a dev-server proxy, keeping the source's "no backend changes" assumption true), or does this require a CORS/config change on the backend?
2. **(OD-2) Single-flight handling of concurrent 401s.** When multiple authenticated requests fail with `401` concurrently, must the client serialize them behind one in-flight `/auth/refresh` call, or may each failing request independently trigger its own refresh attempt?
3. **(OD-3) Proactive vs. purely reactive token refresh.** Does this Story require a proactive, timer-based refresh (using `LoginResponse.expires_in`) ahead of actual expiry, in addition to FR-4's reactive, 401-triggered refresh?
4. **(OD-4) Non-uniform error response shapes on `/auth/register`.** `/auth/register`'s two failure responses (`RegistrationValidationError`, `DuplicateEmailError`) do not carry the RFC 7807 `application/problem+json` envelope FR-9 assumes for "any request." Should the client special-case these two shapes for the Register screen, or is this a backend defect to raise before implementing against it?
5. **(OD-5) Per-screen client validation rule set.** What exact client-side rules should Register's, Login's, and Reset-Password's forms enforce (FR-8), given Register and Password-Reset-Confirm apply different, undocumented password policies, and at least one rule per policy (breach/reuse checking) is server-only and cannot be checked client-side at all?
6. **(OD-6) Current-session revoke affordance.** Should the Active Sessions screen (FR-6) disable or hide the "revoke" control on the row for the caller's own current session, or let the user attempt it and surface the backend's `CurrentSessionError` (409)?
7. **(OD-7) MFA-enrollment-deadline banner copy and dismissal.** What exact copy, tone, and re-appearance rule should the dismissible informational banner use, and does dismissal persist for the session only, or until the deadline changes?
8. **(OD-8) Placeholder authenticated home content.** What should the post-login placeholder route actually contain?
9. **(OD-9) Design system / component library choice.** Is a headless-UI kit (e.g., Radix/Headless UI + Tailwind) or hand-built components the intended foundation for this Story's forms and screens?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| FE-AC1 | "Given a visitor on /register When they submit a valid email and password Then POST /auth/register is called and, on 201, they land on /login with a success message" | FR-1 |
| FE-AC2 | "Given a registered user without MFA enabled When they submit valid credentials on /login Then POST /auth/login returns LoginResponse And the access token is held in memory, the user is redirected to the authenticated placeholder home And the refresh cookie is not read or stored by client code (only the browser holds it)" | FR-2 |
| FE-AC3 | "Given a registered user with MFA enabled When they submit valid credentials on /login Then POST /auth/login returns MfaRequiredResponse (mfa_token, no tokens issued) And the UI navigates to an MFA-verify screen, holding mfa_token only in transient state When they submit a valid 6-digit TOTP code (or a valid recovery code) Then POST /auth/mfa/verify completes the login exactly as FE-AC2's success path" | FR-3 |
| FE-AC4 | "Given an authenticated session whose access token has expired or is rejected with 401 When any authenticated request fails with 401 Then the client calls POST /auth/refresh exactly once, retries the original request on success And on refresh failure, the client clears in-memory state and redirects to /login" | FR-4 |
| FE-AC5 | "Given an authenticated user When they choose \"Log out\" Then POST /auth/logout is called, in-memory state is cleared, and they land on /login When they instead choose \"Log out everywhere\" Then POST /auth/logout-all is called with the same client-side effect" | FR-5 |
| FE-AC6 | "Given an authenticated user on the sessions screen Then GET /auth/sessions renders each session's device label, location (if present), last-used time, and marks the current one When they revoke a non-current session Then DELETE /auth/sessions/{family_id} is called and that row disappears from the list without affecting their own session" | FR-6 |
| FE-AC7 | "Given a visitor on /forgot-password When they submit an email Then POST /auth/password-reset/request is called and a generic \"if an account exists...\" message is shown regardless of whether the account exists Given a visitor on /reset-password?token=... with a valid token When they submit a new password meeting the policy Then POST /auth/password-reset/confirm succeeds and they land on /login with a success message" | FR-7 |
| FE-AC8 | "Given any form in this Story When required fields are empty or malformed (e.g. invalid email shape) Then the form blocks submission and shows field-level errors without calling the API" | FR-8 |
| FE-AC9 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its `detail` (or a mapped, user-friendly message keyed by `type`) without a raw stack trace or JSON dump And a 422 validation-failed response maps its `errors` array to the matching form fields" | FR-9 |
| FE-AC10 | "Given an unauthenticated visitor When they navigate to any authenticated route Then they are redirected to /login, and back to the original route after a successful login Given an authenticated user When they navigate to /login or /register Then they are redirected to the authenticated placeholder home instead" | FR-10 |
| FE-AC11 | "Given a network error or a 5xx response from any endpoint in this Story Then the UI shows a generic retry-capable error state, never a blank screen or an unhandled exception" | FR-11 |
