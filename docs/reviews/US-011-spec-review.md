# Spec Review: Manage Users

**Original Story:** docs/backlog/US-3.1-manage-users.md
**Spec Reviewed:** docs/specifications/US-011-manage-users-spec.md
**Story ID:** US-011 (source backlog file uses US-3.1, covering slices US-3.1.1–US-3.1.5)
**Reviewed:** 2026-08-22
**Overall Verdict:** Pass with Issues

## Summary

The spec covers all five shippable slices of US-3.1 (list/search, create, update, deactivate, resend-invite) and all 21 Acceptance Criteria (MU-AC1–MU-AC21) are Covered, restated almost verbatim as FR-1 through FR-21 with an accurate traceability matrix. No contradictions between spec and story were found, and no scope creep was found — the spec adds nothing beyond what the source states. The issues that keep this from a clean Pass are: the story's Error Envelope section (the concrete RFC 7807 JSON shape) and Enforcement Matrix (test-gate mapping) were dropped rather than carried into the spec; one Out-of-Scope statement about role immutability has an ambiguous referent; and several implied edge cases (unknown-user handling on deactivate, dedicated GET-by-id coverage, the role→permission mapping needed for MU-AC8) are unaddressed by any AC in either document and are surfaced here as open questions rather than defects.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| MU-AC1 | "Given an authenticated admin When GET /v1/admin/users?q=smith&status=active&limit=25 is called Then respond 200 with a cursor-paginated list matching the filters And each item contains id, email, display_name, status, roles, created_at, last_login_at And no password hash, token or other credential material is present in the payload" | Covered | FR-1 | — |
| MU-AC2 | "Given an authenticated user whose roles do not include the users:read permission When GET /v1/admin/users is called Then respond 403 with type \".../errors/insufficient-permission\" And an auth_audit_log entry is written (event=authz_denied)" | Covered | FR-2 | — |
| MU-AC3 | "Given a request with no valid access token When any /v1/admin/* endpoint is called Then respond 401 and the request never reaches the admin handler" | Covered | FR-3 | — |
| MU-AC4 | "Given a request with limit=5000, or an unknown status value, or a malformed cursor When GET /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" And no partial result set is returned" | Covered | FR-4 | — |
| MU-AC5 | "Given an authenticated admin with users:write When POST /v1/admin/users is called with {email, display_name, roles} Then respond 201 with the created resource and its ETag And users.status is \"invited\" and email_verified is false; no password is set And an invitation token (24-hour TTL) is emailed to the address And an admin_audit_log entry is written (actor=admin:{id}, event=user_created)" | Covered | FR-5 | — |
| MU-AC6 | "Given an account already exists with that email (case-insensitive) When POST /v1/admin/users is called Then respond 409 with type \".../errors/email-already-registered\" And no account is created and no invitation is sent" | Covered | FR-6 | See Missing Edge Cases — concurrent duplicate creation not addressed |
| MU-AC7 | "Given a request body containing a \"password\" field When POST /v1/admin/users is called Then respond 422 with type \".../errors/validation-failed\" Because admins must never know or choose another person's password" | Covered | FR-7 | — |
| MU-AC8 | "Given an admin whose own permission set does not include a permission granted by the requested role When POST /v1/admin/users is called with that role Then respond 403 with type \".../errors/privilege-escalation\" And no account is created" | Covered | FR-8 | See Missing Edge Cases — role→permission mapping source undefined |
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

- **[Medium] Error envelope shape dropped from the spec** — The source story defines a concrete RFC 7807 `application/problem+json` schema under "## Error Envelope" (story lines 245–255), e.g. `{"type": "...", "title": "Last Administrator", "status": 409, "detail": "...", "instance": "/v1/admin/users/{id}/deactivate"}`, plus the full list of error `type` slugs introduced by this story. The spec's FRs (e.g. FR-2, FR-6, FR-8) state only the status code and `type` slug ("responds `403` with type `.../errors/insufficient-permission`") but never reproduce the required envelope fields (`title`, `status`, `detail`, `instance`) anywhere in the spec. A developer or QA engineer cannot write a conformance test for an error response body from the spec alone — they would need to go back to the source story (or ask) for the required JSON shape.

- **[Low] Enforcement Matrix (test-gate mapping) omitted** — The story's "## Enforcement Matrix" (lines 264–274) maps each AC group to a test mechanism and a `[gate]` marker (e.g. "MU-AC16 | Concurrency test: two simultaneous deactivations of the last two admins | `[gate]`"). The spec has no equivalent section. This doesn't block understanding the functional requirements, but it does mean the spec alone doesn't tell engineering which scenarios are release-gating versus advisory, or that MU-AC16 specifically requires a concurrency test — information present in the source and not carried forward.

- **[Low] "roles is immutable through this endpoint" — ambiguous referent** — Spec says (Out of Scope): "Role assignment (US-3.2) — `roles` is immutable through this endpoint," carried verbatim from the story's Out of Scope section. Elsewhere, FR-5 (create) explicitly accepts `roles` in the `POST /v1/admin/users` request body, while FR-11 (update) explicitly rejects `roles` in the `PATCH` body as an immutable field. Read in isolation, the Out-of-Scope bullet doesn't say which endpoint it means, so a reader could momentarily conclude roles can never be set anywhere — only cross-referencing FR-5 and FR-11 resolves it. This ambiguity originates in the source story itself (story line 39) and was carried over unchanged rather than clarified.

## Contradictions With Original Story

None found. Every spec requirement checked traces back to matching AC text with no conflicting status codes, conditions, or stated behavior.

## Scope Creep

None found. The Functional Requirements, Non-Functional Requirements, and Out of Scope sections all restate the source's ACs, NFR/Security list, and Out-of-Scope list without adding new fields, endpoints, systems, or behaviors. The one addition to the NFR section (the search-index requirement) is explicitly attributed to the story's own Data Model Notes rather than presented as new scope.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low-Medium] Concurrent duplicate-email creation** — MU-AC6/FR-6 specify that a duplicate email is rejected with `409`, but neither the story nor the spec states whether this is enforced only by a pre-check query or also by a data-layer uniqueness constraint. Does FR-6 need to guarantee correctness under two simultaneous `POST /v1/admin/users` requests for the same email, or is that out of scope for this story?

- **[Low-Medium] Role→permission mapping source for MU-AC8/FR-8 is undefined** — FR-8 requires the system to determine "a permission granted by the requested role" to detect privilege escalation, but no Data Model Notes (in either document) describe where a role's permission set is stored or how it's resolved. Is this mapping expected to already exist (e.g., owned by US-3.2 "Manage Roles") and simply referenced here, or does this story need to define it?

- **[Low] No dedicated AC/FR for `GET /v1/admin/users/{id}`** — The story's "In Scope" and API Contract list `GET /v1/admin/users/{id}` (single-resource fetch, "200 + ETag") as in scope, and the spec's Background section repeats this. However, MU-AC1–MU-AC4 (and their FR-1–FR-4 counterparts) only exercise the list endpoint `GET /v1/admin/users`; no AC tests the single-user fetch's success response, its behavior on an unknown id, or its permission check. Is this endpoint meant to be covered by inference from the list ACs, or is dedicated coverage missing?

- **[Low] Deactivate slice has no explicit "unknown user" case** — Unlike Update (MU-AC12/FR-12) and Resend-invite (MU-AC21/FR-21), the Deactivate slice (MU-AC13–MU-AC17/FR-13–FR-17) has no AC covering `POST /v1/admin/users/{id}/deactivate` against a non-existent user id. Does this fall through to a generic 404, or was it intentionally left unspecified in the source?

## Verdict Rationale

Pass with Issues: AC coverage is complete (21/21 Covered) and no contradictions or scope creep were found, so nothing here blocks implementation outright. However, the dropped Error Envelope schema (Medium) leaves error-response bodies unverifiable from the spec alone, and several implied edge cases and one ambiguous Out-of-Scope statement (Low/Low-Medium) are worth resolving — either by amending the spec or by confirming with the story owner that they're deliberately deferred — before engineering treats this as final.
