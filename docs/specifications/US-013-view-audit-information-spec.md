# Specification: View Audit Information

**Source:** docs/backlog/US-3.3-view-audit-information.md
**Story ID:** US-013
**Generated:** 2026-08-22
**Status:** Draft (refined 2026-08-22 per docs/reviews/US-013-spec-review.md)

## Summary

This spec covers the audit-log query endpoint for administrators and auditors: filtered, cursor-paginated, newest-first retrieval of audit entries; self-auditing of read access; permission-gated access restricted to `audit:read`; database-enforced immutability; a bounded query window; redaction of sensitive fields; a tamper-evident hash chain with a verification job; audit-trail survival through account erasure; and retention of aged entries to cold storage.

## Background

As an auditor or administrator, I want to search a tamper-evident record of who did what and when, so that I can investigate a security incident or answer a compliance request with evidence rather than recollection.

## Functional Requirements

### FR-1: Filtered Audit Log Query

Given an authenticated actor holding the `audit:read` permission, when `GET /v1/admin/audit-logs` is called with filter parameters (`actor_id`, `event`, `target_id`, `from`, `to`, `cursor`, `limit`), the system responds `200` with a cursor-paginated, newest-first list. Each returned entry contains `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `request_id`, `ip`, `user_agent`, and an `outcome`.

**Derived from:** AU-AC1

### FR-2: Reading the Audit Log Is Itself Audited

Given any successful call to `GET /v1/admin/audit-logs`, when the response is returned, the system writes an audit entry (`event=audit_log_viewed`) recording the actor and the exact filter parameters used for that call.

**Derived from:** AU-AC2

### FR-3: Insufficient Permission Is Rejected and Recorded

Given an authenticated actor who does not hold `audit:read` (e.g. a support agent), when `GET /v1/admin/audit-logs` is called, the system responds `403` with a `problem+json` body of type `.../errors/insufficient-permission`, and the denied attempt is itself recorded in the audit log.

**Derived from:** AU-AC3

### FR-4: Audit Log Immutability

Given any actor, including an administrator, when `PATCH`, `PUT`, or `DELETE` is attempted against `/v1/admin/audit-logs` or any entry within it, the system responds `405 Method Not Allowed`. The application's database role holds `INSERT` and `SELECT` grants only on audit tables.

**Derived from:** AU-AC4

### FR-5: Query Window Bound Enforcement

Given a request whose `from`/`to` range exceeds 90 days, or which omits both the `from` and `to` bounds, when `GET /v1/admin/audit-logs` is called, the system responds `422` with a `problem+json` body of type `.../errors/range-too-wide`, and the message states the maximum window and suggests the asynchronous export instead.

**Derived from:** AU-AC5

### FR-6: No Secrets in Audit Records

Given any audit entry of any event type, when it is returned via the API or inspected directly in storage, no password, password hash, raw token, session cookie, or full payment identifier appears in any field. Fields marked sensitive are stored redacted (e.g. `"changed"` rather than the actual value).

**Derived from:** AU-AC6

### FR-7: Tamper-Evident Hash Chain

Every audit entry carries a `previous_hash` computed by a PostgreSQL `BEFORE INSERT` trigger over the previous row's hash, `occurred_at`, `actor_id`, `event`, `target_id`, and `payload`; the hash column is computed server-side only and the application may never supply it. When the chain verification job runs over any day's partition, it reports "intact" for an untouched chain, and when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks.

**Derived from:** AU-AC7

### FR-8: Audit Trail Survives Account Erasure

Given a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job, when their historical audit entries are queried, the entries remain, with `actor_id` retained as an opaque UUID, and every direct identifier the entries contained (email, display_name, ip) is redacted or anonymised — so the audit trail stays intact while the link to the natural person is severed.

**Derived from:** AU-AC8

### FR-9: Retention to Cold Storage

Given an audit entry older than the 400-day retention period, when the scheduled retention job runs, the entry is moved to cold storage rather than silently dropped, and the job's own execution is recorded.

**Derived from:** AU-AC9

## Data Model Notes

- `audit_log`: `id`, `category`, `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `outcome`, `request_id`, `ip`, `user_agent`, `payload` (JSONB), `previous_hash`, `row_hash`.
- `audit_log` is a union view over five per-domain tables: `auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`, `ticket_audit_log`.
- A covering index on `(occurred_at DESC, actor_id, event)`; monthly partitions; pagination (FR-1) is keyset-based, not `OFFSET`-based.

**Derived from:** source Data Model Notes section.

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
- Immutability must be enforced by database grants (see FR-4), not by application code convention alone.
- Any actor holding `audit:read` may read the audit log; nobody — including operators — may edit it.
- Performance target: p95 ≤ 500 ms for a 50-row page over a 30-day window.

**Derived from:** Non-Functional / Security Requirements section of the source.

## Out of Scope

- Asynchronous bulk export (referenced by AU-AC5 as the alternative for wider ranges; its own story).
- Alerting/SIEM forwarding.
- Log ingestion from infrastructure components — this story covers application audit events only.

**Derived from:** Out of Scope section of the source.

## Open Questions

- Cold-storage target and access procedure for AU-AC9 (which system, who may retrieve, how long) — carried over unresolved from the source's own Open Questions section.
- AU-AC5 specifies a `422 range-too-wide` response when the `from`/`to` range exceeds 90 days or when *both* bounds are omitted. It does not state what happens when only one of `from`/`to` is supplied without the other — is a single missing bound also rejected, given a default, or accepted as an open-ended range?
- AU-AC7/FR-7 describe a `BEFORE INSERT` trigger that computes `previous_hash` from the previous row's hash, but neither the story nor this spec states how the chain stays correct under concurrent `INSERT`s into the same partition (e.g., row-level locking or transaction-isolation guarantees). Since AU-AC7's entire purpose is tamper evidence, is this addressed at the trigger/transaction-isolation level, or is it deferred as an implementation detail?
- AU-AC1 shows `limit=50` as an example value, but neither the story nor FR-1 states a maximum enforced `limit`, behavior for an invalid or expired `cursor`, or behavior for zero matching results.
- "Fields marked sensitive" (FR-6) is not enumerated beyond the four named exclusions (password, password hash, raw token, session cookie, full payment identifier) — what is the complete list of fields subject to redaction?
- FR-8's "every direct identifier" (email, display_name, ip) is given as examples, not a closed list — are identifiers embedded inside the `payload` JSONB field also in scope for redaction on account erasure?

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AU-AC1 | "Given an authenticated actor holding the audit:read permission When GET /v1/admin/audit-logs?actor_id=…&event=login_failed&from=…&to=…&limit=50 is called Then respond 200 with a cursor-paginated, newest-first list And each entry contains occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, and an outcome" | FR-1 |
| AU-AC2 | "Given any successful call to GET /v1/admin/audit-logs When the response is returned Then an audit entry is written (event=audit_log_viewed) recording the actor and the exact filter parameters used" | FR-2 |
| AU-AC3 | "Given an authenticated support agent, who does not hold audit:read When GET /v1/admin/audit-logs is called Then respond 403 with type \".../errors/insufficient-permission\" And the denied attempt is itself recorded in the audit log" | FR-3 |
| AU-AC4 | "Given any actor, including an administrator When PATCH, PUT or DELETE is attempted on /v1/admin/audit-logs or any entry Then respond 405 Method Not Allowed And the application's database role holds INSERT and SELECT grants only on audit tables" | FR-4 |
| AU-AC5 | "Given a request whose from/to range exceeds 90 days, or which omits both bounds When GET /v1/admin/audit-logs is called Then respond 422 with type \".../errors/range-too-wide\" And the message states the maximum window and suggests the asynchronous export instead" | FR-5 (fully covered; a related but distinct case — a single missing bound — is raised in Open Questions) |
| AU-AC6 | "Given any audit entry of any event type When it is returned or inspected directly in storage Then no password, password hash, raw token, session cookie or full payment identifier appears in any field And fields marked sensitive are stored redacted (e.g. \"changed\" rather than the value)" | FR-6 |
| AU-AC7 | "Given every audit entry carries a previous_hash computed by a PostgreSQL BEFORE INSERT trigger over (previous row's hash, occurred_at, actor_id, event, target_id, payload) When the chain verification job runs over any day's partition Then it reports \"intact\" for an untouched chain And when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks And the hash column is computed server-side only — the application may never supply it" | FR-7 |
| AU-AC8 | "Given a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job When their historical audit entries are queried Then the entries remain, with actor_id retained as an opaque UUID And every direct identifier they contained (email, display_name, ip) is redacted or anonymised Because the audit trail must stay intact while the link to the natural person is severed" | FR-8 |
| AU-AC9 | "Given an audit entry older than the 400-day retention period When the scheduled retention job runs Then the entry is moved to cold storage (not silently dropped) And the job's own execution is recorded" | FR-9 (fully covered; the cold-storage target and access procedure remain an unresolved Open Question, carried from the source) |
