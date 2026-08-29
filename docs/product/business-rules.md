# Global Business Rules

## BR-001

Customer email is unique across accounts, and the comparison is case-insensitive; leading/trailing whitespace is trimmed before both the format check and the duplicate check. Enforced atomically at the data layer so concurrent registrations for the same email cannot both succeed.

**Source:** `docs/specifications/US-001-register-user-spec.md` FR-2. Reused verbatim for admin-created accounts (`US-011-manage-users-spec.md` FR-6) and for a profile email change (`US-003-update-profile-spec.md` FR-10).

---

## BR-002

A newly registered account cannot authenticate until its email is verified; an unverified account is deleted automatically 7 days after creation if never verified.

**Source:** `docs/specifications/US-002-verify-email-spec.md` FR-5, FR-10.

---

## BR-003

Password hashing is Argon2id, project-wide — login verification, registration, password reset, MFA recovery codes. This was a live inconsistency (the stories' Assumptions & Defaults tables specified Argon2id deliberately, e.g. for its timing-safe/GPU-resistant properties, while `AGENTS.md`/`docs/ARCHITECTURE.md` and the already-shipped US-001 implementation used bcrypt) resolved on 2026-08-29 in favor of Argon2id — see `docs/decisions/password-hashing-algorithm.md`. `AGENTS.md`, `docs/ARCHITECTURE.md`, `pyproject.toml`, `app/core/security.py`, `app/core/config.py`, `.env.example`, and the affected integration test were all updated to match.

**Source:** `docs/stories/US-2.1-login.md` Assumptions & Defaults #6; `docs/specifications/US-005-login-spec.md` FR-3, `US-008-password-reset-spec.md` FR-2, `US-009-mfa-totp-spec.md` FR-2; `AGENTS.md` §2, §7 (updated); `docs/decisions/password-hashing-algorithm.md`.

---

## BR-004

A password, in any form (plaintext or hash), must never appear in an API response, and must never appear in application logs, traces, or APM payloads.

**Source:** `docs/specifications/US-001-register-user-spec.md` FR-6; `US-005-login-spec.md` NFR.

---

## BR-005

Login never distinguishes "no such account" from "wrong password" in status code, body, or response timing — a dummy password-verification cost is paid even when the account doesn't exist. The same anti-enumeration discipline applies to email-verification resend and password-reset request.

**Source:** `docs/specifications/US-005-login-spec.md` FR-3, NFR; `US-002-verify-email-spec.md` FR-8; `US-008-password-reset-spec.md` FR-3.

---

## BR-006

Deactivating an account (self-service or admin-initiated) immediately revokes every access and refresh token by setting `revoke_before:{user_id}`; a deactivated account cannot log in (`403`), but a *wrong-password* attempt against a deactivated account still returns the generic `401` — deactivation status is never leaked to a caller who hasn't proven the password. Admin-initiated deactivation applies the identical revocation invariant as self-service.

**Source:** `docs/specifications/US-004-deactivate-account-spec.md` FR-1, FR-6, FR-7, FR-10; `US-011-manage-users-spec.md` FR-13.

---

## BR-007

A deactivated account can self-reactivate by logging in within a 30-day grace period; after 30 days with no login, a scheduled job permanently deletes or anonymizes the account (exact mechanics pending legal/DPO sign-off).

**Source:** `docs/specifications/US-004-deactivate-account-spec.md` FR-8, FR-9.

---

## BR-008

A refresh token is single-use; reusing an already-consumed token in a family is treated as probable theft, revokes every token in that family immediately, and triggers a security-notification email — not just a silent rejection.

**Source:** `docs/specifications/US-007-refresh-token-spec.md` FR-1, FR-2.

---

## BR-009

Logging out ends only the current device's session by default; "logout everywhere" (`revoke_before`) ends every session for the account at once. Both are idempotent — a repeat logout is not an error.

**Source:** `docs/specifications/US-006-logout-spec.md` FR-1, FR-2, FR-4.

---

## BR-010

The role catalogue is fixed: `customer`, `support_agent`, `admin`, `auditor` — no custom or tenant-defined roles. Application code authorizes on permission *scope* (`users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`), read from the JWT, never on a role-name string comparison.

**Source:** `docs/specifications/US-012-manage-roles-spec.md`, Background.

---

## BR-011

A role assignment change takes effect on the account's next access-token refresh (via `perm_epoch`), not by force-revoking the whole session (`revoke_before`) — a permission change and a security revocation are deliberately different mechanisms.

**Source:** `docs/specifications/US-012-manage-roles-spec.md` FR-2, NFR.

---

## BR-012

An administrator can never modify their own role assignment or deactivate their own account through the admin endpoints (self-service endpoints exist for that), cannot grant a permission they don't themselves hold (no privilege escalation), and the system refuses to leave zero active administrators — the last remaining admin cannot be demoted or deactivated via the admin API.

**Source:** `docs/specifications/US-011-manage-users-spec.md` FR-15, FR-16; `US-012-manage-roles-spec.md` FR-5, FR-6, FR-7.

---

## BR-013

MFA (TOTP) is mandatory for the `admin`, `auditor`, and `support_agent` roles, with a 14-day rollout grace period for a newly granted privileged role; MFA cannot be disabled on an account holding one of these roles.

**Source:** `docs/specifications/US-009-mfa-totp-spec.md` FR-6.

---

## BR-014

The audit log is append-only: no actor, including an administrator, can update or delete an entry through the API or at the database level (the application's DB role holds `INSERT`/`SELECT` only on audit tables). Every audit-log read is itself audited, and every authorization denial is audited even though the underlying action failed.

**Source:** `docs/specifications/US-013-view-audit-information-spec.md` FR-2, FR-3, FR-4; `US-011-manage-users-spec.md` NFR.

---

## BR-015

An internal ticket reply (agent-only note) is invisible to the ticket's customer at both the application layer and the database layer (PostgreSQL Row-Level Security) — the isolation holds even if application code forgets to filter. A customer can never create an internal reply.

**Source:** `docs/specifications/US-015-ticket-replies-spec.md` FR-3, FR-5.

---

## BR-016

A ticket-creation or reply request is rejected with a uniform "not owned" error if it references an `attachment_id` uploaded by a different user, already bound to another ticket, or unknown — the response never reveals which of the three reasons applied (IDOR prevention).

**Source:** `docs/specifications/US-014-support-tickets-spec.md` FR-9.

---

## BR-017

A resolved ticket auto-closes after 7 days with no further reply; a customer reply within that window reopens it instead. Both the auto-close job and the reopen-on-reply guard read the same 7-day constant so the boundary instant belongs to exactly one outcome.

**Source:** `docs/specifications/US-016-ticket-resolution-spec.md` FR-3, FR-4, NFR.
