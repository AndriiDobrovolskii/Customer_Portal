# DB Design: US-2.1 Login

**Spec:** `docs/specifications/US-2.1-spec.md` (Pass with Issues, accepted 2026-08-31)
**API:** `docs/designs/api/US-2.1-openapi.yaml`, `US-2.1-api-design.md`

## What changes, per entity

### Reactivation writes (resolved OD-10, added 2026-08-31) — no new columns

FR-4's reactivation branch reuses columns already added by US-1.4: `users.status` (set back to `"active"`) and `users.deactivated_at` (cleared to `NULL`). No schema change is needed for either. The accompanying audit entry (`event=reactivated, actor=self`) is a write into `account_lifecycle_audit_log` — a table this story does not own (US-1.4's `account` module does) — so the write happens through a cross-module service call (`AccountService.reactivate_account()`, called from `users/service.py`), not through this story's own repository reaching into another module's table. No new table or column is introduced by this addendum; it's a service-layer/architecture note, not a persistence-design one.

### `users` (existing table, `app/modules/users/models.py`)

- **`last_login_at`** — new column, `DateTime(timezone=True)`, nullable. `NULL` until the account's first successful login; set to the login instant on every FR-1 success. No `server_default` — always set explicitly by the service on each successful login, matching the existing style of `deactivated_at`/`UserSession.revoked_at`/`EmailChangeToken.consumed_at` (nullable timestamp, no default, set on a state transition).
- **`status`, `email_verified`, `deactivated_at`** — all already exist (added by US-1.1–US-1.4). This story reads them for FR-4's gating but changes nothing about their definition.

No other `users` columns change.

### `auth_audit_log` (new table)

Mirrors the existing per-module audit-log precedent (`ProfileAuditLog` in `app/modules/profile/models.py`, which already has the closest-matching `request_id` column; `AuditLog` in `app/modules/email_verification/models.py`, which has the closest-matching "no FK, must survive account deletion" rationale). Two columns — `ip`, `user_agent` — have no precedent in any existing audit table; both are new to this story.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid.uuid4()` (app-side) | PK |
| `event` | `String(32)` | No | — | `login_succeeded` (FR-1) or `login_failed` (FR-2, FR-3, FR-4). Free text, not a DB enum — matches `AuditLog.event`'s existing style; validated at the service layer. |
| `reason` | `String(32)` | Yes | — | Set only when `event=login_failed`: `bad_password` (FR-2), `unknown_email` (FR-3), `email_not_verified` / `account_deactivated` (FR-4). `NULL` for `login_succeeded`. |
| `actor_id` | UUID (no FK) | Yes | — | The matched user's id (FR-1, FR-2, FR-4). **`NULL`** for FR-3 (unknown email — no account matched). **Deliberately no FK**, matching `account_lifecycle_audit_log.user_id`'s and `AuditLog.subject_user_id`'s existing rationale: the row must outlive the account through the eventual 30-day-grace-period deletion/anonymization (BR-007), same as every other audit table in this project. |
| `ip` | `String(45)` | No | — | Source IP of the request. `45` chars accommodates the longest IPv6 literal representation. New column, no existing precedent — sized per standard practice, not a project convention. |
| `user_agent` | `Text` | Yes | — | Request's `User-Agent` header. Nullable — a caller can omit the header entirely; not worth rejecting a login attempt over a missing header. New column, no existing precedent. |
| `request_id` | `String(64)` | No | — | Correlation id for the request. Matches `ProfileAuditLog.request_id`'s existing type/length/non-null precedent exactly. |
| `occurred_at` | `DateTime(timezone=True)` | No | `func.now()` (server-side) | Matches `ProfileAuditLog.timestamp` / `AuditLog.occurred_at` naming precedent — `occurred_at` chosen (matches the spec's own Data Model Notes field name and the closer `email_verification` precedent). |

No `429`/`422` rows exist for this table (FR-5, FR-6) — resolved OD-6, restated in the spec. No `actor_role`/`target_id` columns: not required by any US-2.1 FR, and `US-3.3`'s eventual unioned audit view is not this story's concern to pre-guess (same reasoning US-1.4's design applied to its own audit table).

### Indexes

- `auth_audit_log(actor_id)` — the anticipated query pattern (per `US-3.3-view-audit-information-spec.md`'s own `actor_id=...` filter example, AU-AC1) is "audit history for this account." Matches every other audit table's `user_id`/`actor_id` index precedent in this project.
- No index on `event`/`reason`/`occurred_at` individually or composite: no FR or NFR in this story states a query pattern or latency budget against this table beyond what `actor_id` serves — if `US-3.3`'s eventual query needs more, that's its own migration.
- No new index on `users.last_login_at`: nothing in this story or its NFRs queries by it (it's a read-on-profile-view field, not a filter/sort key), and adding one speculatively isn't supported by any stated requirement.

### `refresh_tokens` (new table, resolved OD-9)

Not stated in this story's own Data Model Notes, but required by FR-1 ("sets a refresh token as an HttpOnly, Secure, SameSite=Strict cookie") and assigned to this story by `US-2.3-refresh-token.md`'s own Out of Scope section ("Initial token issuance (US-2.1)"). US-2.3 defines the eventual full shape (`token_hash`, `family_id`, `user_id`, `issued_at`, `consumed_at`, `expires_at`, plus `ip`/`user_agent`/`last_used_at` for US-2.6); this story models only the subset it actually writes on FR-1's success path — the remaining columns are added by US-2.3's own migration when rotation semantics are implemented, not pre-built here on speculation.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | No | `uuid.uuid4()` (app-side) | PK |
| `token_hash` | `String(64)` | No | — | SHA-256 hex digest of the raw token (64 hex chars) — the raw value is never persisted, only returned once in the `Set-Cookie` header, matching `EmailVerificationToken.token_hash`/`EmailChangeToken.token_hash`'s existing precedent exactly (same column name, same non-reversible-hash rationale). Unique. |
| `family_id` | UUID | No | `uuid.uuid4()` (app-side, one per login) | Groups every token descended from this login via later rotation (US-2.3). This story always creates a brand-new family — it never joins an existing one. |
| `user_id` | UUID | No | — | `ForeignKey("users.id", ondelete="CASCADE")`, indexed — unlike the audit tables, a refresh token has no reason to outlive its account; deletion should cascade, matching `EmailVerificationToken.user_id`'s existing FK-with-cascade precedent. |
| `issued_at` | `DateTime(timezone=True)` | No | `func.now()` (server-side) | Matches `EmailVerificationToken.issued_at`/`EmailChangeToken.issued_at` precedent exactly. |
| `expires_at` | `DateTime(timezone=True)` | No | — | Set explicitly by the service from the configured refresh-token TTL (no such setting exists in `app/core/config.py` yet — new setting needed, out of this design's scope to name the exact value since the spec doesn't state one; flagged below). |

**Columns deliberately not added here** (US-2.3/US-2.6 add them with their own migration when needed): `consumed_at` (rotation state — this story never rotates), `ip`, `user_agent`, `last_used_at` (US-2.6's session-listing needs — this story's login-time IP/UA already goes to `auth_audit_log` instead, and duplicating it into a second table serves no FR of this story).

**Indexes:** `ix_refresh_tokens_user_id` on `user_id` (FK column, standard practice); unique index on `token_hash` (lookup path for the eventual `/v1/auth/refresh`, though that lookup itself is US-2.3's code, not this story's).

**Relationships:** `User.refresh_tokens` could be added as a `relationship()`, but nothing in this story's own flow reads it back (login only inserts) — deferred to whichever of US-2.3/US-2.6 first needs to query "every token for this user," so the eager-loading strategy is decided by the story that actually needs the join, not guessed here.

**Sensitive column:** `token_hash` — same class as every other token-hash column in this project (never the raw value, never logged). The raw token itself exists only in memory during the request and in the `Set-Cookie` header.

**Open (new, from resolving OD-9):** the refresh-token TTL value itself is not stated anywhere in `US-2.1-login.md` or its spec — `US-2.3-refresh-token.md`'s Assumption #3 states a 30-day absolute cap, which is that story's own rotation-cap concept, not necessarily the value US-2.1 should use for a token that (in this story alone) never rotates. Flagged for `planner`: recommend reusing US-2.3's 30-day figure as the initial `expires_at`, since a shorter value would strand a client before US-2.3 exists to renew it, but this is a `planner`-level call, not decided here.

## Relationships / loading strategy

`auth_audit_log` has no ORM relationship back to `User` (no FK, so no `relationship()` is possible or desired — intentional per the "must survive deletion" rationale, not an oversight, exactly mirroring `account_lifecycle_audit_log`). The repository writes it standalone; no eager-loading concern arises since the login flow never needs to read it back in the same request.

## Sensitive columns

- `auth_audit_log.ip` and `.user_agent` are the two new sensitive-adjacent columns this story introduces — both are already-established audit-trail data classes elsewhere in the spec's own Data Model Notes and in `docs/product/non-functional-requirements.md` NFR-012 (PII minimization applies to *response* payloads and coarsening of derived location data; it does not prohibit storing raw IP/UA in a staff-only audit table, which is exactly what NFR-006's "audit trail completeness" requires them for). No encryption-at-rest requirement is stated anywhere for this data class — not invented here.
- No password material is ever written to `auth_audit_log` — `event`/`reason` are closed enums of outcome labels, never raw credential values. This matches NFR-001/BR-004 by construction, not by an additional column-level control.

## Explicitly deferred / not decided here

0. **Resolved during PLANNING, restated here for completeness:** the `refresh_tokens` table above did not exist in the original 2026-08-30 version of this design — added 2026-08-31 per resolved OD-9 after `impact-analyzer` surfaced the gap.
1. **`request_id` availability at every call site.** **Resolved 2026-08-31:** `app/core/dependencies.py:get_request_id` is a per-route FastAPI `Depends()` (falls back to `uuid.uuid4()` if no `X-Request-ID` header), not global middleware — it already runs on unauthenticated routes today (`profile/router.py` isn't a counterexample of that, but nothing about it requires authentication either). The non-nullable precedent used above is safe. Item kept here for traceability, not because it's still open. This column follows `ProfileAuditLog`'s existing non-nullable precedent, but `ProfileAuditLog` is only ever written from an authenticated request path (a real request already has a correlation id by the time it reaches that service). Login is unauthenticated and is exactly the endpoint most likely to be hit by scripted/automated traffic that might not populate whatever header-based correlation-id middleware the project uses. **Flagged for `planner`**: confirm the project's request-id middleware runs unconditionally (including on this unauthenticated route) before treating `NULL`-free as safe; if it can't guarantee a value, this column should be nullable instead, contrary to the precedent used above.
2. **Module placement.** `auth_audit_log` is modeled here as living in `app/modules/users/models.py`, alongside `User`/`UserSession` — unlike US-1.4, this doesn't need a new module, since the login endpoint itself already lives in `app/modules/users/`. Confirm at PLANNING; not a schema question but affects where `data-layer-builder` writes `models.py`.
