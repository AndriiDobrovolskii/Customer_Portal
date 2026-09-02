# US-2.5 (MFA/TOTP) — Clarification Report

> **Re-run 2026-09-01.** US-3.2 (Manage Roles) reached PR (#9); this report supersedes the original 2026-09-01 run below where they differ. See "Re-run Findings" for what changed.

## Scope, Actors, Business Value

**Actor:** Any user holding (or about to hold) a privileged role — `admin`, `auditor`, `support_agent` — plus any customer who opts in voluntarily. **Trigger:** enrolling a TOTP authenticator, or logging in on an account with MFA already enabled. **Business value:** a stolen or phished password alone no longer reaches the admin console or other customers' data (`docs/product/personas.md`'s Administrator/Support Agent/Auditor personas are all marked "MFA-mandatory").

In scope: enrolment (pending → active), activation with recovery-code issuance, the login-challenge branch and its verification endpoint, brute-force protection on the verify step, and mandatory enforcement for privileged roles including a 14-day rollout grace period. Out of scope: WebAuthn/passkeys, SMS codes, "remember this device" — all explicitly excluded by the story.

## What's Clear

- The TOTP algorithm choice (RFC 6238, SHA-1, 6-digit, 30s step, ±1 step skew) is fully specified and matches `business-glossary.md`'s MFA/TOTP entry.
- Recovery-code count (10), hashing (Argon2id — consistent with project-wide BR-003), and single-use semantics are unambiguous.
- The four endpoints (`enroll`, `activate`, `verify`, `DELETE`) have request/response shapes stated in the API Contract table.
- Brute-force handling (5 failed attempts → 429, token invalidated, full re-auth) is concrete and testable, and follows the same Valkey-counter pattern already established for login (`login_failure_threshold_account/ip` in `app/core/config.py`).
- The replay-protection mechanism (`mfa_used_step:{user_id}:{step}` in Valkey, TTL one time step) is concrete.
- The self-service MFA-disable requirement (current password + valid code) is unambiguous and consistent with the project's "hijacked session can't unilaterally weaken security" pattern (mirrors BR-006's deactivation-revocation discipline).
- Error-type slugs (`mfa-invalid-code`, `mfa-required-for-role`) and the RFC 7807 envelope are given directly.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-2.5-open-decisions.md` for full detail. Summary:

- **OD-1 (blocking):** US-2.5 depends on US-3.2 (Manage Roles) per this project's own `docs/stories/README.md` dependency notes and suggested build order — but US-3.2 has not been implemented. There is no `role` column on `users`, no permission-scope claim in the JWT, no `perm_epoch` mechanism anywhere in the current codebase. MF-AC6 directly cites "US-3.2 MR-AC1" behavior that doesn't exist yet. This is not a guessable detail — it changes whether this story can be built as scoped at all right now.
- **OD-2:** "Envelope encryption with a KMS-managed key" has no existing implementation or precedent in this codebase to follow (no KMS client, no encryption-at-rest utility anywhere in `app/`).
- **OD-3:** MF-AC1's "QR payload" phrase isn't reflected in the API Contract table's two-field response — unclear if a QR image is actually returned.
- **OD-4:** The 14-day grace-period "warning" mechanism (API field vs. email vs. both, and email cadence) is unresolved — the story itself flags the email-cadence half as an open question and doesn't address the API-response half at all.
- **OD-5:** Whether recovery-code consumption (MF-AC7) is a pure notification event or forces an account-level state change is unstated.
- **OD-6:** Whether disabling MFA should set `revoke_before` (matching the precedent set by password reset and deactivation) is unstated.

## Re-run Findings (2026-09-01)

- **OD-1 is resolved.** US-3.2 reached PR (#9, open/unmerged, `mergeable_state: clean`, every stage Pass). The checked-out codebase (`feat/us-3.2-manage-roles`) now has the fixed role catalogue, the JWT `scopes` claim, and the `perm_epoch` mechanism, matching `business-rules.md` BR-010/BR-011/BR-013 exactly — confirmed by reading `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`, `app/core/security.py`, and `app/core/revocation_cache.py`. `users/service.py` already establishes the precedent of a module depending on `roles.service` (`resolve_scopes_for_user`) for token issuance, which a new MFA module can follow. Caveat: PR #9 is unmerged, so a US-2.5 feature branch must be based on `feat/us-3.2-manage-roles`, not `main`, until it merges.
- **New: OD-7.** Reading US-3.2's actual shipped spec (`docs/specifications/US-012-manage-roles-spec.md`) surfaced that MF-AC6's citation of "US-3.2 MR-AC1" describes a behavior (issuing an enrolment-scoped token when a privileged role is granted) that MR-AC1, as specified and built, does not contain — MR-AC1 covers only role-set replacement, `perm_epoch`, and the audit log. This isn't a case of "the shape differed from what MF-AC6 assumed" (the original OD-1 worried about that) — it's that the specific cross-reference is simply fictional. OD-7 also needed an exit condition MF-AC6 never states (what un-scopes the token after activation — resolved via `perm_epoch`, mirroring BR-011) and is coupled to OD-4 (same clause). See `docs/decisions/US-2.5-open-decisions.md` OD-7.
- **A pre-existing draft spec (US-009) and its review already exist** (`docs/specifications/US-009-mfa-totp-spec.md`, `docs/reviews/specifications/US-009-spec-review.md`, both 2026-08-22) — the same pattern that paid off for US-2.4/US-008. Unlike US-008, this pre-existing spec does **not** resolve any of OD-2/3/4/5/6/7 by precedent — it independently carries the identical ambiguities as its own unresolved Open Questions (corroborating they're real gaps, not artifacts of this pipeline's own reading). It did surface three gaps this pipeline's first CLARIFICATION run missed: **OD-8** (the `DELETE /v1/auth/mfa` success path, non-privileged disable, has zero AC/FR coverage at all — flagged "[High]" by the spec review; absorbs OD-6 as one sub-part), **OD-9** (recovery-code exhaustion has no defined path), and **OD-10** (whether recovery-code failures share MF-AC5's brute-force counter). The spec's own Open Questions section separately raised **OD-11** (re-enrolling into an existing PENDING enrolment).
- OD-2, OD-3, OD-5 are unaffected by US-3.2 landing and remain open exactly as originally logged. OD-6 is superseded/absorbed by OD-8.

## Readiness Verdict

**Ready for Specification** (as of 2026-09-01 — all Open Decisions resolved by the user).

All 11 Open Decisions are resolved; see `docs/decisions/US-2.5-open-decisions.md`'s Resolutions Summary. One resolution (OD-5) overrides the recommended default: recovery-code consumption forces a degraded `mfa_reenrollment_required` state rather than being purely advisory, which generalizes OD-7's enrolment-scoped-token mechanism into a two-trigger primitive (privileged-role grant, or recovery-code use) — `story-spec-writer` must reflect this as one shared mechanism, not role-specific plumbing. Process decision (independent of spec content, needed before IMPLEMENTATION): merge US-3.2's PR #9 first, then branch `feat/us-2.5-mfa-totp` from `main` — avoids the stacked-PR/deleted-base-branch trap that hit US-2.4's PR #7.
