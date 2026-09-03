# Spec Review: Active Session Management

**Original Story:** docs/stories/US-2.6-active-sessions.md
**Spec Reviewed:** docs/specifications/US-2.6-spec.md
**Story ID:** US-2.6 (backlog story numbered US-2.6)
**Reviewed:** 2026-09-02
**Overall Verdict:** Pass with Issues

## Summary

This re-review covers the 2026-09-02 revision of the US-2.6 spec, which incorporates all 4 Open Decisions from `docs/decisions/US-2.6-open-decisions.md` after re-reading the real, now-merged US-2.3 codebase. All five Acceptance Criteria (SM-AC1–SM-AC5) remain fully covered with a clean 1:1 mapping, and no direct contradictions with the source story were found. The verdict is "Pass with Issues" because: one genuine mechanism gap exists that both FR-1 and FR-6 depend on but neither states (how a caller's "current" family is identified from a request), and several disclosed, user-approved Open Decision resolutions (a new error-type slug, a new audit event, two new third-party dependencies, two wholly-new FRs) introduce scope beyond what the source story itself describes — legitimate, but worth flagging as this review's job requires.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| SM-AC1 | "Given an authenticated user with three live refresh-token families When GET /v1/auth/sessions is called Then respond 200 with one entry per family: family_id, created_at, last_used_at, approximate location (city/country from IP), a parsed device/browser label, and is_current And exactly one entry is flagged is_current, matching the caller's own family And no token value, hash or full IP address is returned" | Covered | FR-1 | — |
| SM-AC2 | "Given an authenticated user and a family_id belonging to another of their devices When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 and every token in that family is revoked (as in US-2.2 LO-AC1) And the caller's own session is unaffected And an auth_audit_log entry is written (event=session_revoked, target_family=…)" | Covered | FR-2 | — |
| SM-AC3 | "Given a family_id that belongs to a different user When DELETE /v1/auth/sessions/{family_id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm that the family_id exists" | Covered | FR-3 | — |
| SM-AC4 | "Given a family_id that is already revoked or has expired When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 — the operation is idempotent, mirroring LO-AC4" | Covered | FR-4 | — |
| SM-AC5 | "Given a request with no valid access token When GET /v1/auth/sessions is called Then respond 401 and no session metadata is disclosed" | Covered | FR-5 | — |

## Ambiguities & Non-Verifiable Statements

- **[Medium] Mechanism for identifying the caller's "current" family is unstated** — Spec says (FR-1): "Exactly one entry is flagged `is_current`, matching the caller's own family," and (FR-6): "a `family_id` matching their own current session." Neither FR, nor the story, states *how* the current family is determined from an authenticated `GET`/`DELETE` request. This is not a trivial detail: `app/core/security.py`'s access-token JWT carries no `family_id` claim, so the mechanism cannot be "read it off the bearer token" as one might assume. The only plausible source is the optional `refresh_token` httponly cookie already read by the existing `/v1/auth/refresh` and `/v1/auth/logout` endpoints (`app/modules/users/router.py`) — but the spec never says this endpoint also reads that cookie, and a caller might reasonably arrive at `GET /v1/auth/sessions` with an access token only (e.g. the cookie expired or was never sent cross-origin), leaving `is_current` undefined for that request. A developer cannot implement either FR without this being resolved first.

## Scope Creep

- **[Low] New error-type slug `current-session` (FR-6) not listed in the story's Error Envelope section** — Story says (Error Envelope section): "Error `type` slugs used by this story: `not-found` (shared)." Spec says (FR-6): "responds `409` with a `problem+json` body of type `.../errors/current-session`." This is a disclosed, user-approved Open Decision resolution (OD-1), not a silent invention, but it is a new slug the story's own enumerated list doesn't include.
- **[Low] New audit event `session_evicted` (FR-7) not present in the story** — Story only names `event=session_revoked` (SM-AC2). Spec's FR-7 introduces a second event name for the cap-eviction path. Disclosed via OD-2, but genuinely new vocabulary relative to the source.
- **[Low] Two new third-party dependencies (`user-agents`, MaxMind GeoLite2) not mentioned in the story** — The story states the *outputs* (a device/browser label, an approximate location) but never names a library or dataset. FR-1's mechanism detail (OD-3/OD-4) is a legitimate, disclosed implementation choice, but it is new scope the story itself is silent on.
- **[Low] FR-6 and FR-7 have no corresponding AC** — Both are wholly derived from Open Decisions (OD-1, OD-2), not from any SM-AC. The spec's own Traceability Matrix note already discloses this. Consistent with this project's established pattern (e.g. US-2.5's FR-8), this is legitimate gap-filling rather than silent invention, but it remains scope beyond the five ACs the story actually states.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] Concurrent logins racing past the 20-family cap** — FR-7 describes evicting the oldest family "when a new login creates a 21st family," implying a read-count-then-act check. The spec doesn't address what happens if two logins for the same user race concurrently (each observing a count of 20 before either commits its new family), which could let the live-family count exceed 20 with no eviction firing for the excess. This project has already hit an identical class of concurrency gap once before (US-3.2's FR-7 role-assignment race, found during implementation and fixed with `SELECT...FOR UPDATE`), so it's a reasonable case for this spec to address before implementation rather than discover during a gate re-run.
- **[Low] Does FR-7's eviction apply to the family being created, or only pre-existing ones?** — Implied by "the single oldest family," but worth an explicit statement that the newly-created (21st) family is never itself eligible for eviction on the same login, however far in the past its nominal `issued_at` might be computed.

## Verdict Rationale

Pass with Issues: all five ACs are fully covered with no contradictions, so the spec does not Fail. However, one Medium ambiguity (the undefined "current session" identification mechanism, which both FR-1 and FR-6 depend on) and one Medium missing-edge-case gap (concurrent-login cap eviction) need explicit resolution before this spec is implementation-ready; the remaining Low findings are disclosed, user-approved scope additions worth the implementation team's awareness but not blocking.
