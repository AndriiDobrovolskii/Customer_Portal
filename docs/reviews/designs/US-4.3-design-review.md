---
artifact_type: design_review
story: US-4.3
version: 3
status: ARCHIVED
created_at: "2026-09-06T13:00:00Z"
updated_at: "2026-09-06T18:00:00Z"
produced_by: design-reviewer
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
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
supersedes: docs/reviews/designs/US-4.3-design-review.md
---

# Design Review: Ticket Resolution (US-4.3)

**Reviewed:** 2026-09-06 (re-review after v2's `CHANGES_REQUIRED`)
**Overall Verdict:** PASS

## Summary

This review supersedes v2, whose sole blocking finding (DR-4, Critical) was
that `US-4.3-db-design.md` decided, silently and without a stated exemption,
that FR-4's reply-driven reopen transition writes no `audit_log` entry at
all — contradicting the source story's own Data Model Notes ("`ticket_audit_log`
records every transition, including system-driven ones") and this project's
project-wide `NFR-006` ("every mutation... is audited"), while the
functionally identical FR-5 (`/reopen`) transition *is* audited.

`US-4.3-db-design.md` v3 resolves DR-4 by option (a): FR-4's transition now
writes `event=ticket_reopened` to `audit_log` — the same event value FR-5
already writes for the identical `resolved` → `waiting_on_support`
transition, not a new event string. `actor_id` is the replying requester's
id (FR-4's text has no agent-reply branch); `actor_role` resolves via the
existing `_resolve_actor_role`. Verified against the running code
(`app/modules/audit/service.py:187-220`): `record_event`'s public signature
takes `actor_id: uuid.UUID` (non-optional) and no other new parameter, so
this fifth call site requires no signature change. `entity_model.md` v3 adds
the corresponding row to the `audit_log` write table with no schema-shape
change (reusing an existing event value on an existing table). DR-4 is
confirmed corrected.

DR-1/DR-2/DR-3 (v1, confirmed corrected by v2) remain untouched and sound —
`db-design.md` v3 states plainly that neither was revisited in this
revision, and nothing in it contradicts v2's confirmation.

One new **Minor, non-blocking** finding (DR-8) was found in this pass:
`US-4.3-api-design.md`'s narrative for the `POST .../replies` side effect
(FR-4) still does not mention that an `audit_log` entry is now written —
every other endpoint's narrative in that same document (FR-1, FR-2, FR-5)
states its `ticket_audit_log` write explicitly, but FR-4's section was
written before `db-design.md` v3 added the write and was not updated to
match. This is a documentation-completeness gap between the two design
documents, not a contract or schema defect (no OpenAPI schema, status code,
or response field is affected — the write was never part of any response
body for any of the other endpoints either), so it does not block. DR-5,
DR-6, and DR-7 (v2, Minor, non-blocking) remain open and unaddressed,
consistent with the review's own advisory treatment of them.

## Reviewed Artifacts

| Artifact | Version | Verdict feeding this review |
|---|---|---|
| `docs/stories/US-4.3-ticket-resolution.md` | n/a (source) | — |
| `docs/specifications/US-4.3-spec.md` | 2 | — |
| `docs/reviews/specifications/US-4.3-spec-review.md` | 3 | PASS |
| `docs/designs/api/US-4.3-api-design.md` | 2 | unchanged since v2 of this review |
| `docs/designs/api/US-4.3-openapi.yaml` | 2 | unchanged since v2 of this review |
| `docs/designs/database/US-4.3-db-design.md` | 3 | rework of v2 (DR-4 addressed) |
| `docs/designs/database/US-4.3-entity-model.md` | 3 | input-version refresh + one new audit-write table row, no schema-shape change |
| `docs/decisions/US-4.3-open-decisions.md` | 1 | OD-1–OD-8 resolved at `HUMAN_SPEC_APPROVAL` |

## API Design Review

Unchanged since v2 of this review (no new version of `api_design`/`openapi`
was produced). All findings from that pass stand:

- All 9 ACs / 10 FRs map to an operation and status code across the three
  endpoints, or to the narrative side-effect section on the existing US-4.2
  `POST .../replies` endpoint (FR-4). No FR is unrepresented.
- No ORM model appears in the contract; all request/response schemas are
  plain DTOs.
- `additionalProperties: false` is set on every inbound schema; no inbound
  schema declares a privilege or system field.
- `TicketStateRead` carries an explicit field list; no credential, token, or
  session id is exposed.
- Error responses cover 401/403/404/409/422 as each FR requires; check order
  (state before actor) matches the spec's own anti-leak NFR.
- `resolution_note`'s `minLength: 1` and `maxLength: 5000` both present and
  match the backing column (DR-3, resolved in v1 of this review).

See DR-8 below for the one narrative gap this pass newly surfaced between
this document and `db-design.md` v3.

## Database Design Review

- `tickets` gains four additive, nullable columns (`resolved_at`,
  `resolution_note`, `closed_at`, `closed_by`), each with an explicit type,
  nullability, and default — unchanged since v2 of this review, re-confirmed
  against the current file.
- The corrected `CHECK` constraints (`ck_tickets_closed_requires_closed_fields`,
  `ck_tickets_resolved_requires_resolution_fields`) are unchanged from the
  version DR-1/DR-2 were verified against; no regression.
- DR-1 (strict auto-close predicate) and DR-2 (7-day window embedded in the
  `/reopen`/FR-4 conditional `UPDATE`'s own `WHERE` clause) remain as stated
  and confirmed in v2 of this review — `db-design.md` v3 does not touch
  either section.

### DR-4 (Critical, v2) — confirmed corrected

**Area:** Database design (audit_log write policy).

**Correction verified:** `db-design.md` v3's audit table now includes a
fifth row: FR-4 (reply-driven reopen) writes `event=ticket_reopened`,
`actor_id` = the replying requester's id, `actor_role` resolved via the
existing `_resolve_actor_role`, `target_id` = `ticket.id`, `outcome` =
`"success"`, `payload` = `NULL` — the identical shape FR-5's row already
uses for the same transition, reusing the event value rather than inventing
a new one. This resolves both cited defects: the source story's Data Model
Notes ("`ticket_audit_log` records every transition") and project-wide
`NFR-006` are now satisfied for FR-4's transition, and the FR-4/FR-5
asymmetry (one audited, one not, for the identical state change) is gone.

**Code verification:** `record_event` (`app/modules/audit/service.py:187-220`)
takes `actor_id: uuid.UUID` as a required, unvalidated parameter and resolves
`actor_role` via `_resolve_actor_role`, which in turn calls
`RoleService.get_role_grants_for_user` (`app/modules/roles/service.py:107`) —
a plain lookup against the user-role grant table that returns an empty list
(not an error) for any `user_id` with no grants. A real, non-privileged
requester id is a normal case this path already handles for FR-5's identical
row; no signature change or new code path is required to add this fifth call
site, confirming the design's own claim.

**Call-site note (design-level, not re-litigated here):** the design states
this write is issued from the existing US-4.2 reply-creation service path in
the same transaction as the conditional `tickets` `UPDATE` — a
service-and-router-builder wiring detail, consistent with this review's
`Limitations` section below; not something this stage verifies against code
that does not yet exist.

**Verdict:** DR-4 is resolved. No further rework needed.

## Cross-Model Consistency

- `resolution_note`: schema `maxLength: 5000` matches column `String(5000)`
  exactly (DR-3, resolved in v1) — unchanged.
- `tickets.status`'s value set is identical between the OpenAPI contract and
  the entity model — unchanged.
- No business decision in either design contradicts an approved Open
  Decision. OD-1 through OD-8 are each traced to their consuming FR and
  design section as claimed.

### DR-8 (Minor, non-blocking) — `US-4.3-api-design.md`'s FR-4 narrative does not mention the new audit_log write

**Area:** API design (narrative only — no schema, status code, or response
field is affected).

**Evidence:** `US-4.3-api-design.md`'s "Side effect on the existing `POST
.../replies` endpoint (FR-4...)" section states only that status becomes
`"waiting_on_support"`, `resolved_at` is cleared, and a notification is sent
— it does not mention a `ticket_audit_log` write, unlike the narrative for
every other endpoint in the same document (`/resolve`'s FR-1: "A
`ticket_audit_log` entry is written..."; `/close`'s FR-2: "`ticket_audit_log`
records `actor=self`..."; `/reopen`'s FR-5: "a `ticket_audit_log` entry is
written..."). This section was written in `api_design` v2 (2026-09-06T14:00Z),
before `db-design.md` v3 (2026-09-06T17:00Z) added FR-4's audit write per
DR-4, and was not updated to match.

**Required correction:** Advisory only — at `API_DESIGN`'s next natural
revision, add one sentence to the FR-4 side-effect narrative stating that a
`ticket_audit_log` entry (`event=ticket_reopened`, `actor=self`) is now also
written, for consistency with the other three endpoints' narratives and to
prevent an implementer reading only `api-design.md` from missing the write.
Does not block: the write was never part of any endpoint's response body
(all four are described as side effects "not part of the response"), so no
contract shape is wrong or incomplete — only a cross-document narrative is
stale.

## Security Review of Designs

- `404` is used consistently ahead of `403`/`409` for a non-owning customer
  caller across all three endpoints — unchanged.
- State is checked before actor for `/resolve` — unchanged.
- No new authorization mechanism is introduced — unchanged.
- `closed_by`'s system-actor sentinel is a fixed, non-secret constant —
  unchanged.
- DR-4's resolution closes the audit-trail-completeness gap this section
  flagged in v2 as itself security/compliance-relevant, given this project
  treats the audit log as its append-only compliance record.

## Findings

| ID | Severity | Area | Evidence | Required Correction |
|---|---|---|---|---|
| DR-4 | Critical (resolved) | Database | FR-4's reply-driven reopen now writes `event=ticket_reopened` to `audit_log` in `db-design.md` v3 | None — confirmed corrected |
| DR-5 | Minor (non-blocking, carried) | API design | Reply-endpoint outcome for a `"resolved"`-but-expired-not-yet-auto-closed ticket remains undefined | Advisory: broaden Open Questions #1 at the next natural revision |
| DR-6 | Minor (non-blocking, carried) | Database (migration mechanics) | New partial index on `tickets` silent on `CREATE INDEX CONCURRENTLY` mechanics | Advisory for `migration-manager`, same treatment as `US-4.2-design-review.md` DR-2 |
| DR-7 | Minor (non-blocking, carried) | API design | `reason` fields on `/close`/`/reopen` carry no `maxLength` | Advisory: add a bound at the next natural revision |
| DR-8 | Minor (non-blocking, new) | API design (narrative) | `api-design.md`'s FR-4 side-effect narrative omits the now-decided `audit_log` write | Advisory: state the write explicitly at `API_DESIGN`'s next natural revision |

## Open Decisions

None newly raised requiring `HUMAN_SPEC_APPROVAL`-level resolution.

## Limitations

This review does not re-verify `IMPLEMENTATION_PLANNING`-level mechanics
(e.g. how the reply-creation service path will actually invoke
`record_event` for FR-4's new write, or how `TicketRepository.update()`'s
signature extends to support DR-2's window-scoped conditional `UPDATE`) —
that is `IMPLEMENTATION_PLANNING`'s and `service-and-router-builder`'s
concern, not a schema or contract defect this stage can find.

## Verdict Rationale

PASS: DR-1/DR-2/DR-3 (v1) remain confirmed corrected. DR-4 (v2, Critical) is
now confirmed corrected — `db-design.md` v3 adds the previously-missing
`audit_log` write for FR-4, closing the audit-completeness gap against both
the source story's Data Model Notes and project-wide `NFR-006`, verified
compatible with the existing `record_event`/`_resolve_actor_role` code path.
No new Critical or Major finding was found. DR-5/DR-6/DR-7 remain Minor and
non-blocking (carried from v2); DR-8 is a new Minor, non-blocking narrative
gap in `api-design.md` that does not affect the API contract's shape.
Advances to `IMPACT_ANALYSIS`.
