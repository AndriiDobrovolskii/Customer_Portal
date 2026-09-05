---
artifact_type: impact_analysis
story: US-4.2
version: 2
status: ARCHIVED
created_at: "2026-09-05T13:00:00Z"
updated_at: "2026-09-05T13:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.2-design-review.md
    version: 3
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/impact-analysis/US-4.2-impact-analysis.md (v1)
---

# Impact Analysis: Ticket Replies (US-4.2 / spec US-4.2)

**Spec:** docs/specifications/US-4.2-spec.md (v6)
**API design:** docs/designs/api/US-4.2-api-design.md, US-4.2-openapi.yaml (v3)
**DB design:** docs/designs/database/US-4.2-db-design.md, US-4.2-entity-model.md (v3)
**Design review:** docs/reviews/designs/US-4.2-design-review.md (v3, PASS, no Critical/Major finding)

## Revision Note (v2)

v1 of this document (2026-09-04T22:00:00Z) was produced against spec v2 / api_design v1 / db_design v1 / design_review v1, and its own survey correctly returned `changes_required_specification` on a genuine defect (FR-6 citing a nonexistent `US-4.3-spec.md`). That defect is now resolved: three specification revisions (v3-v6) and a DESIGN_REVIEW loop (v2 BLOCKED on Finding DR-1, resolved by OD-8's actual human resolution) later, spec v6 / spec review v6 (PASS) / api_design v3 / db_design v3 / entity_model v3 / design_review v3 (PASS) are all internally consistent, cite only status values and files that exist in this codebase, and OD-1 through OD-8 are all `RESOLVED`. This revision re-surveys the blast radius against that current, passed design pair — reading the actual codebase (`app/modules/support/*`, `app/core/*`, `app/db/*`) directly rather than trusting the designs' own citations.

`app/modules/support/` already exists (US-4.1, PR #16: `models.py`, `schemas.py`, `repository.py`, `cache.py`, `service.py`, `router.py`, `dependencies.py`, `exceptions.py`, all read directly for this survey). This story extends that module; it also touches three `app/core/` files and adds one Alembic migration. No blocking defect was found this pass.

## Affected Files

### Database / models layer (`AGENTS.md` §3: models before repository)

- **`app/modules/support/models.py`** — new `TicketReply` class (`ticket_replies` table: `id`, `ticket_id` FK, `author_id` FK, `author_kind`, `body`, `visibility`, `created_at`, `CheckConstraint("visibility = 'public' OR author_kind = 'agent'", name="ck_ticket_replies_visibility_agent_only")`, composite `(ticket_id, created_at, id)` index — db-design v3 §"New table"). Additive column `Ticket.first_response_at: Mapped[datetime | None]` on the existing `Ticket` class (db-design v3 §"Existing table: tickets"). Additive column `Attachment.ticket_reply_id: Mapped[uuid.UUID | None]` with `index=True` on the existing `Attachment` class (db-design v3 §"Existing table: attachments", Resolution OD-1). Confirmed by direct read: `Ticket` currently has no `first_response_at`/`resolved_at` column and `Attachment` currently has only `ticket_id`, `uploaded_by`, `created_at` — both additions are genuinely new, not a rename.
- **New Alembic revision under `migrations/versions/`** — touched because: (1) `CREATE TABLE ticket_replies` including the `CHECK` constraint, autogeneratable; (2) `ALTER TABLE tickets ADD COLUMN first_response_at` and `ALTER TABLE attachments ADD COLUMN ticket_reply_id` plus its index, both autogeneratable, additive, nullable, no backfill needed; (3) hand-written DDL the `env.py` Rewriter cannot reach — `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and two `CREATE POLICY` statements (db-design v3's literal SQL) — each needs its own `sa.inspect(op.get_bind())` idempotency guard per `AGENTS.md` §4, the same pattern `US-3.3`'s `AuditLog` partitioning DDL already established in this codebase. `downgrade()` must actually drop the policies and disable RLS, not `pass`.
  - **Carried finding (DESIGN_REVIEW DR-2, Minor, unresolved by any design revision):** `attachments` is an existing, already-shipped table. Whether `ix_attachments_ticket_reply_id` needs `CREATE INDEX CONCURRENTLY` + `op.get_context().autocommit_block()` + `if_not_exists=True` (per `AGENTS.md` §4, and this codebase's own precedent in `1b2b1d52dd71_admin_users_email_display_name_trgm_.py`) depends on whether `attachments` is expected to hold enough production rows by migration time to make a blocking `CREATE INDEX` costly. No design document decides this; `migration-manager` must.

### Repository layer

- **`app/modules/support/repository.py`** — new `TicketReplyRepository` class: `create(...)` and a keyset-paginated `list_for_ticket(ticket_id, cursor, limit)` mirroring `TicketRepository.list_for_requester`'s existing cursor-encode/decode helpers (db-design v3 §"Relationships / loading strategy"). `TicketRepository` needs a new method to persist a status transition and/or `first_response_at` stamp — confirmed by direct read: today's `TicketRepository` has only `create`, `get_by_id`, `list_for_requester`, `commit`; there is no `update`/`set_status` method at all, so FR-1/FR-2/FR-6's status writes have no existing method to reuse. `AttachmentRepository` needs a new bind path for `ticket_reply_id` (either a new `bind_to_reply` method or `bind_to_ticket` extended to accept it) — confirmed `bind_to_ticket`'s existing conditional-`UPDATE`-guarded-by-`ticket_id IS NULL` pattern only ever touches `ticket_id`, never `ticket_reply_id`. Exact method signatures are `IMPLEMENTATION_PLANNING`'s call per db-design v3, not decided here.

### Cache layer

- **`app/modules/support/cache.py`** — new rate-limit cache class for the reply endpoint's 30/user/hour limit (NFR), parallel to the existing `TicketCreationRateLimitCache` (5/user/hour for ticket creation) but a distinct counter — the two limits must not share a key or a reply would consume a ticket-creation-limit slot and vice versa.
- **`app/core/cache_keys.py`** — new key-builder function (parallel to `ticket_create_rate_key`) for the reply rate limit, e.g. `ticket_reply_rate_key(user_id)`. Confirmed by direct read: no existing key function serves this purpose.

### Service layer

- **`app/modules/support/service.py`** — the largest single surface. New business logic to: load the ticket and branch authorization by actor kind (agent `tickets:write` vs. customer ownership vs. neither → `404`, per api-design v3's "Authorization is actor-kind-dependent, not a single check" — this cannot be a single `Depends(require_scope(...))` route dependency the way `reject_agent_queue_access` is, because the decision needs the ticket row, which only the service loads); gate on ticket status (`closed` → `409`; `resolved` agent → no-op; `resolved` customer → reopen to `waiting_on_support`, Resolution OD-8; `waiting_on_customer` customer → `waiting_on_support`; every other status/actor combination is undefined by any FR/AC, carried as non-blocking API_DESIGN OQ-1); enforce FR-5 (`visibility: "internal"` from a customer → `403`, service-level check, the `CHECK` constraint is a backstop only per db-design v3's explicit layering note — must not be implemented by catching `IntegrityError`); validate `body` length (FR-7, reuse the existing `ValidationFailedError`/`FieldError` shape); the reply-scoped attachment-ownership check (reuse `create_ticket`'s existing per-attachment ownership loop, `AttachmentNotOwnedError`, against the new bind method); the new 30/hour rate-limit check and cache write; the `first_response_at` stamp (once, on the first public agent reply); and post-commit email dispatch (FR-1 requester notification, FR-2 queue notification) via two new `EmailSender` methods (see below). New/extended `Protocol`s in this file: `TicketReplyRepositoryProtocol`, an extended `AttachmentRepositoryProtocol` (new bind method), a reply-rate-limit-cache protocol. Mapping a caller's `support_agent`/`admin` role to `author_kind`'s two-value vocabulary is a service-layer decision per db-design v3 (`"tickets:write" in current_user.scopes` is already the exact check `support/dependencies.py::reject_agent_queue_access` uses today, so the derivation itself is not new — only its use for `author_kind`/`app.actor_kind` is).
- **RLS session context — new mechanism, not yet decided where it lives.** The DB design's `ticket_replies` RLS policies read `current_setting('app.actor_kind', true)`; the NFR requires `SET LOCAL app.actor_kind = ...` / `SET LOCAL app.actor_id = ...` inside the same transaction "via a shared dependency so no session can start without them." Confirmed by direct read of `app/db/dependencies.py` and `app/db/session.py`: no `SET LOCAL`, no per-actor-kind session state, and no hook point for one exists anywhere in this codebase today — this is the first story to need it. Db-design v3 explicitly defers *which* service-layer code path sets it; this survey flags that the two natural placements have different blast radii — a new dependency scoped to only this story's two routes (e.g. in `support/dependencies.py`, wrapping `get_db_session`) touches no other module, whereas modifying the shared `app/db/dependencies.py::get_db_session` would run `SET LOCAL` on every request in the application. Not decided here — `IMPLEMENTATION_PLANNING` must pick one, since it changes which files the corresponding task touches.

### Cross-cutting `app/core/` files

- **`app/core/email.py`** — `EmailSender` Protocol needs two new methods (FR-1's requester notification, FR-2's queue notification) and `LoggingEmailSender` needs matching implementations. Confirmed by direct read: `LoggingEmailSender` is the only `EmailSender` implementation in this codebase, so exactly one class needs the two new methods, not several.
- **`app/core/config.py`** — needs a new `Settings` field for the support-queue mailbox address (Resolution OD-2: "a shared support address, e.g. `support-queue@portal.internal`"). Confirmed by direct read: no such field exists in `Settings` today, and this gap was already flagged by v1 of this document (2026-09-04) — it is carried forward here as confirmed unresolved, not restated speculatively.

### Router / dependencies / exceptions layer

- **`app/modules/support/router.py`** — two new routes: `POST /support/tickets/{id}/replies` and `GET /support/tickets/{id}`. Confirmed by direct read: today's router has only `POST ""` (create) and `GET ""` (list) — there is no existing `GET /{id}` handler to modify, so the ticket-detail-plus-thread endpoint is wholly new, not an extension. The agent-authorization branch is the first place this module imports `app.modules.roles.dependencies.require_scope` — confirmed by direct read, today's router only imports from `support.dependencies` and `users.dependencies`.
- **`app/modules/support/dependencies.py`** — a new provider function for whichever service object ends up handling replies (either an extended `get_ticket_service` with more collaborators injected, or a new `get_ticket_reply_service`), and possibly the new RLS-context-setting dependency described above.
- **`app/modules/support/schemas.py`** — new `CreateReplyRequest`, `ReplyRead`, `ReplyThreadPage`, `TicketDetailRead` schemas (openapi v3 `components.schemas`). Confirmed `TicketDetailRead` is new, not a rename of the existing `TicketRead` (which stays as-is for `POST`/`GET`-list; `TicketDetailRead` adds `first_response_at` and the nested `replies` page, per openapi v3).
- **`app/modules/support/exceptions.py`** — new `ProblemError` subclasses: a `409 ticket-closed` error (FR-6, first use of this slug in the codebase); a `404 not-found` error for FR-4 (confirmed by direct read: no `not-found` class exists in this module today; `admin_users/exceptions.py::NotFoundError` is the precedent for a module owning its own copy of a shared slug, per this codebase's established pattern already used for `AccountDeactivatedError` here); a rate-limit-exceeded error for the new 30/hour reply limit (parallel to, but distinct from, `TicketCreationRateLimitError`, since the retry-after/detail text differs). Whether FR-5's `403 insufficient-permission` reuses `app.modules.roles.exceptions.InsufficientPermissionError` directly or gets its own module-owned subclass (this module's established precedent for `AccountDeactivatedError`) is not decided by any design document — flagged for `IMPLEMENTATION_PLANNING`.

## Cross-Module Ripple

| Caller | Callee | New or existing | Reason |
|---|---|---|---|
| `app.modules.support.router` | `app.modules.roles.dependencies.require_scope` | New caller edge (function already exists, reused) | Agent-branch authorization for both new routes (`tickets:write` / `tickets:read`), same factory `roles.dependencies.py:30` already provides to `audit/dependencies.py::require_audit_read`. |
| `app.modules.support.service` | `app.modules.users.service.UserServiceProtocol` (`get_email_for_user`) | Existing edge, reused | FR-1's requester-notification email lookup — same collaborator `create_ticket` already injects; no new cross-module dependency needed for this. |
| `app.modules.support.service` | `app.core.email.EmailSender` | Existing edge, new methods added to the Protocol | FR-1/FR-2 notification dispatch. |
| `app.modules.support.service` | `app.core.config.Settings` (new field) | New | FR-2's queue-notification recipient address — a static config read, not a service call. |
| `app.modules.support.service` / `app.modules.support.dependencies` | (new) RLS session-context setter | New mechanism, placement undecided | See "RLS session context" above — the first cross-cutting session-state write this codebase has needed. |

No new dependency on `app.modules.audit.service` was found: unlike US-4.1's `create_ticket` (which the story's own audit trail explicitly covers), no FR/AC in spec v6 requires an audit-log entry for a reply. Not inventing this call — flagged only as an absence, per this skill's own constraint against adding scope no FR/AC states.

## Migration / Schema Impact

**Yes, a migration is required.** One new table, two additive columns on existing (already-shipped, potentially populated) tables, and PostgreSQL RLS — the first use of RLS anywhere in this codebase.

- **New table `ticket_replies`:** `CREATE TABLE` with the `CHECK` constraint — autogeneratable, no hand-guard needed for the table/column/constraint DDL itself (only the RLS statements below need the guard).
- **`tickets.first_response_at`:** additive, `nullable=True`, no default beyond `NULL` — ordinary `ALTER TABLE ... ADD COLUMN`, no backfill (no existing ticket has a prior public agent reply to retroactively stamp), no expand/migrate/contract sequencing needed.
- **`attachments.ticket_reply_id`:** additive, `nullable=True`, plus a new `index=True` — same no-backfill reasoning, but see the carried DR-2 finding above on whether the index needs `CREATE INDEX CONCURRENTLY`.
- **RLS DDL (`ENABLE`/`FORCE ROW LEVEL SECURITY`, two `CREATE POLICY` statements):** hand-written `op.execute()`, not reached by `env.py`'s Rewriter — each needs its own `sa.inspect(op.get_bind())` idempotency guard per `AGENTS.md` §4, and `downgrade()` must actually reverse it (drop policies, disable RLS), not `pass`.
- **Existing repository queries potentially affected by this migration:** none. `TicketRepository.create` and `list_for_requester` do not read/write `first_response_at`; `AttachmentRepository`'s existing methods (`get_by_id`, `bind_to_ticket`, `find_unbound_older_than`, `purge`) do not read/write `ticket_reply_id`. Both new columns are additive and nullable, so no existing `INSERT`/`SELECT` needs to change to keep working.

## Test-Surface Impact

**Existing files that must change:**
- `tests/integration/modules/support/test_support_router.py` — new test cases for both new routes (happy paths TR-AC1/TR-AC2/TR-AC3, negative paths TR-AC4-TR-AC7), plus the RLS-specific test the spec's own NFR requires ("queries through a customer-context connection with the application filter deliberately disabled").
- `tests/unit/modules/support/test_support_service.py` — new test cases for the new service method(s)' branching (actor-kind authorization, status-gating, rate limit, attachment binding, email dispatch), using hand-written fakes per `AGENTS.md` §5, consistent with this file's existing style for `create_ticket`.

**Wholly new test surface:**
- A migration proof test (or `migration-manager`'s own upgrade/downgrade/upgrade cycle) covering the RLS `CREATE POLICY`/`FORCE ROW LEVEL SECURITY` DDL specifically, since no existing migration test in this codebase exercises RLS.
- No new test *file* is required beyond what's listed above — both `ticket_replies`' new endpoints extend the same router/service the existing test files already cover; `test-writer` may choose to split the reply-specific cases into new files, but that is `test-writer`'s own call, not dictated by this survey.

## Findings Carried Forward (not this survey's own, cited for continuity)

- DESIGN_REVIEW DR-2 (Minor): migration-mechanics gap on `attachments.ticket_reply_id`'s index — restated above under Database/models layer with the specific `AGENTS.md` §4 mechanism and codebase precedent it needs.
- API_DESIGN OQ-1 (non-blocking): FR-2's status transition for a customer reply on a ticket that is neither `waiting_on_customer` nor `resolved` is unstated by any FR/AC — restated above under Service layer, since it is exactly the branch `service.py`'s status-gating logic will need to either implement or explicitly leave unhandled.
- API_DESIGN OQ-2 (non-blocking): `POST /replies`' generalized `404` for a caller with neither ownership nor `tickets:write` is not literally stated by any FR — currently unreachable under the shipped role seed (confirmed: `tickets:read`/`tickets:write` are always granted together in `e50fbe8161fc_add_roles_and_permissions.py`), so this is inert in practice but the router/service must still implement the branch the contract promises.
- GET `limit` enforcement: openapi v3 states `minimum: 1`/`maximum: 100`/`default: 50`, but this module's existing `GET /support/tickets` route accepts a bare `limit: int = 100` with no `Query(ge=1, le=100)` enforcement (confirmed by direct read of `router.py`). The new `GET /support/tickets/{id}` route must not repeat that gap.
