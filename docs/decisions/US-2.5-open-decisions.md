# US-2.5 (MFA/TOTP) — Open Decisions

## OD-1 — BLOCKING: US-3.2 (Manage Roles) has not been implemented yet — RESOLVED

**Resolution (2026-09-01):** Option A — pause US-2.5, run US-3.2 (Manage Roles) through the full pipeline first, matching this project's documented build order. `docs/workflow/active-story.yaml` and `workflow-state.yaml` repointed to US-3.2; US-2.5 remains BLOCKED (not abandoned) until US-3.2 reaches PR/merge, at which point US-2.5's clarification should be re-run against the then-current codebase (the role/scope shape US-3.2 actually ships may differ from what MF-AC6 assumed).

**Question:** Proceed with US-2.5 now (and, if so, how should the parts of it that depend on a role/permission-scope system that doesn't exist yet be handled), or build US-3.2 first as the codebase's own dependency notes prescribe?

**Why it can't be inferred:**
- `docs/stories/README.md` states explicitly: *"US-2.5 depends on US-2.1 and US-3.2 (permission scopes)"* and its suggested build order places US-3.2 **before** US-2.5 (`"US-3.2 first (everything else checks its scopes)... then US-2.6, US-2.5..."`).
- Checked the actual codebase (`app/modules/users/models.py`, `app/core/security.py`): the `users` table has no `role` column, there is no role catalogue, no permission-scope claim in the JWT (`encode_access_token` only sets `sub`, `jti`, `exp`), and no `perm_epoch` mechanism. None of this exists — US-3.2 has not been run through the pipeline (no `docs/catalog/US-3.2*` or `US-012*` files, no role/scope code anywhere in `app/`).
- MF-AC6 explicitly reads: *"when such a role is granted to a user without MFA (US-3.2 MR-AC1), that user's next login issues a token scoped only to the enrolment endpoints until enrolment completes"* — this cites a specific acceptance criterion (MR-AC1) of a story that hasn't been specified, let alone built.
- BR-013 ("MFA mandatory for admin/auditor/support_agent") and BR-010/BR-011 (role catalogue, permission scopes in JWT, `perm_epoch`) are asserted in `business-rules.md` as if already live, but nothing in the codebase backs them yet — the business-rules doc appears to have been written against the eventual full system, not the current state of the repo (the same pattern already found and resolved for US-2.4/US-008's pre-existing spec).

**Impact of leaving unresolved:** MF-AC6 (privileged-role enforcement, the enrolment-scoped token, the 14-day grace period tied to a role grant) cannot be implemented, tested, or even meaningfully specified — there is no role to check, no scope to enforce, and no MR-AC1 to hand off to. A spec-writer would have to either invent role/permission infrastructure from scratch (silently absorbing US-3.2's scope into this story) or silently drop MF-AC6 from the spec.

**Options for the user:**
- **(A) Reorder the backlog:** pause US-2.5, run US-3.2 (Manage Roles) through the full pipeline first, matching the project's own documented build order. Resume US-2.5 afterward with the role/scope system actually in place.
- **(B) Descope for now:** specify and build only the role-independent parts of US-2.5 (MF-AC1, MF-AC2, MF-AC3, MF-AC4, MF-AC5, MF-AC7 — enrolment, activation, the login challenge, brute-force protection, recovery codes), explicitly deferring MF-AC6 (privileged-role mandate + enrolment-scoped token) to a follow-up once US-3.2 lands. `users.mfa_enabled` becomes fully self-service in the interim; nothing is mandatory yet.
- **(C) Build minimal role scaffolding now:** implement just enough of the role/permission-scope system inside this story to satisfy MF-AC6 (a `role` column, a JWT `scopes`/`role` claim, `perm_epoch`), without doing the rest of US-3.2's actual scope (role-assignment endpoints, self-demotion guard, last-admin guard, etc.). Risks duplicated/inconsistent work when US-3.2 is built for real.

---

## OD-2 — Envelope encryption / "KMS-managed key" has no existing implementation

**Question:** What concretely backs "envelope encryption with a KMS-managed key" (Assumption #4) in this codebase, given there is no KMS integration, no encryption-at-rest utility, and no secrets-manager client anywhere in `app/`?

**Why it can't be inferred:** Checked `app/core/config.py`, `app/core/security.py`, and grepped the whole `app/` tree for KMS/encrypt/Fernet/AESGCM — nothing exists. `config.py`'s existing pattern for a sensitive key (`jwt_secret_key`) is a `SecretStr` env var with an explicit "dev-only insecure default, override in prod" comment — there's no precedent in this codebase for talking to a real cloud KMS.

**Impact of leaving unresolved:** A spec-writer has no established pattern to point to for "encrypted at rest, KMS-managed key" and would have to invent either a real KMS client integration (a new external dependency, out of proportion for a project with no cloud-provider integration anywhere else) or a local stand-in — unclear which, and the choice changes the spec's infrastructure requirements materially.

**Likely resolution (for the user to confirm or override):** follow the `jwt_secret_key` precedent — a local symmetric key (e.g. AES-GCM) from an env var/settings field, documented as a dev-only stand-in for a real KMS-managed key in production, the same way OD-1 was resolved for US-2.4's breached-password check (local static resource standing in for a live external service).

---

## OD-3 — MF-AC1's "QR payload" vs. the API Contract's two-field response

**Question:** Does `POST /v1/auth/mfa/enroll` return an actual QR code image (e.g. base64 PNG), or does "QR payload" in MF-AC1's prose just mean the `otpauth_uri` that a client renders into a QR code itself?

**Why it can't be inferred:** MF-AC1 says the response contains *"a TOTP secret (otpauth:// URI + QR payload)"* — phrased as two things. But the API Contract table lists only two response fields: `secret` and `otpauth_uri`, no QR/image field. `business-glossary.md` and `business-rules.md` don't mention QR codes at all.

**Impact of leaving unresolved:** Ambiguous whether the response schema needs a third field (e.g. a base64-encoded PNG) or whether "QR payload" is just describing what the client does with `otpauth_uri`. Affects the response schema and whether a QR-generation library becomes a new dependency.

---

## OD-4 — Grace-period warning mechanism (carries forward the story's own stated Open Question)

**Question:** During the 14-day rollout grace period, MF-AC6 says login "warns the user" — is that warning a field in the login API response (e.g. `mfa_enrollment_deadline`), an email, or both? On what schedule are any warning emails sent? (The story's own "Open Questions" section already flags the email cadence as unresolved; this decision also covers the API-level warning mechanism, which the story doesn't address at all.)

**Why it can't be inferred:** Not covered by `business-rules.md`, `business-glossary.md`, or the story body beyond the one Open Question line about email cadence.

**Impact of leaving unresolved:** Affects the login response schema (whether it gains a new field for non-MFA-enrolled privileged users) and whether an email-sending mechanism/schedule needs to be built as part of this story or deferred.

---

## OD-5 — MF-AC7: is "prompted to re-enrol" advisory or does it force a state change?

**Question:** When a recovery code is consumed (MF-AC7), does the account stay `mfa_enabled = true` with one fewer recovery code (and the email is purely advisory), or does consuming a recovery code force the account into some kind of re-enrolment-required state?

**Why it can't be inferred:** MF-AC7's Gherkin only says "the user is emailed a security notification and prompted to re-enrol" — it doesn't state whether `mfa_enabled` or any other account field changes as a result, and no business rule addresses recovery-code consumption.

**Impact of leaving unresolved:** Determines whether recovery-code consumption needs any state-machine change beyond marking that one code `consumed_at`, or whether it needs a new pending/degraded MFA state and matching enforcement logic.

---

## OD-6 — Does disabling MFA set `revoke_before` (session revocation), matching the precedent for other credential changes?

**Question:** `DELETE /v1/auth/mfa` removes a second factor from the account. Per the glossary's `Revocation (revoke_before)` entry, `revoke_before` is set on logout-everywhere, deactivation, and password reset. MFA disable isn't in that list. Should it be added — should disabling MFA revoke all other active sessions, the same way a password reset does?

**Why it can't be inferred:** The story's Non-Functional/Security Requirements say disabling MFA requires both the password and a valid code (so a hijacked session alone can't strip the second factor), but says nothing about what happens to *other* sessions after a legitimate disable. `business-rules.md`/`business-glossary.md` don't extend the `revoke_before` list to cover this case.

**Impact of leaving unresolved:** Affects whether `DELETE /v1/auth/mfa`'s service logic needs to call the same revocation-cache write that password reset and deactivation use.
