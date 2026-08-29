# Spec Review: Active Session Management

**Original Story:** docs/stories/US-2.6-active-sessions.md
**Spec Reviewed:** docs/specifications/US-010-active-session-management-spec.md
**Story ID:** US-010 (backlog story numbered US-2.6)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

All five Acceptance Criteria (SM-AC1–SM-AC5) are fully covered by FR-1 through FR-5 with a clean 1:1 traceability mapping, and no contradictions or unsanctioned scope additions were found — the spec's Non-Functional Requirements and Out of Scope sections restate the source verbatim. The verdict is "Pass with Issues" because several operational edge cases implied by the story's own Assumptions & Defaults table and In Scope list (session-cap eviction, capture of metadata during rotation, revoking one's own current session) are not addressed by any Acceptance Criterion, and the spec — appropriately, per its own discipline of not inventing requirements — has logged these as Open Questions rather than resolving them. These gaps trace back to the source story rather than to spec-writing error, but they still block a clean implementation-ready sign-off until resolved.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| SM-AC1 | "Given an authenticated user with three live refresh-token families When GET /v1/auth/sessions is called Then respond 200 with one entry per family: family_id, created_at, last_used_at, approximate location (city/country from IP), a parsed device/browser label, and is_current And exactly one entry is flagged is_current, matching the caller's own family And no token value, hash or full IP address is returned" | Covered | FR-1 | — |
| SM-AC2 | "Given an authenticated user and a family_id belonging to another of their devices When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 and every token in that family is revoked (as in US-2.2 LO-AC1) And the caller's own session is unaffected And an auth_audit_log entry is written (event=session_revoked, target_family=…)" | Covered | FR-2 | — |
| SM-AC3 | "Given a family_id that belongs to a different user When DELETE /v1/auth/sessions/{family_id} is called Then respond 404 with type \".../errors/not-found\" Because 403 would confirm that the family_id exists" | Covered | FR-3 | — |
| SM-AC4 | "Given a family_id that is already revoked or has expired When DELETE /v1/auth/sessions/{family_id} is called Then respond 204 — the operation is idempotent, mirroring LO-AC4" | Covered | FR-4 | — |
| SM-AC5 | "Given a request with no valid access token When GET /v1/auth/sessions is called Then respond 401 and no session metadata is disclosed" | Covered | FR-5 | — |

## Ambiguities & Non-Verifiable Statements

- **[Low] Undefined device/browser label derivation** — Spec says: "a parsed device/browser label" (FR-1, carried verbatim from SM-AC1). Neither the story nor the spec defines how the label is derived from the user-agent string or what value (if any) is produced when the user-agent cannot be parsed, so a developer or QA engineer cannot write a deterministic test asserting an exact label or a defined fallback. The spec correctly surfaces this in its Open Questions rather than inventing a definition, which mitigates but does not eliminate the ambiguity.

- **[Low] Dual, unresolved strategy for `last_used_at` writes** — Spec says (Non-Functional Requirements): "`last_used_at` should be written asynchronously, or throttled to once per minute, to keep the refresh path fast." Two divergent implementation strategies are offered without specifying which governs, or what the throttle window is scoped to (per family, per user, globally), so compliance cannot be verified by a single test. This wording is inherited verbatim from the story's Non-Functional / Security Requirements section.

## Contradictions With Original Story

None found. The spec's Functional Requirements, Non-Functional Requirements, and Out of Scope sections restate the story's corresponding sections without conflicting language.

## Scope Creep

None found. Every Functional Requirement traces 1:1 to an SM-AC, and the Non-Functional Requirements / Out of Scope sections are direct restatements of the source. The spec's Open Questions section identifies gaps rather than inventing new requirements to fill them, consistent with the "never invent" discipline this review checks for.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Medium] Revoking the caller's own current session** — SM-AC2 / FR-2 scope the happy path to "a family_id belonging to another of their own devices," and the story's Out of Scope section excludes "Logout of the current session and logout-everywhere (US-2.2)." However, no Acceptance Criterion states what `DELETE /v1/auth/sessions/{family_id}` should do when the caller passes their own current `family_id`. Does it fall through to SM-AC2's 204/revoke behavior (effectively performing a self-logout this story says is out of scope), get rejected with a distinct error, or something else? This is not addressed by the spec.

- **[Medium] Live-session cap eviction behavior** — The story's Assumptions & Defaults table states: "Live-session cap: 20 families per user, oldest evicted," and the spec's Non-Functional Requirements repeat "sessions per user are bounded at 20 live families." No Acceptance Criterion describes what happens when a new session pushes the count past 20 — whether the oldest family is revoked via the same US-2.2 path, whether an `auth_audit_log` entry (`event=session_revoked`) is written for the eviction, or whether the evicted device receives any signal. The spec already raises this in its Open Questions, but the gap remains unresolved.

- **[Low] "Capture and update of session metadata during rotation" has no corresponding AC** — The story's In Scope section lists this as a scoped work item ("Capture and update of session metadata during rotation"), but no SM-AC describes the expected behavior (which fields are captured/updated, on what trigger, or how failures — e.g., a geo-IP lookup error — are handled). The spec's Open Questions section flags this; since the story itself provides no AC for it, the gap originates upstream, but FR-1 through FR-5 do not fully cover everything the story's In Scope list promises.

- **[Low] Malformed or nonexistent `family_id` on DELETE** — SM-AC3 and SM-AC4 (FR-3/FR-4) cover "belongs to a different user" and "already revoked or expired" respectively, but neither the story nor the spec states the response for a syntactically invalid `family_id` (e.g., not a valid identifier format) that matches no record at all. Is this expected to fall under the same 404 path as SM-AC3, or does it warrant separate handling (e.g., 400)?

## Verdict Rationale

Pass with Issues: all five ACs are fully covered with no contradictions or unsanctioned scope additions, so the spec does not Fail. However, two low-severity ambiguities (undefined device/browser label parsing, an unresolved dual strategy for `last_used_at` writes) and four edge-case gaps (own-current-session revocation, cap-eviction behavior, metadata capture during rotation, malformed `family_id` handling) are unresolved before implementation. Most of these originate in the source story rather than spec-writing error, and the spec has already surfaced several of them as Open Questions rather than inventing answers — but they still need explicit resolution (ideally as new or amended ACs in the backlog story) before this spec is implementation-ready.
