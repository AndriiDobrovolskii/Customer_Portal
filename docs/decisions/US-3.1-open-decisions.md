# Open Decisions: US-3.1 Manage Users

**Story:** `docs/stories/US-3.1-manage-users.md` (five slices, `MU-AC` prefix)
**Pre-existing spec:** `docs/specifications/US-3.1-spec.md` (drafted 2026-08-22, Pass with Issues per `docs/reviews/specifications/US-3.1-spec-review.md`, predates the actual US-1.4/US-3.2 codebase now in place).
**Logged:** 2026-09-02

## Resolutions (2026-09-02)

All three Open Decisions below were resolved by the user on 2026-09-02, recommended option accepted in every case:

- **OD-1:** Add nullable `field`/`old_value`/`new_value`/`reason` columns to the existing `admin_audit_log` table, reused across both role-replacement rows and this story's per-field Update rows.
- **OD-2:** Add a nullable `reason` column to `account_lifecycle_audit_log`, populated only by the admin-initiated deactivation path.
- **OD-3:** `story-spec-writer` adds new FR(s) for `GET /v1/admin/users/{id}` with no source AC (US-2.6 FR-6/FR-7 precedent).

## Resolved by existing implementation (not logged as Open Decisions)

Checking the pre-existing spec's and its review's open items against the real codebase (US-1.4's `account` module and US-3.2's `roles` module, both merged since the spec was drafted) resolves four of them outright:

- **Concurrent duplicate-email creation (spec review "Missing Edge Cases" item 1)** — already governed by `business-rules.md` BR-001: email uniqueness is "enforced atomically at the data layer so concurrent registrations for the same email cannot both succeed," and BR-001's own Source line already cites reuse "for admin-created accounts (`US-3.1-manage-users-spec.md` FR-6)." No new mechanism needed; FR-6 just needs to state the atomic-constraint enforcement explicitly rather than implying a pre-check query only.
- **Role→permission mapping source for MU-AC8/FR-8 (spec review "Missing Edge Cases" item 2)** — already built by US-3.2. `app/modules/roles/models.py`'s `Role.permissions` relationship and `RoleRepository.get_by_names()` resolve a role name list to its flattened permission-scope set, and `RoleService.replace_user_roles` (`app/modules/roles/service.py` lines 162-176) already implements the exact `requested_permissions.issubset(actor_scopes)` privilege-escalation check MU-AC8 needs, including the `authz_denied`-audit-then-raise sequence. US-3.1's create-user privilege-escalation check should call into the roles module the same way (mirroring the cross-module read pattern US-2.5 already established for `users.service` → `roles.service`), not invent a second mapping mechanism.
- **Deactivate slice's missing "unknown user" case (spec review "Missing Edge Cases" item 4)** — resolved by precedent within this same spec: Update (MU-AC12/FR-12) and Resend-invite (MU-AC21/FR-21) both already specify a generic `404` for an unknown user id. There is no stated reason for Deactivate to diverge; recommend the identical `404`.
- **Invitation-token shape ("same shape as US-1.2's tokens")** — confirmed accurate. `app/modules/email_verification/models.py`'s `EmailVerificationToken` (`token_hash`, `user_id`, `issued_at`, `expires_at`, `consumed_at`) and `app/modules/users/models.py`'s `PasswordResetToken` are both already built to this exact shape; a new `invitation_tokens` table following the same columns is a direct precedent match, not a new pattern.
- **Resend rate-limit mechanism ("mirroring US-1.2 VE-AC7")** — confirmed accurate. `app/modules/email_verification/service.py`'s `resend_verification` already implements a cooldown-plus-`Retry-After` pattern (`settings.resend_cooldown_seconds`) that FR-20 can reuse directly, adapted to the per-account/per-hour counting FR-20 additionally requires.
- **Last-admin protection mechanism (MU-AC16)** — resolved by precedent, not previously flagged as ambiguous but worth confirming: `RoleService`'s `count_active_admins_excluding` (via `UserRoleRepositoryProtocol`) already implements the exact "how many other active admins remain" query US-1.4/US-3.2's last-admin invariant needs (`business-rules.md` BR-012). US-3.1's deactivate-check should call the same mechanism rather than re-deriving it.

## OD-1 (Medium) — `admin_audit_log`'s existing shape doesn't fit per-field Update audit rows

**Question:** MU-AC9/FR-9 requires "one `admin_audit_log` row per changed field (`old_value`, `new_value`, `actor`, `reason`)" for the Update slice (`PATCH /v1/admin/users/{id}`). But `admin_audit_log` already exists — it was built by US-3.2 (`app/modules/roles/models.py`'s `AdminAuditLog`) with columns `id`, `event`, `actor_id`, `target_id`, `old_roles` (`ARRAY(String(32))`), `new_roles` (`ARRAY(String(32))`), `severity`, `request_id`, `occurred_at`. There is no generic `field`, `old_value`, `new_value`, or `reason` column, and `old_roles`/`new_roles` are role-name arrays, not generic before/after values for an arbitrary field like `display_name`.

**Why it can't be inferred:** The pre-existing spec's Data Model Notes (written 2026-08-22, before US-3.2 shipped) describe `admin_audit_log` as if it were still to be created with exactly the columns FR-9 needs — that assumption is now stale. Neither the story nor the spec anticipated that a same-named table would already exist with a different, narrower shape built for a different story's needs.

**Impact if left unresolved:** `db-designer` can't decide whether to extend the existing table (and how — new nullable columns alongside the role-specific ones, risking a wide/sparse table) or introduce a second table, and `service-and-router-builder` can't write FR-9's per-field audit write without a settled column set.

**Recommendation:** Extend the existing `admin_audit_log` table with nullable `field: str | None`, `old_value: str | None`, `new_value: str | None`, and `reason: str | None` columns, reused across both this story's per-field Update rows and US-3.2's role-replacement rows (which continue to populate `old_roles`/`new_roles` and leave the new columns null, and vice versa). One table per the glossary's existing "`admin_audit_log`" domain-table concept is simpler than splitting audit tables per story, and every other audit table in this codebase (`auth_audit_log`, `account_lifecycle_audit_log`) already tolerates nullable event-specific columns for exactly this reason (e.g. `auth_audit_log.reason`/`.scope` are optional and mean different things depending on `event`).

## OD-2 (Medium) — `account_lifecycle_audit_log` has no column for the admin-supplied deactivation `reason`

**Question:** MU-AC13/FR-13 requires the admin-deactivation endpoint to accept a mandatory `{reason}` and states its side effects are "exactly US-1.4 DA-AC1's side effects... per the DA-AC10 invariant," writing to `account_lifecycle_audit_log`. But the real `account_lifecycle_audit_log` table (`app/modules/account/models.py`) has only `id`, `user_id`, `event`, `actor` (a formatted string, e.g. `"self"` or presumably `"admin:{admin_id}"`), and `occurred_at` — no `reason` column. The self-service deactivation path (DA-AC1) never captures a reason, so this gap wasn't visible until the admin path made `reason` mandatory.

**Why it can't be inferred:** DA-AC10 says the admin path's side effects apply "identically" to the self-service path, which is true for `status`/`deactivated_at`/`revoke_before`/the audit entry's existence — but MU-AC13 additionally requires persisting a `reason` that the self-service path has no equivalent for, and neither US-1.4's spec nor US-3.1's story/spec says where that value is stored.

**Impact if left unresolved:** `db-designer` can't finalize `account_lifecycle_audit_log`'s columns for this story, and `implementation-planner` can't sequence a migration without knowing whether it touches the shared US-1.4 table or a different one.

**Recommendation:** Add a nullable `reason: str | None` column to `account_lifecycle_audit_log`, populated only by the admin-initiated deactivation path (self-service rows leave it `null`, matching how `auth_audit_log.reason` is already optional and event-dependent elsewhere in this codebase). This keeps DA-AC10's "identical side effects" claim true for every column that predates this story while adding the one column only the admin path needs.

## OD-3 (Low) — `GET /v1/admin/users/{id}` is in scope but has zero Acceptance Criteria

**Question:** Both the story's In Scope list/API Contract and the spec's Background repeat `GET /v1/admin/users/{id}` ("200 + ETag") as in scope, but MU-AC1–MU-AC4 (and FR-1–FR-4) only exercise the list endpoint `GET /v1/admin/users`. No AC covers the single-resource fetch's success shape, its `404` on an unknown id, or its `403`/`401` permission checks.

**Why it can't be inferred:** This was already flagged as an unresolved item in the spec review's "Missing Edge Cases" section and carried forward unchanged — nothing in the codebase (US-1.4's or US-3.2's shipped endpoints) establishes a get-by-id precedent for an admin resource that would let this be inferred rather than decided.

**Impact if left unresolved:** If `story-spec-writer` adds FRs for this endpoint without a source AC, `test-writer`/`reconciliation-reviewer` need to know that's expected (mirroring the precedent set by US-2.6's FR-6/FR-7, which had no source AC either); if it's dropped, the story's own API Contract table and this spec's Background both need a correction so they stop listing an endpoint nothing will build or test.

**Recommendation:** Keep the endpoint and have `story-spec-writer` add new FR(s) for it with no source AC (same precedent as US-2.6 FR-6/FR-7): `200` + the same item shape as the list endpoint's entries + ETag on success, `404` on an unknown id, `403`/`401` mirroring FR-2/FR-3's list-endpoint checks. This is the resource an admin naturally lands on after clicking a search result (MU-AC1), and the ETag it returns is exactly what FR-9's `PATCH ... If-Match` flow needs to have come from somewhere.

## Carried forward, non-blocking

- **Second-admin approval for deactivating a privileged account** — raised in US-1.4's own Open Questions (item 3) and carried into this spec's Open Questions unchanged. Deferred twice already with no story picking it up; treated here as a disclosed, non-blocking Open Question rather than a new Open Decision, since neither US-1.4 nor US-3.1 has ever proposed building it.
- **"`roles` is immutable through this endpoint" (Out of Scope) — ambiguous referent** — spec review Low finding, inherited verbatim from the story. FR-5 (create) accepts `roles`; FR-11 (update/`PATCH`) rejects it. Recommend `story-spec-writer` reword the Out-of-Scope bullet to say "through the update endpoint" explicitly rather than leaving the reader to cross-reference FR-5/FR-11. Not blocking — the FRs themselves are unambiguous.

---

## Verdict input

3 Open Decisions (OD-1, OD-2, OD-3) plus 6 items resolved by precedent above are believed to be the complete set of ambiguities; nothing else in the story, the pre-existing spec, or its review appears unresolved.
