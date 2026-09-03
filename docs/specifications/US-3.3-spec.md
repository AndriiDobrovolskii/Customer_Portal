# Specification: View Audit Information

**Source:** docs/stories/US-3.3-view-audit-information.md
**Story ID:** US-3.3
**Generated:** 2026-08-22
**Revised:** 2026-09-02 — incorporates the resolutions of OD-1, OD-2, OD-11, and OD-12 (`docs/decisions/US-3.3-open-decisions.md`), the four blocking Open Decisions `us-clarifier` raised after checking the story against the real, now-current codebase (US-3.1/US-3.2 landed on `main` after this spec's 2026-08-22 draft). Also folds in the source's Data Model Notes and RFC 7807 error envelope, both flagged as omitted by the pre-existing spec review. Further revised 2026-09-02 after `story-spec-reviewer`'s first re-run (verdict Fail — AU-AC4 Partially Covered and a daily/monthly Contradiction; plus a new High finding, OD-13, resolved same-day) to incorporate OD-13's field-aware redaction resolution. Revised a third time 2026-09-02: the source story itself (`docs/stories/US-3.3-view-audit-information.md`) was amended per the user's choice — AU-AC4 split into this story's API-level scope plus a deferred DB-grant follow-up, and the Data Model Notes partition line corrected to daily — so this spec's AU-AC4/Data Model Notes text below now matches the source directly rather than diverging from it under a disclosed OD.
**Status:** Draft (revised)

## Summary

This spec covers the audit-log query endpoint for administrators and auditors: filtered, cursor-paginated, newest-first retrieval of audit entries; self-auditing of read access; permission-gated access restricted to `audit:read`; API-level immutability; a bounded query window; redaction of sensitive fields; a tamper-evident daily hash chain with a verification job; audit-trail survival through account erasure (proven against a new, minimal, provisional erasure job); and retention of aged entries to cold storage.

## Background

As an auditor or administrator, I want to search a tamper-evident record of who did what and when, so that I can investigate a security incident or answer a compliance request with evidence rather than recollection.

## Open Decision Resolutions (2026-09-02)

- **OD-1 (`audit_log` naming collision — BLOCKING, resolved):** A real, already-shipped table named `audit_log` (`app/modules/email_verification/models.py::AuditLog`) exists, serving BR-002's unrelated 7-day unverified-account purge trail. It is renamed to `unverified_account_purge_log` via a migration, freeing `audit_log` for this story's own artifact (the new central table/view this spec's Data Model Notes describe below).
- **OD-2 (AU-AC8's cited dependency didn't exist — BLOCKING, resolved):** "The US-1.4 DA-AC9 retention job" this story's AU-AC8 depends on was never actually built (DA-AC9 is `[manual]`/deferred pending DPO sign-off in its own story). This story now includes building a minimal, provisional version of that job (a standalone script, matching this project's one existing job precedent, `scripts/purge_unverified_accounts.py`): it anonymizes the erased user's `users` row and redacts direct identifiers on that user's existing audit rows — the minimum needed to make AU-AC8 verifiable end-to-end. The broader anonymize-vs-hard-delete legal/DPO policy question (DA-AC9's own Open Question) remains open and is tracked separately, outside this story.
- **OD-11 (daily vs. monthly partitions — BLOCKING, resolved):** The story contradicted itself (Assumption #4 and AU-AC7 said "daily"; Data Model Notes said "monthly"). Daily partitions are authoritative; the hash chain is scoped per day, matching AU-AC7's literal wording. The source story's own Data Model Notes line was corrected to "daily" (2026-09-02), so the story no longer contradicts itself.
- **OD-12 (AU-AC4's database-grant requirement had no supporting infrastructure — BLOCKING, resolved):** No migration in this codebase has ever issued a `GRANT`/`REVOKE`, and the application's configured database connection is the PostgreSQL superuser role, which cannot be restricted by grants at all. This story ships only the API-level `405 Method Not Allowed` on `PATCH`/`PUT`/`DELETE` against `/v1/admin/audit-logs` (gate-tested). Provisioning a non-superuser, non-owner database role plus the accompanying grant migrations is deferred to a separate, project-wide infrastructure follow-up — it would apply to every audit table already shipped (`auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`), not just this story's. `story-spec-reviewer` correctly flagged this as AU-AC4 Partially Covered on the story's original wording (its Gherkin had both a `405` clause and a DB-grant clause). Rather than carry a permanent disclosed gap, the user chose to amend the source story itself (2026-09-02): AU-AC4's Gherkin now states only the `405` requirement, with the DB-grant invariant moved to a documented note tracking it as a separate, project-wide infrastructure follow-up. AU-AC4 is now honestly, fully Covered.
- **OD-13 (AU-AC8's identifier-redaction mechanism for fields not stored in a dedicated column — High, resolved, raised by `story-spec-reviewer` not `us-clarifier`):** `profile_audit_log` stores profile changes as `field`/`old_value`/`new_value` free text — a `field="display_name"` row has the changed value directly in `old_value`/`new_value`, not a dedicated identifier column, so AU-AC8's redaction requirement couldn't be implemented without knowing how to find it. Resolved: field-aware redaction — the erasure script (OD-2) maintains a known list of identifier-bearing `profile_audit_log.field` values (starting with `display_name`) and redacts `old_value`/`new_value` on that user's matching rows. Identifiers potentially embedded in the `payload` JSONB column remain a separate, still-open question (unchanged from the pre-existing Open Questions).

## Functional Requirements

### FR-1: Filtered Audit Log Query

Given an authenticated actor holding the `audit:read` permission, when `GET /v1/admin/audit-logs` is called with filter parameters (`actor_id`, `event`, `target_id`, `from`, `to`, `cursor`, `limit`), the system responds `200` with a cursor-paginated, newest-first list. Each returned entry contains `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `request_id`, `ip`, `user_agent`, and an `outcome`.

None of the four existing per-domain tables this view unions today (see Data Model Notes) currently carries `actor_role`, `outcome`, or `category` as a stored column, and their identity columns disagree with each other (`account_lifecycle_audit_log` has `user_id` + a free-text `actor` string, not `actor_id`). Whether the view synthesizes these fields for historical rows (e.g. `actor_role` resolved from the current role assignment, `category` derived from the source table, `outcome` defaulted) or this guarantee only holds for rows written after this story's migrations land is not stated in the source and is not decided here — see Open Questions.

**Derived from:** AU-AC1

### FR-2: Reading the Audit Log Is Itself Audited

Given any successful call to `GET /v1/admin/audit-logs`, when the response is returned, the system writes an audit entry (`event=audit_log_viewed`) recording the actor and the exact filter parameters used for that call.

Which underlying table this write lands in is not decided by this spec: OD-1 resolved the naming collision (`audit_log` is freed for this story's own artifact) but not whether that artifact is itself a writable table or a read-only view over the four existing per-domain tables (the source's own Assumption #1 and Data Model Notes describe two different designs — see OD-1's discussion in `docs/decisions/US-3.3-open-decisions.md`). If `audit_log` ends up being a view, this write needs a concrete per-domain target table (`admin_audit_log` is the plausible candidate, by analogy with US-3.2's precedent of writing admin-relevant events there) — see Open Questions.

**Derived from:** AU-AC2

### FR-3: Insufficient Permission Is Rejected and Recorded

Given an authenticated actor who does not hold `audit:read` (e.g. a support agent), when `GET /v1/admin/audit-logs` is called, the system responds `403` with a `problem+json` body of type `.../errors/insufficient-permission`, and the denied attempt is itself recorded in the audit log.

Same open write-target question as FR-2 applies here (see Open Questions).

**Derived from:** AU-AC3

### FR-4: Audit Log Immutability (API Layer)

Given any actor, including an administrator, when `PATCH`, `PUT`, or `DELETE` is attempted against `/v1/admin/audit-logs` or any entry within it, the system responds `405 Method Not Allowed`.

This is this story's full AC scope per the source's own amended AU-AC4 (2026-09-02, OD-12): database-grant enforcement (the application's DB role holding `INSERT`/`SELECT`-only on audit tables) is a separate, project-wide invariant, not unique to this story — the current application database connection is the PostgreSQL superuser role, which cannot be restricted by grants, and no grant-based enforcement exists anywhere in this codebase yet, for any of the audit tables already shipped. It is tracked as a separate infrastructure follow-up (see Out of Scope), not a gap in this story's own coverage.

**Derived from:** AU-AC4 (as amended 2026-09-02).

### FR-5: Query Window Bound Enforcement

Given a request whose `from`/`to` range exceeds 90 days, or which omits both the `from` and `to` bounds, when `GET /v1/admin/audit-logs` is called, the system responds `422` with a `problem+json` body of type `.../errors/range-too-wide`, and the message states the maximum window and suggests the asynchronous export instead.

**Derived from:** AU-AC5

### FR-6: No Secrets in Audit Records

Given any audit entry of any event type, when it is returned via the API or inspected directly in storage, no password, password hash, raw token, session cookie, or full payment identifier appears in any field. Fields marked sensitive are stored redacted (e.g. `"changed"` rather than the actual value).

**Derived from:** AU-AC6

### FR-7: Tamper-Evident Hash Chain (Daily)

Every audit entry carries a `previous_hash` computed by a PostgreSQL `BEFORE INSERT` trigger over the previous row's hash, `occurred_at`, `actor_id`, `event`, `target_id`, and `payload`; the hash column is computed server-side only and the application may never supply it. The chain is scoped per daily partition (OD-11), seeded with the previous day's partition's final hash. When the chain verification job runs over any day's partition, it reports "intact" for an untouched chain, and when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks.

**Derived from:** AU-AC7; partition scope per OD-11.

### FR-8: Audit Trail Survives Account Erasure

Given a user account permanently deleted or anonymised by the retention job (a new, minimal, provisional script built as part of this story per OD-2 — see Open Decision Resolutions), when their historical audit entries are queried, the entries remain, with `actor_id` retained as an opaque UUID, and every direct identifier the entries contained (email, display_name, ip) is redacted or anonymised — so the audit trail stays intact while the link to the natural person is severed.

For identifiers not stored in a dedicated column — concretely, `profile_audit_log.old_value`/`new_value` on a `field="display_name"` row — the erasure script uses field-aware redaction (OD-13): a known list of identifier-bearing `profile_audit_log.field` values, redacting `old_value`/`new_value` on that user's matching rows. Identifiers potentially embedded in the `audit_log.payload` JSONB column are not covered by this mechanism — see Open Questions.

**Derived from:** AU-AC8; erasure-job dependency resolved per OD-2; free-text-field redaction mechanism per OD-13.

### FR-9: Retention to Cold Storage

Given an audit entry older than the 400-day retention period, when the scheduled retention job runs, the entry is moved to cold storage rather than silently dropped, and the job's own execution is recorded.

**Derived from:** AU-AC9

## Data Model Notes

- `audit_log`: `id`, `category`, `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `outcome`, `request_id`, `ip`, `user_agent`, `payload` (JSONB), `previous_hash`, `row_hash`. The name is now free for this artifact — the pre-existing, unrelated `email_verification` table of the same name is renamed to `unverified_account_purge_log` (OD-1).
- Union over the per-domain audit tables that exist today: `auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`. A fifth source, `ticket_audit_log`, doesn't exist yet — Epic 4 (Support Tickets) is unbuilt at this project's current build order. The view is scoped to the four existing tables for this story; extending it to include `ticket_audit_log` is a small follow-up migration once Epic 4 ships (mirrors this project's precedent of `admin_audit_log` being added ahead of every other consumer needing it).
- None of the four existing per-domain tables currently carries the columns this view needs (`previous_hash`/`row_hash`/`category`/`outcome`/`payload`), and their existing columns are inconsistent with each other (e.g. only `auth_audit_log` has `ip`/`user_agent`; only `admin_audit_log` has `target_id`). This story's migration work includes adding the missing columns to all four tables, not just creating the view — carried forward for `implementation-planner`/`db-designer` to size accordingly.
- A covering index on `(occurred_at DESC, actor_id, event)`; daily partitions (OD-11; the source's own Data Model Notes line was corrected 2026-09-02 to match, having originally contradicted Assumption #4/AU-AC7); keyset (not `OFFSET`) pagination.
- `limit`/`cursor` bounds follow the precedent already shipped in `app/modules/admin_users/service.py::list_users`: `limit` capped at 100 (`422` field error, `code="max"`, if exceeded), invalid `cursor` rejected the same way.

**Derived from:** source Data Model Notes section; table name and partition-scope updates per OD-1/OD-11; four-of-five-table scope per the ticket_audit_log/Epic-4 build-order gap; `limit`/`cursor` precedent from the shipped `admin_users` endpoint.

## Response Schemas

### Error Envelope Schema

Applies to the `problem+json` responses referenced by FR-3 and FR-5 (`application/problem+json`, RFC 7807):

```json
{
  "type": "https://portal.internal/errors/range-too-wide",
  "title": "Query Range Too Wide",
  "status": 422,
  "detail": "Audit queries cover at most 90 days. Use the export for wider ranges.",
  "instance": "/v1/admin/audit-logs"
}
```

Error `type` slugs introduced by this story: `range-too-wide`. FR-3's `insufficient-permission` slug follows the same envelope shape but is not introduced by this story.

**Derived from:** source Error Envelope section.

## Non-Functional Requirements

- `request_id` ties an audit entry to the corresponding application log line and trace, which is what makes an investigation tractable.
- Immutability at the API layer must be enforced for every actor, including operators (FR-4); database-grant enforcement is a separate, project-wide follow-up per the source's own amended AU-AC4 (OD-12).
- Any actor holding `audit:read` may read the audit log; nobody — including operators — may edit it, at the API layer.
- Performance target: p95 ≤ 500 ms for a 50-row page over a 30-day window.

**Derived from:** Non-Functional / Security Requirements section of the source; database-grant scope note per OD-12.

## Out of Scope

- Asynchronous bulk export (referenced by AU-AC5 as the alternative for wider ranges; its own story).
- Alerting/SIEM forwarding.
- Log ingestion from infrastructure components — this story covers application audit events only.
- Database-role/grant-based enforcement of AU-AC4 (a non-superuser, non-owner application database role plus `GRANT`/`REVOKE` migrations) — deferred to a separate, project-wide infrastructure follow-up per OD-12; applies to every audit table, not unique to this story.
- The final anonymize-vs-hard-delete policy for account erasure (DA-AC9's own open legal/DPO question) — this story's provisional erasure script (OD-2) anonymizes as an interim mechanic; the policy decision itself stays out of scope.
- `ticket_audit_log` as a union-view source, until Epic 4 (Support Tickets) ships.

**Derived from:** Out of Scope section of the source; database-grant deferral per OD-12; erasure-policy and ticket-table deferrals per OD-2/Data Model Notes.

## Open Questions

- **Write target for FR-2/FR-3's own audit entries:** OD-1 resolved the `audit_log` naming collision but not whether `audit_log` is itself a writable central table or a read-only view over the four existing per-domain tables — the source's Assumption #1 and Data Model Notes describe two different designs, and the user's OD-1 resolution only settled the name. If it's a view, FR-2 (`audit_log_viewed`) and FR-3 (denial) need a concrete per-domain target table to write into.
- **Hash-chain genesis rule (FR-7):** the chain is "seeded with the previous day's partition's final hash" (OD-11), but two cases are unstated: what the very first partition seeds from (no previous day exists), and what a day seeds from when the prior day's partition has zero rows (the last non-empty day's final hash, or an empty-chain sentinel). AU-AC7's "reports the exact row at which the chain breaks" is not implementable without a defined genesis rule.
- AU-AC5 specifies a `422 range-too-wide` response when the `from`/`to` range exceeds 90 days or when *both* bounds are omitted. It does not state what happens when only one of `from`/`to` is supplied without the other — is a single missing bound also rejected, given a default, or accepted as an open-ended range? (Carried forward, unresolved by anything in the current codebase.)
- AU-AC7/FR-7 describe a `BEFORE INSERT` trigger that computes `previous_hash` from the previous row's hash, but neither the story nor this spec states how the chain stays correct under concurrent `INSERT`s into the same daily partition (e.g., row-level locking or transaction-isolation guarantees). Since AU-AC7's entire purpose is tamper evidence, is this addressed at the trigger/transaction-isolation level, or is it deferred as an implementation detail? (Carried forward, Medium per the pre-existing spec review.)
- "Fields marked sensitive" (FR-6) is not enumerated beyond the four named exclusions (password, password hash, raw token, session cookie, full payment identifier) — what is the complete list of fields subject to redaction? (Carried forward, unresolved.)
- FR-8's "every direct identifier" (email, display_name, ip) is given as examples, not a closed list — are identifiers embedded inside the `payload` JSONB field also in scope for redaction on account erasure? (Carried forward, unresolved.)
- Cold-storage target and access procedure for AU-AC9 (which system, who may retrieve, how long) — carried over unresolved from the source's own Open Questions section; needs legal/DPO sign-off, same footing as OD-2's erasure-policy question.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AU-AC1 | "Given an authenticated actor holding the audit:read permission When GET /v1/admin/audit-logs?actor_id=…&event=login_failed&from=…&to=…&limit=50 is called Then respond 200 with a cursor-paginated, newest-first list And each entry contains occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, and an outcome" | FR-1 (query/pagination shape fully covered; the per-entry field list assumes `actor_role`/`outcome`/`category`/consistent-`actor_id` are available on every source row, which none of the four existing tables currently provides — see FR-1's note and Open Questions) |
| AU-AC2 | "Given any successful call to GET /v1/admin/audit-logs When the response is returned Then an audit entry is written (event=audit_log_viewed) recording the actor and the exact filter parameters used" | FR-2 |
| AU-AC3 | "Given an authenticated support agent, who does not hold audit:read When GET /v1/admin/audit-logs is called Then respond 403 with type \".../errors/insufficient-permission\" And the denied attempt is itself recorded in the audit log" | FR-3 |
| AU-AC4 | "Given any actor, including an administrator When PATCH, PUT or DELETE is attempted on /v1/admin/audit-logs or any entry Then respond 405 Method Not Allowed" (amended 2026-09-02 — the source's DB-grant clause, previously part of this AC's Gherkin, is now a documented note on AU-AC4 tracking it as a separate, project-wide follow-up, OD-12) | FR-4 (fully covered) |
| AU-AC5 | "Given a request whose from/to range exceeds 90 days, or which omits both bounds When GET /v1/admin/audit-logs is called Then respond 422 with type \".../errors/range-too-wide\" And the message states the maximum window and suggests the asynchronous export instead" | FR-5 (fully covered; the single-missing-bound case is raised in Open Questions) |
| AU-AC6 | "Given any audit entry of any event type When it is returned or inspected directly in storage Then no password, password hash, raw token, session cookie or full payment identifier appears in any field And fields marked sensitive are stored redacted (e.g. \"changed\" rather than the value)" | FR-6 |
| AU-AC7 | "Given every audit entry carries a previous_hash computed by a PostgreSQL BEFORE INSERT trigger over (previous row's hash, occurred_at, actor_id, event, target_id, payload) When the chain verification job runs over any day's partition Then it reports \"intact\" for an untouched chain And when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks And the hash column is computed server-side only — the application may never supply it" | FR-7 |
| AU-AC8 | "Given a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job When their historical audit entries are queried Then the entries remain, with actor_id retained as an opaque UUID And every direct identifier they contained (email, display_name, ip) is redacted or anonymised Because the audit trail must stay intact while the link to the natural person is severed" | FR-8 (erasure-job dependency resolved per OD-2 — a new, minimal, provisional script, not the still-deferred full DA-AC9; free-text-field redaction — e.g. `display_name` in `profile_audit_log.old_value`/`new_value` — resolved per OD-13) |
| AU-AC9 | "Given an audit entry older than the 400-day retention period When the scheduled retention job runs Then the entry is moved to cold storage (not silently dropped) And the job's own execution is recorded" | FR-9 (fully covered; the cold-storage target and access procedure remain an unresolved Open Question, carried from the source) |
