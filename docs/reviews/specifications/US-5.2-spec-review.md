---
artifact_type: specification_review
story: US-5.2
version: 2
status: APPROVED
created_at: "2026-09-08T06:33:36Z"
updated_at: "2026-09-08T08:02:31Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: docs/reviews/specifications/US-5.2-spec-review.md
---

# Spec Review: Account & Profile Self-Service (Frontend)

**Original Story:** docs/stories/US-5.2-account-self-service-ui.md
**Spec Reviewed:** docs/specifications/US-5.2-spec.md (version 2)
**Story ID:** US-5.2
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Summary

This is a fresh review of spec v2, not a carry-over of v1's PASS: v1 was rejected by the human at `HUMAN_SPEC_APPROVAL` and reworked to reflect three newly-resolved Open Decisions (OD-1, OD-2, OD-4). All 10 Acceptance Criteria remain Covered. The main scrutiny for this pass — whether FR-2, FR-5, FR-6, and FR-7 correctly cite the resolving Open Decision as authority for their deliberate deviation from PS-AC2/PS-AC5/PS-AC6/PS-AC7's literal wording, rather than silently restating new behavior as if it always matched — checks out: each of the four FRs, their "Derived from" lines, and their Traceability Matrix rows explicitly name the resolving OD and quote what it supersedes, and each cited deviation matches the actual resolution text in `docs/decisions/US-5.2-open-decisions.md` v2. No contradiction or unexplained scope-creep was found in these four FRs. OD-3, OD-5, OD-6, and OD-7 are correctly carried forward, unresolved, as Open Questions. One Low-severity question is raised about FR-2's generalization of OD-1's "first write" framing, and the same two non-blocking findings the v1 review recorded (untracked backend Story for FR-1's deferral; unspecified confirm-email-change failure outcomes) still apply, since the spec's own rework note states no other section changed from v1.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| PS-AC1 | "Given an authenticated user on /settings/profile Then the current display_name, locale, timezone, avatar_url, email, pending_email and email_verified are shown # Blocked on Dependencies & Blockers #1 — no read endpoint exists. This AC cannot be implemented until a backend Story adds GET /profile (or GET /users/me)." | Covered | FR-1 ("Profile View (Deferred)") | Unchanged from v1. The AC itself states it is blocked; FR-1 records that deferred status rather than inventing behavior. |
| PS-AC2 | "Given the profile form When the user changes display_name, locale (en-US \| en-GB) or timezone (IANA name) and saves Then PATCH /profile is called with only the changed fields And If-Match is sent only when an ETag from a previous write in this session is known, and is omitted otherwise And on 200 the form reflects the returned ProfileRead and stores the returned ETag And a 412 shows a \"changed elsewhere, reload\" conflict state instead of silently overwriting" | Covered | FR-2 | Deliberately deviates from the AC's literal "omitted otherwise" clause: sends `If-Match: *` instead of omitting the header when no ETag is known. Correctly and explicitly cited to OD-1's resolution (see below); not a silent contradiction. |
| PS-AC3 | "Given the profile screen When the user submits a new email together with their current password Then PATCH /profile returns 202 and the UI shows a \"confirm the link sent to <pending_email>\" state And the primary email is unchanged until confirmation Given a visitor opens the confirmation link Then POST /profile/confirm-email-change succeeds whether or not they are signed in" | Covered | FR-3 | Unchanged from v1; matches the story including the 202/no-ETag behavior. |
| PS-AC4 | "Given a visitor opens a verification link carrying a token Then POST /auth/verify-email is called and success / expired / invalid each render a distinct outcome And a \"resend verification email\" control calls POST /auth/verify-email/resend and shows a generic confirmation regardless of whether the address exists" | Covered | FR-4 | Unchanged from v1; matches the story. |
| PS-AC5 | "Given an authenticated user without MFA on /settings/security When they start enrollment Then POST /auth/mfa/enroll is called and a locally rendered QR from otpauth_uri is shown alongside the manual secret When they submit a 6-digit code Then POST /auth/mfa/activate is called and the returned recovery_codes are displayed exactly once And the flow cannot be completed until the user explicitly confirms they saved the codes And the codes, secret and otpauth_uri are never written to localStorage, sessionStorage, a cookie, the console, or any third-party request" | Covered | FR-5 | Deliberately deviates: adds a required `current_password` field the AC never names. Correctly and explicitly cited to OD-2's resolution. |
| PS-AC6 | "Given an authenticated user with MFA enabled When they confirm disabling it Then DELETE /auth/mfa is called and the security screen reflects MFA as disabled" | Covered | FR-6 | Deliberately deviates: adds required `current_password` and TOTP `code` fields, plus a session-revocation warning, none of which the AC names. Correctly and explicitly cited to OD-2's resolution (twice — once for the fields, once for the warning). |
| PS-AC7 | "Given an authenticated user on the deactivation screen When they confirm (supplying their current password where the form requires it) Then POST /account/deactivate is called and, on 200, all in-memory auth state is cleared and they land on /login with a confirmation message And the action is behind an explicit, non-accidental confirmation step naming the consequence" | Covered | FR-7 | Deliberately deviates: `current_password` becomes unconditionally required instead of conditional ("where the form requires it"). Correctly and explicitly cited to OD-4's resolution, and mirrored consistently in the new Out of Scope bullet on password-less accounts. |
| XC-AC1 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | Covered | FR-8 | Unchanged from v1; matches the story. |
| XC-AC2 | "Given any form in this Story When a required field is empty or malformed (invalid email shape, non-6-digit MFA code, unknown IANA timezone) Then submission is blocked with a field-level error and no API call is made" | Covered | FR-9 | Unchanged from v1; matches the story. |
| XC-AC3 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | Covered | FR-10 | Unchanged from v1; matches the story. |

## Ambiguities & Non-Verifiable Statements

- **[Low] FR-2 generalizes OD-1's "first write" framing to "whenever no ETag is known"** — OD-1's resolution text (`docs/decisions/US-5.2-open-decisions.md`) is scoped to "the first `PATCH /profile` write in a session, when no ETag is yet known from a prior write." FR-2 states the `If-Match: *` behavior applies "when no ETag is yet known — including on the very first write in a session," which also covers a second scenario the resolution text does not name verbatim: after a `202` email-change response (which "sets no ETag" per the story's own Client State Notes and FR-3), the *next* profile write also has no known ETag even though it isn't literally the session's first write. The generalization is internally consistent with the spec's own FR-3/Client-State-Notes handling and appears to be the only way to avoid a guaranteed 400 on that second scenario too, so this reads as a necessary, reasoned extension rather than an unauthorized one — but it is technically broader than OD-1's resolution as literally worded. Worth confirming at the next `HUMAN_SPEC_APPROVAL` that "whenever no ETag is known" (not just "the first write") is the intended scope of OD-1's resolution, rather than treating this as settled by inference.
- **[Low] PS-AC1 / FR-1 — deferral scope still lacks a tracked backend Story** — Unchanged from v1. FR-1 states the requirement "is deferred until a backend Story adds a read endpoint," but per OD-5 (still `OPEN` in v2), no such backend Story exists in `docs/stories/`. Does not affect FR-1's coverage of PS-AC1, but the deferral's exit condition remains untracked; already surfaced as spec's Open Question 2.
- **[Low] OD-3, OD-6, OD-7 remain open and carry real ambiguity into build** — Correctly carried forward, unresolved, as Open Questions 1, 3, and 4 in spec v2 rather than silently resolved or dropped. This is the expected, non-blocking handling at `SPECIFICATION`/`SPEC_REVIEW` — resolution belongs to a human at `HUMAN_SPEC_APPROVAL` — but each remains a real gap a developer could not act on without an answer (enrollment-scoped-token navigation behavior, locale-list extensibility, timezone picker shape).

## Contradictions With Original Story

None found. FR-2, FR-5, FR-6, and FR-7 each deviate from their source AC's literal wording, but each deviation is explicitly flagged as such (not silently restated as if it always matched), cites the specific resolving Open Decision (OD-1, OD-2, OD-2, OD-4 respectively), and — checked directly against `docs/decisions/US-5.2-open-decisions.md` v2's inline resolution text for each — accurately reflects what the human actually resolved. This is the correct handling of a human-resolved authority superseding an AC's literal text, not a contradiction: the spec is explicit about what changed and why, both in the FR bodies, the "Derived from" lines, and the Traceability Matrix. No other FR, NFR, or section states behavior conflicting with the story's stated scope or user goal.

## Scope Creep

None found. The four cited deviations (FR-2, FR-5, FR-6, FR-7) all trace to a specific resolved Open Decision rather than being invented; the new Out of Scope bullet on password-less accounts likewise traces to OD-4's resolution and is stated as such. No FR, NFR, or Open Question introduces content untraceable to the story or `docs/decisions/US-5.2-open-decisions.md`. The one candidate noted above (FR-2's "whenever no ETag is known" vs. OD-1's literal "first write" framing) is logged as a Low ambiguity rather than Scope Creep, since it is a narrow, internally-necessary generalization rather than new, unrelated behavior.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Confirm-email-change failure outcomes are unspecified, unlike verify-email's** — Unchanged from v1. PS-AC4 requires verify-email to render three distinct outcomes ("success / expired / invalid"), but PS-AC3 specifies no failure outcomes for `POST /profile/confirm-email-change`, and FR-3 inherits that asymmetry. XC-AC1's generic problem+json handling would apply to any 4xx from this endpoint, so this may already be adequately covered — phrased as a question rather than a defect: should confirm-email-change distinguish expired/invalid outcomes the way verify-email does, or is XC-AC1's generic handling sufficient for this endpoint specifically?

## Verdict Rationale

PASS: every AC is Covered (none Missing or Partially Covered) and no Contradiction was found. FR-2, FR-5, FR-6, and FR-7's deliberate deviations from PS-AC2/PS-AC5/PS-AC6/PS-AC7's literal wording are each correctly and explicitly cited to their resolving Open Decision (OD-1, OD-2, OD-2, OD-4), accurately reflect what the human actually resolved, and read as authorized changes rather than unexplained contradictions or scope creep — the specific risk this re-review was asked to scrutinize. The remaining findings (one Low ambiguity on FR-2's generalization scope, OD-3/OD-6/OD-7 still open, the untracked backend Story for FR-1, and the confirm-email-change edge case) are all non-blocking: none are Critical or Major, and the open items are correctly left unresolved for a human at `HUMAN_SPEC_APPROVAL` rather than guessed at here.
