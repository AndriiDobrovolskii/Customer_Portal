---
artifact_type: specification_review
story: US-5.5
version: 2
status: APPROVED
created_at: "2026-09-13T22:00:00Z"
updated_at: "2026-09-14T03:15:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/reviews/specifications/US-5.5-spec-review.md (v1)
---

# Spec Review: Agent Console (Frontend)

**Original Story:** docs/stories/US-5.5-agent-console-ui.md
**Spec Reviewed:** docs/specifications/US-5.5-spec.md (version 2)
**Story ID:** US-5.5
**Reviewed:** 2026-09-14
**Overall Verdict:** PASS

## Summary

This is a re-run against specification v2, which resolves OD-1 through OD-5
(v1 deferred them to `HUMAN_SPEC_APPROVAL`, which never carried a resolution
back into the spec text — the root cause of the downstream `PLAN_REVIEW`
`BLOCKED` verdict recorded at `2026-09-14T02:10:00Z`). Independently checked:
the spec's Open Questions section now reads "None" rather than carrying
OD-1–OD-5 forward, and each of the five resolutions from
`docs/decisions/US-5.5-open-decisions.md` (v2) appears as concrete,
testable requirement text in FR-1, FR-2, FR-3, FR-6, FR-7, and new FR-11 —
not merely restated in the "Decisions Resolved by Human" table with no
functional consequence. The defect that caused the v1 chain's
`PLAN_REVIEW` to block does not survive into v2. All nine Acceptance
Criteria (AG-AC1–AG-AC9) remain Covered, and no contradiction between spec
and story was found. Three new ambiguities surface from the added
resolution text (none rising to Major/Critical), and the two pre-existing
Low-severity edge-case gaps from the v1 review remain unaddressed since
their host sections (FR-1's empty-result state, FR-5's whitespace-only
note) were not among the sections the human resolutions touched.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| AG-AC1 | "Given an agent holding tickets:read on /agent/tickets Then GET /support/tickets renders every non-closed ticket with ticket_number, subject, category, status, assignee and updated_at, oldest-updated first And status / category / assignee_id filters re-request the queue and reset the cursor And assignee_id=me and assignee_id=none are offered as one-click presets, mutually exclusive (US-4.4's assignee_id takes a single value; a union of the two is not expressible) And a non-null next_cursor drives \"Load more\"; no total count or page number is displayed" | Covered | FR-1 | FR-1 restates every clause and now also states the assignee-display rule (Resolution OD-1) and the "a specific agent" filter mechanism (Resolution OD-2), both grounded in the story's own In Scope bullet and API Contract table, not invented. |
| AG-AC2 | "Given an agent holding tickets:write on a ticket in the queue When they choose \"Assign to me\" Then POST /support/tickets/{id}/assign is called with their own id and the row reflects the new assignee When they assign to another agent, or unassign Then the corresponding assign / DELETE assign call is made and the queue is invalidated And a 409 (closed ticket) or 422 (assignee is not an agent) renders its problem+json detail" | Covered | FR-2 | The "assign to another agent" mechanism, previously left open as OD-2, is now the raw-UUID text input — concrete and testable. |
| AG-AC3 | "Given an agent opening a ticket Then GET /support/tickets/{id} renders the ticket header and the full thread And internal-visibility replies are rendered visually distinct from public ones and explicitly labelled \"internal\" And \"Load older replies\" pages the thread by its own cursor" | Covered | FR-3 | Now also specifies the header's assignee source (navigation-state handoff, Resolution OD-3) and its unknown/stale fallback for direct-URL entry — see Ambiguities. |
| AG-AC4 | "Given an agent on a ticket that is not closed Then the composer's visibility control defaults to \"public\" When they submit a public reply Then POST /{id}/replies is called with visibility \"public\" and the ticket detail is invalidated... When they submit an internal note Then visibility \"internal\" is sent and the note renders in the internal style, with no status change expected And choosing \"internal\" is a deliberate, visible action — never the default and never a silent state" | Covered | FR-4 | Unchanged from v1; not touched by any of OD-1–OD-5. |
| AG-AC5 | "Given an agent on a ticket in open, waiting_on_support or waiting_on_customer When they resolve it with a non-empty resolution_note (1..5000) Then POST /{id}/resolve is called and the screen reflects status \"resolved\" And an empty note blocks submission client-side with a field-level error And a 409 on a closed ticket renders the returned problem+json detail" | Covered | FR-5 | Unchanged from v1. See Missing Edge Cases — whitespace-only note boundary (carried forward). |
| AG-AC6 | "Given any agent ticket detail screen Then only actions valid for its current status are offered: \| status \| offered \| \| open \| reply, assign, resolve, close \| \| waiting_on_support \| reply, assign, resolve, close \| \| waiting_on_customer \| reply, assign, resolve, close \| \| resolved \| reply, assign, close, reopen \| \| closed \| (none) \| And an agent holding tickets:read but not tickets:write sees a read-only view with every write control disabled" | Covered | FR-6, FR-7 | FR-6 now also specifies the detail-screen "assign" affordance's data source (Resolution OD-3) and its invalidation behavior; FR-7 now specifies the close/reopen interaction shape (Resolution OD-5, single button, no reason field, no confirmation). |
| AG-AC7 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields" | Covered | FR-8 | Unchanged from v1. |
| AG-AC8 | "Given POST /{id}/replies returns 429 with a retry-after signal Then the UI shows a message naming when the agent may retry and disables the submit control until then And it does not auto-retry in a loop" | Covered | FR-9 | Unchanged from v1. |
| AG-AC9 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | Covered | FR-10 | Unchanged from v1. |

FR-11 (Shared App Shell Navigation, new in v2) traces to the story's own
Open Question #2 as resolved by Decision OD-4, not to any AC — the spec's
own Traceability Matrix correctly notes this rather than fabricating an AC
link.

## Ambiguities & Non-Verifiable Statements

- **[Medium] Unspecified rendering for "unknown/stale" assignee** — FR-3 says: "If the screen is opened by a direct URL rather than by clicking a queue row, no handed-off value exists and the assignee is treated as unknown/stale until the first assign/unassign call on this screen resolves it." The resolution mechanism (no value, no workaround call) is concrete and testable, but the actual rendered output for this state is not specified (a blank cell? a literal "Unknown" label? a placeholder dash?). A developer or QA engineer could not write a precise assertion for AG-AC3's "renders the ticket header" in this state without a follow-up question.
- **[Low] Queue invalidation on detail-screen assign not restated** — FR-6 states the detail screen's local assignee value is updated "from the response (`AgentTicketStateRead`)... since the invalidated-and-refetched `TicketDetailRead`... carries no `assignee_id` field" — so `TicketDetailRead` invalidation on assign-from-detail is stated. Whether the **queue** (per the story's Client State Notes: "every successful reply, assign, resolve, close or reopen invalidates the ticket detail and the queue") is also invalidated when assign/unassign originates from the detail screen (as opposed to FR-2's queue-originated assign, which explicitly invalidates the queue) is not restated in FR-6. Likely intended given the Client State Notes' blanket rule, but not stated for this specific path.
- **[Low] No rendering specified for a null assignee** — FR-1 says: "Where present, the assignee column renders the assigned agent's identity as a shortened/truncated `assignee_id` UUID." The case where `assignee_id` is null (unassigned ticket) — a state AG-AC1's own default view (per the story's Assumption #4, "no `assignee_id` filter applied — every non-closed ticket") will routinely surface — is not addressed: blank cell vs. an explicit "Unassigned" label is undetermined.

## Contradictions With Original Story

None found. The five newly-added resolutions (FR-1, FR-2, FR-3, FR-6, FR-7,
FR-11) do not conflict with any AC's Gherkin text or the story's Client
State Notes / API Contract table; where they narrow an open point (e.g.
FR-3's navigation-state handoff for the "assign" affordance's data source),
they do so consistently with the story's own documented backend constraint
that `TicketDetailRead` carries no `assignee_id` field.

## Scope Creep

None found. Every clause added in v2 (FR-1's assignee display and
specific-agent filter mechanism, FR-2's assign-target input, FR-3's
navigation-state handoff, FR-6's assign-affordance data source, FR-7's
close/reopen interaction shape, and new FR-11) is traceable either to an
existing AC/In-Scope bullet the story already named, or — for FR-11 — to
the story's own Open Question #2, resolved via Decision OD-4. None
introduces a new field, endpoint, or system the story never mentioned.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low] Empty queue result** — Carried forward from the v1 review: FR-1 does not state what the screen shows when zero non-closed tickets match the current filters. The Non-Functional Requirements list an explicit loading state and an explicit error state but not an empty-result state. Does AG-AC1's queue screen need a distinguishable "no tickets" state, or is an empty list sufficient? Phrased as a question since neither AG-AC1 nor the NFR section clearly requires one; FR-1's v2 additions (assignee display, specific-agent filter) do not touch this gap.
- **[Low] Whitespace-only `resolution_note`** — Carried forward from the v1 review, unchanged: AG-AC5 and FR-5 both state "an empty note blocks submission client-side with a field-level error," using the API Contract's `resolution_note: 1..5000` bound. Neither the story nor the spec states whether a note consisting only of whitespace (non-zero length, no visible content) is treated as empty for this client-side check. This ambiguity originates in the source story and remains unresolved by v2's OD-1–OD-5 changes, which did not touch FR-5.

## Verdict Rationale

PASS: every Acceptance Criterion is Covered with no Missing or Partially
Covered items, and no contradiction between the spec and the source story
was found. Critically, the spec's Open Questions section no longer defers
OD-1–OD-5 — it reads "None," and each of the five resolutions is embedded
as concrete, implementable requirement text in FR-1, FR-2, FR-3, FR-6,
FR-7, and new FR-11 (verified against `docs/decisions/US-5.5-open-decisions.md`
v2 clause by clause), not merely echoed in the "Decisions Resolved by
Human" table with no functional consequence. This is the specific defect
that caused v1's downstream `PLAN_REVIEW` to return `BLOCKED`
(`docs/workflow/history.jsonl` at `2026-09-14T02:10:00Z`), and it does not
recur here. The Medium/Low findings above (an unspecified "unknown/stale"
assignee rendering, an unrestated queue-invalidation path, an unspecified
null-assignee rendering, plus the two pre-existing Low edge-case gaps) are
non-blocking and do not warrant `CHANGES_REQUIRED`.
