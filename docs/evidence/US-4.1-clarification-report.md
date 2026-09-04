---
artifact_type: clarification_report
story: US-4.1
version: 1
status: ARCHIVED
created_at: "2026-09-03T00:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
supersedes: null
---

# US-4.1 (Support Tickets — Create) — Clarification Report

## Scope, Actors, Business Value

**Actor:** Customer (`personas.md`), with a secondary read path for Support Agent. **Trigger:** a customer needs help and wants it tracked with a reference number instead of vanishing into an inbox (`docs/stories/US-4.1-create-ticket.md` User Story). **Business value:** turns an ad-hoc support channel into a trackable, auditable record — the first slice of Epic 4 (`product-vision.md` goal 3, "communicate with support"; `personas.md` Customer frustration: "Support tickets that read as a black hole").

In scope: `POST /v1/support/tickets` (create, idempotent, with attachment binding and its IDOR check), `GET /v1/support/tickets` (list the caller's own tickets). Out of scope: attachment *upload* itself (separate, blocking story), replies (US-4.2), status transitions (US-4.3), agent queue views/assignment/routing, SLA targets and CSAT.

## Dependency Check

`docs/stories/README.md`: "US-4.1 is blocked by an as-yet-unwritten attachment-upload story." Confirmed — no `attachments`, `support`, or `tickets` module exists anywhere under `app/modules/`, and no attachment-upload story exists under `docs/stories/`. This is not a hard blocker on running CLARIFICATION or SPECIFICATION (the story's own Assumptions table and Open Questions already anticipate building minimal attachment-ownership handling without the upload endpoint), but it is the single largest open question for this story — see OD-1.

## What's Clear

- All seven Acceptance Criteria (ST-AC1–ST-AC7) are concrete, testable Given/When/Then statements, confirmed Covered 1:1 by the pre-existing draft spec's FR-1–FR-10 with an accurate traceability matrix (`docs/reviews/specifications/US-4.1-spec-review.md`, verdict Pass with Issues).
- Field limits (subject 1–150, body 1–5000), the rate limit (5/user/hour), the RFC 7807 error envelope, and the IDOR-prevention shape for attachment ownership (BR-016, already codified in `business-rules.md` citing this story's own FR-9) are all stated directly and need no inference.
- The confirmation-email-is-queued-never-inline pattern and the `ticket_audit_log` write match this codebase's established conventions (queued email per `US-1.2`, append-only audit tables per `business-glossary.md`'s Audit Log entry).
- A pre-existing draft spec and review (both dated 2026-08-22) exist and are substantially corroborating: independently, they raised five of the six gaps below as their own Open Questions rather than guessing — a good sign about the draft's discipline, even though it predates the current codebase and is context only per `docs/catalog/stories.yaml`.

## What's Ambiguous / Not Yet Resolved

See `docs/decisions/US-4.1-open-decisions.md` for full detail. Summary:

- **OD-1 (High):** No attachment-upload story or `attachments` table exists yet, and the story's Assumptions table and Open Questions section give conflicting interim defaults (accept-and-bind vs. reject-until-upload-story-ships).
- **OD-2 (Medium):** Idempotency-Key mechanics are under-specified three ways — per-user vs. global Valkey key scoping, response to a missing header, and whether the "different body" reuse check covers the full payload or just `body`.
- **OD-3 (Medium):** `category` has no enumerated value set anywhere in this story or the product docs — needs product/stakeholder input, not an inferred harness decision.
- **OD-4 (Medium):** The story's In Scope list and Out of Scope section directly conflict on agent-facing `GET /v1/support/tickets` behavior (ST-AC2 requires agent-scoped queue visibility; Out of Scope excludes "Agent queue views"), and the endpoint's `status`/`cursor`/`limit` query parameters are unaddressed by any AC.
- **OD-5 (Low):** "Plain text or sanitised Markdown" leaves the actual rendering behavior — needed for the Enforcement Matrix's "No HTML rendering" gate test — undecided.

One non-blocking carry-forward note: `ticket_number`'s non-guessability is a stated security intent (Assumptions table) that the pre-existing spec review found had been lost in FR-1's wording — not ambiguous, but `story-spec-writer` should state it as its own explicit requirement rather than repeating that omission.

## Readiness Verdict

**Not Ready — see Open Decisions.** Five Open Decisions (OD-1 through OD-5) need resolution before `story-spec-writer` can produce a spec that is internally consistent (OD-4 resolves a direct In-Scope/Out-of-Scope contradiction in the story itself) and buildable against the current, empty-of-attachments codebase (OD-1) rather than the stale 2026-08-22 draft's assumptions.
