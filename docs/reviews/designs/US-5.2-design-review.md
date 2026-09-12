---
artifact_type: design_review
story: US-5.2
version: 1
status: ARCHIVED
created_at: "2026-09-08T08:15:00Z"
updated_at: "2026-09-08T18:25:00Z"
produced_by: design-reviewer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.2-spec-review.md
    version: 2
  - path: docs/decisions/US-5.2-open-decisions.md
    version: 2
supersedes: null
---

# Design Review: Account & Profile Self-Service (Frontend)

**Story ID:** US-5.2
**Reviewed:** 2026-09-08
**Overall Verdict:** NOT_APPLICABLE

## Summary

Both upstream design stages for this Story returned `NOT_APPLICABLE` before this
review ran: `API_DESIGN` and `DB_DESIGN` each determined, independently, that
US-5.2 is a frontend-only Story consuming already-shipped backend endpoints, and
that it changes no public API contract, request/response shape, or database
schema. The approved specification (`docs/specifications/US-5.2-spec.md`,
version 2, `APPROVED`) makes this explicit in its own **Out of Scope** section:
"Any backend/API/DB change. This Story implements only against already-shipped
backend endpoints; it does not add, modify, or design any API route,
request/response contract, or database schema/table/column. `API_DESIGN` and
`DB_DESIGN` are `NOT_APPLICABLE` for US-5.2." There is consequently no `api_design`,
`openapi`, `database_design`, or `entity_model` artifact to review. Per this
skill's own operational contract ("If both `API_DESIGN` and `DB_DESIGN` recorded
`NOT_APPLICABLE`, there is no design to review. Still produce a `design_review`
artifact recording both areas as out of scope..., and return
`verdict: NOT_APPLICABLE`"), this review confirms that precondition holds, finds
no design artifact was silently produced or hidden elsewhere, and closes the
`DESIGN_REVIEW` stage as not applicable so the story can proceed to
`IMPACT_ANALYSIS`.

## Reviewed Artifacts

| Artifact | Path | Version | Status |
|---|---|---|---|
| Story | docs/stories/US-5.2-account-self-service-ui.md | n/a (story artifact, no version progression) | — |
| Specification | docs/specifications/US-5.2-spec.md | 2 | APPROVED |
| Specification Review | docs/reviews/specifications/US-5.2-spec-review.md | 2 | APPROVED |
| Open Decisions | docs/decisions/US-5.2-open-decisions.md | 2 | DRAFT (OD-3, OD-5, OD-6, OD-7 OPEN, non-blocking) |
| API Design | NOT_APPLICABLE (no artifact produced) | — | — |
| OpenAPI contract | NOT_APPLICABLE (no artifact produced) | — | — |
| Database Design | NOT_APPLICABLE (no artifact produced) | — | — |
| Entity Model | NOT_APPLICABLE (no artifact produced) | — | — |

No staleness issue: every consumed artifact's recorded version matches the
current file on disk at the time of this review.

## API Design Review

Not applicable. `docs/specifications/US-5.2-spec.md`'s Out of Scope section
states this Story "does not add, modify, or design any API route,
request/response contract" and that `API_DESIGN` is `NOT_APPLICABLE`. FR-2
through FR-7 each call already-shipped endpoints (`PATCH /profile`,
`POST /profile/confirm-email-change`, `POST /auth/verify-email`,
`POST /auth/verify-email/resend`, `POST /auth/mfa/enroll`,
`POST /auth/mfa/activate`, `DELETE /auth/mfa`, `POST /account/deactivate`) whose
contracts were designed and reviewed under their originating backend Stories
(US-1.3, US-2.5, and the account-deactivation Story), not this one. No new or
modified contract exists for this review to check against the API-design
checklist (ORM containment, `extra="forbid"`, privilege-field exclusion,
outbound field lists, RFC 7807 error model, auth/scope statements). Confirmed
by direct reading of the spec: no section proposes a new route, verb, path, or
schema change.

## Database Design Review

Not applicable, for the same reason and citation as above. No entity,
column, relationship, index, or migration is proposed anywhere in the approved
specification. FR-2's `ETag`/`If-Match` handling (OD-1) is a client-state
concern (transient session state in the frontend), not a persistence change;
FR-5's `current_password`/`secret`/`otpauth_uri`/`recovery_codes` handling is
explicitly required to be held only in transient component state and never
persisted client-side — again not a database-design concern for this Story.

## Cross-Model Consistency

Not applicable — there is no API design and no database design to check for
mutual consistency. The one cross-cutting check this review can still perform
without either artifact is whether the spec itself introduces any implicit
backend/persistence decision under cover of a frontend requirement; none was
found (see Findings).

## Security Review of Designs

No new attack surface is introduced at the API or persistence layer by this
Story, since neither layer changes. The specification's own security-relevant
frontend requirements were verified for internal consistency with the backend
behavior they claim to consume, per `docs/decisions/US-5.2-open-decisions.md`
(OD-1, OD-2, OD-4, all resolved and reflected in FR-2/FR-5/FR-6/FR-7):
- FR-2's `If-Match: *` fallback matches the backend's actual unconditional
  `If-Match` requirement (confirmed against `app/modules/profile/service.py`
  by `us-clarifier` in OD-1) rather than the story's original, backend-inconsistent
  assumption — a design-correctness fix already made at the spec layer, not
  something this review needs to re-litigate.
- FR-5/FR-6's added `current_password` (and, for disable, TOTP `code`) fields
  match the backend's actual required request bodies (OD-2), so the frontend
  will not omit fields the already-shipped API requires.
- The NFR bar (never logging or persisting `secret`, `otpauth_uri`,
  `recovery_codes`, `current_password` client-side) is stated as a hard
  requirement (FR-5 body, NFR section) and is the correct mitigation for a
  frontend-only Story handling these values transiently.
No credential, token, or PII field is exposed by a new contract because no new
contract exists.

## Findings

None. No `Critical`, `Major`, or `Minor` finding is raised: there is no design
artifact to hold a defect, and the specification's own framing of "no
backend/API/DB change" was independently corroborated (Out of Scope section
citation, cross-checked against FR-1 through FR-10, none of which proposes a
route, schema, or table change).

## Open Decisions

OD-3, OD-5, OD-6, and OD-7 remain `OPEN` in
`docs/decisions/US-5.2-open-decisions.md` (version 2) and are carried forward
as Open Questions in the approved spec. None of the four concerns API contract
shape or persistence design:
- OD-3 (enrollment-scoped-token navigation behavior) is a frontend routing/UX
  decision.
- OD-5 (untracked backend Story for `GET /profile`/`GET /users/me`) concerns a
  *future* backend Story's existence, not this Story's design — FR-1 is
  already deferred, not designed here.
- OD-6 (locale-list extensibility) and OD-7 (timezone-picker shape) are
  frontend component/UX decisions consuming an already-fixed backend
  validation set (`SupportedLocale`, `zoneinfo.available_timezones()`).

None of these four constitutes a blocking Open Decision affecting API or
persistence design under this stage's preconditions; this confirms the
`BLOCKED` verdict path does not apply.

## Limitations

This review could not check DTO-to-column field agreement, eager-loading
strategy, or contract-to-acceptance-criterion mapping, because no such
artifacts exist for this Story — by design, per the approved specification's
Out of Scope section. Should a future Story (the backend read-endpoint Story
referenced in OD-5/FR-1) introduce an API or DB design, that Story will require
its own `DESIGN_REVIEW` pass; this review's `NOT_APPLICABLE` verdict does not
extend to that future work.

## Verdict Rationale

`NOT_APPLICABLE`: both `API_DESIGN` and `DB_DESIGN` recorded `NOT_APPLICABLE`
upstream, each citing the same approved specification section
(`docs/specifications/US-5.2-spec.md` §Out of Scope), and this review
independently confirmed that citation is accurate — the spec proposes no new
or modified route, contract, schema, table, column, or relationship anywhere
in FR-1 through FR-10. No Open Decision left OPEN (OD-3, OD-5, OD-6, OD-7)
bears on API or persistence design, so `BLOCKED` does not apply either. Per
this skill's operational contract for the both-`NOT_APPLICABLE` case, this
artifact records both areas as out of scope and the stage returns
`NOT_APPLICABLE` so the orchestrator can advance the story to
`IMPACT_ANALYSIS`.
