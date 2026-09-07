---
id: US-5.2
epic: EPIC-5
title: Account & Profile Self-Service (Frontend)
slug: account-self-service-ui
priority: MEDIUM
track: frontend
source:
  type: github_issue
  repository: AndriiDobrovolskii/Customer_Portal
  issue_number: 25
  issue_url: https://github.com/AndriiDobrovolskii/Customer_Portal/issues/25
  last_synced_at: "2026-09-07T00:00:00Z"
---

# Epic 5 — Frontend: Account & Profile Self-Service

**Story ID:** US-5.2
**Project:** Customer Portal
**Depends on:** US-5.1 (auth store, API client, route guards, problem+json rendering)
**Split note:** originally drafted together with the Admin Console; that slice is now **US-5.4**. The two share no screens and no permission model.

## User Story
As an authenticated user,
I want to view and edit my profile, verify or change my email address, enroll in MFA, and deactivate my account through a real web UI,
So that EPIC-1 (US-1.2/1.3/1.4) and the enrollment half of US-2.5 are usable end-to-end, not just through raw API calls.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Stack | Reuses US-5.1's `frontend/` — same API client, auth store, guards | Adds screens, not infrastructure |
| 2 | **ETag / If-Match** | The shared API client is extended to expose **response headers**, not only JSON bodies. `PATCH /profile`'s 200 returns an `ETag` header, captured and echoed as `If-Match` on the next write; a 412 renders a "changed elsewhere — reload" conflict state | A typical query wrapper returns the body only. This is a real client-layer change, and **US-5.4 depends on it** |
| 3 | Profile screen is **write-only in the interim** | The form starts blank rather than pre-populated, and omits `If-Match` until a write in the same session yields an ETag (`if_match: str \| None = None` — the header is optional server-side) | There is no `GET /profile` and no `GET /users/me`. See Dependencies & Blockers #1 |
| 4 | Recovery codes | `POST /auth/mfa/activate`'s `recovery_codes` are shown **once**, with copy/download and an explicit "I have saved these" confirmation before the flow can complete. Never re-fetchable, never persisted by the client | The backend returns them exactly once; there is no re-fetch endpoint |
| 5 | QR rendering | The `otpauth_uri` QR is generated **locally in the browser** (bundled library), never by an external QR service | The URI embeds the TOTP secret; sending it to a third party would leak it |
| 6 | `mfa_enrollment_deadline` banner | US-5.1's dismissible banner (its Assumption #6) now links to this Story's enrollment flow | The link target finally exists |
| 7 | No backend changes | `API_DESIGN` / `DB_DESIGN` record `NOT_APPLICABLE` | Except the blocker below, which becomes a *new backend Story* rather than a frontend workaround |

## Dependencies & Blockers (backend gap — new Story required)
1. **There is no `GET /profile` and no `GET /users/me`.** `ProfileRead` is only ever returned *as the result of a write*, so the profile screen cannot pre-populate and `If-Match` has no ETag source on first load. **PS-AC1 (view) is blocked outright; PS-AC2 (edit) ships write-only.** A backend Story must be raised to add the read endpoint. The rest of this Story (email verification, MFA, deactivation) is unaffected.

## In Scope
- Profile edit (`PATCH /profile`: `display_name`, `locale`, `timezone`, `avatar_url`) with conditional `If-Match` — profile *view* is blocked on Dependencies & Blockers #1
- Email change (`PATCH /profile` with `email` + `current_password` → **202** and a `pending_email`) and confirmation (`POST /profile/confirm-email-change`)
- Email verification landing (`POST /auth/verify-email`) and resend (`POST /auth/verify-email/resend`)
- MFA enrollment: `POST /auth/mfa/enroll` (locally rendered QR from `otpauth_uri` + manual `secret`) → `POST /auth/mfa/activate` (6-digit code) → one-time recovery-code display; disable via `DELETE /auth/mfa`
- Account deactivation (`POST /account/deactivate`) with explicit confirmation and forced client-side sign-out
- **Changes US-5.1's shipped code:** the `mfa_enrollment_deadline` banner gains a link into this Story's enrollment flow (Assumption #6), and the shared API client is extended to surface response headers (Assumption #2)

## Out of Scope
- Admin console (users, roles, audit) — Story **US-5.4**
- Support Tickets UI — Story **US-5.3**
- Login, registration, sessions, password reset, MFA *challenge* — delivered in US-5.1
- Any backend/API/DB change

## API Contract (existing backend — reference only, not designed by this Story)
| Method | Path | Auth | Request | Success |
|---|---|---|---|---|
| PATCH | `/api/v1/profile` | Bearer + optional `If-Match` | partial `{display_name, locale, timezone, avatar_url}` or `{email, current_password}` | 200 `ProfileRead` + `ETag` header — **202 `ProfileRead` (no ETag) when an email change is initiated** |
| POST | `/api/v1/profile/confirm-email-change` | optional `Authorization` — **works signed-in and signed-out** | `{token}` | 200 `ConfirmEmailChangeResponse` |
| POST | `/api/v1/auth/verify-email` | None | `{token}` | 200 `VerifyEmailResponse` |
| POST | `/api/v1/auth/verify-email/resend` | None | `{email}` | 200 `ResendResponse` |
| POST | `/api/v1/auth/mfa/enroll` | Bearer | — | 200 `{secret, otpauth_uri}` |
| POST | `/api/v1/auth/mfa/activate` | Bearer | `{code}` (`^\d{6}$`) | 200 `{recovery_codes}` — **once only** |
| DELETE | `/api/v1/auth/mfa` | Bearer | — | 204 |
| POST | `/api/v1/account/deactivate` | Bearer | `{current_password?}` | 200 `{status, deactivated_at}` |

`ProfileRead`: `id`, `email`, `pending_email`, `display_name`, `locale`, `timezone`, `avatar_url`, `email_verified`, `created_at`.
`locale` is a closed set (`en-US`, `en-GB`); `timezone` must be a valid IANA name (server-validated against the full `zoneinfo.available_timezones()`).

## Client State Notes
- **ETags** are captured from the `ETag` response header and held per-resource in query cache metadata. A `PATCH /profile` returning **202 sets no ETag** — the client invalidates rather than reusing a stale one.
- MFA `secret`, `otpauth_uri` and `recovery_codes` live only in transient component state for the duration of the flow; cleared on navigation away, never written to any storage.
- `pending_email` drives the "confirm the link we sent" state; the primary `email` is unchanged until confirmation succeeds.

## Acceptance Criteria

**PS-AC1 — Profile view** *(blocked: no `GET /profile`)*
```gherkin
Given an authenticated user on /settings/profile
Then the current display_name, locale, timezone, avatar_url, email, pending_email and email_verified are shown
# Blocked on Dependencies & Blockers #1 — no read endpoint exists. This AC cannot be
# implemented until a backend Story adds GET /profile (or GET /users/me).
```

**PS-AC2 — Profile edit (write-only in the interim)**
```gherkin
Given the profile form
When the user changes display_name, locale (en-US | en-GB) or timezone (IANA name) and saves
Then PATCH /profile is called with only the changed fields
And If-Match is sent only when an ETag from a previous write in this session is known, and is omitted otherwise
And on 200 the form reflects the returned ProfileRead and stores the returned ETag
And a 412 shows a "changed elsewhere, reload" conflict state instead of silently overwriting
```

**PS-AC3 — Email change**
```gherkin
Given the profile screen
When the user submits a new email together with their current password
Then PATCH /profile returns 202 and the UI shows a "confirm the link sent to <pending_email>" state
And the primary email is unchanged until confirmation
Given a visitor opens the confirmation link
Then POST /profile/confirm-email-change succeeds whether or not they are signed in
```

**PS-AC4 — Email verification**
```gherkin
Given a visitor opens a verification link carrying a token
Then POST /auth/verify-email is called and success / expired / invalid each render a distinct outcome
And a "resend verification email" control calls POST /auth/verify-email/resend and shows a generic confirmation regardless of whether the address exists
```

**PS-AC5 — MFA enrollment**
```gherkin
Given an authenticated user without MFA on /settings/security
When they start enrollment
Then POST /auth/mfa/enroll is called and a locally rendered QR from otpauth_uri is shown alongside the manual secret
When they submit a 6-digit code
Then POST /auth/mfa/activate is called and the returned recovery_codes are displayed exactly once
And the flow cannot be completed until the user explicitly confirms they saved the codes
And the codes, secret and otpauth_uri are never written to localStorage, sessionStorage, a cookie, the console, or any third-party request
```

**PS-AC6 — MFA disable**
```gherkin
Given an authenticated user with MFA enabled
When they confirm disabling it
Then DELETE /auth/mfa is called and the security screen reflects MFA as disabled
```

**PS-AC7 — Account deactivation**
```gherkin
Given an authenticated user on the deactivation screen
When they confirm (supplying their current password where the form requires it)
Then POST /account/deactivate is called and, on 200, all in-memory auth state is cleared and they land on /login with a confirmation message
And the action is behind an explicit, non-accidental confirmation step naming the consequence
```

**XC-AC1 — problem+json errors**
```gherkin
Given any request in this Story returns a 4xx application/problem+json body
Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace
And a 422 validation-failed maps its errors array onto the matching form fields
```

**XC-AC2 — Client-side validation**
```gherkin
Given any form in this Story
When a required field is empty or malformed (invalid email shape, non-6-digit MFA code, unknown IANA timezone)
Then submission is blocked with a field-level error and no API call is made
```

**XC-AC3 — Network / server failure**
```gherkin
Given a network error or 5xx from any endpoint in this Story
Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception
```

## Non-Functional / Security Requirements
- MFA `secret`, `otpauth_uri`, `recovery_codes` and `current_password`: never logged to the console, never written to `localStorage`/`sessionStorage`/a client-set cookie, never sent to any third party.
- Destructive/irreversible actions (account deactivation, MFA disable) sit behind an explicit confirmation naming the consequence.
- Full keyboard navigation and visible focus on every form and control (a11y); the recovery-code list is selectable and copyable by keyboard.
- Responsive from ~375px through desktop.
- Every screen has an explicit loading state and an explicit error state.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| PS-AC1 | **Deferred** — blocked on Dependencies & Blockers #1 | `[blocked]` |
| PS-AC2 | Test asserting `If-Match` is sent when an ETag is known, omitted when not, and that a 412 renders the conflict state | `[gate]` |
| PS-AC3 | Test asserting a 202 yields the pending-email state and stores no ETag; confirmation works signed-in and signed-out | `[gate]` |
| PS-AC4, PS-AC6–7 | Component/integration tests against the mocked API layer (MSW or equivalent) | `[gate]` |
| PS-AC5 | Test asserting one-time display, required save-confirmation, and that no storage API, console, or external host receives the secret/codes | `[gate]` |
| XC-AC1–3 | Tests per screen for problem+json, validation, and network/5xx failure | `[gate]` |
| a11y bar | Automated a11y check (e.g. axe) on the profile, security and deactivation screens | `[gate]` |

## Open Questions
1. `GET /profile` (Dependencies & Blockers #1) — confirm the backend Story will be raised, and that the write-only interim is acceptable rather than deferring the whole screen.
2. `SupportedLocale` currently holds only `en-US`/`en-GB` and its own source comment calls it "a placeholder set pending product confirmation" — confirm the UI ships that two-item list.
3. Timezone input: a full IANA picker (~600 entries) vs. a searchable subset. The backend validates against the complete `zoneinfo.available_timezones()`; no curated list exists anywhere in the codebase.
4. Whether `POST /account/deactivate`'s `current_password` should always be required by the UI — the schema makes it optional (`SecretStr | None`), which may be a deliberate allowance for password-less (invited) accounts.
