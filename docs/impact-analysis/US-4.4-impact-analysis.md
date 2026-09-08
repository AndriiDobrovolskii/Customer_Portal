---
artifact_type: impact_analysis
story: US-4.4
version: 1
status: DRAFT
created_at: "2026-09-07T23:00:00Z"
updated_at: "2026-09-07T23:00:00Z"
produced_by: impact-analyzer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/reviews/designs/US-4.4-design-review.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Impact Analysis: Agent Ticket Queue & Assignment (US-4.4)

Blast-radius survey only — sequencing, risk mitigation narrative, and
validation strategy are `planner`'s/`implementation-planner`'s job, not
this artifact's. Every file below was checked against the actual code in
`app/modules/support/`, `app/modules/roles/`, `app/modules/users/`,
`app/modules/audit/`, and `migrations/versions/`, not inferred from the
designs alone.

**Input currency confirmed.** All nine consumed artifacts were read
directly (not assumed from the invocation prompt) and are `version: 1`,
non-`SUPERSEDED`/non-`ARCHIVED` on disk, matching the `inputs:` recorded
above — including `specification_review` (`APPROVED`, PASS, its one Low
finding on `limit` bounds already carried into `api_design`'s own Open
Questions #3, no new survey impact). `docs/workflow/active-story.yaml`
and `docs/workflow/workflow-state.yaml` agree the active story is US-4.4
and the current stage is `IMPACT_ANALYSIS` (both read-only; neither is
written by this skill).

## 1. Affected files by AGENTS.md §3 layer

### `models.py` — `app/modules/support/models.py`

- **`Ticket.assignee_id`** (new column): `Mapped[uuid.UUID | None]`,
  `ForeignKey("users.id")`, `nullable=True`, no default — FR-3/FR-4, Data
  Model Notes, db-design.md/entity-model.md. `Ticket.__table_args__`
  (currently lines 37-67: two indexes, two `CheckConstraint`s) grows three
  new `Index(...)` entries:
  - `ix_tickets_queue_default_updated_at_id` on `(updated_at, id)`, partial
    `WHERE status != 'closed'` — FR-1's default (filterless) queue order;
    the db-designer's own addition beyond the story's literal notes (DR-1,
    confirmed by design-reviewer).
  - `ix_tickets_status_updated_at_id` on `(status, updated_at, id)` — FR-2's
    `status` filter.
  - `ix_tickets_assignee_id_updated_at_id` on `(assignee_id, updated_at,
    id)` — FR-2's `assignee_id` filter (equality and `IS NULL`).
  No `CHECK` constraint added (db-design.md's explicit reasoning: a closed
  ticket legitimately retains its last `assignee_id`).

### `schemas.py` — `app/modules/support/schemas.py`

- **`AgentTicketRead`** (new): every `TicketRead` (lines 24-40) field plus
  `assignee_id` — FR-1/FR-2 queue item, OD-1's adopted schema.
- **`AgentTicketListResponse`** (new): FR-1/FR-2 envelope, parallel to
  `TicketListResponse` (lines 43-45).
- **`AgentTicketStateRead`** (new): every `TicketStateRead` (lines 142-156)
  field plus `assignee_id` — FR-3/FR-4/FR-9 assign/unassign response, OD-1's
  adopted schema.
- **`AssignTicketRequest`** (new): `{assignee_id: uuid.UUID}`,
  `extra="forbid"` — FR-3 request body.
- `TicketRead` / `TicketListResponse` / `TicketStateRead` are **not**
  modified — confirmed field-for-field against the API design's restated
  copies (design review already verified no drift); this is the whole
  point of OD-1's adopted resolution (keeps `/close`/`/reopen`'s
  customer-reachable contract untouched).

### `repository.py` — `app/modules/support/repository.py`

- **New list method** on `TicketRepository` (e.g. `list_for_agent_queue`):
  FR-1/FR-2's `(updated_at, id)`-ordered, multi-filter (`status`,
  `category`, `assignee_id` incl. `me`/`none`) keyset query. Confirmed by
  reading `list_for_requester` (lines 60-91, `(created_at, id)`-desc,
  single `requester_id` equality filter, cursor codec tied to
  `created_at`): it cannot be extended in place without changing its sort
  column and filter contract for the *existing* customer-branch caller —
  a new method is required, not an extension of this one. Confirms DR-5.
- **New cursor codec** for the `(updated_at, id)` ordering: `_encode_cursor`
  / `_decode_cursor` (lines 23-34) are `(datetime, uuid.UUID)`-shaped and
  already generic enough to reuse verbatim by passing `updated_at` instead
  of `created_at` — but the *decision predicate* built from the decoded
  tuple (`Ticket.created_at < cursor_created_at`, line 74-79) is
  ordering-direction-specific (desc there; FR-1's agent branch is
  oldest-first, i.e. ascending) and filter-specific, so the new list
  method needs its own `WHERE`-building logic even if it reuses the same
  encode/decode helpers.
- **New conditional-update method(s)** for assign/unassign: a
  `UPDATE tickets SET assignee_id = :new WHERE id = :id AND status !=
  'closed' AND assignee_id IS NOT DISTINCT FROM :expected RETURNING *`
  (FR-3/FR-10) and an unconditional `UPDATE ... WHERE id = :id AND status
  != 'closed'` (FR-4). Same `.returning()` / zero-rows-affected idiom as
  `transition_status` (lines 117-162), but not a call to
  `transition_status` itself — no `status` value is written by either
  operation, so this is new method(s), not a new parameter on the existing
  one.

### `service.py` — `app/modules/support/service.py`

- **`TicketRepositoryProtocol`** (lines 61-94): grows the new method
  signatures above.
- **New cross-module Protocol** for FR-8's target-validation ("does the
  named user hold `tickets:write`") — see Cross-Module Ripple below; no
  existing Protocol in this file reaches into `roles`.
- **New `TicketService` method** for the agent queue (parallel to
  `list_own_tickets`, lines 361-391): FR-1/FR-2, including `assignee_id=me`
  (resolves to the caller) / `=none` (IS NULL) resolution — logic not
  present anywhere in this file today.
- **New `TicketService` method** `assign_ticket(...)`: FR-3/FR-7/FR-8/FR-9/
  FR-10. Check order is genuinely new relative to every existing
  transition method in this file — `resolve_ticket`/`close_ticket`/
  `reopen_ticket` (lines 393-539) all check ticket lookup/ownership
  *before* permission; `assign_ticket` runs the permission gate *first*
  (no ticket lookup needed for a scope check), per API design's stated
  departure from that precedent.
- **New `TicketService` method** `unassign_ticket(...)`: FR-4, OD-3's
  409-on-closed default, unconditional clear, its own unresolved
  "does an idempotent no-op still audit?" branch (API design Open
  Questions #5) — not fixed by any upstream artifact; this is a `service.py`
  decision point for whoever implements it, not something this survey
  scopes further.
- Both new methods write to `AuditServiceProtocol.record_event(...)`
  (already imported, lines 137-152) with new `event` values
  (`ticket_assigned`, `ticket_unassigned`) — reused signature, no Protocol
  change needed there.

### `router.py` — `app/modules/support/router.py`

- **`list_own_tickets`** (lines 58-80): drop
  `dependencies=[Depends(reject_agent_queue_access)]`; branch on
  `tickets:read` presence to call either the existing customer-branch
  service method or the new agent-branch one; new query params `category`,
  `assignee_id`; `response_model`/return type becomes a
  `TicketListResponse | AgentTicketListResponse` union — a genuinely new
  pattern for this router file (every other route here returns one
  concrete model).
- **New route** `POST /{id}/assign` → `AgentTicketStateRead`.
- **New route** `DELETE /{id}/assign` → `AgentTicketStateRead`.

### `dependencies.py` — `app/modules/support/dependencies.py`

- **Remove** `reject_agent_queue_access` (lines 53-65) — In Scope
  explicitly retires it; `resolve_actor_kind` (lines 67-74), which reuses
  the same scope check internally, is unaffected and stays.
- **New wiring**: whichever service ends up owning `assign_ticket`/
  `unassign_ticket` needs the roles-service collaborator injected — either
  a new constructor arg on `get_ticket_service` (lines 28-47) or a new
  `get_ticket_assignment_service`-style factory, sourcing
  `app/modules/roles/dependencies.py::RoleServiceDep` (already exported,
  confirmed present) rather than constructing `RoleService` directly.
- **Possibly new**: a reusable 404-vs-403 permission-check dependency for
  `assign`/`unassign` (API design Open Questions #1 leaves this open
  between "reusable dependency mirroring `reject_agent_queue_access`'s old
  shape" and "inlined in the service") — not resolved by any design
  artifact; a genuine implementation-planning decision, not scoped further
  here.

### `exceptions.py` — `app/modules/support/exceptions.py`

- **Remove** `AgentQueueNotAvailableError` (lines 72-81) — In Scope
  explicitly retires it.
- **New** `AssignmentConflictError` (409, slug `assignment-conflict`) —
  FR-10; confirmed this slug does not exist anywhere yet in this file or
  project (first use, per API design).
- **Reused, no new class**: `InvalidStateTransitionError` (lines 123-140)
  with `allowed_events=[]` for FR-9 and FR-4's OD-3 default;
  `InsufficientPermissionError` / `TicketNotFoundError` (existing) for
  FR-7; `ValidationFailedError` (existing) for FR-8/OD-4 — new call sites
  only, no new class needed for any of these four.

### `cache.py` — `app/modules/support/cache.py`

- **No change.** Neither FR-3 nor FR-4 nor the OpenAPI fragment declares
  an `Idempotency-Key` header or a rate limit for `assign`/`unassign`
  (unlike `create_ticket`/`create_reply`, which both have dedicated Valkey
  gateways in this file) — confirmed by re-reading the full fragment; no
  cache surface is touched.

### Out-of-module caller — `scripts/auto_close_resolved_tickets.py`

- **No change.** This script imports `TicketRepository`/`Ticket` directly
  (bypassing `service.py`, per its own docstring) and calls
  `auto_close_resolved_past_window`, whose `UPDATE` sets `status`,
  `closed_at`, `closed_by` only — it never references `assignee_id`, so a
  new nullable, no-default column requires no change to this script.
  Noted explicitly because it is the one caller of `TicketRepository` in
  this codebase outside `service.py`/`router.py`/the test suite, and §1
  above enumerates only in-module repository consumers.

## 2. Cross-module ripple

- **Caller:** `app/modules/support/service.py` (new `assign_ticket`
  method). **Callee:** `app/modules/roles/service.py::RoleService
  .resolve_scopes_for_user` (confirmed present, `service.py:94-105`) — FR-8's
  "does the named `assignee_id` hold `tickets:write`" check.
  **This is a new cross-module dependency.** A grep of
  `app/modules/support/` for `roles` today matches only two files
  (`exceptions.py`, `dependencies.py`) and both hits are prose/comments
  referencing `roles.dependencies.require_scope` by name, not an import —
  `support` has no live call into `roles` today. This story is the first
  to require one, and it must be wired as a new `RoleServiceProtocol` in
  `service.py` (mirroring the existing `AuditServiceProtocol`/
  `UserServiceProtocol` shape) plus a new constructor argument, sourced at
  `dependencies.py` from the already-existing `RoleServiceDep`
  (`app/modules/roles/dependencies.py:27`) rather than constructing
  `RoleService` directly. Verified against `pyproject.toml`'s
  `[tool.importlinter]` contracts: Contract 1 (the per-module
  router→dependencies→service→repository|cache→models|schemas layering) is
  wildcarded per-module (`containers = ["app.modules.*"]`) and does not
  restrict which *other* modules a given module's `dependencies.py` may
  import — confirmed by precedent: `support/dependencies.py` already
  imports both `app.modules.audit.dependencies` and
  `app.modules.users.dependencies` today. Adding
  `app.modules.roles.dependencies` follows the identical, already-used
  pattern; no `importlinter` contract needs a change. `service.py` itself
  imports nothing from `roles` either way (the collaborator is a
  `Protocol`, resolved by dependency injection at `dependencies.py`), so
  Contract 4 ("services must not import ... raw infrastructure clients")
  and the layering contract are both satisfied the same way
  `AuditServiceProtocol`/`UserServiceProtocol` already are.
- **Caller:** `app/modules/support/service.py` (new `assign_ticket`,
  OD-4's deactivated-account check). **Callee:**
  `app/modules/users/service.py::UserService.get_account_status_for_user`
  (confirmed present, `service.py:698`) — **not new**: `TicketService`
  already holds this exact collaborator via `UserServiceProtocol` (lines
  155-165) and already calls it in `create_ticket` (line 227) for a
  different FR; the assign path reuses the same method against the
  *target* user id instead of the caller's own.
- **Caller:** `app/modules/support/service.py` (new `assign_ticket`/
  `unassign_ticket`). **Callee:**
  `app/modules/audit/service.py::record_event(...)` — **not new**: same
  generic path already used by `create_ticket`/`resolve_ticket`/
  `close_ticket`/`reopen_ticket`, service→service per AGENTS.md §3, no
  direct `AuditRepository`/`AuditLog` import either before or after this
  story.
- No new inbound caller (nothing outside `support` reads `assignee_id`
  per spec/design — `AgentTicketRead`/`AgentTicketStateRead` are consumed
  only by this story's own two routes/one route-branch).

## 3. Migration/schema impact

**Required: yes.**

- Table: `tickets` (existing, `app/modules/support/models.py`).
- New column: `assignee_id UUID NULL REFERENCES users(id)` — no
  `ondelete` override (`RESTRICT`-by-default, same placeholder pattern as
  `requester_id`/`uploaded_by`, pending BR-007).
- New indexes, all on `tickets`:
  `ix_tickets_queue_default_updated_at_id` (partial, `(updated_at, id)`
  `WHERE status != 'closed'`), `ix_tickets_status_updated_at_id`
  (`(status, updated_at, id)`), `ix_tickets_assignee_id_updated_at_id`
  (`(assignee_id, updated_at, id)`).
- **Additive only** — no column type change, no `NOT NULL` addition, no
  backfill, no destructive step. `AGENTS.md` §4's expand→migrate→contract
  cycle is not required (that cycle is only for destructive changes).
- **Existing repository queries checked for impact:** `TicketRepository
  .create` (models.py-backed `Ticket(...)` constructor, repository.py
  lines 41-54) supplies only the four fields it always has — a new
  nullable, no-default column requires no change to this call site, and
  every pre-existing row gets `assignee_id = NULL` on migration (no
  backfill needed since the column is nullable with no `NOT NULL`).
  `list_for_requester`, `update`, `transition_status`,
  `auto_close_resolved_past_window` (repository.py) touch no column this
  story adds or changes and need no modification.
- **Partial-index Rewriter caveat** (`AGENTS.md` §4) applies to
  `ix_tickets_queue_default_updated_at_id` — the same guard-injection
  treatment `migration-manager` already applied to the existing
  `ix_tickets_resolved_at_pending_autoclose` partial index in migration
  `242e0dba5ba2` (confirmed present in `models.py` lines 48-52).
- **Migration chain:** confirmed by scanning every `down_revision` in
  `migrations/versions/` — the current head is `242e0dba5ba2`
  (`add_ticket_resolution_columns`); no other migration branches off it.
  The new migration for this story chains directly from that head.

## 4. Test-surface impact

### Existing files that must change

- `tests/integration/modules/support/test_support_router.py`
  - `test_list_own_tickets_agent_scope_caller_returns_403` (line 697) —
    confirmed the sole existing test asserting the `403
    agent-queue-not-available` response this story removes (design review
    already verified this is the only such test in the codebase). Per the
    spec's own NFR, it must be **updated, not deleted** — its replacement
    assertion is the new agent-branch `200` behavior (FR-1/FR-2).
  - The existing customer-branch tests (`test_list_own_tickets_returns_
    only_callers_tickets_newest_first` line 277,
    `test_list_own_tickets_malformed_cursor_returns_422` line 326, the
    four `401` tests lines 520-556) are not expected to change in
    assertion (FR-5 requires the customer branch stay byte-identical),
    but every one of them exercises the same route this story adds a
    second branch and two new query params to — each is a regression
    check that must still pass unmodified once the router changes land.
- `tests/unit/modules/support/test_support_service.py`
  - `FakeTicketRepository` (line 97) must gain the new
    `TicketRepositoryProtocol` methods (agent-queue list, assign/unassign
    conditional updates) — without this, any existing test constructing
    `TicketService(...)` with this fake breaks structurally once the
    Protocol grows.
  - A new `FakeRoleService` (no existing analog in this file) is needed to
    exercise FR-8's target-validation branch, since this is the first
    cross-module collaborator into `roles` this test file will need to
    fake.
  - `FakeUserService` (line 339) already exposes
    `get_account_status_for_user`; reusable as-is for OD-4's
    deactivated-target check, subject to confirming (at
    `IMPLEMENTATION_PLANNING`) that its fake API supports querying an
    arbitrary target id, not only the caller's own.

### New test files/cases (net-new)

- New unit tests, added to `test_support_service.py` (this project's
  one-file-per-module test convention — not a new file) covering the
  agent-queue listing (filters, ordering, `assignee_id=me`/`none`
  resolution — FR-1/FR-2), `assign_ticket`'s full check order including
  404-before-403, closed-ticket 409, target-validation 422 (including the
  OD-4 deactivated-account variant), and concurrency-loss 409 (FR-10);
  `unassign_ticket`'s success/idempotent-no-op/closed-ticket-409 (OD-3)
  paths.
- New integration tests, added to `test_support_router.py`, for the `GET
  /v1/support/tickets` agent branch (200, filters, cursor pagination,
  `assignee_id` field presence — AQ-AC1/AQ-AC2), `POST`/`DELETE
  .../assign` full HTTP paths (AQ-AC3/AQ-AC4/AQ-AC7/AQ-AC8/AQ-AC9), and a
  genuine two-simultaneous-requests concurrency test (AQ-AC10, the
  Enforcement Matrix's own `[gate]` marker) — no existing test in this
  file exercises true request concurrency, so this is a new test pattern
  for this module, not only new test cases.
- A migration `upgrade → downgrade → upgrade` proof (AGENTS.md §4,
  Enforcement Matrix `[gate]`) — run directly by `migration-manager`, not
  a checked-in test file, consistent with how prior stories' migrations
  were proven.
- An `EXPLAIN`-based (or migration-review) index-coverage check for
  `ix_tickets_queue_default_updated_at_id` being selected under the
  literal `status != 'closed'` predicate (Enforcement Matrix `[gate]` if
  enforceable) — no existing analog in
  `tests/integration/modules/support/`.
- Checked for an existing checked-in OpenAPI-schema-rendering test (the
  `GET` route's response type changes to a `TicketListResponse |
  AgentTicketListResponse` union and two routes are added): a
  project-wide search for `.openapi(`/`openapi_schema`/`/openapi.json`
  in `tests/` found none. AGENTS.md §6 item 7's "OpenAPI renders" check
  is therefore not a checked-in test file this story's changes would
  modify — it is verified at `QUALITY_GATE` by running the app, out of
  this survey's file-level scope.

## Findings carried from DESIGN_REVIEW, verified against code (not re-decided here)

- **DR-3 (`updated_at` queue-reset).** Verified directly:
  `Ticket.updated_at` (`models.py` line 85-87) carries
  `onupdate=func.now()` unconditionally. Every ORM-mapped `UPDATE` against
  a `Ticket` row bumps it — confirmed by `transition_status`'s existing
  behavior (repository.py lines 159-162) issuing exactly this kind of
  update today. The new assign/unassign conditional-update method(s) (see
  §1 `repository.py`) are the same kind of `UPDATE` and will bump
  `updated_at` with **no additional code required** to produce that
  effect — i.e. the queue-reset behavior DR-3 describes is what the
  design already implies structurally, not a hypothetical. Blast radius
  if a fix is directed here: a "document as intended" resolution touches
  only spec text (no file in §1 changes); a "suppress the bump for
  assign/unassign" resolution would require the new repository UPDATE(s)
  to set `updated_at` explicitly rather than letting the column's
  `onupdate` fire, and the FR-1 ordering test named above would need to
  assert whichever behavior is chosen instead of being left implicit. This
  survey does not select a resolution — per
  `design-reviewer`'s own routing note, that decision belongs to
  `ARCHITECTURE_PLANNING`, with a route to `SPECIFICATION` still
  available if human confirmation is judged necessary before build.
- **DR-5 (new repository method/cursor codec).** Confirmed above (§1
  `repository.py`): `list_for_requester` cannot be extended in place to
  serve the agent branch without breaking its existing ordering/filter
  contract for the customer branch — a new method and a
  direction-specific `WHERE`-building routine (reusing the existing
  cursor encode/decode helpers) are required. This is now a concretely
  scoped, named task rather than an advisory note, for
  `IMPLEMENTATION_PLANNING` to schedule.
- **OD-3/OD-4.** Both remain unconfirmed per the spec. No schema-level
  blast radius attaches to either resolution (confirmed: no `CHECK`
  constraint or column definition changes either way) — the entire
  difference is contained to the `service.py`/`repository.py` entries
  already itemized in §1 (the conditional-`UPDATE` `WHERE` predicate for
  OD-3; the target-validation branch for OD-4). Both should be confirmed
  before `IMPLEMENTATION` begins, consistent with the spec's own stated
  gate — no earlier stage's artifact needs to change to accommodate
  either outcome.
