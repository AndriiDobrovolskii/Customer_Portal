---
artifact_type: impact_analysis
story: US-4.3
version: 1
status: ARCHIVED
created_at: "2026-09-06T19:00:00Z"
updated_at: "2026-09-06T19:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/reviews/specifications/US-4.3-spec-review.md
    version: 3
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.3-design-review.md
    version: 3
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
supersedes: null
---

# Impact Analysis: Ticket Resolution (US-4.3 / spec US-4.3)

**Spec:** docs/specifications/US-4.3-spec.md (v2)
**API design:** docs/designs/api/US-4.3-api-design.md, US-4.3-openapi.yaml (v2)
**DB design:** docs/designs/database/US-4.3-db-design.md, US-4.3-entity-model.md (v3)
**Design review:** docs/reviews/designs/US-4.3-design-review.md (v3, PASS, no unresolved Critical/Major finding)

`app/modules/support/` already exists (US-4.1/US-4.2, PR #16 and this story's own dependency). This story extends it with three new endpoints (`/resolve`, `/close`, `/reopen`), one modification to the already-shipped `POST .../replies` path (FR-4), one new scheduled batch script, and one Alembic migration. Every file below and its reason was confirmed by directly reading the current `app/modules/support/*` source, not inferred from the design documents' own citations.

## Affected Files

### Database / models layer (`AGENTS.md` §3: models before repository)

- **`app/modules/support/models.py`** — four additive, nullable columns on the existing `Ticket` class: `resolved_at` (`DateTime(timezone=True)`), `resolution_note` (`String(5000)`), `closed_at` (`DateTime(timezone=True)`), `closed_by` (`Mapped[uuid.UUID | None]`, no `ForeignKey`) — db-design v3 "Existing table: tickets". Two new `CheckConstraint`s (`ck_tickets_closed_requires_closed_fields`, `ck_tickets_resolved_requires_resolution_fields`) and one new partial `Index` (`ix_tickets_resolved_at_pending_autoclose`, `resolved_at` `WHERE status = 'resolved'`). Confirmed by direct read: `Ticket` today has none of these four columns and its only `__table_args__` entry is `ix_tickets_requester_id_created_at_id` — all four additions are genuinely new, not renames.
- **New Alembic revision under `migrations/versions/`** — touched because: (1) four `ALTER TABLE tickets ADD COLUMN ...` statements, additive/nullable, autogeneratable, no backfill (no existing ticket has ever been resolved or closed); (2) two `CHECK` constraints and one partial index, also autogeneratable DDL, no hand-written `op.execute()` expected (unlike US-4.2's RLS policies) — but `migration-manager` must still read the generated file and confirm Alembic's autogenerate actually emitted the partial-index `postgresql_where` clause and both `CHECK` expressions verbatim, since a missed clause here is silent, not an error.

### Repository layer

- **`app/modules/support/repository.py`** — `TicketRepository` needs new method(s) for the three endpoints' conditional `UPDATE`s. Confirmed by direct read: today's `TicketRepository.update()` (lines 87-109) is **unconditional** — it builds `UPDATE ... WHERE id = :id` with no status predicate at all, so it cannot satisfy FR-9's "conditional update scoped to the expected current status" requirement (a losing concurrent caller must get `rowcount == 0`, not silently overwrite). `/resolve` (source status ∈ `open`/`waiting_on_support`/`waiting_on_customer`, OD-5), `/close` (source status ≠ `closed`), and `/reopen` (source status = `resolved` **and** the inclusive 7-day window, `resolved_at >= now() - interval '7 days'`, DR-2) each need their own status-scoped (and, for `/reopen`, window-scoped) `WHERE` clause — none of them can reuse `update()` as it exists today. The auto-close job (FR-3) needs a batch-scoped conditional `UPDATE ... WHERE status = 'resolved' AND resolved_at < now() - interval '7 days'` served by the new partial index — also not expressible with the existing method.
- **`app/modules/support/repository.py`** (same file) — FR-4's reply-driven reopen transition (the existing `POST .../replies` path) also needs the identical window-scoped conditional `UPDATE` (DR-2: "both transitions' `WHERE` clause must … read" the same predicate as `/reopen`), so whatever new method serves `/reopen` must also serve `TicketReplyService.create_reply`'s status-transition branch (`service.py` line 515-518 today) — confirmed this is not automatically true today since that branch currently calls the same unconditional `update()`.

### Service layer

- **`app/modules/support/service.py`** — three new business-logic paths (`/resolve`, `/close`, `/reopen`), each implementing api-design v2's stated check order (lookup/ownership → transition validity `409` → permission `403` → conditional update) and each writing one `audit_log` entry via the already-injected `AuditServiceProtocol`/`record_event(...)` (`TicketService.__init__` already takes `audit_service`, confirmed lines 156-172 — no new collaborator needed for whichever of these three lands on `TicketService`).
- **`app/modules/support/service.py`** (same file) — `TicketReplyService.create_reply`'s existing status-transition branch (line 515-518, "Resolution OD-8: the resolved-ticket case reopens the ticket") must gain an `audit_log` write (`event=ticket_reopened`, `actor=self`) per DESIGN_REVIEW v2's DR-4 finding. Confirmed by direct read: **`TicketReplyService.__init__` (lines 394-421) has no `audit_service` parameter at all today** — unlike `TicketService`, this class currently has zero dependency on `AuditServiceProtocol`. Adding FR-4's audit write is therefore not just a new call inside an existing method — it requires a new constructor parameter on `TicketReplyService` and, consequently, a change to whatever wires it (see Cross-Module Ripple and `dependencies.py` below).
- **Where `/close` and `/reopen` land is not decided by any design document.** Both endpoints share `/close`'s existing requester-or-agent authorization shape (api-design v2: "same requester-or-agent shape as `/close`"), which is structurally the same actor-kind-dependent check `TicketReplyService.create_reply` already implements (customer ownership vs. `tickets:write` agent vs. neither → `404`) — not `TicketService`'s existing pattern, which only ever does pure ownership (`list_own_tickets`) or pure creation (`create_ticket`, no ownership branch at all). Whether `/close`/`/reopen` (and `/resolve`, which is agent-only like `TicketService.create_ticket`'s account-status gate) are added as new methods on `TicketService`, on `TicketReplyService` (which will already gain `audit_service` for FR-4), or split across both is an `IMPLEMENTATION_PLANNING` call, not decided here — flagged because it changes which file's constructor/collaborator list each task touches.

### Router / dependencies / schemas / exceptions layer

- **`app/modules/support/router.py`** — three new routes: `POST /support/tickets/{id}/resolve`, `POST /support/tickets/{id}/close`, `POST /support/tickets/{id}/reopen`. Confirmed by direct read: today's router has exactly four routes (`POST ""`, `GET ""`, `POST /{id}/replies`, `GET /{id}`) — none of these three paths exist yet, so all three are wholly new route functions, not extensions of an existing one.
- **`app/modules/support/dependencies.py`** — new provider function(s) for whichever service class(es) end up handling `/resolve`/`/close`/`/reopen` (see Service layer above). If any of the three lands on `TicketReplyService`, `get_ticket_reply_service` (lines 101-118) must add an `audit_service: AuditLogServiceDep` parameter and pass it through — confirmed by direct read this function currently constructs `TicketReplyService` with exactly five collaborators (`ticket_repository`, `reply_repository`, `attachment_repository`, `rate_limit_cache`, `email_sender`, `user_service`) and no `audit_service`, whereas `get_ticket_service` (lines 28-47) already wires `AuditLogServiceDep` through to `TicketService`. FR-4's audit fix (above) forces this wiring change regardless of where `/close`/`/reopen` land, since `create_reply` itself needs it.
- **`app/modules/support/schemas.py`** — new `ResolveTicketRequest` (`resolution_note: str = Field(min_length=1, max_length=5000)`, per FR-10 and db-design v3's `String(5000)` column), `CloseTicketRequest`/`ReopenTicketRequest` (each carrying the source story's optional, unconstrained `reason: str | None` field per api-design v2 Open Questions #4 — accepted but not persisted anywhere), and a new `TicketStateRead` response schema (`id`, `ticket_number`, `status`, `resolved_at`, `closed_at`, `updated_at` only — api-design v2 Open Questions #5's stated data-minimization scope, deliberately omitting `closed_by`/`resolution_note`). Confirmed by direct read: none of these four schemas exist in today's `schemas.py`.
- **`app/modules/support/exceptions.py`** — one new `ProblemError` subclass, `InvalidStateTransitionError` (`type_slug="invalid-state-transition"`, `status=409`), carrying the `allowed_events: list[str]` field FR-6/TC-AC5 requires. Confirmed by direct read: this module has no `409` exception today (`TicketClosedError`, US-4.2, uses a different slug, `"ticket-closed"`, and carries no `allowed_events` field); `app/modules/admin_users/exceptions.py::InvalidStateTransitionError` (US-3.1) is the cited "shared slug" precedent, but its version also carries no `allowed_events` field — confirming api-design v2's own statement that this story's subclass is additively-shaped, not the identical class, and cannot be imported directly (module-ownership convention already established here by `AccountDeactivatedError`/`InsufficientPermissionError`). FR-7 (`403`) and FR-8 (`404`) reuse this module's existing `InsufficientPermissionError` and `TicketNotFoundError` unchanged — confirmed both classes already exist with the exact shape FR-7/FR-8 need, so no new exception is required for either.

### New file, outside `app/modules/support/`

- **`scripts/auto_close_resolved_tickets.py`** (new) — FR-3's scheduled auto-close job. Confirmed by direct read of `scripts/`: no in-process scheduler exists anywhere in this codebase (no `app/` directory or dependency for APScheduler/cron-in-process); the established pattern for a periodic batch job is a standalone cron entry point invoked externally (`scripts/purge_unbound_attachments.py`'s own docstring: "Not wired to any in-process scheduler. Invoke externally, e.g. a daily cron line"). This new script follows that same shape, but is a strictly larger surface than either existing purge script: `purge_unbound_attachments.py` and `purge_unverified_accounts.py` both talk to a repository directly with no audit concern; FR-3 additionally requires a `ticket_audit_log` write (`event=ticket_auto_closed`, `actor=`the system-actor sentinel) for every ticket the job closes. Confirmed by direct read of every file in `scripts/`: **no existing script calls `app.modules.audit.service.record_event` today** — `anonymize_erased_user.py` matches a naive grep for "audit" only because it touches tables named `*_audit_log` via raw SQL, and does not call the audit service. This is the first script in the codebase that needs both a business-conditional batch `UPDATE` and a per-row audit write in the same run — no existing script is a drop-in template for that combination, only for the two halves separately.

## Cross-Module Ripple

| Caller | Callee | New or existing | Reason |
|---|---|---|---|
| `app.modules.support.service.TicketService` (whichever new method) | `app.modules.audit.service.record_event` | Existing edge, reused | `/resolve` (and `/close`/`/reopen` if placed here) writes `ticket_resolved`/`ticket_closed`/`ticket_reopened` — `TicketService` already has this collaborator injected (`audit_service`, constructor arg 5). |
| `app.modules.support.service.TicketReplyService` | `app.modules.audit.service.record_event` | **New edge** | FR-4's reply-driven reopen (DR-4) — confirmed `TicketReplyService` has no `audit_service` collaborator today; also needed if `/close`/`/reopen` land on this class instead of `TicketService`. |
| `app.modules.support.dependencies.get_ticket_reply_service` | `app.modules.audit.dependencies.AuditLogServiceDep` | **New wiring** | Consequence of the edge above — confirmed this provider function does not inject `AuditLogServiceDep` today (`get_ticket_service` does; `get_ticket_reply_service` does not). |
| `scripts/auto_close_resolved_tickets.py` (new) | `app.modules.support.repository.TicketRepository` (new batch-conditional method) | New file, existing module | FR-3's batched `UPDATE ... WHERE status = 'resolved' AND resolved_at < now() - interval '7 days'`, served by the new partial index. |
| `scripts/auto_close_resolved_tickets.py` (new) | `app.modules.audit.service.record_event` | **New edge, no precedent in `scripts/`** | Per-row `ticket_auto_closed` write — see "New file" note above; this is the first script-to-audit-service call in the codebase. |

No new dependency on `app.modules.roles` or `app.modules.users` beyond what `/resolve`'s existing `require_scope("tickets:write")` and `/close`/`/reopen`'s existing `CurrentUserDep` ownership pattern already provide — both mechanisms are reused unchanged (api-design v2 "Cross-Cutting Patterns Reused, Not Invented"), confirmed already present via `app.modules.roles.dependencies.require_scope` (used by `/resolve`'s US-4.2 agent-branch precedent) and `app.modules.users.dependencies.CurrentUserDep` (already imported by `router.py`).

## Migration / Schema Impact

**Yes, a migration is required.** Four additive nullable columns, two `CHECK` constraints, and one partial index — all on the existing `tickets` table. No new table.

- **`resolved_at`, `resolution_note`, `closed_at`, `closed_by`:** each `nullable=True`, no default beyond `NULL` — ordinary `ALTER TABLE ... ADD COLUMN`, no backfill needed (no existing ticket has ever been resolved or closed).
- **`ck_tickets_closed_requires_closed_fields`, `ck_tickets_resolved_requires_resolution_fields`:** both `CHECK` constraints reference only the four new columns plus `status` (already `NOT NULL`) — safe to add against existing rows, since every existing row has `status != 'resolved'` and `status != 'closed'` today (no prior code path ever wrote either value), so both constraints are trivially satisfied for all pre-existing data.
- **`ix_tickets_resolved_at_pending_autoclose`:** new partial index, `postgresql_where=text("status = 'resolved'")` — matches zero existing rows (same reasoning), so this is a cheap index build even on a populated `tickets` table; unlike US-4.2's `ix_attachments_ticket_reply_id` (carried finding on that story), there is no live-table `CREATE INDEX CONCURRENTLY` concern of comparable weight here, but `migration-manager` should still confirm this against `AGENTS.md` §4's general index-creation guidance rather than assume it from this survey (DESIGN_REVIEW's own DR-6, Minor, non-blocking, already flagged this as advisory-only).
- **Existing repository queries potentially affected:** `TicketRepository.create()` and `list_for_requester()` do not read or write any of the four new columns — no existing `INSERT`/`SELECT` needs to change. `TicketReplyRepository`'s methods are entirely unaffected (no column on `ticket_replies` changes). The one behavioral change to existing code is `TicketReplyService.create_reply`'s status-transition branch (FR-4), which starts calling a new, window-scoped conditional update method instead of today's unconditional `TicketRepository.update()` — this changes *which* method that existing call site invokes, not any other existing query.

## Test-Surface Impact

**Existing files that must change:**
- `tests/integration/modules/support/test_support_router.py` — new test cases for the three new routes' happy paths (FR-1/FR-2/FR-3-equivalent-at-the-route-level/FR-5) and negative paths (FR-6/FR-7/FR-8/FR-9/FR-10), plus a case for FR-4's now-modified `POST .../replies` behavior (a reply on a `"resolved"` ticket within the 7-day window) and its new audit-log side effect.
- `tests/unit/modules/support/test_support_service.py` — new test cases for whichever service class ends up hosting `/resolve`/`/close`/`/reopen`'s branching (check order, conditional-update race loss → `409`, audit write), using hand-written fakes per `AGENTS.md` §5, matching this file's existing style. Also needs a new/extended case for `TicketReplyService.create_reply`'s FR-4 audit write, since that method's existing tests do not yet exercise an `audit_service` collaborator.
- `tests/unit/modules/support/test_support_schemas.py` — new cases for `ResolveTicketRequest`'s `resolution_note` length validation (FR-10) and the two new `*TicketRequest` schemas' `reason` field acceptance.

**Wholly new test surface:**
- A test file/module for `scripts/auto_close_resolved_tickets.py` (FR-3) — no existing test file covers any of the three current `scripts/*.py` batch jobs' entry points directly by name, so this is new regardless of whether it's a new file or a new module within an existing test tree; `test-writer` decides the exact location.
- A migration proof (`migration-manager`'s own upgrade/downgrade/upgrade cycle) covering the two new `CHECK` constraints and the partial index specifically — no existing migration test in this codebase exercises a partial index with a `postgresql_where` clause.

## Findings Carried Forward (not this survey's own, cited for continuity)

- API_DESIGN Open Questions #1 (non-blocking): the response for `/resolve`/`/reopen` on a `"resolved"` ticket outside the 7-day window but not yet auto-closed is undefined by any FR — restated above under Service layer as one of the branches whichever hosting method must either implement or explicitly leave unhandled.
- API_DESIGN Open Questions #2 (non-blocking): FR-6's `409` generalized to every non-normative source state for all three endpoints — restated above under Repository/Service layers as the exact set of source-status predicates each new conditional-`UPDATE` method must encode.
- DESIGN_REVIEW DR-5/DR-6/DR-7 (v2, Minor, non-blocking, unaddressed by any design revision): DR-5 (the same undefined-response gap as API_DESIGN OQ-1, but for the reply endpoint too), DR-6 (the new partial index's `CREATE INDEX CONCURRENTLY` question, restated above under Migration/Schema Impact), DR-7 (`reason` field on `/close`/`/reopen` has no `maxLength` — restated above under Router/schemas layer as "unconstrained" by design).
- DR-8 (design_review v3, Minor, non-blocking): `US-4.3-api-design.md`'s FR-4 side-effect narrative was never updated to mention the now-decided `audit_log` write (DR-4) — a documentation gap only, no code-file impact beyond what this survey already lists for `service.py`/`dependencies.py`.
