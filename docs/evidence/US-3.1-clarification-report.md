# US-3.1 (Manage Users) — Clarification Report

## Scope, Actors, Business Value

**Actor:** Administrator (MFA-mandatory, per `personas.md`). **Trigger:** provisioning, finding, correcting, or withdrawing access for a colleague's account — five independently shippable slices sharing one Acceptance Criteria prefix (`MU-AC`). **Business value:** the directory stays accurate and access can be withdrawn "the moment it should be" (`docs/stories/US-3.1-manage-users.md` User Story), without an admin ever handling another person's password (Invitation-only creation, `business-glossary.md`'s "Invitation" entry).

In scope: `GET /v1/admin/users` (list/search), `GET /v1/admin/users/{id}` (single fetch), `POST /v1/admin/users` (create by invitation), `PATCH /v1/admin/users/{id}` (correct whitelisted fields), `POST /v1/admin/users/{id}/deactivate`, `POST /v1/admin/users/{id}/resend-invite`. `DELETE /v1/admin/users/{id}` exists only to return `405`. Out of scope: role assignment (US-3.2 owns `roles`), email change (US-1.3's verified flow), bulk export, permanent deletion (US-1.4 DA-AC9's retention job).

## Dependency Check

`docs/stories/README.md` states US-3.1 depends on US-1.4 (the DA-AC10 invariant — admin deactivation must apply DA-AC1's side effects identically) and US-3.2 (permission scopes). Both are confirmed merged to `main`: US-1.4 as PR #1, US-3.2 as PR #9 (merged before US-2.5 resumed, per `docs/workflow/workflow-state.yaml` history). `app/modules/account/` (US-1.4) and `app/modules/roles/` (US-3.2) are both live in the current codebase. **No blocking dependency** — this story can proceed on the current `main` as-is.

## What's Clear

- All 21 Acceptance Criteria (MU-AC1–MU-AC21) across the five slices are concrete, testable Given/When/Then statements — confirmed Covered 1:1 by the pre-existing spec's FR-1–FR-21 with an accurate traceability matrix (`docs/reviews/specifications/US-011-spec-review.md`).
- Authorization model (`users:read`/`users:write` scopes, not role-string comparison), the 401-vs-403 anonymous/insufficient-permission split, invitation-only creation with no admin-set password, and `If-Match`-required `PATCH` are all stated directly in the story's Assumptions & Defaults table and carried through the spec unchanged.
- Six items the pre-existing spec/review left as open (concurrent duplicate-email creation, the role→permission mapping for privilege-escalation checks, Deactivate's missing unknown-user case, the invitation-token shape, the resend rate-limit mechanism, and the last-admin-check mechanism) are **already resolved by reading the real US-1.4/US-3.2 codebase** shipped since the spec was drafted — see the Open Decisions log's "Resolved by existing implementation" section. None of these need a new decision; each has a direct, working precedent to reuse.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-3.1-open-decisions.md` for full detail. Summary:

- **OD-1 (Medium):** `admin_audit_log` already exists (built by US-3.2) with a role-specific shape (`old_roles`/`new_roles` arrays) that doesn't fit MU-AC9/FR-9's per-field Update audit requirement (`field`, `old_value`, `new_value`). The pre-existing spec's Data Model Notes assumed this table didn't exist yet.
- **OD-2 (Medium):** `account_lifecycle_audit_log` already exists (built by US-1.4) with no `reason` column, but MU-AC13/FR-13 requires the admin-deactivation path to persist a mandatory `reason`.
- **OD-3 (Low):** `GET /v1/admin/users/{id}` is listed as in-scope by both the story and the spec but has zero Acceptance Criteria — a real gap the spec review already flagged and that persists unresolved.

Two more items are carried forward as disclosed, non-blocking Open Questions (deferred second-admin-approval requirement; one ambiguous Out-of-Scope wording) — neither blocks specification.

A pre-existing draft spec and review (`docs/specifications/US-011-manage-users-spec.md`, `docs/reviews/specifications/US-011-spec-review.md`, both 2026-08-22) already exist for this story, following the same pattern that paid off for US-2.4/US-2.5/US-2.6. The review's own "Missing Edge Cases" findings substantially corroborate this run's independent read — four of its five items resolve outright against the now-shipped US-1.4/US-3.2 code, and the fifth (GET-by-id coverage) is confirmed still open. This run additionally surfaced OD-1 and OD-2, neither of which the 2026-08-22 review could have caught since `admin_audit_log` and `account_lifecycle_audit_log` didn't exist in their current shipped form until US-3.2 and US-1.4 respectively landed after that date.

## Readiness Verdict

**Not Ready — see Open Decisions.** Three Open Decisions (OD-1, OD-2, OD-3) need a resolution before `story-spec-writer` can produce a spec whose audit-table interactions and endpoint coverage match the real, already-shipped schema rather than the stale 2026-08-22 assumptions.
