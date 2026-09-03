# Epic 3 — Administration: View Audit Information

**Story ID:** US-3.3
**Project:** Customer Portal
**Revised:** 2026-09-02 — AU-AC4 split into this story's API-level scope and a deferred DB-grant follow-up (OD-12), and the Data Model Notes' partition-granularity line corrected to match the story's own Assumption #4/AU-AC7 (OD-11). Both were found self-contradictory/under-scoped by `us-clarifier` and `story-spec-reviewer` against the real, now-current codebase; full detail and rationale in `docs/decisions/US-3.3-open-decisions.md` (OD-11, OD-12) and `docs/reviews/specifications/US-013-spec-review.md`. No other AC changed.

## User Story
As an auditor or administrator,
I want to search a tamper-evident record of who did what and when,
So that I can investigate a security incident or answer a compliance request with evidence rather than recollection.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Storage shape | One append-only `audit_log` table with a `category` discriminator; existing per-domain tables exposed through a union view | A single query surface makes an investigation tractable |
| 2 | Immutability | Enforced by database grants (INSERT + SELECT only), not application convention | An ORM-level rule is not an audit control |
| 3 | Tamper evidence | Hash chain: `previous_hash` computed by a `BEFORE INSERT` trigger | Detects retroactive edits without the cost of WORM storage |
| 4 | Chain scope | Per daily partition, seeded with the previous partition's final hash | Keeps verification cheap and preserves partition pruning |
| 5 | Retention | 400 days, then cold storage | Common "13 months" default; pending DPO sign-off on wording |
| 6 | Query window | Maximum 90 days per query, bounds required | Keeps the endpoint predictable; wider ranges go through export |
| 7 | Permission | `audit:read`, held by `admin` and `auditor` | Support agents have no business reading the audit trail |

## In Scope
- `GET /v1/admin/audit-logs` — filtered, cursor-paginated, newest-first
- Immutability and tamper-evidence guarantees
- Retention and post-erasure behaviour

## Out of Scope
- Asynchronous bulk export (referenced by AU-AC5; its own story)
- Alerting/SIEM forwarding
- Log ingestion from infrastructure components — this story covers application audit events only

## API Contract
| Method | Path | Auth | Request Body | Success |
|---|---|---|---|---|
| GET | `/v1/admin/audit-logs` | `audit:read` | — (query: `actor_id`, `event`, `target_id`, `from`, `to`, `cursor`, `limit`) | 200, cursor-paginated |
| PATCH / PUT / DELETE | `/v1/admin/audit-logs*` | — | — | 405 (never implemented) |

## Data Model Notes
- `audit_log`: `id`, `category`, `occurred_at`, `actor_id`, `actor_role`, `event`, `target_id`, `outcome`, `request_id`, `ip`, `user_agent`, `payload` (JSONB), `previous_hash`, `row_hash`
- Union view over `auth_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`, `admin_audit_log`, `ticket_audit_log`
- Covering index on `(occurred_at DESC, actor_id, event)`; daily partitions (corrected 2026-09-02, OD-11 — matches Assumption #4 and AU-AC7, which this line originally contradicted); keyset (not `OFFSET`) pagination

## Acceptance Criteria

### Happy path
**AU-AC1 — Filtered query**
```gherkin
Given an authenticated actor holding the audit:read permission
When GET /v1/admin/audit-logs?actor_id=…&event=login_failed&from=…&to=…&limit=50 is called
Then respond 200 with a cursor-paginated, newest-first list
And each entry contains occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, and an outcome
```

**AU-AC2 — Reading the log is itself audited**
```gherkin
Given any successful call to GET /v1/admin/audit-logs
When the response is returned
Then an audit entry is written (event=audit_log_viewed) recording the actor and the exact filter parameters used
```

### Access control and immutability
**AU-AC3 — Insufficient permission**
```gherkin
Given an authenticated support agent, who does not hold audit:read
When GET /v1/admin/audit-logs is called
Then respond 403 with type ".../errors/insufficient-permission"
And the denied attempt is itself recorded in the audit log
```

**AU-AC4 — The log is immutable (API layer)**
```gherkin
Given any actor, including an administrator
When PATCH, PUT or DELETE is attempted on /v1/admin/audit-logs or any entry
Then respond 405 Method Not Allowed
```
*Database-grant enforcement (the application's DB role holding INSERT/SELECT-only on audit tables) is a separate, project-wide invariant, not unique to this story — it applies equally to every audit table already shipped (`auth_audit_log`, `admin_audit_log`, `profile_audit_log`, `account_lifecycle_audit_log`) and requires provisioning a non-superuser, non-owner database role plus grant migrations, none of which exist yet anywhere in this codebase (OD-12). Tracked as a separate infrastructure follow-up; this story's own AC is the API-level `405` only.*

### Query bounds and content
**AU-AC5 — Query window too wide**
```gherkin
Given a request whose from/to range exceeds 90 days, or which omits both bounds
When GET /v1/admin/audit-logs is called
Then respond 422 with type ".../errors/range-too-wide"
And the message states the maximum window and suggests the asynchronous export instead
```

**AU-AC6 — No secrets in the record**
```gherkin
Given any audit entry of any event type
When it is returned or inspected directly in storage
Then no password, password hash, raw token, session cookie or full payment identifier appears in any field
And fields marked sensitive are stored redacted (e.g. "changed" rather than the value)
```

**AU-AC7 — Tamper evidence**
```gherkin
Given every audit entry carries a previous_hash computed by a PostgreSQL BEFORE INSERT trigger
    over (previous row's hash, occurred_at, actor_id, event, target_id, payload)
When the chain verification job runs over any day's partition
Then it reports "intact" for an untouched chain
And when any historical row is altered or removed by any means, the job reports the exact row
    at which the chain breaks
And the hash column is computed server-side only — the application may never supply it
```

**AU-AC8 — Audit survives account erasure**
```gherkin
Given a user account permanently deleted or anonymised by the US-1.4 DA-AC9 retention job
When their historical audit entries are queried
Then the entries remain, with actor_id retained as an opaque UUID
And every direct identifier they contained (email, display_name, ip) is redacted or anonymised
Because the audit trail must stay intact while the link to the natural person is severed
```

### Background invariant
**AU-AC9 — Retention**
```gherkin
Given an audit entry older than the 400-day retention period
When the scheduled retention job runs
Then the entry is moved to cold storage (not silently dropped)
And the job's own execution is recorded
```

## Error Envelope (RFC 7807 `application/problem+json`)
```json
{
  "type": "https://portal.internal/errors/range-too-wide",
  "title": "Query Range Too Wide",
  "status": 422,
  "detail": "Audit queries cover at most 90 days. Use the export for wider ranges.",
  "instance": "/v1/admin/audit-logs"
}
```
Error `type` slugs introduced by this story: `range-too-wide`.

## Non-Functional / Security Requirements
- `request_id` ties an audit entry to the application log line and the trace — this is what makes an investigation tractable.
- Immutability MUST be enforced at the API layer for every actor (AU-AC4); database-grant enforcement is a separate, project-wide follow-up (see AU-AC4's note), not application code convention alone once it ships.
- Anyone permitted may read; nobody may edit — including the operators, at the API layer.
- **Performance:** target p95 ≤ 500 ms for a 50-row page over a 30-day window.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| AU-AC1–2 | Integration test suite | `[gate]` |
| AU-AC3 | Integration test asserting both the 403 and the resulting audit entry | `[gate]` |
| AU-AC4 | Integration test asserting `405` on PATCH/PUT/DELETE | `[gate]` |
| Database-grant enforcement (project-wide, not this story's AC — see AU-AC4's note) | Test executing an UPDATE/DELETE as the application role and asserting a permission error, once the follow-up provisions a non-superuser role | `[manual]` pending infrastructure follow-up (OD-12) |
| AU-AC5–6 | Integration test suite; AU-AC6 additionally by a CI grep over audit-write call sites | `[gate]` |
| AU-AC7 | Test that mutates a row via a privileged connection and asserts the verifier reports the break | `[gate]` |
| AU-AC8 | Integration test running the US-1.4 erasure job and re-querying | `[gate]` |
| AU-AC9 | Unit test on the retention job; scheduled execution verified in staging | `[manual]` |

## Open Questions
1. Cold-storage target and access procedure for AU-AC9 (which system, who may retrieve, how long).