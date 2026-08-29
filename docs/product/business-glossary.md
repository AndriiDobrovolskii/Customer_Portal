# Business Glossary

## Customer

A person who registers an account to access the Customer Portal (`docs/specifications/US-001-register-user-spec.md`). Holds the `customer` role by default.

---

## Account

The persisted `users` row for a Customer or staff member: email, password hash, `status` (`invited` / `active` / `deactivated`, or implicitly `pending_verification` before `email_verified`), and role assignments (`docs/specifications/US-001-register-user-spec.md`, `US-011-manage-users-spec.md`).

---

## Registration

Self-service account creation with email and password; the account starts unverified and cannot log in until email verification completes (`US-001-register-user-spec.md` FR-1; `US-002-verify-email-spec.md` FR-5).

---

## Invitation

Admin-initiated account provisioning: an admin creates a `users` row in `invited` status with no password, and a 24-hour invitation token is emailed for the invitee to complete setup — the admin never sets or knows the password (`US-011-manage-users-spec.md` FR-5, FR-7).

---

## Authentication

Verifying a Customer's or staff member's identity via email + password (`POST /v1/auth/login`), optionally followed by an MFA challenge for privileged roles (`US-005-login-spec.md`, `US-009-mfa-totp-spec.md`).

---

## Session

The period during which an authenticated caller can act, backed by an access token (short-lived JWT) and a refresh token (long-lived, rotating). A session corresponds to one refresh-token family (`family_id`) and can be listed and individually revoked (`US-010-active-session-management-spec.md` FR-1).

---

## Refresh Token / Token Family

A single-use, rotating credential that renews an access token without re-authentication. All refresh tokens issued from the same original login share a `family_id`; reusing an already-consumed token in the family is treated as theft and revokes the whole family (`US-007-refresh-token-spec.md` FR-1, FR-2).

---

## Revocation (`revoke_before`)

A per-user Valkey timestamp; any access or refresh token issued before it is rejected on next use. Set on logout-everywhere, deactivation, and password reset — kills the entire session including refresh (`US-006-logout-spec.md` FR-2, `US-004-deactivate-account-spec.md` FR-1, `US-008-password-reset-spec.md` FR-2).

---

## Permission Epoch (`perm_epoch`)

A per-user Valkey timestamp distinct from `revoke_before`: invalidates only access tokens (forcing a scope refresh via `/auth/refresh`) when a role assignment changes, without forcing a full re-login (`US-012-manage-roles-spec.md` FR-2, NFR).

---

## MFA / TOTP

Time-based one-time-password second factor (RFC 6238, SHA-1, 6 digits, 30-second step), mandatory for `admin`, `auditor`, and `support_agent` roles, with a 14-day rollout grace period and single-use recovery codes for device loss (`US-009-mfa-totp-spec.md` FR-1, FR-6, FR-7).

---

## Role

A named, fixed catalogue entry (`customer`, `support_agent`, `admin`, `auditor`) that grants a set of permission scopes. Custom/tenant-defined roles are not supported (`US-012-manage-roles-spec.md`, Background).

---

## Permission Scope

The actual unit application code checks (`users:read`, `users:write`, `roles:write`, `audit:read`, `tickets:read`, `tickets:write`), read from the JWT `scopes` claim — never a role-name string comparison (`US-012-manage-roles-spec.md`, Background).

---

## Administrator

Staff role that manages the user directory and role assignments; MFA-mandatory; cannot deactivate or demote themselves, cannot grant a permission they don't hold, and the system blocks removing the last remaining admin (`US-011-manage-users-spec.md` FR-15, FR-16; `US-012-manage-roles-spec.md` FR-5–FR-7).

---

## Support Agent

Staff role that handles support tickets: replies (public or internal), and marks tickets resolved. MFA-mandatory (`US-009-mfa-totp-spec.md` FR-6; `US-015-ticket-replies-spec.md`, `US-016-ticket-resolution-spec.md`).

---

## Auditor

Staff role holding `audit:read`, able to query the audit log but never modify it — audit tables grant `INSERT`/`SELECT` only at the database level, to anyone (`US-013-view-audit-information-spec.md` FR-4). MFA-mandatory.

---

## Profile

A Customer's own editable, non-sensitive account fields (`display_name`, `locale`, `timezone`, `avatar_url`); email changes require a separate confirmed, re-authenticated flow (`US-003-update-profile-spec.md`).

---

## Audit Log

An append-only, tamper-evident record (hash-chained via a database trigger) of security- and admin-relevant events across five domain tables (`auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`, `ticket_audit_log`), unioned into one queryable view (`US-013-view-audit-information-spec.md` FR-7, Data Model Notes).

---

## Support Ticket

A customer-raised issue with a human-readable, non-guessable `ticket_number`, a lifecycle (`open` → `waiting_on_support`/`waiting_on_customer` → `resolved` → `closed`, with reopen), and threaded replies (`US-014-support-tickets-spec.md`, `US-016-ticket-resolution-spec.md`).

---

## Ticket Reply

A message on a ticket thread, either `public` (visible to the customer) or `internal` (agent-only, enforced by PostgreSQL Row-Level Security so the isolation holds even if application code forgets to filter) (`US-015-ticket-replies-spec.md` FR-3, FR-5).
