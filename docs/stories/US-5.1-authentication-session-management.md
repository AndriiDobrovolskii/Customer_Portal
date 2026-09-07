---
id: US-5.1
epic: EPIC-5
title: Authentication & Session Management (Frontend)
slug: authentication-session-management
priority: MEDIUM
track: frontend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: 22
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/22
  last_synced_at: "2026-09-07T13:00:00Z"
---

# Epic 5 — Frontend: Authentication & Session Management

**Story ID:** US-5.1
**Project:** Customer Portal

## User Story
As a customer,
I want to register, log in, manage my active sessions, and reset my password through a real web UI,
So that the Customer Portal backend (EPIC-1..4) is usable and demonstrable end-to-end, not just through raw API calls.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Stack | React + Vite + TypeScript + TanStack Query + React Hook Form, new `frontend/` directory in this repo | Confirmed with the user during intake |
| 2 | Access token storage | In-memory only (a store, e.g. Zustand/Context — not `localStorage`/`sessionStorage`) | Backend never intended the access token for durable client storage; XSS-resistant by construction |
| 3 | Refresh token handling | Never read or stored by the client. The backend already sets it as an `httpOnly`+`secure`+`samesite=strict` cookie (`app/modules/users/router.py`); the client only calls `POST /auth/refresh` and lets the browser attach the cookie | Confirmed against actual backend code, not assumed |
| 4 | MFA scope | Only the login-time challenge (`POST /auth/mfa/verify`, 6-digit TOTP or recovery code) is in this Story. Enrollment (`/auth/mfa/enroll`, `/auth/mfa/activate`) is explicitly deferred to a future Story | Confirmed with the user during intake |
| 5 | Post-login redirect target | Redirect to a minimal authenticated placeholder route (e.g. `/`), NOT `/tickets` | Support Tickets UI (Story 5.2) does not exist yet; redirecting to `/tickets` today would be a dead route |
| 6 | `mfa_enrollment_deadline` (present on `LoginResponse`/`RefreshResponse` for privileged roles in their 14-day grace period) | Show a dismissible informational banner naming the deadline; no link into an enrollment flow (none exists yet) | Surfacing the field costs little; building a flow toward it would cross into out-of-scope MFA enrollment |
| 7 | No backend changes | This Story changes no API/DB — `API_DESIGN` and `DB_DESIGN` pipeline stages should record `NOT_APPLICABLE` | Purely a frontend consuming the existing, already-delivered contract |

## In Scope
- Register screen (`POST /auth/register`)
- Login screen, including the MFA-required branch (`POST /auth/login` → `LoginResponse` or `MfaRequiredResponse`)
- MFA verify screen (`POST /auth/mfa/verify`, TOTP code or recovery code)
- Logout (`POST /auth/logout`) and "log out everywhere" (`POST /auth/logout-all`)
- Active sessions screen: list (`GET /auth/sessions`) and revoke one (`DELETE /auth/sessions/{family_id}`)
- Password reset: request (`POST /auth/password-reset/request`) and confirm (`POST /auth/password-reset/confirm`)
- Silent access-token refresh (`POST /auth/refresh`) on 401 / near-expiry
- Route guards: unauthenticated → `/login`; authenticated visiting `/login` or `/register` → placeholder home
- Auth layout (no main sidebar/header) distinct from the authenticated app shell
- Client-side validation, loading states, and RFC 7807 `application/problem+json` error rendering for every screen above

## Out of Scope
- MFA enrollment/activation UI (`/auth/mfa/enroll`, `/auth/mfa/activate`, `DELETE /auth/mfa`) — future "Profile / Settings" Story
- Support Tickets UI — Story 5.2
- Admin UI, profile-editing UI — future Stories
- Any backend/API/DB change

## API Contract (existing backend — reference only, not designed by this Story)
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | None | `{email, password}` | 201 `UserRead` |
| POST | `/api/v1/auth/login` | None | `{email, password}` | 200 `LoginResponse` \| `MfaRequiredResponse` |
| POST | `/api/v1/auth/mfa/verify` | None (carries `mfa_token` in body) | `{mfa_token, code}` | 200 `MfaVerifyResponse`, sets refresh cookie |
| POST | `/api/v1/auth/refresh` | Refresh cookie | — | 200 `RefreshResponse`, rotates refresh cookie |
| POST | `/api/v1/auth/logout` | Bearer | — | 204 |
| POST | `/api/v1/auth/logout-all` | Bearer | — | 204 |
| GET | `/api/v1/auth/sessions` | Bearer | — | 200 `SessionListResponse` |
| DELETE | `/api/v1/auth/sessions/{family_id}` | Bearer | — | 204 |
| POST | `/api/v1/auth/password-reset/request` | None | `{email}` | 202 `PasswordResetRequestResponse` |
| POST | `/api/v1/auth/password-reset/confirm` | None | `{token, new_password}` | 200, empty body |

## Client State Notes
- Auth store: `accessToken` (in-memory, never persisted), `isAuthenticated`, current user (from `UserRead`/decoded from login), transient `mfaToken` (held only between the MFA-required response and the verify call, cleared after use or on navigation away).
- No client-side storage of the refresh token — it never appears in JS-reachable state.
- `mfa_enrollment_deadline`, when present, drives a dismissible banner only; dismissal state may live in `sessionStorage` (non-sensitive).

## Acceptance Criteria

### Happy path
**FE-AC1 — Register**
```gherkin
Given a visitor on /register
When they submit a valid email and password
Then POST /auth/register is called and, on 201, they land on /login with a success message
```

**FE-AC2 — Login without MFA**
```gherkin
Given a registered user without MFA enabled
When they submit valid credentials on /login
Then POST /auth/login returns LoginResponse
And the access token is held in memory, the user is redirected to the authenticated placeholder home
And the refresh cookie is not read or stored by client code (only the browser holds it)
```

**FE-AC3 — Login with MFA challenge**
```gherkin
Given a registered user with MFA enabled
When they submit valid credentials on /login
Then POST /auth/login returns MfaRequiredResponse (mfa_token, no tokens issued)
And the UI navigates to an MFA-verify screen, holding mfa_token only in transient state
When they submit a valid 6-digit TOTP code (or a valid recovery code)
Then POST /auth/mfa/verify completes the login exactly as FE-AC2's success path
```

**FE-AC4 — Silent refresh**
```gherkin
Given an authenticated session whose access token has expired or is rejected with 401
When any authenticated request fails with 401
Then the client calls POST /auth/refresh exactly once, retries the original request on success
And on refresh failure, the client clears in-memory state and redirects to /login
```

**FE-AC5 — Logout / logout-all**
```gherkin
Given an authenticated user
When they choose "Log out"
Then POST /auth/logout is called, in-memory state is cleared, and they land on /login
When they instead choose "Log out everywhere"
Then POST /auth/logout-all is called with the same client-side effect
```

**FE-AC6 — Active sessions**
```gherkin
Given an authenticated user on the sessions screen
Then GET /auth/sessions renders each session's device label, location (if present), last-used time, and marks the current one
When they revoke a non-current session
Then DELETE /auth/sessions/{family_id} is called and that row disappears from the list without affecting their own session
```

**FE-AC7 — Password reset**
```gherkin
Given a visitor on /forgot-password
When they submit an email
Then POST /auth/password-reset/request is called and a generic "if an account exists..." message is shown regardless of whether the account exists
Given a visitor on /reset-password?token=... with a valid token
When they submit a new password meeting the policy
Then POST /auth/password-reset/confirm succeeds and they land on /login with a success message
```

### Validation, guards, and errors
**FE-AC8 — Client-side validation**
```gherkin
Given any form in this Story
When required fields are empty or malformed (e.g. invalid email shape)
Then the form blocks submission and shows field-level errors without calling the API
```

**FE-AC9 — Server-side (problem+json) errors**
```gherkin
Given any request in this Story returns a 4xx application/problem+json body
Then the UI renders its `detail` (or a mapped, user-friendly message keyed by `type`) without a raw stack trace or JSON dump
And a 422 validation-failed response maps its `errors` array to the matching form fields
```

**FE-AC10 — Route guards**
```gherkin
Given an unauthenticated visitor
When they navigate to any authenticated route
Then they are redirected to /login, and back to the original route after a successful login
Given an authenticated user
When they navigate to /login or /register
Then they are redirected to the authenticated placeholder home instead
```

**FE-AC11 — Network / server failure**
```gherkin
Given a network error or a 5xx response from any endpoint in this Story
Then the UI shows a generic retry-capable error state, never a blank screen or an unhandled exception
```

## Non-Functional / Security Requirements
- Access token: memory only. Never `localStorage`/`sessionStorage`/a cookie the client sets itself.
- Refresh token: never read, logged, or stored by client code.
- No sensitive field (password, token, recovery code) ever logged to the browser console in production builds.
- Full keyboard navigation and visible focus states on every form and interactive control (a11y).
- Responsive: usable at common mobile widths (~375px) through desktop.
- Every screen has a loading state for its in-flight request(s) and an explicit error state — no indefinite spinners.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| FE-AC1–3, FE-AC5–7 | Component/integration tests against a mocked API layer (MSW or equivalent) | `[gate]` |
| FE-AC4 | Integration test simulating a 401 mid-session | `[gate]` |
| FE-AC6 | Component test for list + revoke, including the "current session" marker | `[gate]` |
| FE-AC8 | Form-level unit tests (React Hook Form + validation schema) | `[gate]` |
| FE-AC9 | Test asserting problem+json `type`/`errors` map to rendered messages/fields | `[gate]` |
| FE-AC10 | Route-guard unit/integration tests for both directions | `[gate]` |
| FE-AC11 | Test forcing a network/5xx failure per screen | `[gate]` |
| a11y bar | Automated a11y check (e.g. axe) in CI on key screens | `[gate]` |

## Open Questions
1. `mfa_enrollment_deadline` banner (Assumption #6): confirm the exact copy/dismissal behavior wanted, or accept the default above.
2. Placeholder authenticated home (Assumption #5): confirm a specific minimal screen (e.g. "Welcome, logged in" stub) rather than leaving this to be decided ad hoc during implementation.
3. Design system / component library choice (e.g. a headless-UI kit vs. hand-built components) is not yet decided — left for API_DESIGN-equivalent design work in this Story's own pipeline pass, since it doesn't touch the backend contract.
