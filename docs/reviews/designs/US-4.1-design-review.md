---
artifact_type: design_review
story: US-4.1
version: 3
status: APPROVED
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-03T00:10:00Z"
produced_by: design-reviewer
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
supersedes: 2
---

# Design Review: Support Tickets (Create) (US-4.1)

**Story:** docs/stories/US-4.1-create-ticket.md
**Specification:** docs/specifications/US-4.1-spec.md (version 1, PASS per spec review)
**API design:** docs/designs/api/US-4.1-api-design.md, US-4.1-openapi.yaml (version 3)
**DB design:** docs/designs/database/US-4.1-db-design.md, US-4.1-entity-model.md (version 3)
**Reviewed:** 2026-09-03
**Overall Verdict:** PASS

## Summary

This revision resolves every finding this stage's version-2 review left open:
DR-4 (Critical, API design), DR-5 (Minor, API design), and DR-6 (Minor,
database design). All three were re-verified against the actual artifacts on
disk and the codebase files they cite, not accepted on the revision notes'
own say-so. No regression was found in any previously-passed checklist item.
No new finding is raised by this pass. `PASS`, advancing to `IMPACT_ANALYSIS`.

## Reviewed Artifacts

| Artifact | Path | Version |
|---|---|---|
| Specification | docs/specifications/US-4.1-spec.md | 1 (unchanged) |
| Spec review | docs/reviews/specifications/US-4.1-spec-review.md | 1 (PASS, unchanged) |
| API design | docs/designs/api/US-4.1-api-design.md | 3 |
| OpenAPI contract | docs/designs/api/US-4.1-openapi.yaml | 3 |
| DB design | docs/designs/database/US-4.1-db-design.md | 3 |
| Entity model | docs/designs/database/US-4.1-entity-model.md | 3 |
| Open Decisions | docs/decisions/US-4.1-open-decisions.md | 1 (unchanged) |

All input versions recorded in each design's own front matter `inputs:`
match the versions actually on disk — no staleness. `US-4.1-db-design.md` v3's
own revision note records that it is a staleness/wording-only re-run (API_DESIGN
v3 was authorization-language-only; DB_DESIGN required no schema change), and
that is confirmed by direct read: no column, index, or table changed from v2
except the `actor_role` mechanism prose (DR-6).

## API Design Review

- Every FR (FR-1–FR-7) with externally observable behavior still maps to an
  operation and status code. No gaps.
- `additionalProperties: false` / no privileged field on `CreateTicketRequest`;
  explicit field list on `TicketRead`; no credential/token/session field
  exposed. Unchanged from the previously-passed checklist items.
- `category maxLength: 50` remains present on both `CreateTicketRequest` and
  `TicketRead` (`US-4.1-openapi.yaml` v3, lines 199, 243), matching
  `tickets.category String(50)`. No regression.
- **DR-4 verified fixed.** `US-4.1-openapi.yaml` v3 now states, per
  operation, an actual authorization mechanism instead of the undefined
  "staff-role account" language: `POST`'s `201` description and `GET`'s
  `200` description both cite `CurrentUserDep` with "deliberately no
  `tickets:*` scope requirement"; `GET`'s `403` description cites
  `roles.dependencies.require_scope` explicitly. Cross-checked directly
  against the codebase, not just the design's own citations:
  `app/modules/users/dependencies.py:82` defines
  `CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]`;
  `app/modules/roles/dependencies.py:30` defines `require_scope(scope: str)`;
  `app/modules/audit/dependencies.py:29` defines `require_audit_read`, the
  precedent the design cites for the same `require_scope` mechanism. All
  three citations are accurate. The resulting authorization design is also
  consistent with BR-010 (authorize on scope, never on a role-name string)
  and with the shipped role/permission seed data (`customer` holds zero
  `tickets:*` scopes) — a `require_scope("tickets:write")` gate on `POST`
  would no longer be the plausible next step for an implementer, since the
  design now says explicitly not to add one.
- **DR-5 verified fixed.** `US-4.1-openapi.yaml` v3's `TicketRead.id`
  description now reads "this contract's own addition (design review DR-5
  fix — matches US-4.1-api-design.md Open Questions #7)," matching
  `US-4.1-api-design.md`'s own Open Questions #7. The two documents no
  longer contradict each other.
- Error responses still cover 401/403/422/429 per the spec's documented
  failure cases; the `422 oneOf` still keeps the three attachment-ownership
  causes indistinguishable (FR-7/BR-016). No regression.
- RFC 7807 `ProblemBase`, `FieldError`-shaped `errors[]`, and the
  `429`/`Retry-After` pattern remain correctly reused, not reinvented.

## Database Design Review

- DR-1 and DR-3 (both fixed in v2, re-verified in the prior review pass)
  remain fixed in v3 — the design's own revision note states, and direct
  read confirms, no schema change was made in this revision beyond the
  DR-6 prose fix. The `audit_log` write path, the atomic `SET NX EX`
  idempotency gate, and the bounded-poll mid-flight case are all present
  and unchanged from the previously-verified v2 content.
- **DR-6 verified fixed.** `US-4.1-db-design.md` v3's `audit_log` mapping
  table now states `actor_role` is "resolved via a service-to-service call,
  not middleware: `app/modules/audit/service.py`'s `_resolve_actor_role`
  helper calls the `RoleServiceProtocol` collaborator's
  `get_role_grants_for_user`." Cross-checked directly against
  `app/modules/audit/service.py`: `_resolve_actor_role` (line 65) takes a
  `RoleServiceProtocol` (line 52) and calls
  `role_service.get_role_grants_for_user(actor_id)` (line 75); both call
  sites (`create`/another write path, lines 135 and 162) pass
  `self._role_service`. The citation is accurate — this is a
  service-to-service call, not middleware, matching this design's own
  "Cross-module layering note" for the write path itself (`AGENTS.md` §3).
- `tickets`/`attachments` columns remain explicit SQLAlchemy 2.0 declarative
  with type/nullability/default/index stated per column; no `relationship()`
  is declared and the justification (no nested collection in any response
  schema) still correctly means the mandatory eager-loading rule is not
  triggered rather than silently skipped. No regression.
- Indexes remain purposeful: unique `ticket_number`, composite
  `(requester_id, created_at DESC, id DESC)` for FR-2 keyset pagination,
  partial index on `attachments.created_at WHERE ticket_id IS NULL` for the
  purge job. No unjustified index added. No regression.

## Cross-Model Consistency

- Resource ↔ persistence mapping remains coherent: `TicketRead` ↔ `tickets`,
  `attachment_ids` ↔ `attachments.ticket_id` binding, the `audit_log` write
  ↔ the existing table (no new persistence surface for the audit path).
- `category` (`maxLength: 50` / `String(50)`), `subject`
  (`maxLength: 150` / `String(150)`), and `body`
  (`maxLength: 5000` / `String(5000)`) all agree between contract and
  column. No regression from v2.
- Layering survives both designs: the audit write is explicitly stated as
  service → service (`app/modules/audit/service.py`), never a direct
  cross-module repository import — and is now independently confirmed
  accurate by direct read of that file (see DR-6 above), not merely
  asserted by the design.
- **BR-010 is now correctly followed.** The prior pass's cross-model gap
  (DR-4: an authorization narrative that named no actual scope check, and
  so could not be checked against BR-010's "authorize on scope, not
  role-name string" rule) is closed — both designs now name the real
  mechanism (`CurrentUserDep` for identity/ownership, `require_scope` for
  the staff-rejection branch), and neither compares a role-name string.
- Pagination (`cursor`/`limit`) remains supportable by the declared
  composite index.

## Security Review of Designs

- FR-7/BR-016 IDOR prevention and UUIDv4/non-enumerable attachment ids:
  unchanged and correct, as in the prior passes.
- `ticket_number`'s sequential-looking format remains correctly treated as
  display-only, not an authorization boundary.
- The `audit_log` write's tamper-evidence (trigger-computed
  `previous_hash`/`row_hash`) is unaffected by the DR-6 wording fix.
- DR-4's underlying risk (an implementer adding an unbuildable
  `tickets:write` scope gate to `POST` and breaking FR-1 for every real
  customer) is now closed by the design stating the actual, intended
  authorization mechanism explicitly, per operation, in both
  `US-4.1-api-design.md` and `US-4.1-openapi.yaml`.

## Findings

None. No `Critical` or `Major` finding remains open, and this pass raises no
new one.

## Open Decisions

OD-1, OD-2, OD-4, OD-5 remain adopted design assumptions, carried as
non-blocking findings for `PLAN_REVIEW`/`IMPLEMENTATION_PLANNING` to confirm.
OD-3 (`category`'s enumerated value set) remains correctly unresolved pending
stakeholder input — neither design invents a value list, consistent with
`docs/decisions/US-4.1-open-decisions.md`'s own instruction. No new Open
Decision is logged by this review.

Also carried forward as non-blocking findings, unchanged from the prior
review and not re-litigated here (neither is a design defect; both are
implementation-sequencing concerns for later stages):

- BR-007's account-erasure job mechanics remain pending legal/DPO sign-off;
  `requester_id`/`uploaded_by`'s `ondelete: RESTRICT` default is a stated,
  deliberate gap pending that job's own design.
- The idempotency create/replay race's bounded-poll exhaustion path returns
  an undocumented `500` (no new contract slug) — flagged by `db-designer`
  itself as a design assumption for `PLAN_REVIEW`/`IMPLEMENTATION_PLANNING`
  to confirm, not re-litigated by this review.

## Limitations

This review re-verified DR-4, DR-5, and DR-6's fixes against the actual files
they cite — `app/modules/users/dependencies.py`,
`app/modules/roles/dependencies.py`, `app/modules/audit/dependencies.py`, and
`app/modules/audit/service.py` — by direct read with line numbers, rather
than trusting the revision notes' own claims. DR-1/DR-2/DR-3 were re-verified
against their cited files in the prior (version 2) review pass and are not
re-derived here, since `US-4.1-db-design.md` v3's own revision note states,
and direct read confirms, that no schema content changed in those areas
between v2 and v3. The idempotency poll-exhaustion `500` path and BR-007's
FK gap are not re-litigated here; both remain non-blocking carry-forwards for
`PLAN_REVIEW`/`IMPLEMENTATION_PLANNING`.

## Verdict Rationale

`PASS`: every `Critical`/`Major` finding this stage raised across its two
prior passes (DR-1 through DR-4) is verified fixed against the actual
artifacts and codebase files they depend on, not merely claimed fixed; both
remaining Minor findings (DR-5, DR-6) are also verified fixed; and this pass
finds no new `Critical` or `Major` defect. The two designs are internally
consistent with each other, with `AGENTS.md` §3/§4, and with the business
rules (BR-010, BR-016) and shipped codebase state (role/permission seed data,
`audit_log`'s architecture) they depend on. `IMPACT_ANALYSIS` may proceed.
