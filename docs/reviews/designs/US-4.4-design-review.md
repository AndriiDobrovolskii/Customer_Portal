---
artifact_type: design_review
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T22:00:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: design-reviewer
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
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Design Review: Agent Ticket Queue & Assignment (US-4.4)

**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

`US-4.4-api-design.md`/`US-4.4-openapi.yaml` and `US-4.4-db-design.md`/`US-4.4-entity-model.md`
(all v1, DRAFT) were reviewed together against `US-4.4-spec.md` v1 (APPROVED),
its PASS spec review, `AGENTS.md` §3–§4, and the running code in
`app/modules/support/`, `app/modules/users/`, `app/modules/audit/`, and
`app/modules/roles/`. No Critical or Major finding was found. Both designs
correctly trace every FR/AC to a contract element or a schema element, keep
the customer-facing contract provably unchanged, and correctly identify (and
decline to silently invent an answer for) three genuinely open questions of
their own — the three items this review was explicitly asked to confirm:

1. **The third, db-designer-added partial index
   (`ix_tickets_queue_default_updated_at_id`) is justified — confirmed.** A
   `(status, updated_at, id)` composite orders rows by `status` first; it
   cannot give FR-1's default (filterless) query a single global
   `updated_at` order across four non-`closed` status values without relying
   on the planner to merge four range scans, which is not a safe design
   assumption. The dedicated partial index is the correct fix, and the
   requirement that the repository's default-queue predicate be written as
   the literal `status != 'closed'` (not an `IN`-list) is accurate PostgreSQL
   planner behavior — `postgresql_where` partial-index selection proves
   predicate implication reliably for a literal `<>` comparison, not for a
   `ScalarArrayOpExpr`. See DR-1.
2. **`assignee_id`'s `onupdate=func.now()` side effect on `tickets.updated_at`
   is a real, unresolved product-behavior question — not silently
   acceptable, but also not something either design stage can fix by
   itself.** Both designs correctly decline to invent a suppression
   mechanism (no FR asks for one), but the resulting behavior — an
   assign/unassign cycle resets a ticket's position in the "longest-waiting"
   queue — is not stated anywhere in the specification, contradicts
   Assumption #8's own stated rationale, and sits oddly next to Out of
   Scope's claim that assignment is "orthogonal to the state machine." This
   is recorded as a new question in Open Decisions below (not resolved here)
   rather than as a blocking finding, because the fix is a spec/product
   decision that neither `API_DESIGN` nor `DB_DESIGN` can make unilaterally
   without inventing a requirement — looping back to either stage would only
   reproduce the same correctly-declined non-decision. See DR-3.
3. **RLS absence on `tickets` is confirmed, and FR-1's "regardless of
   requester" scope being service-layer-only is consistent with both
   designs.** Verified directly against
   `migrations/versions/9132a68b73c8_add_ticket_replies.py`: the only
   `ENABLE`/`FORCE ROW LEVEL SECURITY` and `CREATE POLICY` statements in this
   codebase target `ticket_replies`, not `tickets`. Neither design adds an
   RLS policy to `tickets`, and neither design's query relies on one being
   absent in a way that would break if one were later added without
   corresponding review. See DR-2.

Three further Minor, non-blocking items were found (DR-4, DR-5) and are
carried forward as advisory notes for `IMPLEMENTATION_PLANNING` /
`TEST_WRITING`, not as defects requiring rework of either design.

## Reviewed Artifacts

| Artifact | Version | Status |
|---|---|---|
| `docs/stories/US-4.4-agent-ticket-queue-and-assignment.md` | n/a (source) | — |
| `docs/specifications/US-4.4-spec.md` | 1 | APPROVED |
| `docs/reviews/specifications/US-4.4-spec-review.md` | 1 | PASS |
| `docs/designs/api/US-4.4-api-design.md` | 1 | DRAFT |
| `docs/designs/api/US-4.4-openapi.yaml` | 1 | DRAFT |
| `docs/designs/database/US-4.4-db-design.md` | 1 | DRAFT |
| `docs/designs/database/US-4.4-entity-model.md` | 1 | DRAFT |
| `docs/decisions/US-4.4-open-decisions.md` | 1 | DRAFT (OD-1 adopted; OD-2 confirmed; OD-3/OD-4 carried, unconfirmed, non-blocking) |

## API Design Review

- **AC/FR coverage.** All 10 ACs (AQ-AC1–AQ-AC10) map to an operation and
  status code: the `GET /v1/support/tickets` agent branch (FR-1, FR-2), the
  customer branch left untouched (FR-5, FR-6), `POST .../assign` (FR-3,
  FR-8, FR-9, FR-10), and `DELETE .../assign` (FR-4). No FR is
  unrepresented.
- **No ORM model in the contract.** All schemas (`AgentTicketRead`,
  `AgentTicketListResponse`, `AgentTicketStateRead`, `AssignTicketRequest`,
  the `*Problem` schemas) are plain DTOs. Verified against
  `app/modules/support/schemas.py`: `TicketRead`'s and `TicketStateRead`'s
  actual, shipped field lists match the fragment's restated versions
  field-for-field, and `AgentTicketRead`/`AgentTicketStateRead` are each
  exactly that field list plus `assignee_id` — no drift between the
  fragment's restatement and the running code.
- **Inbound schema.** `AssignTicketRequest` sets `additionalProperties:
  false`, declares only `assignee_id` (required), and carries no privilege
  or system field.
- **Outbound schemas.** `AgentTicketRead`/`AgentTicketListResponse`/
  `AgentTicketStateRead` each declare an explicit field list; no field
  exposes a credential, token, or session id. `assignee_id` is a plain user
  FK, already the class of value this project exposes elsewhere
  (`requester_id`, `author_id`).
- **Error coverage.** 401/403/404/409/422 are each covered exactly where
  the corresponding FR requires; no 400 is needed since no case beyond
  cursor/limit/assignee_id malformation exists, and those are folded into
  422 consistent with US-4.1's own precedent.
- **Auth per operation, matching the scope system.** `tickets:read` /
  `tickets:write` match `BR-010`'s scope-based (not role-name) authorization
  model, and match what `support_agent`/`admin` are already granted per
  `migrations/versions/e50fbe8161fc_add_roles_and_permissions.py`.
- **Check-order / IDOR discipline.** The 404-before-403 split for a
  scope-absent caller on `assign`/`unassign` (step 1, no ticket lookup
  needed) correctly reuses `TicketNotFoundError`/`InsufficientPermissionError`
  verbatim from `app/modules/support/exceptions.py` (confirmed present,
  same `type_slug`/`status`), consistent with FR-7's "never confirm the
  ticket id exists" requirement and this module's `TR-AC4`/`TC-AC7`
  precedent.
- **Backward compatibility.** The customer branch's response
  (`TicketListResponse`/`TicketRead`) is restated, not modified — the `200`
  schema widens to `anyOf: [TicketListResponse, AgentTicketListResponse]`,
  which is additive (every existing valid customer-branch body still
  validates). Removing `reject_agent_queue_access`'s `403` is a genuine
  contract change for a `tickets:read`/`tickets:write` caller specifically —
  correctly named as such (In Scope, NFR) rather than left implicit.
  Verified there is exactly one existing test asserting that `403`
  (`tests/integration/modules/support/test_support_router.py::
  test_list_own_tickets_agent_scope_caller_returns_403`), so the spec's NFR
  ("MUST update, not delete" that test) is concretely satisfiable, not an
  unfulfillable requirement.
- **`anyOf` vs `oneOf` reasoning (GET `200`).** Correct and well-justified:
  `TicketRead`/`AgentTicketRead` carry no `additionalProperties: false`
  (outbound schemas are exempt from this project's inbound-only
  `extra="forbid"` convention), so an agent-branch body would validate
  against both members under `oneOf`, which requires exactly one match.
  `anyOf` is the right choice here. See DR-4 for a related, non-blocking
  observation about the `409` response's own `oneOf`.

## Database Design Review

- **Additive-only column.** `tickets.assignee_id`: `Mapped[uuid.UUID |
  None]`, `ForeignKey("users.id")`, `nullable=True`, no default — explicit
  type, nullability, and FK target are all stated; no reliance on a
  framework default. Matches the story's Data Model Notes in intent (the
  `RESTRICT`-by-default/no-`ondelete` terminology is the same phrasing
  already used verbatim in `app/modules/support/models.py`'s own
  `requester_id` docstring — not a new imprecision this design introduces).
- **No relationship() / eager-loading N/A, with reason.** `Ticket` declares
  no `relationship()` today (verified in `app/modules/support/models.py`:
  neither `Ticket` nor `TicketReply` nor `Attachment` declares one), and
  this design adds none — consistent with this module's established
  precedent of direct repository queries over ORM graph traversal.
  `AgentTicketRead`/`AgentTicketStateRead` carry only the raw `assignee_id`
  UUID, so no nested `User` object needs eager loading. The
  `lazy="raise_on_sql"` checklist item is correctly N/A, not silently
  skipped — the design states the reason.
- **No `CHECK` constraint tying `assignee_id` to `status`.** Correct: a
  closed ticket legitimately retains its last `assignee_id` (no code path
  clears it), so a biconditional or implication constraint here would be
  actively wrong, not merely unneeded — same reasoning class as
  `US-4.3-db-design.md`'s own corrected `CHECK` constraints.
- **Migration.** Additive-only (one nullable FK column, three indexes) —
  correctly identified as not requiring an expand→migrate→contract cycle.
  The Rewriter guard-injection caveat for the two partial indexes is flagged
  for `migration-manager`. Silence on `CREATE INDEX CONCURRENTLY` for the
  three new indexes matches this project's own established precedent:
  `migrations/versions/242e0dba5ba2_add_ticket_resolution_columns.py`
  (US-4.3) added a partial index to the same, by-then-populated `tickets`
  table via plain `op.create_index(..., if_not_exists=True)`, not
  `autocommit_block()`/`CONCURRENTLY` — this design is not introducing a new
  gap relative to that precedent.
- **DR-1 — third partial index, confirmed.** See Summary #1 above.
- **DR-2 — RLS absence, confirmed.** See Summary #3 above.
- **DR-3 — `updated_at` queue-reset side effect.** See Summary #2 above and
  Open Decisions below.
- **DR-5 — agent-branch cursor/keyset mechanism not named.** See Findings
  below.
- **Audit trail.** Two new `event` values (`ticket_assigned`,
  `ticket_unassigned`) via the existing `record_event(...)` generic path —
  verified against `app/modules/audit/service.py:187-220`: the public
  signature (`category`, `event`, `actor_id: uuid.UUID`, `target_id`,
  `outcome`, `payload`) needs no change, and `actor_role` resolution via
  `_resolve_actor_role` → `RoleService.get_role_grants_for_user`
  (`app/modules/roles/service.py:107`) already handles an arbitrary,
  non-privileged `actor_id`. Placing `assignee_id` in `payload` (departing
  from US-4.1/US-4.3's `payload: NULL` precedent) is correctly justified:
  unlike `resolution_note`/`closed_at`, `tickets.assignee_id` is overwritten
  by every subsequent assign/unassign, so `target_id` alone cannot
  reconstruct history — this is the story's own Data Model Notes
  requirement, not an invention.
- **Concurrency (FR-10).** The conditional `UPDATE ... WHERE id = :id AND
  status != 'closed' AND assignee_id IS NOT DISTINCT FROM :expected` pattern
  matches the exact `.returning()` / zero-rows-affected idiom already used
  by `TicketRepository.transition_status` (`app/modules/support/
  repository.py:117-162`, US-4.3) — no new concurrency mechanism, correctly
  reused.
- **Sensitive columns.** `assignee_id` is correctly classified as a plain
  internal user reference, not a credential/token/PII field requiring
  special storage treatment.

## Cross-Model Consistency

- `assignee_id`: OpenAPI (`type: string, format: uuid, nullable: true`)
  matches the column (`uuid.UUID | None`, FK to `users.id`) exactly.
- `AgentTicketRead`/`AgentTicketStateRead` field lists match `TicketRead`/
  `TicketStateRead`'s actual shipped field lists (verified against
  `app/modules/support/schemas.py`) plus `assignee_id` — no drift.
- The three new indexes support every filter/ordering combination the
  contract exposes (`status`, `assignee_id` equality/`IS NULL`, the default
  global `updated_at` order) except the concrete keyset-pagination mechanism
  for the agent branch, which neither design names a repository method or
  cursor codec for — DR-5, non-blocking.
- No business decision appears in either design that is absent from the
  spec or an approved Open Decision, **except** the `updated_at` queue-reset
  side effect (DR-3), which is why it is called out explicitly rather than
  passed over.
- Layering (`AGENTS.md` §3) is undisturbed: the audit write is stated as a
  service→service call (`app/modules/audit/service.py`'s existing generic
  path), not a direct repository import; no router-level SQLAlchemy or
  service-level FastAPI/HTTPException usage is proposed by either design.

## Security Review of Designs

- The agent branch is scope-gated (`tickets:read`) and cannot be reached by
  widening the customer branch's own query — the two branches are stated as
  sharing a route, not a query, matching the NFR.
- `assignee_id` is excluded from `TicketRead`/`TicketListResponse`/
  `TicketStateRead` by type separation (OD-1's adopted schemas), not
  per-caller runtime redaction — the stronger of the two enforcement
  mechanisms, and consistent with this project's existing data-minimization
  pattern (`closed_by`/`resolution_note` already excluded from
  `TicketStateRead` the same way).
- `404`-before-`403` for a scope-absent caller on `assign`/`unassign`
  preserves this module's established IDOR-safety precedent (never confirm
  a ticket id exists to an unauthorized caller).
- FR-8's assign-target validation (does the named user hold `tickets:write`)
  requires a service→service lookup against `RoleService` — the exact
  capability already exposed by `RoleService.resolve_scopes_for_user`
  (`app/modules/roles/service.py:94`), so this design does not require a new
  cross-module authorization primitive to be built; deferring the concrete
  call site to `IMPLEMENTATION_PLANNING` is appropriate, not a gap.
- No new secret, token, or credential is introduced. `payload.assignee_id`
  in the audit row is an internal identifier already exposed elsewhere in
  this project's API surface, consistent with `US-3.3-db-design.md`'s
  existing payload-redaction-is-per-write-call-site-responsibility note.

## Findings

| ID | Severity | Area | Evidence | Required Correction |
|---|---|---|---|---|
| DR-1 | Confirmed correct | Database | `ix_tickets_queue_default_updated_at_id` is needed because a `(status, updated_at, id)` composite cannot give FR-1's filterless query a single global `updated_at` order; the literal `status != 'closed'` predicate requirement is accurate PostgreSQL partial-index selection behavior | None — confirmed; carry the literal-predicate requirement into `IMPLEMENTATION_PLANNING`/`TEST_WRITING` so the repository query and its `[gate]` EXPLAIN assertion are written accordingly |
| DR-2 | Confirmed correct | Database | `migrations/versions/9132a68b73c8_add_ticket_replies.py` is the only migration with `ENABLE`/`FORCE ROW LEVEL SECURITY`/`CREATE POLICY`, and it targets only `ticket_replies` | None — confirmed; FR-1's "regardless of requester" scope is correctly service-layer-only |
| DR-3 | Minor (non-blocking) | Both | `tickets.updated_at`'s existing `onupdate=func.now()` means every `assign`/`unassign` resets the ticket's position in FR-1's "oldest-`updated_at`-first" queue, contradicting Assumption #8's own "longest-waiting ticket surfaces first" rationale and sitting oddly against Out of Scope's "assignment is orthogonal to the state machine" claim; not covered by OD-1–OD-4; both designs correctly decline to invent a suppression mechanism | Not fixable by `API_DESIGN` or `DB_DESIGN` alone — see Open Decisions below. Recorded as a new open question for `IMPACT_ANALYSIS`/`ARCHITECTURE_PLANNING` to route to `SPECIFICATION` if a decision is needed before build |
| DR-4 | Minor (non-blocking) | API | `POST .../assign`'s `409` response models `oneOf: [InvalidStateTransitionProblem, AssignmentConflictProblem]`; neither schema sets `additionalProperties: false` or discriminates `type` via `enum`/`const`, so an `invalid-state-transition` body (with `allowed_events` present) also structurally validates against `AssignmentConflictProblem`'s more permissive schema — the same `oneOf`-without-a-discriminator pattern already shipped in `US-4.1-openapi.yaml`'s and `US-4.2-openapi.yaml`'s `422` responses, so this is not a new departure this story introduces | Advisory only, consistent with existing project convention: at a future revision, project-wide, consider a `const`/`enum` on each Problem schema's `type` field for a real discriminator; not specific to this story |
| DR-5 | Minor (non-blocking) | Database | `db-design.md`'s "Combined filters" section states results are "bounded by the cursor's own keyset range either way" as the basis for its never-a-full-table-scan claim, but the agent branch needs an `(updated_at, id)`-ordered, multi-filter (`status`/`category`/`assignee_id`) list method and cursor codec distinct from `TicketRepository.list_for_requester`'s existing `(created_at, id)`-ordered, single-filter (`requester_id`) one (`app/modules/support/repository.py:60-91`) — neither design names the new repository method | Advisory: `IMPLEMENTATION_PLANNING`/`task_breakdown` should explicitly scope a new `list_*` repository method (and cursor codec) for the agent branch as its own task, not assume `list_for_requester` extends to cover it |

## Open Decisions

- **OD-1 (Critical, spec).** Adopted by `API_DESIGN` and carried unchanged
  by `DB_DESIGN` (distinct `AgentTicketRead`/`AgentTicketStateRead`
  schemas). The substance is sound — the alternative (extending the shared
  `TicketRead`/`TicketStateRead`) would leak `assignee_id` into the already-
  shipped, customer-reachable `/close`/`/reopen` responses, violating the
  story's own NFR. `HUMAN_SPEC_APPROVAL` passed on spec text that states
  this default explicitly in its own "Response Schemas" section, but no
  artifact records an explicit, separate reconfirmation of OD-1 itself.
  Not escalated as a finding here — the content is correct and two
  downstream design artifacts already depend on it — but noting once, since
  the API design's own text calls a reversal "the largest single point of
  rework risk" in this story.
- **OD-2 (Medium, spec).** Confirmed: `GET /{id}`/`TicketDetailRead` is not
  extended by this story. Consistent across spec, API design, and DB
  design.
- **OD-3 (Medium, spec) / OD-4 (Low, spec).** Carried forward as drafting
  defaults, still not formally human-confirmed, but both are non-blocking
  for this stage: neither changes the `assignee_id` column's schema (OD-3
  is purely a service-layer `WHERE` predicate difference) nor the assign
  `422`'s contract shape (OD-4 uses the identical error either way) if
  reversed. Confirm before `IMPLEMENTATION` begins, consistent with the
  spec's own stated gate.
- **New — not covered by OD-1–OD-4, first surfaced at `DB_DESIGN`, carried
  here as DR-3.** Should an `assign`/`unassign` write reset a ticket's
  position in the default "longest-waiting-first" queue? The current design
  answers this implicitly and by omission (reusing `updated_at` as both the
  general "last modified" column and the FR-1 sort key, with no mechanism
  added to separate the two). Two viable resolutions exist, and this review
  does not pick one (design-reviewer does not resolve Open Decisions):
  (a) accept the reset as intended, documented behavior — add a sentence to
  the spec's Assumption #8 or FR-1 acknowledging it; or (b) introduce a
  dedicated timestamp (or otherwise exclude assign/unassign from bumping
  `updated_at`) that FR-1's ordering reads instead, leaving `updated_at`
  itself for its original "last modified" purpose. Concrete impact of
  leaving this unresolved into `IMPLEMENTATION`: `test-writer` cannot write
  a determinate test for "does assign move a ticket to the back of the
  queue" without an answer, and a build proceeding on the current design's
  silence would ship whichever behavior `onupdate=func.now()` happens to
  produce, by default rather than by decision.

## Limitations

This review does not re-verify `IMPLEMENTATION_PLANNING`-level mechanics: the
concrete FastAPI `response_model` technique for the `GET` endpoint's
`Union`-typed success response (API design's own Open Questions #1), the
exact dependency structure for the `assign`/`unassign` 404-vs-403 permission
gate, or the new repository method/cursor codec named in DR-5. These are
correctly left to `IMPLEMENTATION_PLANNING`/`service-and-router-builder`
rather than fixed prematurely at this stage. This review also does not
re-litigate the `oneOf`-without-discriminator pattern (DR-4) project-wide —
only notes that US-4.4 does not introduce a new instance of an
already-accepted pattern.

## Verdict Rationale

PASS: no Critical or Major finding. The three items this review was asked to
confirm are each resolved — DR-1 (third index) and DR-2 (RLS absence) are
confirmed correct with no required correction; the `updated_at` queue-reset
question (DR-3) is real but is not a defect in either design (both correctly
decline to invent unrequested behavior) and cannot be fixed by looping back
to `API_DESIGN` or `DB_DESIGN` — it is recorded as a new open question for
`IMPACT_ANALYSIS`/`ARCHITECTURE_PLANNING` to carry, with a route to
`SPECIFICATION` available at `IMPACT_ANALYSIS` if human confirmation is
needed before build. DR-4 and DR-5 are Minor and non-blocking. Advances to
`IMPACT_ANALYSIS`.
