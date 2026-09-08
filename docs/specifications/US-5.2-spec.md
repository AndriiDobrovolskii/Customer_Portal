---
artifact_type: specification
story: US-5.2
version: 2
status: ARCHIVED
created_at: "2026-09-08T06:28:21Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/evidence/US-5.2-clarification-report.md
    version: 1
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: docs/specifications/US-5.2-spec.md
---

# Specification: Account & Profile Self-Service (Frontend)

**Source:** docs/stories/US-5.2-account-self-service-ui.md
**Story ID:** US-5.2
**Generated:** 2026-09-08
**Status:** Draft

## Summary

This spec covers the frontend account-and-profile self-service surface for the Customer Portal: profile editing (write-only in the interim), email change and confirmation, email verification landing and resend, MFA enrollment (enroll → activate → one-time recovery-code display) and disable, and account deactivation — plus the client-side validation, problem+json error rendering, and network/server-failure handling common to all of these screens. It also covers two changes to already-shipped US-5.1 code: the shared API client is extended to expose response headers (for `ETag`/`If-Match`), and the `mfa_enrollment_deadline` banner gains a link into this Story's enrollment flow.

**Rework note (v2):** This revision supersedes spec v1, which was reviewed (`docs/reviews/specifications/US-5.2-spec-review.md`, PASS) and then rejected by the human at `HUMAN_SPEC_APPROVAL` with rework directions. Three of the seven Open Decisions carried as Open Questions in v1 — OD-1, OD-2, and OD-4 — have since been resolved by the human (`docs/decisions/US-5.2-open-decisions.md`, now v2) and are reflected below in FR-2, FR-5, FR-6, and FR-7. Each of those four FRs now states behavior that deviates from its source AC's literal wording; each such deviation is called out explicitly, citing the resolved Open Decision as its authority, rather than silently restated as if it always matched the AC. OD-3, OD-5, OD-6, and OD-7 remain unresolved and are carried forward unchanged as Open Questions. No other section changed from v1.

## Background

As an authenticated user, the actor wants to view and edit their profile, verify or change their email address, enroll in MFA, and deactivate their account through a real web UI, so that EPIC-1 (US-1.2/1.3/1.4) and the enrollment half of US-2.5 are usable end-to-end, not just through raw API calls. This Story reuses US-5.1's frontend infrastructure (API client, auth store, route guards, problem+json rendering) and, per the source, makes no backend/API/DB change of its own — with one caveat the source itself names: there is no `GET /profile` or `GET /users/me` endpoint, so the profile *view* half of this Story is blocked pending a backend Story, and the edit half ships write-only in the interim.

## Functional Requirements

### FR-1: Profile View (Deferred)

On `/settings/profile`, an authenticated user's current `display_name`, `locale`, `timezone`, `avatar_url`, `email`, `pending_email`, and `email_verified` would be shown. This requirement cannot be implemented in this Story: no `GET /profile` or `GET /users/me` endpoint exists on the backend today. It is deferred until a backend Story adds a read endpoint; in the interim, the profile screen ships write-only per FR-2.

**Derived from:** PS-AC1 (see Open Question 2 for the status of the backend Story this defers to)

### FR-2: Profile Edit (Write-Only Interim)

On the profile form, when the user changes `display_name`, `locale` (`en-US` | `en-GB`) or `timezone` (a valid IANA name) and saves, the client calls `PATCH /profile` with only the changed fields. If an `ETag` from a previous write earlier in the same session is known, it is echoed as `If-Match`. **Per OD-1's resolution, this deviates from PS-AC2's literal "omitted otherwise" wording: when no ETag is yet known — including on the very first write in a session — the client sends `If-Match: *` rather than omitting the header.** `If-Match: *` is the backend's documented unconditional-overwrite escape hatch; it is required because the backend rejects any `PATCH /profile` request that carries no `If-Match` header at all (`400 precondition-required`), with no carve-out for "no ETag known yet." On a `200` response, the form reflects the returned `ProfileRead` and stores the returned `ETag` for use on the next write in the session. A `412` response renders a "changed elsewhere, reload" conflict state instead of silently overwriting. Supporting this, the shared API client (from US-5.1) is extended to expose response headers, not only JSON bodies, so the `ETag` header can be captured.

**Derived from:** PS-AC2, per OD-1's resolution (superseding PS-AC2's literal "omitted otherwise" wording for the no-ETag-known case)

### FR-3: Email Change — Request and Confirm

On the profile screen, when the user submits a new email together with their current password, `PATCH /profile` returns `202` and the UI shows a "confirm the link sent to `<pending_email>`" state; the primary `email` is unchanged until confirmation succeeds. A `202` response sets no `ETag` — the client invalidates rather than reusing a stale one. When a visitor (signed in or not) opens the confirmation link, `POST /profile/confirm-email-change` succeeds either way.

**Derived from:** PS-AC3

### FR-4: Email Verification Landing and Resend

When a visitor opens a verification link carrying a token, the client calls `POST /auth/verify-email`; success, expired, and invalid outcomes each render distinctly. A "resend verification email" control calls `POST /auth/verify-email/resend` and shows a generic confirmation regardless of whether the submitted address exists.

**Derived from:** PS-AC4

### FR-5: MFA Enrollment

An authenticated user without MFA, on `/settings/security`, starts enrollment. **Per OD-2's resolution, this deviates from PS-AC5, which names no such field: the enrollment step requires the user to also supply their `current_password`.** The client calls `POST /auth/mfa/enroll` with `current_password`, and a locally rendered (in-browser) QR code generated from the returned `otpauth_uri` is shown alongside the manual `secret`. When the user submits a 6-digit code, the client calls `POST /auth/mfa/activate`, and the returned `recovery_codes` are displayed exactly once, with copy/download support. The flow cannot be completed until the user explicitly confirms they have saved the codes. The `current_password`, `secret`, `otpauth_uri`, and `recovery_codes` are held only in transient component state — never written to `localStorage`, `sessionStorage`, a cookie, the console, or sent to any third party — and are cleared on navigation away. The already-shipped `mfa_enrollment_deadline` banner (US-5.1) is updated to link into this enrollment flow.

**Derived from:** PS-AC5, per OD-2's resolution (adding a `current_password` field PS-AC5 does not mention)

### FR-6: MFA Disable

An authenticated user with MFA enabled confirms disabling it. **Per OD-2's resolution, this deviates from PS-AC6, which names no such fields: the disable form requires the user to also supply their `current_password` and a 6-digit TOTP `code`.** The client calls `DELETE /auth/mfa` with `current_password` and `code`, and on success the security screen reflects MFA as disabled. **Also per OD-2's resolution**, the confirmation step preceding this call includes an explicit warning that disabling MFA revokes every other active session — a consequence PS-AC6's own wording does not name.

**Derived from:** PS-AC6, per OD-2's resolution (adding `current_password` and `code` fields, and the session-revocation warning, none of which PS-AC6 mentions)

### FR-7: Account Deactivation

On the deactivation screen, an authenticated user confirms deactivation. **Per OD-4's resolution, this deviates from PS-AC7's literal "supplying their current password where the form requires it" (conditional) wording: the form unconditionally requires `current_password` for every deactivation.** The client calls `POST /account/deactivate` with `current_password`; on `200`, all in-memory auth state is cleared and the user lands on `/login` with a confirmation message. This action sits behind an explicit, non-accidental confirmation step that names the consequence. Password-less accounts are excluded from self-service deactivation through this Story's UI — see Out of Scope.

**Derived from:** PS-AC7, per OD-4's resolution (making `current_password` unconditionally required, superseding PS-AC7's literal "where the form requires it" conditional wording)

### FR-8: Server-Side (problem+json) Error Rendering

When a request in this Story returns a 4xx `application/problem+json` response, the UI renders the response's `detail` (or a mapped, user-friendly message keyed by `type`) — never raw JSON or a stack trace. A `422` validation-failure response's `errors` array is mapped onto the matching form fields.

**Derived from:** XC-AC1

### FR-9: Client-Side Validation Before Submission

For any form in this Story, when a required field is empty or malformed (an invalid email shape, a non-6-digit MFA code, an unrecognized IANA timezone), submission is blocked with a field-level error and no API call is made.

**Derived from:** XC-AC2

### FR-10: Network / Server Failure Handling

When a request in this Story encounters a network error or a 5xx response, a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception.

**Derived from:** XC-AC3

## Non-Functional Requirements

- MFA `secret`, `otpauth_uri`, `recovery_codes`, and `current_password`: never logged to the console, never written to `localStorage`/`sessionStorage`/a client-set cookie, never sent to any third party.
- Destructive/irreversible actions (account deactivation, MFA disable) sit behind an explicit confirmation naming the consequence. Per OD-2's resolution, MFA disable's confirmation step names the session-revocation consequence specifically (FR-6).
- Full keyboard navigation and visible focus on every form and control (accessibility); the recovery-code list is selectable and copyable by keyboard.
- Responsive from ~375px through desktop.
- Every screen has an explicit loading state and an explicit error state.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Admin console (users, roles, audit) — Story US-5.4.
- Support Tickets UI — Story US-5.3.
- Login, registration, sessions, password reset, MFA *challenge* — delivered in US-5.1.
- Any backend/API/DB change. This Story implements only against already-shipped backend endpoints; it does not add, modify, or design any API route, request/response contract, or database schema/table/column. `API_DESIGN` and `DB_DESIGN` are `NOT_APPLICABLE` for US-5.2. The one gap the source itself names — no `GET /profile` / `GET /users/me` read endpoint — is not closed by this Story; it is deferred to a future backend Story (FR-1, Open Question 2).
- Password-less accounts, for self-service account deactivation. Per OD-4's resolution, the deactivation form (FR-7) always requires `current_password`; an account that has never set a real password cannot complete self-service deactivation through this Story's UI. No alternate flow for that account type is in scope here.

**Derived from:** Out of Scope section of the source (backend-change bullet expanded per Assumption #7: "`API_DESIGN` / `DB_DESIGN` record `NOT_APPLICABLE`"; password-less-account bullet added per OD-4's resolution).

## Open Questions

The following four items are carried forward, unresolved, from `docs/decisions/US-5.2-open-decisions.md` (version 2). OD-1, OD-2, and OD-4 — previously carried here in spec v1 — were resolved by the human at `HUMAN_SPEC_APPROVAL` and are now reflected directly in FR-2, FR-5, FR-6, and FR-7 above (and in the Out of Scope section for OD-4); they are not repeated here. OD-3, OD-5, OD-6, and OD-7 remain logged `OPEN` in the decisions file; resolution happens at a future `HUMAN_SPEC_APPROVAL`, not in this document. Each is phrased so a reviewer can answer it directly.

1. **(OD-3) No navigation behavior is specified for enrollment-scoped access tokens, which get a `403` on every route except `/mfa/enroll`/`/mfa/activate`.** During a privileged-role account's MFA grace period, every other authenticated route rejects an enrollment-scoped token outright. The source treats US-5.1's dismissible banner-plus-link (Assumption #6) as the entire integration point. Should the authenticated app shell force-navigate such a caller to the MFA enrollment screen, or is the banner link considered sufficient even though dismissing it (or navigating elsewhere first) leads to a raw `403` on every other screen?
2. **(OD-5 / the source's own Open Question #1) Has a backend Story been raised for the missing `GET /profile` / `GET /users/me` (FR-1)?** No such Story currently exists in `docs/stories/`. Should `SPECIFICATION` proceed treating PS-AC1 as permanently deferred/out-of-scope for this Story, or should progression wait until that backend Story exists or is at least scheduled?
3. **(OD-6 / the source's own Open Question #2) Should the UI ship `SupportedLocale`'s current two-item list (`en-US`, `en-GB`) as-is (FR-2)?** The backend's own source comment calls this set "a placeholder pending product confirmation." If the list later expands, should the client be built so the set is forward-compatible (re-derived from a shared constant) rather than hard-coded twice?
4. **(OD-7 / the source's own Open Question #3) Should the timezone input (FR-2) present the full ~600-entry IANA set or a curated subset?** The backend validates against the complete `zoneinfo.available_timezones()` with no narrower allow-list anywhere in the codebase, and this Story's own accessibility bar requires full keyboard navigation on every control.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| PS-AC1 | "Given an authenticated user on /settings/profile Then the current display_name, locale, timezone, avatar_url, email, pending_email and email_verified are shown # Blocked on Dependencies & Blockers #1 — no read endpoint exists. This AC cannot be implemented until a backend Story adds GET /profile (or GET /users/me)." | FR-1 (deferred — see Open Question 2) |
| PS-AC2 | "Given the profile form When the user changes display_name, locale (en-US \| en-GB) or timezone (IANA name) and saves Then PATCH /profile is called with only the changed fields And If-Match is sent only when an ETag from a previous write in this session is known, and is omitted otherwise And on 200 the form reflects the returned ProfileRead and stores the returned ETag And a 412 shows a \"changed elsewhere, reload\" conflict state instead of silently overwriting" | FR-2 — per OD-1's resolution, this AC's literal "omitted otherwise" wording is superseded: the client sends `If-Match: *` (not omission) whenever no ETag is known, including the first write |
| PS-AC3 | "Given the profile screen When the user submits a new email together with their current password Then PATCH /profile returns 202 and the UI shows a \"confirm the link sent to <pending_email>\" state And the primary email is unchanged until confirmation Given a visitor opens the confirmation link Then POST /profile/confirm-email-change succeeds whether or not they are signed in" | FR-3 |
| PS-AC4 | "Given a visitor opens a verification link carrying a token Then POST /auth/verify-email is called and success / expired / invalid each render a distinct outcome And a \"resend verification email\" control calls POST /auth/verify-email/resend and shows a generic confirmation regardless of whether the address exists" | FR-4 |
| PS-AC5 | "Given an authenticated user without MFA on /settings/security When they start enrollment Then POST /auth/mfa/enroll is called and a locally rendered QR from otpauth_uri is shown alongside the manual secret When they submit a 6-digit code Then POST /auth/mfa/activate is called and the returned recovery_codes are displayed exactly once And the flow cannot be completed until the user explicitly confirms they saved the codes And the codes, secret and otpauth_uri are never written to localStorage, sessionStorage, a cookie, the console, or any third-party request" | FR-5 — per OD-2's resolution, this AC's silence on a request body is superseded: enrollment also requires a `current_password` field the AC does not mention |
| PS-AC6 | "Given an authenticated user with MFA enabled When they confirm disabling it Then DELETE /auth/mfa is called and the security screen reflects MFA as disabled" | FR-6 — per OD-2's resolution, this AC's silence on a request body and on session revocation is superseded: disable also requires `current_password` and a TOTP `code`, and its confirmation step warns that every other session is revoked, none of which the AC mentions |
| PS-AC7 | "Given an authenticated user on the deactivation screen When they confirm (supplying their current password where the form requires it) Then POST /account/deactivate is called and, on 200, all in-memory auth state is cleared and they land on /login with a confirmation message And the action is behind an explicit, non-accidental confirmation step naming the consequence" | FR-7 — per OD-4's resolution, this AC's conditional "where the form requires it" wording is superseded: `current_password` is unconditionally required, and password-less accounts are out of scope (see Out of Scope) |
| XC-AC1 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | FR-8 |
| XC-AC2 | "Given any form in this Story When a required field is empty or malformed (invalid email shape, non-6-digit MFA code, unknown IANA timezone) Then submission is blocked with a field-level error and no API call is made" | FR-9 |
| XC-AC3 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | FR-10 |
