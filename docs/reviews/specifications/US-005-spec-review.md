# Spec Review: Login

**Original Story:** docs/stories/US-2.1-login.md
**Spec Reviewed:** docs/specifications/US-005-login-spec.md (2026-08-31 revision, incorporating resolved Open Decisions OD-1–OD-7)
**Story ID:** US-005 (spec's own Story ID field; the backlog story itself is filed as US-2.1)
**Reviewed:** 2026-08-31
**Overall Verdict:** Pass with Issues

## Summary

All six Acceptance Criteria (LI-AC1–LI-AC6) remain fully and accurately covered by FR-1–FR-6, with no contradictions. The revision resolves both findings from the prior review (2026-08-22): response/error/audit JSON shapes are now explicitly stated as complete in their dedicated schema sections, and the `auth_audit_log` field list is now spelled out per-FR. One new, lower-severity item emerges from the revision itself: several audit-logging clauses in FR-3 and FR-4 (the specific `reason` values `unknown_email`, `email_not_verified`, `account_deactivated`) are not present in LI-AC3/LI-AC4's literal text — they trace to resolved Open Decisions (OD-3, OD-4) made during clarification, not to the story's Acceptance Criteria themselves. The spec discloses this honestly via its "Derived from" citations, so it does not rise to a blocking finding, but it's worth the record showing where story-derived requirements end and decision-derived requirements begin.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| LI-AC1 | "Given an active user whose email is verified When POST /v1/auth/login is called with the correct email and password Then respond 200 with an access token (JWT, 15-minute TTL) in the body And set a refresh token as an HttpOnly, Secure, SameSite=Strict cookie (Path=/v1/auth) And an auth_audit_log entry is written (event=login_succeeded) And users.last_login_at is updated" | Covered | FR-1 | Unchanged from prior review; still fully covered. |
| LI-AC2 | "Given an active, verified user When POST /v1/auth/login is called with an incorrect password Then respond 401 with problem+json type \".../errors/invalid-credentials\" And no token of any kind is issued And an auth_audit_log entry is written (event=login_failed, reason=bad_password)" | Covered | FR-2 | Unchanged from prior review; still fully covered. |
| LI-AC3 | "Given an email address that is not registered When POST /v1/auth/login is called with that email and any password Then respond 401 with the same body, status and comparable timing as LI-AC2 Because a dummy Argon2id verification is performed so response time does not reveal account existence" | Covered | FR-3 | Timing/body/status requirement covered per the story; the audit-logging clause added to FR-3 (`reason=unknown_email`) is not itself part of LI-AC3's text — see Scope Creep below. |
| LI-AC4 | "Given correct credentials are supplied When the account is unverified Then respond 403 with type \".../errors/email-not-verified\" ... When the account is deactivated Then respond 403 with type \".../errors/account-deactivated\" ... And in both cases credential verification runs first, so an attacker without the password only ever sees 401" | Covered | FR-4 | Both branches and the ordering guarantee are preserved; the audit-logging clauses added (`reason=email_not_verified` / `account_deactivated`) are not themselves part of LI-AC4's text — see Scope Creep below. |
| LI-AC5 | "Given 10 failed login attempts for the same account within 15 minutes When POST /v1/auth/login is called again for that account Then respond 429 with a Retry-After header and type \".../errors/too-many-attempts\" And the same limit applies independently per source IP (20 attempts / 15 minutes) And a successful login resets the account counter" | Covered | FR-5 | Now also states the per-IP counter's non-reset explicitly (was silent, now resolved and stated) — a clarification of a genuine story silence, not a new requirement. |
| LI-AC6 | "Given a request body missing \"password\", or containing an unknown field When POST /v1/auth/login is called Then respond 422 with type \".../errors/validation-failed\" And the errors array names the offending field(s) And no login attempt is recorded against the rate-limit counter" | Covered | FR-6 | Unchanged from prior review; still fully covered. |

## Ambiguities & Non-Verifiable Statements

Both findings from the 2026-08-22 review are resolved in this revision:

- ~~Concrete response/error JSON shapes not reproduced~~ — **Resolved.** The Error Envelope Schema section now states explicitly "Every response of this shape carries all five fields: `type`, `title`, `status`, `detail`, `instance`," and the Success Response Schema section retains the full `access_token`/`token_type`/`expires_in` shape. Both are now unambiguous without needing to cross-reference the source story.
- ~~`auth_audit_log` field composition not specified~~ — **Resolved.** The Audit Log Schema section now states "every entry, regardless of `event`/`reason`, is populated with the full field set below" and enumerates all seven fields (`event`, `reason`, `actor_id`, `ip`, `user_agent`, `request_id`, `occurred_at`), including which FRs populate `actor_id` as null.

No new ambiguities were introduced by this revision.

## Contradictions With Original Story

None found. The Assumption Resolutions section, the revised Non-Functional Requirements entry on token signing, and the two added Out of Scope entries all correct the spec's prior alignment with the story's *own* Assumptions & Defaults table (Assumption #2, #3) rather than conflicting with it — the story's Assumptions table and the actual shipped codebase disagreed, and the spec now sides with the codebase per an explicit resolved decision, which is disclosed rather than silently substituted.

## Scope Creep

- **[Low] FR-3's and FR-4's audit-logging clauses derive from resolved Open Decisions, not from LI-AC3/LI-AC4's literal text.** Spec says (FR-3): "An `auth_audit_log` entry is written (`event=login_failed`, `reason=unknown_email`)..." (`docs/specifications/US-005-login-spec.md`, FR-3); similarly FR-4 for `email_not_verified`/`account_deactivated`. LI-AC3 and LI-AC4 in the story say nothing about audit logging at all — only LI-AC1 and LI-AC2 mention `auth_audit_log` explicitly. The spec is honest about this (each FR's "Derived from" line cites "resolved OD-3" / "resolved OD-4" rather than claiming the AC itself required it), and the underlying decision (`docs/decisions/US-2.1-open-decisions.md`) was made deliberately by the user during clarification — so this is not an error, just a place where spec content extends past the story's own AC text via a properly-tracked side channel rather than the AC itself. Worth flagging so a future reader auditing "does every spec sentence trace to an AC" knows where the answer is "no, it traces to a recorded decision instead."
- **[Low] NFR and Out of Scope additions for token signing and mobile transport trace to the story's Assumptions & Defaults table, not to any AC.** Spec adds (NFR): "Access tokens are signed with the project's existing HS256 shared-secret scheme... this story does not introduce RS256 signing or a JWKS endpoint" and (Out of Scope): the same plus the mobile-transport exclusion. These are grounded in the story's own Assumption #2/#3 rows (`docs/stories/US-2.1-login.md`, lines 15–16) plus resolved OD-1/OD-2 — not scope creep in the sense of inventing new behavior, but noted here because, like the item above, neither addition is anchored to a numbered AC (LI-AC1–6), only to the story's Assumptions table and the decision log.

## Missing Edge Cases, Boundary Conditions & Error Handling

None found beyond what the prior review already covered (none were flagged there either). Does LI-AC6's "missing `password`" also cover an empty-string password (`"password": ""`)? The story and spec are both silent on this distinction — flagging as a question rather than a defect, since it's unclear whether the story's scope intended to address it.

## Verdict Rationale

Pass with Issues: full AC coverage with no contradictions, so this does not rise to Fail. The Scope Creep items are both Low severity and both transparently disclosed in the spec's own "Derived from" citations rather than hidden — they reflect the spec correctly absorbing clarification-stage decisions, not drift introduced by the spec-writer. Recommend proceeding to DESIGN; no further spec revision is required unless the user wants the empty-password question in Missing Edge Cases resolved first.

## Addendum — FR-4 reactivation branch (OD-10), reviewed 2026-08-31

**Trigger:** an `advisor()` consultation during the PLANNING→IMPLEMENTATION handoff cross-referenced `docs/stories/US-1.4-deactivate-account.md` DA-AC8 and `docs/specifications/US-004-deactivate-account-spec.md` FR-8/`US-004-api-design.md` (which explicitly assigns "reactivation on login within the 30-day grace period" to this story) against this spec's FR-4, and found FR-4 only implemented the unconditional-403 half. User resolved OD-10: build reactivation now. FR-4 was amended accordingly (see the spec's own revision history).

**AC-coverage re-check:** LI-AC4's own text (story source) states only the two `403` branches — it does not mention reactivation at all. The reactivation branch traces instead to DA-AC8 (a different story's AC), correctly disclosed in FR-4's "Derived from" line and in the Traceability Matrix's LI-AC4 row rather than misattributed to LI-AC4 itself. This is the same pattern as OD-9's `refresh_tokens` table and this review's own earlier Scope Creep findings (FR-3/FR-4's audit-logging clauses) — content justified by a resolved cross-story decision, not by the AC text, and transparently labeled as such. Not a new Scope Creep finding requiring its own bullet above; consistent with how this review already treats that class of addition.

**No contradiction found:** the amended FR-4 is internally consistent (grace-period boundary is the sole discriminator between the two deactivated-account branches) and does not conflict with anything else in this spec (FR-1's success path is reused verbatim for the reactivation case, not duplicated).

**Verdict unchanged:** Pass with Issues stands. This addendum does not introduce a new blocking finding.
