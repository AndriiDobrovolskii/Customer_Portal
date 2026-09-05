---
artifact_type: design_review
story: US-4.2
version: 3
status: DRAFT
created_at: "2026-09-05T12:00:00Z"
updated_at: "2026-09-05T12:00:00Z"
produced_by: design-reviewer
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
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
supersedes: docs/reviews/designs/US-4.2-design-review.md (v2)
---

# Design Review: Ticket Replies (US-4.2)

## Revision Note (v3)

v2 of this artifact reviewed api_design v2 / openapi v2 / db_design v2 /
entity_model v2 against specification v5 / open_decisions v2, and returned
`BLOCKED` (Finding DR-1, Major): both designs asserted OD-8 (does a customer
reply reopen a `"resolved"` ticket?) was "confirmed" by `HUMAN_SPEC_APPROVAL`'s
silent, comment-free approval of specification v5, when the canonical
`open_decisions.md` v2 still recorded OD-8 as open. That was a correct call —
re-running `API_DESIGN`/`DB_DESIGN` against the same inputs would have
reproduced the identical inference, so the review correctly named it a human
decision, not a design defect.

The human has since supplied OD-8's actual resolution directly in-session
(2026-09-05T09:00:00Z): a customer reply on a `"resolved"` ticket is accepted
(`201`) and `tickets.status` transitions to `"waiting_on_support"` — reopening
it via the same target status FR-2's ordinary case already produces. This is
candidate (b), not v2's candidate (a) ("stays resolved"). The resolution was
formalized as `open_decisions.md` v3 (OD-8 now `RESOLVED`, with an explicit
quoted resolution matching the OD-1–OD-7 pattern), and specification v6 /
spec review v6 (PASS) / api_design v3 / db_design v3 / entity_model v3 were
all regenerated against it. This revision re-reviews that v3 pair.

## Summary

Both designs are internally consistent, correctly grounded in the shipped
codebase (every cross-referenced file, class, or precedent checked in this
pass — `app/modules/support/models.py`, `app/modules/support/router.py`'s
`_TicketStatus` literal, `app/modules/roles/dependencies.py::require_scope`,
`app/modules/roles/exceptions.py::InsufficientPermissionError`,
`app/core/problem_details.py::ProblemError(DomainError)`,
`app/core/exceptions.py::FieldError`, `app/db/session.py`'s single-engine/
single-role setup, `app/modules/support/repository.py`'s cursor-pagination and
`AttachmentRepository.bind_to_ticket` patterns, `docs/product/business-rules.md`
BR-015/BR-016/BR-017, `docs/product/business-glossary.md`'s Support Ticket
lifecycle entry — all match as cited), and now resolve Finding DR-1 correctly:
`open_decisions.md` v3 records OD-8 as `RESOLVED` with an explicit,
individually-quoted human resolution (the same pattern OD-1–OD-7 already
used), and both api_design v3 and db_design v3 state that resolution — and
only that resolution — rather than re-asserting the prior "confirmed by silent
approval" reasoning. No column, constraint, index, or RLS policy changed from
v2 (correctly, since OD-8 was never a schema-shape question — `"waiting_on_
support"` is an existing unconstrained string value, not a new one). The
contract's schemas still carry no ORM object, no privilege field on
`CreateReplyRequest`, and an explicit field list on every `*Read`. No
`Critical` or `Major` finding remains. One `Minor` finding (DR-2, carried
forward unchanged from v2) is advisory only. Verdict: `PASS`.

## Reviewed Artifacts

| Artifact | Path | Version |
|---|---|---|
| Story | docs/stories/US-4.2-ticket-replies.md | — |
| Specification | docs/specifications/US-4.2-spec.md | 6 |
| Spec review | docs/reviews/specifications/US-4.2-spec-review.md | 6 (PASS) |
| API design | docs/designs/api/US-4.2-api-design.md | 3 |
| OpenAPI fragment | docs/designs/api/US-4.2-openapi.yaml | 3 |
| DB design | docs/designs/database/US-4.2-db-design.md | 3 |
| Entity model | docs/designs/database/US-4.2-entity-model.md | 3 |
| Open decisions | docs/decisions/US-4.2-open-decisions.md | 3 (OD-8 `RESOLVED`) |

## API Design Review

- **AC → operation mapping.** TR-AC1/2 → `POST .../replies` `201`; TR-AC3 →
  `GET .../{id}` `200` with the customer/agent visibility split; TR-AC4 →
  `404`/`401` on both routes; TR-AC5 → `POST` `403`; TR-AC6 → `POST` `409`
  (closed) plus the now-correctly-stated `201` resolved-ticket branches
  (agent: status unchanged, OD-5; customer: reopens to
  `"waiting_on_support"`, OD-8); TR-AC7 → `POST` `422`. Every AC with
  observable behavior traces to a status code.
- **No ORM in the contract.** `ReplyRead`, `TicketDetailRead`,
  `ReplyThreadPage`, `CreateReplyRequest` are DTOs only; nothing resembling
  `TicketReply`/`Ticket`/`Attachment` leaks through.
- **Inbound schema / mass assignment.** `CreateReplyRequest` declares
  `additionalProperties: false` and only `body`/`visibility`/`attachment_ids`
  — no `id`, `author_id`, `author_kind`, `created_at`. Confirmed by direct
  read of the YAML.
- **Outbound schema / field list.** `ReplyRead` and `TicketDetailRead` each
  declare an explicit `required`/`properties` list; nothing exposes a
  credential, hash, token, or session id.
- **Validation constraints match the spec.** `body` `minLength: 1`,
  `maxLength: 5000` (FR-7); `visibility` enum matches FR-5/OD-6; pagination
  `limit` `minimum: 1`/`maximum: 100`/`default: 50` matches the NFR's
  "paginated at 50" example, honestly flagged as the design's own
  unstated-by-spec choice (Open Question #6), not invented silently.
- **Error responses.** `401/403/404/409/422/429` all present, each maps to a
  real FR/NFR, none invented without citation. The `409` description now
  correctly states that a `"resolved"` ticket is accepted per FR-6 (agent,
  OD-5) / FR-2 (customer, OD-8) rather than v2's "confirmed at
  HUMAN_SPEC_APPROVAL" language.
- **Authorization stated per operation and grounded in real code.**
  `require_scope("tickets:write")`/`require_scope("tickets:read")` confirmed
  as a real factory at `app/modules/roles/dependencies.py:30`.
- **Cross-cutting error shapes reused, not invented,** re-verified against
  real files this pass: `ProblemError(DomainError)`
  (`app/core/problem_details.py`), `FieldError`
  (`app/core/exceptions.py`), `InsufficientPermissionError`
  (`app/modules/roles/exceptions.py`) all exist exactly as cited.
- **Open Questions #1–#6 in api_design v3** are each honestly surfaced as
  unresolved-by-spec inferences (not silently decided) and are non-blocking:
  #1 (FR-2's status transition outside `"waiting_on_customer"`/`"resolved"`)
  and #2 (POST's generalized-404 authorization branch) are carried in
  `workflow-state.yaml`'s `non_blocking_findings`; #3–#6 are internally
  consistent with the spec/DB design and need no further design-stage
  action. #3 (`resolved_at` does not exist) is now moot rather than merely
  confirmed — v6's FR-2/FR-6 no longer reference clearing a `resolved_at`
  field at all, since OD-8's actual resolution is a real status transition,
  not a no-op.

## Database Design Review

- **SQLAlchemy 2.0 idioms.** `Mapped[T]`/`mapped_column()` throughout, no
  `Column()`; table plural (`ticket_replies`), model singular (`TicketReply`).
- **Every column has explicit type/nullability/default.** No column relies
  on a framework default. `visibility`'s `server_default="public"` and
  `author_kind`'s no-default (service states it explicitly) both re-verified
  against `Ticket.category`/`Ticket.status`'s real precedent in
  `app/modules/support/models.py`.
- **No relationships declared**, consistent with `app/modules/support/
  models.py` having zero `relationship()` calls today (re-confirmed by
  direct read) — the "every relationship declares `lazy="raise_on_sql"`"
  rule is correctly N/A here.
- **`CHECK` constraint** (`ck_ticket_replies_visibility_agent_only`) is
  correctly named (no `naming_convention` registered on `Base.metadata`) and
  its layering note is accurate: the constraint is a backstop, the `403` is
  a service-level `ProblemError`/`DomainError`, and `service-and-
  router-builder` is correctly warned not to implement FR-5 by catching the
  resulting `IntegrityError`.
- **Row-Level Security.** First use of RLS in this codebase (confirmed — no
  `SET LOCAL`/`app.actor_kind` reference exists anywhere under `app/`
  today). `FORCE ROW LEVEL SECURITY`'s necessity is correctly reasoned from
  the single-engine/single-owning-role setup re-confirmed in
  `app/db/session.py` (one `create_async_engine(database_url)`, no
  per-actor-kind role). The fail-closed analysis
  (`current_setting(..., true)` → `NULL` → policy denies) is sound. Two
  command-scoped policies (`SELECT`/`INSERT` only) is a defensible,
  explicitly-reasoned choice consistent with Assumptions & Defaults #6
  (append-only).
- **Migration mechanics gap (Minor — see DR-2, unchanged from v2).**
  `attachments` is an existing, already-shipped table; `ticket_reply_id`'s
  new `index=True` is a new index on a table that may already hold
  production rows, not a fresh `CREATE TABLE`. The design's "Migration
  mechanics note" still discusses only the RLS DDL guard and remains silent
  on whether `CREATE INDEX CONCURRENTLY` (`AGENTS.md` §4) applies to this
  `ALTER TABLE`. Not changed by the v3 revision (which touched only the
  OD-8 narrative), so this finding carries forward unchanged rather than
  being re-derived.
- **No `create_all()`, no schema change outside a migration.**
- **Sensitive columns.** None added; `body` is plain text, equivalent to
  `tickets.body`'s existing precedent.

## Cross-Model Consistency

- `visibility`/`author_kind` enums agree between `ReplyRead`/
  `CreateReplyRequest` and the `CHECK` constraint / RLS predicate.
- `TicketDetailRead.status` enum
  (`open, waiting_on_support, waiting_on_customer, resolved, closed`)
  matches the `_TicketStatus` `Literal` shipped in
  `app/modules/support/router.py:11`, re-confirmed by direct read —
  `"waiting_on_support"` (OD-8's reopening target) is an existing value in
  this literal, not a new one, so the API contract's response schema needs
  no change to represent it.
- Pagination (`cursor`/`limit`, `items`/`next_cursor`) is supportable by the
  DB design's composite `(ticket_id, created_at, id)` index.
- Layering survives: neither design requires the router to reach a
  repository, or the service to import `fastapi`/`HTTPException`.
- **Finding DR-1 (v2) is resolved, not just re-asserted.** OD-8's business
  decision (a customer reply on a `"resolved"` ticket reopens it) now
  appears in both designs *and* is recorded as `RESOLVED` in the canonical
  `open_decisions.md` v3 with an explicit, individually-quoted human
  resolution timestamped 2026-09-05T09:00:00Z — the same evidentiary bar
  OD-1–OD-7 met. No design asserts a business decision absent from an
  approved Open Decision or the specification.

## Security Review of Designs

- IDOR prevention: `attachment-not-owned` `422` never discloses which of
  the three causes applied — matches BR-016 and the shipped US-4.1
  precedent.
- Enumeration prevention: `404` (never `403`) for cross-customer/
  insufficient-scope access on both `POST` and `GET`, per FR-4/TR-AC4.
- Two-layer internal-note isolation (application filter + `FORCE ROW LEVEL
  SECURITY`) correctly implements BR-015's defense-in-depth requirement.
- No credential/token/session material anywhere in the new schemas.
- Rate limiting (`429`/`Retry-After`) reuses the shipped US-4.1 mechanism
  pattern (`TicketCreationRateLimitCacheProtocol`, re-confirmed present in
  `app/modules/support/service.py`); the new cache key itself is not yet
  created (already tracked as a non-blocking `IMPACT_ANALYSIS` finding in
  `workflow-state.yaml`, not a design-stage gap).

## Findings

| ID | Severity | Area | Evidence | Required Correction |
|---|---|---|---|---|
| DR-2 (carried from v2, unchanged) | Minor | Database (migration mechanics) | `docs/designs/database/US-4.2-db-design.md` v3's "Migration mechanics note" still addresses only the RLS hand-written DDL; silent on whether `attachments.ticket_reply_id`'s new `index=True` — landing on the existing, already-shipped `attachments` table — needs `CREATE INDEX CONCURRENTLY` + `autocommit_block()` + `if_not_exists=True` per `AGENTS.md` §4. | Advisory for `migration-manager`: confirm whether `attachments` is expected to hold enough production rows by migration time that `CONCURRENTLY` matters, and apply it if so. Does not block this stage — no design document need change. |

## Open Decisions

- None outstanding. OD-1 through OD-8 are all `RESOLVED` in
  `docs/decisions/US-4.2-open-decisions.md` v3, each with an individually
  quoted human resolution. Finding DR-1 (v2) — the only prior blocker — is
  fully resolved by OD-8's formal resolution and its correct incorporation
  into specification v6 and both v3 designs.

## Limitations

- This review spot-checked, rather than exhaustively diffed, every prose
  cross-reference to existing code (e.g. did not re-verify every field of
  `US-4.1-openapi.yaml`'s `TicketListResponse`/`ProblemBase` byte-for-byte
  against this fragment's restated copies). No contradiction was found in
  the files actually opened this pass.
- DR-2 (migration mechanics) is carried forward unchanged from v2 rather
  than re-derived from scratch, since the v3 revision to both designs
  touched only the OD-8 narrative and changed no column/index/constraint.
- The already-carried non-blocking findings in `workflow-state.yaml`
  (API_DESIGN OQ-1/OQ-2, the GET `limit` enforcement-at-the-router gap) were
  reviewed for continued relevance and remain accurate; none changed
  between v2 and v3 of the designs.

## Verdict Rationale

`PASS`. The single blocking finding from v2 (DR-1: OD-8 asserted as
"confirmed" without a canonical resolution matching OD-1–OD-7's evidentiary
bar) is resolved — `open_decisions.md` v3 now records an explicit,
individually-quoted human resolution for OD-8, and both api_design v3 and
db_design v3 state exactly that resolution (candidate (b): reopens to
`"waiting_on_support"`), not a re-assertion of the prior unconfirmed reading.
No new `Critical`/`Major` finding was introduced by the v3 revision, which
changed only the OD-8 narrative text across all four documents and no
column/constraint/index/RLS policy. DR-2 remains Minor/advisory and does not
block progression.

```yaml
result:
  verdict: PASS
  stage: DESIGN_REVIEW
  story: US-4.2
  artifact_status: APPROVED
  artifacts:
    - docs/reviews/designs/US-4.2-design-review.md
  next_stage: IMPACT_ANALYSIS
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings:
    - "DR-2 (Minor, carried from v2, unchanged in v3): db_design v3's migration-mechanics note covers only the RLS hand-written DDL guard; silent on whether attachments.ticket_reply_id's new index (added to the already-shipped, potentially populated attachments table) needs CREATE INDEX CONCURRENTLY + autocommit_block() + if_not_exists=True per AGENTS.md section 4. Advisory for migration-manager; no design change required."
    - "API_DESIGN OQ-1 (v3, carried from v2): FR-2's status transition for a customer reply on a ticket neither waiting_on_customer nor resolved (e.g. open, waiting_on_support) is unstated by any FR/AC - docs/designs/api/US-4.2-api-design.md"
    - "API_DESIGN OQ-2 (v3, carried from v2): POST /replies' 404 for a caller with neither ticket ownership nor tickets:write generalizes FR-4's GET-specific rule; not literally stated for POST by any FR, currently unreachable under the shipped role seed - docs/designs/api/US-4.2-api-design.md"
    - "GET limit enforcement: openapi v3 correctly states limit minimum:1/maximum:100/default:50 in the contract, but US-4.1's own GET /support/tickets route accepts limit:int=100 with no Query(ge=1,le=100) enforcement; service-and-router-builder should enforce this story's limit with Query(), not a bare int default, to actually match the contract."
```
