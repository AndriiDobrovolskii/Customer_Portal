# US-2.6 (Active Session Management) — Clarification Report

## Scope, Actors, Business Value

**Actor:** Any authenticated user (any role — this is a self-service capability, not privileged). **Trigger:** the user wants to review or prune the devices currently signed in to their account. **Business value:** lets a user spot and cut off access they don't recognise (a lost/stolen device, a forgotten public-computer login) without the blunt instrument of logging themselves out everywhere (`business-glossary.md`'s Session entry; BR-009 covers the existing logout/logout-everywhere mechanisms this story deliberately doesn't replace).

In scope: `GET /v1/auth/sessions` (list live refresh-token families with privacy-safe metadata) and `DELETE /v1/auth/sessions/{family_id}` (revoke one, by another-device ownership). Out of scope: ending your own current session (US-2.2 already owns that) and admin visibility into other users' sessions.

## Dependency Check

`docs/stories/README.md` states US-2.6 depends only on US-2.3 (reads the refresh-token family metadata it writes). US-2.3 reached PR #6 and is confirmed merged to `main` (verified via `git log`/`gh pr view`); its `RefreshToken` model already carries every column this story reads from (`family_id`, `ip`, `user_agent`, `last_used_at`, `revoked_at`) and its rotation path already populates them. **No blocking dependency**, unlike US-2.5's US-3.2 situation — this story can proceed on the current `main` as-is.

## What's Clear

- The two endpoints, their auth requirement (self, always required), and success shapes are stated directly in the story's API Contract table.
- SM-AC1's field list, the `is_current` flag semantics, and the no-token-material rule are concrete and directly testable.
- SM-AC2's revocation semantics reuse US-2.2's existing revocation path (BR-009) — no new revocation mechanism needed, just a new trigger for the existing one.
- SM-AC3's 404-not-403 anti-enumeration choice is explicit and consistent with this project's existing anti-enumeration discipline (BR-005, BR-016).
- SM-AC4's idempotency requirement mirrors US-2.2 LO-AC4 directly — same pattern, same precedent.
- The `auth_audit_log` write on revocation (`event=session_revoked`) follows the established plain-string `event` convention already used throughout `users/service.py` (no enum to extend).
- Three items the pre-existing spec left as Open Questions turn out to be **already resolved by US-2.3's real implementation**, not by this story: session-metadata capture during rotation, and the `last_used_at` write-strategy question, are both already built and running (see Open Decisions log's "Resolved by existing implementation" section) — this story only needs to add the read side.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-2.6-open-decisions.md` for full detail. Summary:

- **OD-1 (Medium):** No AC states what happens when the caller `DELETE`s their own current `family_id` — silently revoke it (a de facto self-logout this story says is out of scope), or reject it distinctly.
- **OD-2 (Medium):** The 20-family live-session cap ("oldest evicted") has no AC describing the eviction mechanics — revocation path, audit event, any notification. No cap-enforcement code exists anywhere today.
- **OD-3 (Low):** Device/browser label derivation has no defined format or fallback, and no UA-parsing library exists in this codebase yet.
- **OD-4 (Low):** Geo-IP city/country derivation names no mechanism, and no geo-IP library/dataset exists in this codebase yet — this project has an established precedent (US-2.4 OD-1) against live third-party network calls from the test suite.

A pre-existing draft spec and review (`docs/specifications/US-2.6-spec.md`, `docs/reviews/specifications/US-2.6-spec-review.md`, both 2026-08-22) already exist for this story, following the same pattern that paid off for US-2.4/US-2.5. It independently raised the same core ambiguities (own-session revocation, cap eviction, label derivation, malformed `family_id`) as unresolved Open Questions/review findings — corroborating they're real gaps in the source story, not artifacts of this run's own reading. It did not surface the geo-IP mechanism question explicitly (it treated "approximate location" as a given), and this run resolved three of its six items by reading the codebase that's shipped since 2026-08-22 (see above).

## Readiness Verdict

**Ready for Specification** (as of 2026-09-02 — all Open Decisions resolved by the user, recommended option accepted throughout).

`story-spec-writer` should reflect: `DELETE` on the caller's own current `family_id` returns `409` (new error type, not a silent revoke); a new eviction path fires on login once a user's live-family count would exceed 20, reusing US-2.2's revocation write and logging `event=session_evicted`; the device/browser label uses the `user-agents` library with a defined format and fallback; location uses a bundled local MaxMind GeoLite2-City database, never a live network call.
