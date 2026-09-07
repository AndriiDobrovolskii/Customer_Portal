# US-5.1 — Clarification Report

**Story:** `docs/stories/US-5.1-authentication-session-management.md` — Authentication & Session Management (Frontend)
**Stage:** CLARIFICATION
**Active-story check:** Confirmed. `docs/workflow/active-story.yaml` names `US-5.1` / `docs/stories/US-5.1-authentication-session-management.md` as the active Story (`status: IN_PROGRESS`). This report clarifies that Story.
**Prior open-decisions log:** None existed for `US-5.1` before this run — nothing to reconcile.

## Scope, actors, and business value (restated)

**Actor:** the `Customer` persona (`docs/product/personas.md`) — an external user who registers and logs in to reach the rest of the Customer Portal.

**Trigger:** the Customer needs a real browser UI, since EPIC-1..4 shipped only backend APIs. This Story is EPIC-5's first slice: a new `frontend/` (React + Vite + TS) that consumes the already-delivered, already-designed `/auth/*` endpoints — it explicitly designs and changes no backend contract or schema (Assumption #7).

**Business value:** makes the already-built authentication/session backend (registration, login, MFA challenge, refresh, logout, session management, password reset — EPIC-1/2's stories) usable and demonstrable end-to-end, which is a direct instance of Product Goal #1 ("Secure authentication") and #2 ("User self-service") in `docs/product/product-vision.md`, and directly serves the Customer persona's stated goals of logging in securely, seeing/managing active devices, and self-service password recovery (`docs/product/personas.md`).

**In-scope surface:** register, login (incl. MFA challenge branch), MFA verify, logout / logout-everywhere, active sessions (list + revoke), password reset (request + confirm), silent refresh, route guards, and a distinct unauthenticated layout — eleven acceptance criteria (FE-AC1–FE-AC11) plus NFRs (token storage, no sensitive logging, a11y, responsiveness, loading/error states per screen).

**Out of scope, correctly excluded:** MFA enrollment/activation UI, Support Tickets UI (Story 5.2, which doesn't exist locally yet — confirmed, no `docs/stories/US-5.2-*` file present), admin/profile UI, and any backend/API/DB change.

## What's clear

- The endpoint list, methods, auth requirements, and success responses in the Story's "API Contract" table were checked directly against `app/modules/users/router.py` and `app/modules/users/schemas.py` — they match. `LoginResponse`/`RefreshResponse` carry `mfa_enrollment_deadline: datetime | None`; `MfaVerifyResponse` deliberately does not (a separate class per its own docstring) — consistent with the Story's Assumption #6 scoping the banner to `LoginResponse`/`RefreshResponse` only.
- The refresh-cookie mechanics in Assumption #3 (`httpOnly`+`secure`+`samesite=strict`, set by `/login`, `/refresh`, `/mfa/verify`, cleared by `/logout`) match `router.py` exactly, including the `/api/v1/auth` cookie path scope.
- Anti-enumeration behavior FE-AC7 assumes for password-reset request (generic message regardless of account existence) matches `PasswordResetRequestResponse`'s fixed literal message and BR-005's stated policy.
- BR-008's single-use/theft-detection refresh model and BR-009's logout-vs-logout-everywhere distinction are consistent with what FE-AC4/FE-AC5 ask the client to do at the request/response level (though see OD-2 below for a concurrency gap those business rules expose in the AC's own wording).
- Session-list rendering fields in FE-AC6 (device label, location if present, last-used time, current-session marker) map cleanly onto `SessionEntry`'s fields — no invented field was needed.
- The Story's own three "Open Questions" are genuine, previously-unresolved gaps, not something a spec-writer could answer from `docs/product/*`; they are carried into the Open Decisions log as OD-7, OD-8, OD-9 rather than silently dropped.

## What's ambiguous (see `docs/decisions/US-5.1-open-decisions.md` for full detail)

Nine Open Decisions were raised, three carried forward from the Story's own "Open Questions" section and six newly surfaced by reading the actual backend implementation this Story must integrate against (not invented — each cites the specific file/behavior):

1. **OD-1 — CORS / cross-origin cookie config.** `app/main.py`'s `CORSMiddleware` only allowlists a `dev-gui/` static-page origin (`:5500`) with no `allow_credentials=True`; it doesn't cover a Vite dev-server origin. This directly threatens Assumption #7 ("no backend changes") and Assumption #3 (browser auto-attaching the cookie).
2. **OD-2 — Concurrent-401 refresh single-flight.** FE-AC4 only specifies the single-failing-request case; BR-008 makes concurrent, un-serialized refresh attempts a real risk of false theft-detection (whole-family revocation + security email) during ordinary use.
3. **OD-3 — Proactive vs. reactive refresh.** FE-AC4's `Given` names token expiry as a trigger, but only its `Then` for a reactive 401 is actually tested by the AC.
4. **OD-4 — Non-uniform register error shapes.** `/auth/register`'s two failure paths (`RegistrationValidationError`, `DuplicateEmailError`) don't produce the RFC 7807 envelope FE-AC9 assumes uniformly.
5. **OD-5 — Per-screen client validation rules.** Register's and Reset-Password's password policies are different, undocumented in the Story, and neither one is fully client-checkable (breach/reuse checks are server-only).
6. **OD-6 — Current-session revoke affordance.** FE-AC6 only exercises revoking a *non-current* session; whether the UI should proactively disable that control for the current row (vs. surfacing the backend's dedicated `CurrentSessionError` 409) is undecided.
7. **OD-7 — MFA-deadline banner copy/dismissal** (Story's Open Question #1).
8. **OD-8 — Placeholder authenticated home content** (Story's Open Question #2).
9. **OD-9 — Design system/component library choice** (Story's Open Question #3) — flagged as also bearing on the Story's own accessibility NFR if left ad hoc.

No security- or authorization-boundary gap beyond OD-1/OD-2 was found: this Story adds no new backend authorization surface, and the client-side route guards (FE-AC10) are a UX convenience, not the actual security boundary (the backend's own bearer/cookie checks remain authoritative either way).

## Readiness Verdict

**Not Ready — see Open Decisions.**

The Story is well-scoped, its actor/trigger/value are clear, and eight of its eleven acceptance criteria were verified consistent with the actual backend it integrates against. However, nine Open Decisions remain unresolved — three inherited from the Story's own author, six newly surfaced against the real `/auth/*` implementation — and at least OD-1 (CORS) and OD-2 (refresh concurrency) are architecturally load-bearing: a spec written without resolving them would either silently fail in development (OD-1) or risk spuriously logging users out account-wide under ordinary concurrent request load (OD-2). `story-spec-writer` should not proceed until these are answered or the risk is explicitly accepted.
