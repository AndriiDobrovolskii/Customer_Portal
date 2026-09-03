# US-2.5 (MFA/TOTP) — Open Decisions

## Resolutions Summary (2026-09-01)

All decisions below are resolved by the user. Branch strategy (process decision, not a spec OD): **merge US-3.2's PR #9 first, then branch `feat/us-2.5-mfa-totp` from `main`** — avoids the stacked-PR/deleted-base-branch trap that hit US-2.4's PR #7.

| OD | Resolution |
|---|---|
| OD-1 | Resolved — US-3.2 reached PR, role/scope system confirmed live. |
| OD-2 | Local AES-GCM key via settings, dev-only stand-in for a real KMS (recommended option). |
| OD-3 | No third response field — client renders `otpauth_uri` into a QR code itself (recommended option). |
| OD-4 + OD-7 | Net-new US-2.5 login-time logic; grace-period warning is a login-response field; `perm_epoch` set on activation un-scopes the token (recommended option, in full). |
| OD-5 | **Overridden the recommendation.** Recovery-code use forces a degraded re-enrolment-required state (see OD-5 below for the exact mechanics chosen). |
| OD-6 + OD-8 | Full recommended resolution: `mfa_enabled→false`, secret+codes purged, `mfa_disabled` audit event, AND `revoke_before` set. |
| OD-9 | Out of scope for this story, deferred to a future support-mediated recovery story (recommended option). |
| OD-10 | Shared brute-force counter for TOTP and recovery-code attempts (recommended option). |
| OD-11 | Re-enroll always issues a fresh secret, overwriting the pending one (recommended option). |

## OD-1 — BLOCKING: US-3.2 (Manage Roles) has not been implemented yet — RESOLVED

**Resolution (2026-09-01):** Option A — pause US-2.5, run US-3.2 (Manage Roles) through the full pipeline first, matching this project's documented build order. `docs/workflow/active-story.yaml` and `workflow-state.yaml` repointed to US-3.2; US-2.5 remains BLOCKED (not abandoned) until US-3.2 reaches PR/merge, at which point US-2.5's clarification should be re-run against the then-current codebase (the role/scope shape US-3.2 actually ships may differ from what MF-AC6 assumed).

**Re-confirmed 2026-09-01 (clarification re-run):** US-3.2 reached PR (GitHub PR #9, open, `mergeable_state: clean`, not yet merged to `main`) with every pipeline stage Pass. The checked-out codebase (`feat/us-3.2-manage-roles`, the branch this session is on) now has the role/permission-scope system live and matching `business-rules.md` BR-010/BR-011/BR-013 exactly:
- A fixed, seeded role catalogue — `customer`, `support_agent`, `admin`, `auditor` (`migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`).
- A JWT `scopes` claim, not a role-name claim (`app/core/security.py::encode_access_token`).
- A `perm_epoch:{user_id}` Valkey mechanism, separate from `revoke_before`, that invalidates access tokens only (`app/core/revocation_cache.py::PermissionEpochCache`).
- `app/modules/users/service.py` already depends on `roles.service.resolve_scopes_for_user` to build the `scopes` claim at login/refresh — establishing the precedent that a new MFA module may depend on the `roles` module the same way, per `AGENTS.md` §3 layering.

OD-1 is resolved: the structural blocker is gone. **Caveat carried forward, not blocking:** PR #9 is unmerged. Any US-2.5 feature branch should be based on `feat/us-3.2-manage-roles` (or created only after #9 merges) — branching from `main` today would not see the roles module at all.

**See OD-7 below** — re-reading US-3.2's actual shipped spec (`docs/specifications/US-3.2-spec.md`) surfaced a second problem MF-AC6's text depends on, which OD-1's original framing didn't anticipate: the "MR-AC1" behavior MF-AC6 cites does not exist.

---

## OD-2 — Envelope encryption / "KMS-managed key" has no existing implementation

**Question:** What concretely backs "envelope encryption with a KMS-managed key" (Assumption #4) in this codebase, given there is no KMS integration, no encryption-at-rest utility, and no secrets-manager client anywhere in `app/`?

**Why it can't be inferred:** Checked `app/core/config.py`, `app/core/security.py`, and grepped the whole `app/` tree for KMS/encrypt/Fernet/AESGCM — nothing exists. `config.py`'s existing pattern for a sensitive key (`jwt_secret_key`) is a `SecretStr` env var with an explicit "dev-only insecure default, override in prod" comment — there's no precedent in this codebase for talking to a real cloud KMS.

**Impact of leaving unresolved:** A spec-writer has no established pattern to point to for "encrypted at rest, KMS-managed key" and would have to invent either a real KMS client integration (a new external dependency, out of proportion for a project with no cloud-provider integration anywhere else) or a local stand-in — unclear which, and the choice changes the spec's infrastructure requirements materially.

**Likely resolution (for the user to confirm or override):** follow the `jwt_secret_key` precedent — a local symmetric key (e.g. AES-GCM) from an env var/settings field, documented as a dev-only stand-in for a real KMS-managed key in production, the same way OD-1 was resolved for US-2.4's breached-password check (local static resource standing in for a live external service).

**RESOLVED (2026-09-01):** Recommended option accepted — local AES-GCM key via settings, dev-only stand-in for a real KMS-managed key in production.

---

## OD-3 — MF-AC1's "QR payload" vs. the API Contract's two-field response

**Question:** Does `POST /v1/auth/mfa/enroll` return an actual QR code image (e.g. base64 PNG), or does "QR payload" in MF-AC1's prose just mean the `otpauth_uri` that a client renders into a QR code itself?

**Why it can't be inferred:** MF-AC1 says the response contains *"a TOTP secret (otpauth:// URI + QR payload)"* — phrased as two things. But the API Contract table lists only two response fields: `secret` and `otpauth_uri`, no QR/image field. `business-glossary.md` and `business-rules.md` don't mention QR codes at all.

**Impact of leaving unresolved:** Ambiguous whether the response schema needs a third field (e.g. a base64-encoded PNG) or whether "QR payload" is just describing what the client does with `otpauth_uri`. Affects the response schema and whether a QR-generation library becomes a new dependency.

**RESOLVED (2026-09-01):** No third field — `otpauth_uri` is the payload; the client renders it into a QR code itself. Response schema stays exactly the two fields already in the API Contract table (`secret`, `otpauth_uri`). No QR-generation library added.

---

## OD-4 — Grace-period warning mechanism (carries forward the story's own stated Open Question)

**Question:** During the 14-day rollout grace period, MF-AC6 says login "warns the user" — is that warning a field in the login API response (e.g. `mfa_enrollment_deadline`), an email, or both? On what schedule are any warning emails sent? (The story's own "Open Questions" section already flags the email cadence as unresolved; this decision also covers the API-level warning mechanism, which the story doesn't address at all.)

**Why it can't be inferred:** Not covered by `business-rules.md`, `business-glossary.md`, or the story body beyond the one Open Question line about email cadence.

**Impact of leaving unresolved:** Affects the login response schema (whether it gains a new field for non-MFA-enrolled privileged users) and whether an email-sending mechanism/schedule needs to be built as part of this story or deferred.

**RESOLVED (2026-09-01), together with OD-7:** Login-response field (e.g. `mfa_enrollment_deadline`) during the grace period, not email. Email-cadence question is moot under this resolution — no warning email is sent; the field is refreshed on every login until enrolment completes.

---

## OD-5 — MF-AC7: is "prompted to re-enrol" advisory or does it force a state change?

**Question:** When a recovery code is consumed (MF-AC7), does the account stay `mfa_enabled = true` with one fewer recovery code (and the email is purely advisory), or does consuming a recovery code force the account into some kind of re-enrolment-required state?

**Why it can't be inferred:** MF-AC7's Gherkin only says "the user is emailed a security notification and prompted to re-enrol" — it doesn't state whether `mfa_enabled` or any other account field changes as a result, and no business rule addresses recovery-code consumption.

**Impact of leaving unresolved:** Determines whether recovery-code consumption needs any state-machine change beyond marking that one code `consumed_at`, or whether it needs a new pending/degraded MFA state and matching enforcement logic.

**RESOLVED (2026-09-01) — user overrode the recommended (advisory-only) resolution.** Recovery-code use forces a degraded state, chosen over the alternative of fully disabling MFA (which would have reused OD-8's disable logic outright):

- `mfa_enabled` stays `true`; the existing secret and remaining recovery codes are untouched.
- A new flag, `users.mfa_reenrollment_required: bool`, is set to `true` on the consumed code's `UPDATE`.
- `auth_audit_log` event `mfa_recovery_used` is written (in addition to marking that one code `consumed_at`).
- The *next* successful login (password + a valid TOTP code or another recovery code) issues an **enrolment-scoped token** — reusing the exact same mechanism OD-7 builds for the privileged-role case — instead of a full-access token, regardless of role.
- Completing a fresh enrol+activate cycle (MF-AC1/MF-AC2) clears `mfa_reenrollment_required` and sets `perm_epoch:{user_id}`, the same exit condition OD-7 uses — one shared un-scoping mechanism serves both triggers (privileged-role grant, and recovery-code use).
- Consequence for `story-spec-writer`: the enrolment-scoped-token mechanism (OD-7) is no longer solely a privileged-role feature — it must be designed as a general "account requires re-enrolment" primitive with two independent triggers. Flag this explicitly in the spec so it isn't built as role-specific plumbing that later needs reworking.

---

## OD-6 — Does disabling MFA set `revoke_before` (session revocation), matching the precedent for other credential changes?

**Note:** This is one sub-part of the broader **OD-8** gap (the whole disable-success path has no AC coverage) — resolve together.

**Question:** `DELETE /v1/auth/mfa` removes a second factor from the account. Per the glossary's `Revocation (revoke_before)` entry, `revoke_before` is set on logout-everywhere, deactivation, and password reset. MFA disable isn't in that list. Should it be added — should disabling MFA revoke all other active sessions, the same way a password reset does?

**Why it can't be inferred:** The story's Non-Functional/Security Requirements say disabling MFA requires both the password and a valid code (so a hijacked session alone can't strip the second factor), but says nothing about what happens to *other* sessions after a legitimate disable. `business-rules.md`/`business-glossary.md` don't extend the `revoke_before` list to cover this case.

**Impact of leaving unresolved:** Affects whether `DELETE /v1/auth/mfa`'s service logic needs to call the same revocation-cache write that password reset and deactivation use.

**RESOLVED (2026-09-01), as part of OD-8:** Yes — `revoke_before` is set, matching password-reset/deactivation precedent. Full accepted resolution (see OD-8).

---

## OD-7 — NEW (found on re-clarification): MF-AC6 cites a "US-3.2 MR-AC1" behavior that US-3.2 never specified or built

**Question:** MF-AC6 says *"when such a role is granted to a user without MFA (US-3.2 MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes."* Since no such mechanism exists anywhere in US-3.2, must this "enrolment-scoped token" behavior be designed and built entirely fresh within US-2.5 (triggered from US-2.5's own login logic), or should it instead require a change to US-3.2's `PUT /v1/admin/users/{id}/roles` endpoint (e.g. a hook fired on role assignment) — which would be new scope added to an already-shipped, PR'd story?

**Why it can't be inferred:**
- Read `docs/specifications/US-3.2-spec.md` (US-3.2's actual shipped spec) in full, including its Traceability Matrix's verbatim MR-AC1 text: *"...Then respond 200 with the resulting role set And the operation is a full replacement... And perm_epoch:{target_id} is set to now in Valkey And an admin_audit_log entry is written..."* — nothing about MFA, enrolment, or a scoped token anywhere in MR-AC1, any other FR, or the NFRs.
- Grepped `app/modules/roles/` for `mfa` (case-insensitive): zero matches.
- The JWT carries only a `scopes` claim (`app/core/security.py`), not a role name — so "issue a token scoped only to the enrolment endpoints" cannot mean "give it the normal scopes minus some"; it must mean something new (e.g. a distinct token type/audience), which has no precedent in this codebase's token design (compare to the existing `mfa_token` concept MF-AC3 already introduces for the *login-challenge* case — a plausible reusable pattern, but the story never says so explicitly).
- `resolve_scopes_for_user` (used by `users/service.py`) returns scopes only; nothing in `roles.service` currently exposes "does this user hold role X" by name — a new dependency surface a spec-writer would have to define explicitly rather than infer.

**Impact of leaving unresolved:** Without this decision, a spec-writer risks either (a) assuming a hand-off point already exists in the `roles` module and inventing one that doesn't match how US-3.2 was actually built, or (b) silently proposing to reopen and modify the already-PR'd US-3.2/US-3.2 endpoint, which is out of this story's stated scope and would need separate sign-off. It also determines whether US-2.5 needs a new `roles.service` method (role names, not just scopes) as a cross-module dependency.

**Likely resolution (for the user to confirm or override):** Treat this as net-new US-2.5 logic, checked at login time (alongside MF-AC3's challenge branch), not a change to US-3.2: on every successful password verification, look up the user's role names (a new read-only `roles.service` method, mirroring the existing `resolve_scopes_for_user` dependency pattern already established in `users/service.py`) and if any is `admin`/`auditor`/`support_agent` and `mfa_enabled` is false, apply the enrolment-scoped-token/grace-period behavior — no change to US-3.2's endpoints or spec.

**Exit condition (missing from the story, needed for a complete resolution):** MF-AC6 says the scoped token holds "until enrolment completes" but never states what un-scopes it. `perm_epoch` already exists for exactly this shape of problem — BR-011's discipline is that a permission change (not a security revocation) refreshes transparently via `perm_epoch`, and completing enrolment is a permission change. Recommended: on `POST /v1/auth/mfa/activate` (MF-AC2) succeeding, also set `perm_epoch:{user_id}`; the next call with the old enrolment-scoped token 401s `token-stale`, and `/auth/refresh` then issues a normal, fully-scoped token. Without this, a spec-writer builds a one-way door with no documented way back to normal access.

**Coupling note:** This decision and **OD-4** (grace-period warning mechanism) are the same MF-AC6 clause — "issues a scoped token" (this OD) and "each login warns the user and records the outstanding enrolment" (OD-4) both describe what happens during the same grace-period login. Resolve them together, not independently, so the login-response shape and the enrolment-tracking mechanism are designed once.

**RESOLVED (2026-09-01):** Recommended resolution accepted in full — net-new US-2.5 login-time logic (new `roles.service` method returning role names), `perm_epoch` set on activation as the exit condition, grace-period warning delivered as a login-response field (OD-4). **Extended by OD-5's override:** the same enrolment-scoped-token/exit-condition mechanism is now also triggered by recovery-code consumption, not just a privileged-role grant — see OD-5 for the second trigger and the shared `mfa_reenrollment_required` flag.

---

## OD-8 — NEW (surfaced by the pre-existing US-2.5 spec review): `DELETE /v1/auth/mfa`'s success path (204, non-privileged disable) has zero AC/FR coverage

**Question:** MF-AC6 only describes the *blocked* disable (privileged role, 409). No acceptance criterion in the story describes what happens when a non-privileged user's disable actually succeeds: does `users.mfa_enabled` become `false`? Are `mfa_secret_encrypted` and the recovery codes purged or merely orphaned? Is an `mfa_disabled` event (already listed in the story's own Data Model Notes) written to `auth_audit_log`?

**Why it can't be inferred:** `docs/reviews/specifications/US-2.5-spec-review.md` flagged this independently as a "[High]" gap on 2026-08-22, before this pipeline's own re-clarification: *"no MF-AC narrates the success path's behavior... this looks like a genuine gap worth flagging upstream rather than silently absorbing."* The story's API Contract table documents the `204` response but no Gherkin covers it. This absorbs and supersedes the narrower **OD-6** question below (whether disable sets `revoke_before`) — OD-6 is one sub-part of this broader gap.

**Impact of leaving unresolved:** Without this, `story-spec-writer` has an endpoint with a documented request/response shape but no behavioral specification at all for its main success path — the single largest coverage gap in the story.

**Likely resolution (for the user to confirm or override):** On successful disable: `mfa_enabled → false`, `mfa_secret_encrypted → NULL`, all recovery codes for the user deleted (not just marked consumed — they're worthless without a secret, keeping them is pure liability), `auth_audit_log` event `mfa_disabled` written. Plus OD-6's `revoke_before` question below.

**RESOLVED (2026-09-01):** Full recommended resolution accepted — `mfa_enabled → false`, secret set `NULL`, all recovery codes deleted, `auth_audit_log` event `mfa_disabled` written, AND `revoke_before:{user_id}` set (OD-6) so every other active session is revoked, matching the deactivation/password-reset precedent (BR-006).

---

## OD-9 — NEW (surfaced by the pre-existing US-2.5 spec review): Recovery-code exhaustion has no defined path

**Question:** MF-AC7 describes consuming one recovery code. What happens once a user has consumed all 10 and still cannot access their authenticator — is a support-mediated recovery path expected as part of this story, or is that deliberately out of scope (like WebAuthn/SMS)?

**Why it can't be inferred:** Flagged independently by `docs/reviews/specifications/US-2.5-spec-review.md` ("[Medium]", Missing Edge Cases) on 2026-08-22. Neither the story's Out of Scope list nor its Open Questions mention this case.

**Impact of leaving unresolved:** Determines whether this story needs an admin-mediated MFA-reset flow (a new endpoint, likely gated by a `users:write`-equivalent scope) or can legitimately ship without one, deferring "locked out with zero recovery codes" to a follow-up story.

**Likely resolution (for the user to confirm or override):** Out of scope for this story, same footing as WebAuthn/SMS/remember-device — a locked-out user must go through an out-of-band support process (matching this project's existing "break-glass is a runbook, not an API" pattern from US-3.2 OD-2), formalized as its own future story rather than absorbed here.

**RESOLVED (2026-09-01):** Recommended option accepted — out of scope for this story, deferred to a future support-mediated recovery story.

---

## OD-10 — NEW (surfaced by the pre-existing US-2.5 spec review): Do recovery-code failures count toward the MF-AC5 brute-force counter?

**Question:** MF-AC5 counts "5 failed verification attempts against the same `mfa_token`" without distinguishing a wrong TOTP code from a wrong recovery code, both submitted to the same `POST /v1/auth/mfa/verify` endpoint. Does a wrong recovery code increment the same failure counter as a wrong TOTP code?

**Why it can't be inferred:** Flagged independently by `docs/reviews/specifications/US-2.5-spec-review.md` ("[Low]") on 2026-08-22. `business-rules.md`/`business-glossary.md` don't distinguish the two attempt types.

**Impact of leaving unresolved:** Minor but affects the verify-endpoint's implementation — whether the brute-force check is one shared counter or two independent code paths sharing the same Valkey key namespace.

**Likely resolution (for the user to confirm or override):** Yes, shared counter — both are guesses against the same `mfa_token`, and MF-AC5's stated rationale ("must not be guessable online") applies equally to a 10-recovery-code guess space, which is smaller than the 6-digit TOTP space and therefore needs the *same* protection, not less.

**RESOLVED (2026-09-01):** Recommended option accepted — shared counter for TOTP and recovery-code attempts against the same `mfa_token`.

---

## OD-11 — NEW (surfaced by the pre-existing US-2.5 spec, its own Open Questions): Re-enrolling while a PENDING enrolment already exists

**Question:** What happens when `POST /v1/auth/mfa/enroll` is called again for a user who already has a PENDING (not yet activated) enrolment — re-issue a new secret, return the existing pending secret, or error?

**Why it can't be inferred:** `docs/specifications/US-2.5-spec.md` (the pre-existing draft spec, 2026-08-22) lists this as its own unresolved Open Question; neither the story nor `business-rules.md`/`business-glossary.md` address it.

**Impact of leaving unresolved:** Affects whether `/v1/auth/mfa/enroll` needs idempotency/upsert logic or can simply always insert-and-overwrite.

**Likely resolution (for the user to confirm or override):** Re-issue a new secret each time (overwrite the pending one), matching MF-AC1's own stated invariant that an unfinished enrolment "can never lock the user out" — the previous pending secret was never activated, so nothing is lost by replacing it, and this avoids a stale-secret QR code being scanned after the user re-requested enrolment.

**RESOLVED (2026-09-01):** Recommended option accepted — always issue a fresh secret, overwriting any existing pending one.
