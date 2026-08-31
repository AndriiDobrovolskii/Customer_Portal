# DB Design: US-004 Deactivate Account

**Spec:** `docs/specifications/US-004-deactivate-account-spec.md` (Pass)
**API:** `docs/designs/api/US-004-openapi.yaml`, `US-004-api-design.md`

## What changes, per entity

### `users` (existing table, `app/modules/users/models.py`)

- **`status`** already exists (`String(32)`, `nullable=False`, free-text) — no column change. This story adds a new value, `"deactivated"`, alongside the existing `"active"`/`"pending_verification"` values already implied by `docs/product/business-glossary.md`'s `User Account` entry. `app/modules/users/schemas.py:UserStatus` currently only defines `PENDING_VERIFICATION` — extending it with `ACTIVE`/`DEACTIVATED` is a `data-layer-builder`-stage change, not a schema migration, but noted here so the migration author doesn't have to rediscover it.
- **`deactivated_at`** — new column, `DateTime(timezone=True)`, nullable. `NULL` while active; set to the deactivation instant on FR-1's transition; cleared (`NULL`) again on FR-8 reactivation. No `server_default` — always set explicitly by the service, matching the existing style of `EmailChangeToken.consumed_at`/`UserSession.revoked_at` (nullable timestamp, no default, set on state transition).

### `account_lifecycle_audit_log` (new table, new module `app/modules/account/` — see Naming below)

Mirrors the existing per-module audit-log precedent (`ProfileAuditLog` in `app/modules/profile/models.py`, `AuditLog` in `app/modules/email_verification/models.py`), specifically following the email_verification variant since both need a `system`-actor row with no HTTP request context (FR-9's job).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid.uuid4()` (app-side) | PK |
| `user_id` | UUID | No | — | The account the event is about. **Deliberately no FK** — FR-9 removes the `users` row *after* writing this entry, so the row must outlive the account, matching `AuditLog.subject_user_id`'s documented rationale in `email_verification/models.py:30-31`. |
| `event` | String(32) | No | — | One of `deactivated` / `reactivated` / `permanently_deleted` (FR-1, FR-8, FR-9). Stored as free text, not a DB enum — matches `AuditLog.event`'s existing style; validated at the service layer. |
| `actor` | String(64) | No | — | One of `self`, `system`, or `admin:{admin_id}` — stored exactly as the spec's AC text (DA-AC1, DA-AC8, DA-AC9, DA-AC10), not decomposed into `actor_type`/`actor_id` columns. Decomposing was considered and rejected: nothing downstream in this story's own ACs queries by admin id, and inventing that shape isn't supported by the spec — logged as an open item below since `US-013`'s audit-view spec may need it. |
| `occurred_at` | DateTime(timezone=True) | No | `func.now()` (server-side) | Matches `ProfileAuditLog.timestamp` / `AuditLog.occurred_at` naming precedent — `occurred_at` chosen (matches the closer email_verification precedent's system-actor case). |

No `request_id`/`ip`/`user_agent`/`actor_role`/`target_id` columns: not required by any US-004 FR, and the existing two audit tables (`ProfileAuditLog`, email_verification's `AuditLog`) aren't uniform on these either — see Open Items.

### Indexes

- `account_lifecycle_audit_log(user_id)` — every FR-1/FR-8/FR-9 write and any future lookup ("audit history for this account") filters by subject. Matches `email_verification_tokens`/`email_change_tokens`'s `user_id` index precedent.
- No new index on `users.status` or `users.deactivated_at`: the FR-9 job's query ("deactivated more than 30 days ago") is a scheduled batch job, not a request-path query — no NFR states a latency budget for it (contrast with the NFR's explicit p95 budget for the request-path `revoke_before` check). If the job's query plan proves slow at implementation time, that's a `migration-manager`-stage `CONCURRENTLY` addition, not a day-one requirement here.

## Relationships / loading strategy

`account_lifecycle_audit_log` has no ORM relationship back to `User` (no FK, so no `relationship()` is possible or desired — this is intentional per the "must survive deletion" rationale, not an oversight). The repository queries it standalone by `user_id`; no eager-loading concern arises since nothing joins through it.

## Sensitive columns

None new. `deactivated_at` is a timestamp, not PII beyond what `users` already holds. `account_lifecycle_audit_log.actor` may contain an admin's UUID (`admin:{admin_id}`) — same sensitivity class as any other UUID already stored in existing audit tables' actor columns (`ProfileAuditLog.actor_id`); no new handling required.

## Explicitly deferred / not decided here

1. **Revocation substrate** (Valkey `revoke_before:{user_id}` vs. the existing `user_sessions.revoked_at` bulk-revoke) — carried over unresolved from `US-004-api-design.md`'s Open Question 1. This is the single biggest undecided item and it determines whether FR-1's implementation needs a `cache.py` write, a `user_sessions` bulk-`UPDATE`, or both. **Logged for PLANNING, not decided here** per this skill's own constraint ("if something is needed but undecided, log it... rather than guessing").
2. **Concurrent-deactivation atomicity** (Clarification #2: `UPDATE users SET status='deactivated' ... WHERE status='active'` returning 0 rows → `409`) — this is a repository-query shape decision, not a schema decision; no new column or constraint is needed for it, just documented here so `data-layer-builder` doesn't have to re-derive it from the spec.
3. **`account_lifecycle_audit_log` vs. `US-013`'s eventual unioned view** — whether the view needs `actor_role`/`request_id`/`target_id`/`ip`/`user_agent` uniformly across all five audit tables is a `US-013`-stage decision; this table matches its closest existing sibling rather than pre-guessing US-013's requirements.
4. **Module placement.** No `app/modules/account/` exists yet. This story's one endpoint (`POST /v1/account/deactivate`) and this one table don't obviously belong inside `users` (auth/registration) or `profile` (self-service profile fields) — recommend a new `account` module, named after the endpoint's own path segment (`/v1/account/deactivate`) rather than overloading `users`. Confirm at PLANNING; not a schema question but affects where `data-layer-builder` writes `models.py`.
