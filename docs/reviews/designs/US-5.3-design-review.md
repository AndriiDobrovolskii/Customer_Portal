---
artifact_type: design_review
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-08T19:40:00Z"
updated_at: "2026-09-08T19:40:00Z"
produced_by: design-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Design Review: Support Tickets (Frontend)

**Story ID:** US-5.3
**Reviewed:** 2026-09-08
**Overall Verdict:** NOT_APPLICABLE

## Summary

Both upstream design stages for this Story returned `NOT_APPLICABLE` before this
review ran: `API_DESIGN` (`openapi-designer`, history entry
`2026-09-08T19:30:00Z`) and `DB_DESIGN` (`db-designer`, history entry
`2026-09-08T19:35:00Z`) each determined, independently, that US-5.3 is a
frontend-only Story consuming already-shipped backend endpoints (all six
routes it calls were designed and reviewed under EPIC-4's own Stories —
US-4.1/US-4.2/US-4.3/US-4.4; the story's reference contract table lists a
seventh, `POST /{id}/resolve`, but that route is explicitly out of scope and
never called by this Story), and that it introduces no new or modified public
API contract, request/response shape, or database schema. The approved
specification (`docs/specifications/US-5.3-spec.md`, version 1, `APPROVED`)
states this explicitly in its own **Out of Scope** section: "Any backend/API/DB
change. This Story implements only against already-shipped backend endpoints;
it does not add, modify, or design any API route, request/response contract,
or database schema/table/column. `API_DESIGN` and `DB_DESIGN` are
`NOT_APPLICABLE` for US-5.3." There is consequently no `api_design`, `openapi`,
`database_design`, or `entity_model` artifact to review. Per this skill's own
operational contract for the both-`NOT_APPLICABLE` case, this review confirms
that precondition holds, finds no design artifact was silently produced or
hidden elsewhere, and closes the `DESIGN_REVIEW` stage as not applicable so the
story can proceed to `IMPACT_ANALYSIS`.

## Reviewed Artifacts

| Artifact | Path | Version | Status |
|---|---|---|---|
| Story | docs/stories/US-5.3-support-tickets-ui.md | n/a (story artifact, no version progression) | — |
| Specification | docs/specifications/US-5.3-spec.md | 1 | APPROVED |
| Specification Review | docs/reviews/specifications/US-5.3-spec-review.md | 1 | APPROVED |
| Open Decisions | docs/decisions/US-5.3-open-decisions.md | 1 | DRAFT (OD-1..OD-6 OPEN, non-blocking to this stage) |
| API Design | NOT_APPLICABLE (no artifact produced) | — | — |
| OpenAPI contract | NOT_APPLICABLE (no artifact produced) | — | — |
| Database Design | NOT_APPLICABLE (no artifact produced) | — | — |
| Entity Model | NOT_APPLICABLE (no artifact produced) | — | — |

No staleness issue: every consumed artifact's recorded version matches the
current file on disk at the time of this review (`specification` v1, matching
`specification_review`'s recorded input; `open_decisions` v1, matching both
the specification's and specification review's recorded input).

## API Design Review

Not applicable. `docs/specifications/US-5.3-spec.md`'s Out of Scope section
states this Story "does not add, modify, or design any API route,
request/response contract" and that `API_DESIGN` is `NOT_APPLICABLE`. FR-1
through FR-9 and FR-14 each call already-shipped endpoints — `GET
/support/tickets`, `POST /support/tickets`, `GET /support/tickets/{id}`, `POST
/support/tickets/{id}/replies`, `POST /support/tickets/{id}/close`, `POST
/support/tickets/{id}/reopen` — whose contracts were designed and reviewed
under EPIC-4's originating Stories (US-4.1 create, US-4.2 reply, US-4.3
resolve/close/reopen, US-4.4 agent queue), not this one. FR-15 (post-login
redirect and nav entry to `/tickets`) is pure client-side routing and calls no
endpoint at all. No section of the spec proposes a new route, verb, path, or
schema change; no FR requires a change to any existing response DTO shape.
Confirmed directly: a glob of `docs/designs/**/*` finds no `US-5.3-*` file
under `docs/designs/api/` (only entries through US-4.4) — no `api_design` or
`openapi` artifact was silently produced for this Story outside the registry
path.

One item requires explicit note: FR-12/TK-AC12's 429 `Retry-After` handling
(OD-1, High, still open) is a genuine, disclosed implementation gap in the
*frontend* HTTP client (`frontend/src/api/httpClient.ts`'s `parseResponse` /
`normalizeApiError` never threads `response.headers` into the thrown
`ApiError`). This review confirms OD-1 is correctly scoped as a frontend
client-layer concern, not a backend API-contract change: the `Retry-After`
header already exists on the wire today (`app/modules/support/exceptions.py`'s
`TicketCreationRateLimitError`/`TicketReplyRateLimitError` already set
`self.headers = {"Retry-After": ...}`), so no new or modified backend route,
schema, or status code is implicated — only how the existing header is read
client-side. This is consistent with the `workflow-state.yaml`
`non_blocking_findings` entry recorded when `API_DESIGN` returned
`NOT_APPLICABLE` ("OD-1 assessed as a frontend httpClient concern, not a
backend API contract change"), which this review independently corroborates
rather than merely repeats.

## Database Design Review

Not applicable, for the same reason and citation as above. No entity, column,
relationship, index, or migration is proposed anywhere in the approved
specification. Every field this Story reads or writes (`ticket_number`,
`subject`, `category`, `status`, `updated_at`, `created_at`,
`first_response_at`, reply `author_kind`/`body`/`created_at`, `next_cursor`)
already exists on `TicketRead`/`TicketDetailRead`/`ReplyRead`/list-response
shapes shipped under EPIC-4. FR-4's `Idempotency-Key` handling and OD-6's
edited-resubmission question are transient client-side form state concerns
(the key "lives in transient form state for the lifetime of one composition;
it is not persisted across a full page reload" — spec FR-4), not a
persistence-layer decision for this Story. Confirmed directly: the same glob
of `docs/designs/**/*` finds no `US-5.3-*` file under `docs/designs/database/`
either (only entries through US-4.4) — no `database_design` or `entity_model`
artifact was silently produced for this Story.

## Cross-Model Consistency

Not applicable — there is no API design and no database design to check for
mutual consistency. The one cross-cutting check this review can still perform
without either artifact is whether the spec itself introduces any implicit
backend/persistence decision under cover of a frontend requirement; none was
found (see Findings). In particular, FR-9's status-affordance table and FR-7's
close-eligibility list were checked against the story's own "Verified
transition eligibility" reference table (sourced from
`app/modules/support/service.py`) and matched without discrepancy — this is
existing backend behavior being consumed and correctly reflected, not a new
design decision.

## Security Review of Designs

No new attack surface is introduced at the API or persistence layer by this
Story, since neither layer changes. The specification's own security-relevant
frontend requirements were checked for internal consistency with the backend
behavior they claim to consume:

- FR-6 correctly states the reply composer offers no `visibility` control and
  that a customer sending `internal` is rejected with a `403` "by design" —
  consistent with the already-shipped RLS/write-path behavior on
  `POST /support/tickets/{id}/replies`; no new authorization surface is
  proposed.
- FR-9 states "Resolve" is never offered to a customer under any status,
  matching the already-shipped `TicketService.resolve_ticket` raising
  `InsufficientPermissionError` for any non-agent caller — the frontend
  correctly mirrors an existing backend authorization boundary rather than
  attempting to enforce it client-side only.
- FR-11 correctly treats a `404` (not `403`) on a ticket the caller does not
  own as existing, deliberate backend behavior to render as "not found" — the
  frontend does not need to (and does not) infer ownership itself.
- The NFR bar (no ticket/reply body or `Idempotency-Key` logged to console in
  production; plain-text rendering only, no `dangerouslySetInnerHTML`) is
  stated as a hard requirement and is the correct mitigation for a
  frontend-only Story rendering user-supplied text.

No credential, token, hash, or internal-only field is exposed by a new
contract because no new contract exists.

## Findings

None. No `Critical`, `Major`, or `Minor` finding is raised: there is no design
artifact to hold a defect, and the specification's own framing of "no
backend/API/DB change" was independently corroborated (Out of Scope section
citation, cross-checked against FR-1 through FR-15, none of which proposes a
route, schema, table, or column change).

## Open Decisions

OD-1 through OD-6 remain `OPEN` in `docs/decisions/US-5.3-open-decisions.md`
(version 1) and are carried forward as Open Questions 1–6 in the approved
spec. None constitutes a blocking Open Decision affecting API contract shape
or persistence design under this stage's preconditions:

- OD-1 (High — `Retry-After` header not reachable through `httpClient`'s error
  path) is a frontend HTTP-client concern, addressed above under API Design
  Review; it does not require a backend API-contract change.
- OD-2 (Medium — `category` free-text vs. future enum) is a product/UX
  decision about a form control's input mode, not a schema or contract shape;
  the backend field (`CreateTicketRequest.category`, `str(max_length=50)`)
  is unchanged either way.
- OD-3 (Medium — reactive-only handling of the 7-day reopen window) is a
  frontend UX decision about whether to pre-disable a button; the backend
  `409` behavior is unchanged and already shipped.
- OD-4 (Low — `first_response_at` label/copy) is frontend copy, not a schema
  change.
- OD-5 (Low — component/design-system convention) is a frontend
  implementation convention, carried forward from US-5.1/US-5.2, unrelated to
  API or DB design.
- OD-6 (Medium — edited-resubmission `Idempotency-Key` reuse) is client-side
  form-state behavior; the backend's `IdempotencyKeyReuseError` (`422`) is
  existing, already-shipped behavior this Story must handle, not change.

This confirms the `BLOCKED` verdict path does not apply.

## Limitations

This review could not check DTO-to-column field agreement, eager-loading
strategy, or contract-to-acceptance-criterion mapping, because no such
artifacts exist for this Story — by design, per the approved specification's
Out of Scope section. Should a future Story (US-5.5, the agent-side
counterpart referenced in the spec's Background and Out of Scope sections)
introduce an API or DB design, that Story will require its own
`DESIGN_REVIEW` pass; this review's `NOT_APPLICABLE` verdict does not extend
to that future work. This review also does not resolve OD-1 through OD-6 —
resolution remains with product/architecture decision-making outside this
stage, as it was already correctly deferred through `SPEC_REVIEW` and
`HUMAN_SPEC_APPROVAL`.

## Verdict Rationale

`NOT_APPLICABLE`: both `API_DESIGN` and `DB_DESIGN` recorded `NOT_APPLICABLE`
upstream (confirmed via `docs/workflow/history.jsonl` entries timestamped
`2026-09-08T19:30:00Z` and `2026-09-08T19:35:00Z`), each consistent with the
same approved specification section (`docs/specifications/US-5.3-spec.md` §Out
of Scope), and this review independently confirmed that citation is accurate —
the spec proposes no new or modified route, contract, schema, table, column,
or relationship anywhere in FR-1 through FR-15. No Open Decision left OPEN
(OD-1 through OD-6) bears on API or persistence design, so `BLOCKED` does not
apply either. Per this skill's operational contract for the both-`NOT_APPLICABLE`
case, this artifact records both areas as out of scope and the stage returns
`NOT_APPLICABLE` so the orchestrator can advance the story to
`IMPACT_ANALYSIS`.
