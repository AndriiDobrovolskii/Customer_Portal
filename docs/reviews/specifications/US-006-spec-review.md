# Spec Review: Logout

**Original Story:** docs/stories/US-2.2-logout.md
**Spec Reviewed:** docs/specifications/US-006-logout-spec.md (2026-08-31 revision, incorporating resolved Open Decisions OD-1–OD-6)
**Story ID:** US-006
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass with Issues

## Summary

This is a re-review of the 2026-08-22 spec, revised 2026-08-31 to incorporate `docs/decisions/US-2.2-open-decisions.md`'s six resolved Open Decisions, found while clarifying this story against the now-implemented US-2.1 codebase. All five ACs (LO-AC1–LO-AC5) remain covered, and the prior review's single blocking [High] ambiguity (LO-AC4 vs. LO-AC5) is resolved by the disclosed OD-2 carve-out. Verdict remains Pass with Issues: one new [Low] edge-case gap was introduced by the OD-3 mechanism (a refresh cookie whose token_hash has no matching `refresh_tokens` row), and the OD-driven mechanism substitutions are worth noting as disclosed-but-unanchored content, same as the prior review's Low findings — neither blocks implementation.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| LO-AC1 | "Given an authenticated user with a valid access token and refresh cookie When POST /v1/auth/logout is called Then respond 204 And the presented refresh token is marked revoked (its whole rotation family, per US-2.3) And the access token's jti is added to a Valkey denylist with TTL = its remaining lifetime And the refresh cookie is cleared (Set-Cookie with Max-Age=0) And an auth_audit_log entry is written (event=logout, scope=session)" | Covered | FR-1 | Revocation mechanism substituted per resolved OD-1 (`user_sessions.revoked_at`, not a Valkey `jti_denylist`) and OD-3 (`refresh_tokens.revoked_at` + family lookup); family-revocation and audit-entry outcomes are preserved |
| LO-AC2 | "Given an authenticated user with active sessions on three devices When POST /v1/auth/logout-all is called Then respond 204 And revoke_before:{user_id} is set to now in Valkey And every access and refresh token issued before that moment is rejected on next use (401) And an auth_audit_log entry is written (event=logout, scope=all_sessions)" | Covered | FR-2 | Unchanged from the prior spec version |
| LO-AC3 | "Given a request with no access token, or an expired/invalid one When POST /v1/auth/logout is called Then respond 401 And no session state is modified" | Covered | FR-3 | Unchanged |
| LO-AC4 | "Given a refresh token that was already revoked by a previous logout When POST /v1/auth/logout is called again with the same still-valid access token Then respond 204 (identical to LO-AC1) — the operation is idempotent And no additional revocation side effects occur And no error is surfaced that would confirm the token's prior state" | Covered | FR-4 | Prior review's [High] ambiguity resolved per OD-2's logout-only leniency carve-out — see Contradictions note below |
| LO-AC5 | "Given a user who has just logged out When any authenticated endpoint is called with the pre-logout access token Then respond 401 Because the jti is on the denylist, regardless of the token's exp claim" | Covered | FR-5 | Now explicitly scoped to "any authenticated endpoint other than POST /v1/auth/logout" — see Contradictions note below |

## Ambiguities & Non-Verifiable Statements

None found. The prior review's single [High] ambiguity (LO-AC4/LO-AC5's unresolved interaction) is resolved by the OD-2 carve-out, stated identically and consistently in both FR-4 and FR-5. The prior review's two [Low] open questions (missing refresh cookie; CSRF failure behavior) are resolved: the former by OD-6 (FR-1's explicit missing-cookie branch), the latter is moot since CSRF enforcement itself is now descoped (OD-4) rather than left undefined.

## Contradictions With Original Story

None found. Three places where the revised spec states something different from the story's literal text are all disclosed, sourced substitutions from the Open Decision Resolutions section, not silent departures:

- FR-1/FR-5 revoke via `user_sessions.revoked_at` rather than the story's literal "Valkey denylist" (LO-AC1, LO-AC5) — per resolved OD-1, because that mechanism already exists and is already the enforcement point in the shipped US-2.1 codebase.
- FR-4/FR-5 narrow LO-AC5's "any authenticated endpoint" to "any authenticated endpoint other than POST /v1/auth/logout" — per resolved OD-2, the only reading that makes LO-AC4 and LO-AC5 simultaneously satisfiable (see the prior review's own ambiguity finding, which reasoned to exactly this same carve-out as one of two possible readings).
- The Non-Functional Requirements section states CSRF is "not enforced by this story," reversing the story's stated NFR ("CSRF token required") — per resolved OD-4, and disclosed in both the Open Decision Resolutions section and the Out of Scope section rather than silently dropped.

This mirrors how US-005's own OD-driven spec revision was reviewed (`docs/reviews/specifications/US-005-spec-review.md`): a disclosed, decision-log-sourced substitution of the story's stated design is not treated as a spec-authored contradiction.

## Scope Creep

- **[Low] OD-driven content is anchored to the decision log, not to a numbered AC's literal wording.** The Open Decision Resolutions section, the `user_sessions`/`refresh_tokens` schema specifics in FR-1, the logout-only carve-out in FR-4/FR-5, and the CSRF/refresh-token-scope entries in Out of Scope all trace to `docs/decisions/US-2.2-open-decisions.md`, not to LO-AC1–LO-AC5's own text. Not scope creep in the sense of inventing new behavior — every addition narrows or substitutes existing AC-covered behavior rather than adding new behavior — but flagged for the same reason the prior US-005 review flagged its analogous OD-sourced additions: a reader checking spec-against-AC alone, without also reading the decision log, could not derive this content.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Refresh cookie present but its `token_hash` matches no `refresh_tokens` row.** FR-1 (per OD-3) says the presented refresh cookie is resolved to its `refresh_tokens` row "by `token_hash`" but doesn't state what happens if no row matches (a stale, tampered, or already-deleted cookie value). This is a new question introduced by adding the token-hash lookup step (OD-3) — the pre-revision spec never described *how* the token was resolved, so this branch didn't previously exist to address. Does the endpoint still respond `204` and skip the refresh-family revocation silently (consistent with the story's anti-enumeration idempotency intent for LO-AC4), or should this be treated differently? Phrased as a question since the story gives no direct basis either way.

## Verdict Rationale

Pass with Issues: full AC coverage (5/5 Covered) and no contradictions — the OD-driven substitutions are disclosed, sourced departures rather than spec-invented conflicts, consistent with how the analogous US-005 revision was reviewed. One new [Low] edge case (unresolved refresh-token lookup miss) and one [Low] scope-creep note (OD-anchored rather than AC-anchored content) remain, neither of which blocks implementation, but the lookup-miss branch should be confirmed before the OD-3 repository method is built.

## Addendum — refresh-token lookup-miss finding, resolved 2026-08-31

User resolved the [Low] Missing Edge Case finding above: a refresh cookie whose `token_hash` matches no `refresh_tokens` row silently skips the family-revocation step but still revokes the jti, clears the cookie, writes the audit entry, and returns `204` — identical to the matched case, no response-level signal distinguishes the two. `docs/specifications/US-006-logout-spec.md` FR-1 was amended accordingly. Verdict remains Pass with Issues; the only open item is the Low scope-creep note, which does not block implementation.
