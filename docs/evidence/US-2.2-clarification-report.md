# Clarification Report: US-2.2 (Logout)

**Story:** `docs/stories/US-2.2-logout.md`
**Generated:** 2026-08-31

## Scope, Actors, Business Value

As an authenticated user, end my session on this device (`POST /v1/auth/logout`) or on every device at once (`POST /v1/auth/logout-all`), with server-side revocation of both the access and refresh token — clearing the cookie client-side is explicitly stated as insufficient. Business value: a lost/shared device or a walked-away session shouldn't remain usable as the account owner. Fits directly into the Epic 2 authentication set alongside US-2.1 (Login, merged as PR #2) and US-2.3 (Refresh Token, not yet built).

## What's Clear

- Both endpoints, their auth requirement, and success responses (`204`) are explicit.
- All 5 ACs (LO-AC1–5) are testable and covered 1:1 by FRs in the existing `docs/specifications/US-006-logout-spec.md`.
- Idempotency and anti-enumeration intent (no error confirming a token's prior state) is explicit.
- `revoke_before:{user_id}` reuse for logout-all is consistent with the already-implemented US-1.4/US-2.1 mechanism (`RevocationCache`) — this part needs no new design.
- BR-009 (business-rules.md) already codifies this story's core behavior (per-device default, `revoke_before` for everywhere, both idempotent) — no conflict found.

## What's Ambiguous / Newly Surfaced

This story and its pre-existing spec (`US-006-logout-spec.md`, drafted 2026-08-22, spec review Pass with Issues) were written before US-2.1 was actually implemented. Reading the current codebase surfaced real divergences a spec-writer cannot resolve alone — logged as OD-1 through OD-6 in `docs/decisions/US-2.2-open-decisions.md`:

- **OD-1 (High):** The story assumes a Valkey `jti_denylist:{jti}` mechanism for access-token revocation, but US-2.1 already built a Postgres `user_sessions` table with `revoked_at`, already checked on every authenticated request. Which one does logout use?
- **OD-2 (High, carried over from the spec review):** LO-AC4 (repeat logout → `204`) is difficult to reconcile with LO-AC5 (any request with a denylisted/revoked jti → `401`) — never resolved when the spec was first reviewed.
- **OD-3 (High):** `refresh_tokens` has no revocation column and no lookup-by-hash method today; US-2.3, which was meant to add this, hasn't been built. Does US-2.2 add a minimal column now (same pattern as US-2.1's OD-9)?
- **OD-4 (High):** No CSRF mechanism exists anywhere in the codebase; logout is the first endpoint that actually needs one (login was explicitly exempted). Build it here, or descope?
- **OD-5 (Medium):** `auth_audit_log` has no `scope` column for the `session`/`all_sessions` distinction LO-AC1/LO-AC2 require.
- **OD-6 (Low, carried over from the spec review):** Undefined behavior when an access token is valid but no refresh cookie is present.

Every recommendation in the Open Decisions log follows the same precedent US-2.1 already established (minimal schema additions ahead of a dependency story, descoping genuinely out-of-size cross-cutting work) — these are not new patterns, just this story's instance of them.

## Dependency Note

`docs/stories/README.md`'s suggested build order is US-2.1 → **US-2.3 → US-2.2**; the user is building US-2.2 next instead, ahead of US-2.3. This is a legitimate sequencing choice (flagged, not blocked) but is the direct cause of OD-3 — logout needs a sliver of what US-2.3 would otherwise have built first.

## Verdict

**Ready for Specification** (was Not Ready, resolved by user 2026-08-31). All 6 Open Decisions resolved — the user accepted the recommended option on every item (OD-1–OD-4 confirmed explicitly; OD-5–OD-6 carried the stated recommendation, same pattern as US-2.1). Summary of resolutions, all in `docs/decisions/US-2.2-open-decisions.md`:

- **OD-1:** Revoke via the existing `UserSession.revoked_at` — no Valkey `jti_denylist` key.
- **OD-2:** `POST /v1/auth/logout` specifically carves out leniency for an already-revoked jti (returns `204`); every other endpoint, including `logout-all`, still `401`s.
- **OD-3:** Add a minimal `revoked_at` column to `refresh_tokens` now, plus a hash-lookup and family-revoke repository method; single-use rotation stays out of scope for US-2.3.
- **OD-4:** CSRF protection is descoped from this story — stated explicitly in the spec's Out of Scope, tracked as a follow-up.
- **OD-5:** Add a dedicated nullable `scope` column to `AuthAuditLog`.
- **OD-6:** A valid access token with no refresh cookie still revokes the jti and returns `204`; only the cookie/family steps are skipped.

`story-spec-writer` should revise `docs/specifications/US-006-logout-spec.md` to incorporate all six resolutions before `story-spec-reviewer` re-runs.
