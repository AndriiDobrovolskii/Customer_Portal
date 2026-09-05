---
artifact_type: clarification_report
story: US-4.2
version: 3
status: DRAFT
created_at: "2026-09-04T16:30:00Z"
updated_at: "2026-09-05T09:15:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
supersedes: docs/evidence/US-4.2-clarification-report.md (v2)
---

# US-4.2 (Ticket Replies) — Clarification Report

## Revision note (v3)

This revision supersedes v2. It formalizes the resolution of **OD-8**, the
last open item: a customer reply on a `"resolved"` ticket is accepted (`201`)
and the ticket transitions to `"waiting_on_support"` (reopens), supplied
directly by the human in-session on 2026-09-05 after `DESIGN_REVIEW` v2
found that `api_design`/`db_design` v2 had incorrectly treated this
question as already settled (`docs/reviews/designs/US-4.2-design-review.md`
Finding DR-1; `docs/decisions/US-4.2-open-decisions.md` v3). All eight Open
Decisions for this story are now resolved. This story is **Ready for
Specification**.

## Revision note (v2)

This revision supersedes v1. It was triggered by `SPEC_REVIEW` v3
(`docs/reviews/specifications/US-4.2-spec-review.md`), which found that
specification v3's handling of the story's Assumptions & Defaults #5 /
TR-AC6 "customer reply reopens a resolved ticket" clause leaves TR-AC6
Partially Covered and produces a Contradiction with the story text —
correctly, per the review's own rule, forcing `CHANGES_REQUIRED` rather than
`PASS`. `story-orchestrator` routed this back to `CLARIFICATION`
(loop_back key `changes_required_clarification`) rather than to
`SPECIFICATION`, because the root defect traces to the story itself, not to
anything `story-spec-writer` could have inferred. This revision's only
substantive addition is **OD-8**, formalizing that gap
(`docs/decisions/US-4.2-open-decisions.md` v2). OD-1 through OD-7 are
unchanged from v1 and remain resolved.

## Scope, Actors, Business Value

**Actors:** Customer and Support Agent (`personas.md`), sharing one endpoint pair. **Trigger:** either party needs to add to an existing ticket's conversation. **Business value:** keeps support history in one threaded place instead of scattered emails (`docs/stories/US-4.2-ticket-replies.md` User Story; `personas.md` Customer frustration — "Support tickets that read as a black hole, with no visible status or reply"; Support Agent goal — "Reply publicly to a customer, or leave an internal note visible only to other staff").

In scope: `POST /v1/support/tickets/{id}/replies` (public or internal reply, with status side effects and `first_response_at` stamping), `GET /v1/support/tickets/{id}` (the thread, filtered by caller visibility). Out of scope: resolution/closure/reopening transitions (US-4.3), inbound reply-by-email ingestion, reply editing/deletion.

## Dependency Check

`docs/stories/README.md`: "US-4.2 depends on US-4.1." Confirmed satisfied — US-4.1 is archived and merged (PR #16); `app/modules/support` exists with `Ticket` and `Attachment` models, a `TicketService`, repository, cache, router, and schemas already in place for this story to extend.

`docs/catalog/stories.yaml` records US-4.3 (the story TR-AC6 and Assumptions & Defaults #5 point to for the reopen behavior) as `state: BACKLOG`, with its own spec (`docs/specifications/US-4.3-spec.md`) flagged "predates the current codebase" — the same caveat that applied to US-4.2's own pre-existing draft. This matters for OD-8 below: citing US-4.3 does not verify a behavior against this codebase.

## What's Clear

- All seven Acceptance Criteria (TR-AC1–TR-AC7) are concrete, testable Given/When/Then statements, confirmed Covered 1:1 by the pre-existing draft spec's FR-1–FR-7 (`docs/reviews/specifications/US-4.2-spec-review.md`, verdict Pass with Issues).
- The internal-note isolation design (application-layer filter + PostgreSQL RLS, `SET LOCAL app.actor_kind`/`app.actor_id`) is stated in enough concrete detail — down to the CHECK constraint and the RLS test's specific "app filter disabled" requirement — to build without inference.
- The status side-effect table (agent public reply → `waiting_on_customer`; customer reply → `waiting_on_support`), the 404-not-403 cross-customer default, append-only mutability, and the 30/user/hour rate limit are all stated directly with rationale.
- The rate-limit-exceeded response, left unresolved by the pre-existing draft spec (written 2026-08-22, before US-4.1 existed), is now resolved by precedent: US-4.1 shipped `429` + `Retry-After` for its own rate limit, which this story can reuse directly.
- A pre-existing draft spec and review exist and are substantially corroborating: independently, they raised six of the seven OD-1–OD-7 gaps as their own Open Questions, plus flagged a seventh (GET pagination) as a Medium review finding — a good sign about the draft's discipline, even though it predates the current codebase and is context only per `docs/catalog/stories.yaml`.
- OD-1 through OD-7 were resolved by explicit human decision at `HUMAN_SPEC_APPROVAL` (2026-09-04T18:15:00Z) and are correctly incorporated into specification v3, confirmed by `SPEC_REVIEW` v3's Acceptance Criteria Coverage table (all seven OD-resolved behaviors traced to specific FRs with no ambiguity flagged).

## What's Ambiguous / Not Yet Resolved

Nothing. See `docs/decisions/US-4.2-open-decisions.md` v3 for full detail —
all eight Open Decisions (OD-1–OD-8) are resolved.

- **OD-8 (Medium, resolved v3):** The story asserted, in both Assumptions & Defaults #5 and TR-AC6, that a customer reply reopens a resolved ticket — a transition owned by *this* story's own endpoint — while simultaneously listing "reopening transitions (US-4.3)" as Out of Scope. `business-rules.md` BR-017 documents the reopen behavior as an established rule, but its cited source (`US-4.3-spec.md`) is an unverified, `BACKLOG`-state draft predating the codebase, and the behavior it describes is inseparable from a 7-day auto-close job and shared boundary constant this story does not build. Not resolvable by citation to `docs/product/*` alone (though `business-glossary.md`'s "Support Ticket" entry does already document "with reopen" as part of the ticket lifecycle, corroborating that reopening is a real product concept, not an invented one) — resolved by explicit human decision, supplied in-session on 2026-09-05: the ticket transitions to `"waiting_on_support"` (not a no-op, and not a new status value). The auto-close/boundary-constant half of BR-017 is explicitly *not* built by this story; `story-spec-writer` must state that split plainly.

## Readiness Verdict

**Ready for Specification.** All eight Open Decisions are resolved and recorded in `docs/decisions/US-4.2-open-decisions.md` v3. `story-spec-writer` must revise FR-2 and FR-6 for OD-8's resolution (customer reply on a `"resolved"` ticket → `201`, status → `"waiting_on_support"`), narrow the Out of Scope line that currently excludes "reopening transitions" wholesale (this story now performs one), and add an explicit note that BR-017's auto-close job and shared boundary constant remain unbuilt — this story implements only the reply-side half of that rule.
