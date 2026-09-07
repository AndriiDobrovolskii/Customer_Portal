# Intent: EPIC-5 / Story 5.1 — Authentication & Session Management (Frontend)

Confirmed via `interview-me`, 2026-09-06/07.

## Outcome

A production-quality React frontend (Vite + TypeScript + TanStack Query + React
Hook Form) in a new `frontend/` directory in this same repository, covering:

- Register
- Login (including the MFA-verify challenge branch)
- Logout / logout-all
- Password reset (request + confirm)
- Active session management (list + revoke)
- Route guards with redirect logic (unauthenticated → `/login`, authenticated → `/tickets`)

Built as EPIC-5's first Story, through the full `/so:next` delivery pipeline —
doubling as the first live test of the sub-agent-dispatch orchestrator change
(see `docs/intent/` sibling note or conversation history for that automation
work, once written down separately).

## User

The developer (sbruhov) — for a live, working demonstration that the existing
backend (EPIC-1..4) functions end-to-end, at a quality bar that holds up to
showing others.

## Why now

Two purposes at once: (1) visible proof the backend works, (2) pilot run for
the new sub-agent-dispatch mechanism being added to `story-orchestrator`.

## Success

A user can register, log in (including completing an MFA challenge when
required), view and revoke active sessions, reset a forgotten password, and log
out — all through a responsive, accessible UI against the real backend.

Client-side session handling matches the backend's actual security model
(confirmed against `app/modules/users/router.py`):
- Access token held in memory only (never `localStorage`).
- Refresh is silent via the existing `httpOnly` + `secure` + `samesite=strict`
  `refresh_token` cookie the backend already sets — the client never reads or
  stores the refresh token itself, it only calls `POST /auth/refresh` and lets
  the browser attach the cookie.

## Constraint

- No backend changes.
- Same repository, new `frontend/` directory (not a separate repo).

## Out of scope (deferred to future EPIC-5 Stories)

- MFA enrollment/activation screens (`/mfa/enroll`, `/mfa/activate`) — planned
  for a future "Profile / Settings" Story, not this one.
- Admin UI.
- Support tickets UI.
- Profile editing UI.

## Next step

Draft and create the GitHub Issue for Story 5.1 (title, description, draft
acceptance criteria) so `backlog-sync` can pull it into a `docs/stories/`
file and `docs/catalog/stories.yaml`. Creating the Issue is a shared/visible
action — confirm with the user before executing.

Done: Issue #22 created; synced to
`docs/stories/US-5.1-authentication-session-management.md`; Story activated
and in progress.
