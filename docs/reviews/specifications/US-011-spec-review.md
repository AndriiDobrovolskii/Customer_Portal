# Spec Review: Manage Users

**Original Story:** docs/stories/US-3.1-manage-users.md
**Spec Reviewed:** docs/specifications/US-011-manage-users-spec.md
**Story ID:** US-011 (source backlog file uses US-3.1, covering slices US-3.1.1–US-3.1.5)
**Reviewed:** 2026-09-02 (re-review of the 2026-09-02 revision, superseding the 2026-08-22 review of the original draft)
**Overall Verdict:** Pass with Issues

## Summary

This re-review covers the 2026-09-02 revision of the spec, which incorporated `us-clarifier`'s three Open Decisions (OD-1–OD-3, `docs/decisions/US-3.1-open-decisions.md`) and six precedent-resolved items after reading the real US-1.4/US-3.2 codebase. All 21 source ACs remain Covered, restated accurately, and no contradictions were found. All three findings from the prior (2026-08-22) review are now resolved: the Error Envelope schema and Enforcement Matrix are both still present and updated, and the ambiguous "roles is immutable" Out-of-Scope wording now names "the update endpoint" explicitly. The issue keeping this from a clean Pass is narrower than before: three new Functional Requirements (FR-17b, FR-22, FR-23) were added with no corresponding source AC, which is a defensible, disclosed practice this project has used before (US-2.6's FR-6/FR-7) but is flagged here per this skill's traceability check regardless of precedent.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| MU-AC1 | "Given an authenticated admin When GET /v1/admin/users?q=smith&status=active&limit=25 is called Then respond 200 with a cursor-paginated list matching the filters And each item contains id, email, display_name, status, roles, created_at, last_login_at And no password hash, token or other credential material is present in the payload" | Covered | FR-1 | — |
| MU-AC2 | "Given an authenticated user whose roles do not include the users:read permission When GET /v1/admin/users is called Then respond 403 with type \".../errors/insufficient-permission\" And an auth_audit_log entry is written (event=authz_denied)" | Covered | FR-2 | — |
| MU-AC3 | "Given a request with no valid access token When any /v1/admin/* endpoint is called Then respond 401 and the request never reaches the admin handler" | Covered | FR-3 | — |
| MU-AC4 | "Given a request with limit=5000, or an unknown status value, or a malformed cursor When GET /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" And no partial result set is returned" | Covered | FR-4 | — |
| MU-AC5 | "Given an authenticated admin with users:write When POST /v1/admin/users is called with {email, display_name, roles} Then respond 201 with the created resource and its ETag And users.status is \"invited\" and email_verified is false; no password is set And an invitation token (24-hour TTL) is emailed to the address And an admin_audit_log entry is written (actor=admin:{id}, event=user_created)" | Covered | FR-5 | — |
| MU-AC6 | "Given an account already exists with that email (case-insensitive) When POST /v1/admin/users is called Then respond 409 with type \".../errors/email-already-registered\" And no account is created and no invitation is sent" | Covered | FR-6 | FR-6 adds a BR-001-sourced concurrency sentence not stated by this AC — see Ambiguities/Scope note below |
| MU-AC7 | "Given a request body containing a \"password\" field When POST /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" Because admins must never know or choose another person's password" | Covered | FR-7 | — |
| MU-AC8 | "Given an admin whose own permission set does not include a permission granted by the requested role When POST /v1/admin/users is called with that role Then respond 403 with type \".../errors/privilege-escalation\" And no account is created" | Covered | FR-8 | — |
| MU-AC9 | "Given an authenticated admin and a current ETag for the target user When PATCH /v1/admin/users/{id} is called with If-Match and a whitelisted field Then respond 200 with the updated resource and a new ETag And one admin_audit_log row is written per changed field (old_value, new_value, actor, reason)" | Covered | FR-9 | — |
| MU-AC10 | "Given the record changed since the admin last read it When PATCH /v1/admin/users/{id} is called with the stale If-Match value Then respond 412 and no field is changed Given the If-Match header is absent Then respond 400 with type \".../errors/precondition-required\"" | Covered | FR-10 | — |
| MU-AC11 | "Given a request body containing id, created_at, email_verified, roles or an unknown field When PATCH /v1/admin/users/{id} is called Then respond 422 with type \".../errors/immutable-field\" or \".../errors/validation-failed\" And no field is changed Because role changes go through US-3.2 and email changes through the verified flow in US-1.3" | Covered | FR-11 | — |
| MU-AC12 | "Given a user id that does not exist When PATCH /v1/admin/users/{id} is called Then respond 404 with type \".../errors/not-found\"" | Covered | FR-12 | — |
| MU-AC13 | "Given an authenticated admin with users:write and an active target user When POST /v1/admin/users/{id}/deactivate is called with a required {reason} Then respond 200 And users.status becomes \"deactivated\" and deactivated_at is set And revoke_before:{target_id} is set to now, killing all access and refresh tokens And an account_lifecycle_audit_log entry is written (event=deactivated, actor=admin:{admin_id}, reason) Because these are exactly US-1.4 DA-AC1's side effects, per the DA-AC10 invariant" | Covered | FR-13 | — |
| MU-AC14 | "Given a target user whose status is already \"deactivated\" When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/already-deactivated\"" | Covered | FR-14 | — |
| MU-AC15 | "Given an admin whose id equals the target id When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/cannot-target-self\" And the self-service endpoint POST /v1/account/deactivate must be used instead" | Covered | FR-15 | — |
| MU-AC16 | "Given the target user is the only remaining active account holding the admin role When POST /v1/admin/users/{id}/deactivate is called Then respond 409 with type \".../errors/last-admin\" And the account remains active, so the system can never be locked out of administration" | Covered | FR-16 | — |
| MU-AC17 | "Given any actor When DELETE /v1/admin/users/{id} is called Then respond 405 Method Not Allowed Because erasure is handled only by the retention job in US-1.4 DA-AC9" | Covered | FR-17 | — |
| MU-AC18 | "Given an authenticated admin with users:write and a target user whose status is \"invited\" When POST /v1/admin/users/{id}/resend-invite is called Then respond 202 with a generic body And any previously issued, unconsumed invitation token for that account is invalidated And a fresh token with a 24-hour TTL is emailed to the address on file And an admin_audit_log entry is written (event=invitation_resent, actor=admin:{id}) Because the user id, its roles and its audit history must survive — recreating the record would not" | Covered | FR-18 | — |
| MU-AC19 | "Given a target user whose status is \"active\" or \"deactivated\" When POST /v1/admin/users/{id}/resend-invite is called Then respond 409 with type \".../errors/invalid-state-transition\" And no email is sent Because an active user needing access should use password reset (US-2.4), not an invitation" | Covered | FR-19 | — |
| MU-AC20 | "Given an invitation was resent to the same account less than 60 seconds ago When POST /v1/admin/users/{id}/resend-invite is called again Then respond 429 with a Retry-After header And the per-account limit is 5 resends per hour, mirroring US-1.2 VE-AC7" | Covered | FR-20 | — |
| MU-AC21 | "Given an unknown user id Then respond 404 Given an actor without users:write Then respond 403, and the denied attempt is audited" | Covered | FR-21 | — |

## Ambiguities & Non-Verifiable Statements

None found. Every FR (including the three added without a source AC) states concrete, testable status codes, error type slugs, and persisted-state effects.

## Contradictions With Original Story

None found. Every spec requirement checked traces back to matching AC text (or, for FR-9/FR-13, to the story's own Data Model Notes and MU-AC13's explicit `reason` mention — see Scope Creep below) with no conflicting status codes, conditions, or stated behavior.

## Scope Creep

- **[Low] FR-6's concurrency sentence is sourced from `business-rules.md` BR-001, not from MU-AC6 itself** — Spec says: "Per BR-001, the case-insensitive uniqueness check is enforced atomically at the data layer, so two simultaneous `POST /v1/admin/users` requests for the same email cannot both succeed — the loser receives this same `409`, not a distinct concurrency error" (FR-6). MU-AC6's own text says only "Given an account already exists with that email... respond 409... no account is created and no invitation is sent" — it says nothing about concurrent requests. This is disclosed in the spec's Open Decision Resolutions as a precedent pulled from a project-wide business rule (which itself already cites reuse "for admin-created accounts (US-011-manage-users-spec.md FR-6)"), not an invented mechanism — low risk, but strictly speaking not traceable to story text.

- **[Low] FR-17b (Deactivate unknown-user 404) has no source AC at all** — Spec says: "Given a user id that does not exist, when `POST /v1/admin/users/{id}/deactivate` is called, the system responds `404`..." (FR-17b). Unlike FR-22/FR-23 below, this endpoint's unknown-user behavior is not named anywhere in the story — not in an AC, not in the API Contract table, not in Data Model Notes. It's justified by precedent with Update (MU-AC12) and Resend-invite (MU-AC21), both of which do state this behavior for their own endpoints, and was explicitly identified as a gap by the prior (2026-08-22) review's Missing Edge Cases section. Reasonable and low-risk, but the spec should not be read as if MU-AC13–MU-AC17 themselves specify a 404 case — they don't.

- **[Low] FR-22/FR-23 (`GET /v1/admin/users/{id}`) have no source AC** — Spec adds two new FRs for an endpoint the story's In Scope list and API Contract table both name ("`GET /v1/admin/users/{id}` — `200 + ETag`"), but which MU-AC1–MU-AC4 never actually exercise. The endpoint itself is traceable to the story; its specific success/404/403/401 behavior in FR-22/FR-23 is inferred by mirroring FR-1/FR-2/FR-3/FR-12, not stated by any AC. Same disclosed pattern this project used for US-2.6's FR-6/FR-7 (Open-Decision-derived, no source AC) — consistent practice, but a reviewer or `test-writer` reading the Traceability Matrix should not expect an MU-AC id for these two FRs.

## Missing Edge Cases, Boundary Conditions & Error Handling

None found. The three gaps the 2026-08-22 review raised under this heading (concurrent duplicate-email creation, the role→permission mapping source, missing GET-by-id coverage) are now addressed — two by precedent-citation (FR-6, FR-8/FR-16) and one by new FRs (FR-22/FR-23); the fourth gap that review raised (Deactivate's missing unknown-user case) is now filled by FR-17b. See Scope Creep above for the traceability caveat on how these were filled.

## Verdict Rationale

Pass with Issues: AC coverage remains complete (21/21 Covered) and no contradictions were found, so nothing here blocks implementation. The three Low findings above are all disclosed, precedent-grounded additions (FR-6's BR-001 sentence; FR-17b, FR-22, FR-23's no-source-AC status) rather than undisclosed invention — engineering can build from this spec as-is, but `test-writer`/`reconciliation-reviewer` should treat FR-17b/FR-22/FR-23 as Open-Decision-derived requirements with no MU-AC to trace against, not as gaps in this review.
