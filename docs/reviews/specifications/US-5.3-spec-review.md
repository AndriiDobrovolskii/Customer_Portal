---
artifact_type: specification_review
story: US-5.3
version: 1
status: APPROVED
created_at: "2026-09-08T19:05:00Z"
updated_at: "2026-09-08T19:05:00Z"
produced_by: story-spec-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Spec Review: Support Tickets (Frontend)

**Original Story:** docs/stories/US-5.3-support-tickets-ui.md
**Spec Reviewed:** docs/specifications/US-5.3-spec.md (version 1)
**Story ID:** US-5.3
**Reviewed:** 2026-09-08
**Overall Verdict:** PASS

## Summary

All 14 Acceptance Criteria (TK-AC1–TK-AC14) are Covered by a corresponding Functional Requirement, each restating the AC's Gherkin behavior, thresholds, and status tables without drift. No Contradiction with the source story was found, including in the spec's Background section, which corrects the story's stated *rationale* for the customer-only agent-queue exclusion (citing US-4.4's retirement of `reject_agent_queue_access`) without changing the exclusion itself or inventing new scope. FR-15 (post-login redirect to `/tickets`, nav entry) is not an AC but is explicitly traceable to the story's own "In Scope" bullet, so it is not scope creep. The six Open Decisions from `docs/decisions/US-5.3-open-decisions.md` v1 are correctly carried forward, unresolved, as the spec's Open Questions 1–6 rather than silently guessed at — the expected, non-blocking handling at this stage, matching this project's precedent (US-5.2's spec review treated its own carried-forward Open Decisions the same way). The one item worth flagging above the others is FR-12: it honestly discloses that TK-AC12's 429 `Retry-After` behavior cannot be implemented as literally stated until OD-1 (High) is resolved, since the shared `httpClient.ts` error path never threads response headers into `ApiError`. This is correctly disclosed, not silently glossed over, so it does not block this review, but it is the highest-priority item for `HUMAN_SPEC_APPROVAL`.

## Acceptance Criteria Coverage

| AC ID | Acceptance Criterion (verbatim from story) | Status | Covered By (spec section) | Notes |
|-------|---------------------------------------------|--------|----------------------------|-------|
| TK-AC1 | "Given an authenticated customer on /tickets When the screen loads Then GET /support/tickets is called and each ticket renders its ticket_number, subject, category, status and updated_at And when next_cursor is non-null a \"Load more\" control appends the next page using that cursor And when items is empty an explicit empty state with a \"New ticket\" call to action is shown, not a blank screen" | Covered | FR-1 | Field list, load-more, and empty-state behavior all match verbatim; also folds in the Client State Notes rule on rendering an unrecognized `status` value verbatim. |
| TK-AC2 | "Given the ticket list When the customer selects one of open / waiting_on_support / waiting_on_customer / resolved / closed Then GET /support/tickets is re-called with that status and the cursor is reset And clearing the filter re-requests the unfiltered list" | Covered | FR-2 | Matches verbatim. |
| TK-AC3 | "Given an authenticated customer on the new-ticket form When they submit a subject (1–150), body (1–5000) and category (≤50) Then POST /support/tickets is called with an Idempotency-Key header and attachment_ids: [] And on 201 they land on that ticket's detail screen" | Covered | FR-3 | Matches verbatim, including field bounds. |
| TK-AC4 | "Given a create submission that failed with a network error or 5xx When the customer retries the same composed ticket Then the identical Idempotency-Key value is sent again And starting a new ticket composition generates a different key" | Covered | FR-4 | Matches verbatim; also folds in the Client State Notes rule that the key is transient (not persisted across a full reload). |
| TK-AC5 | "Given an authenticated customer opening a ticket they own Then GET /support/tickets/{id} renders the ticket header (ticket_number, status, category, created_at, first_response_at when present) and the reply thread And each reply shows its author_kind (customer / agent), body and created_at And when replies.next_cursor is non-null an \"Load older replies\" control fetches the next page with that cursor" | Covered | FR-5 | Matches verbatim, including the note that the thread cursor is independent of the list cursor. |
| TK-AC6 | "Given a ticket that is not closed When the customer submits a reply body (1–5000) Then POST /support/tickets/{id}/replies is called without a visibility field and with attachment_ids: [] And on 201 the new reply appears in the thread and the composer clears And the ticket detail is invalidated/refetched, because a customer reply on a \"waiting_on_customer\" ticket transitions it to \"waiting_on_support\" server-side and ReplyRead carries no status field to report that" | Covered | FR-6 | Matches verbatim, including the invalidation rationale and the no-visibility-control rule from Client State Notes. |
| TK-AC7 | "Given a ticket in open, waiting_on_support, waiting_on_customer or resolved When the customer chooses \"Close ticket\" Then POST /support/tickets/{id}/close is called and the screen reflects status \"closed\" And the reply composer becomes unavailable for a closed ticket" | Covered | FR-7 | Matches verbatim, including the full four-status eligibility list. |
| TK-AC8 | "Given a ticket in status \"resolved\" When the customer chooses \"Reopen\" Then POST /support/tickets/{id}/reopen is called and the screen reflects status \"waiting_on_support\" And a 409 (outside the 7-day reopen window) renders the returned problem+json detail, not a generic failure" | Covered | FR-8 | Matches verbatim. |
| TK-AC9 | "Given any ticket detail screen Then only actions valid for its current status are offered: [status/offered table] And \"Resolve\" is never offered to a customer under any status" | Covered | FR-9 | Status/offered-action table reproduced exactly; "Resolve never offered" line preserved. |
| TK-AC10 | "Given the create-ticket or reply form When a required field is empty or exceeds its max length (subject 150, body 5000, category 50) Then submission is blocked with a field-level error and no API call is made" | Covered | FR-10 | Matches verbatim. |
| TK-AC11 | "Given any request in this Story returns a 4xx application/problem+json body Then the UI renders its detail (or a mapped, user-friendly message keyed by type) with no raw JSON or stack trace And a 422 validation-failed maps its errors array onto the matching form fields And a 404 on a ticket id shows a \"not found\" state (the backend deliberately returns 404, not 403, for a ticket the caller does not own)" | Covered | FR-11 | Matches verbatim. |
| TK-AC12 | "Given POST /support/tickets or POST /{id}/replies returns 429 with a retry-after signal Then the UI shows a message naming when the customer may retry and disables the submit control until then And it does not auto-retry the request in a loop" | Covered | FR-12 | Required behavior restated verbatim, but FR-12 itself discloses the behavior "cannot be implemented as literally stated" until OD-1 (High) decides how `Retry-After` reaches `ApiError`. See Ambiguities below — disclosed, not silently glossed over, so coverage stands, but this is the spec's most consequential open item. |
| TK-AC13 | "Given a network error or 5xx from any endpoint in this Story Then a retry-capable error state is shown — never a blank screen, an indefinite spinner, or an unhandled exception" | Covered | FR-13 | Matches verbatim. |
| TK-AC14 | "Given a request in this Story fails with 401 Then US-5.1's silent-refresh path handles it (single refresh, retry once, else clear state and redirect to /login) Given the customer's account was deactivated Then POST /support/tickets' 403 renders its problem+json detail rather than a generic error" | Covered | FR-14 | Matches verbatim. |

## Ambiguities & Non-Verifiable Statements

- **[Medium] FR-12 states a requirement whose implementation mechanism is undecided (OD-1, High)** — Spec says: "This requirement therefore cannot be implemented as literally stated without a scoped change to that shared client, and how that change should be shaped is not yet decided" (FR-12). This is a genuine, disclosed gap, not a silently-invented workaround — FR-12 correctly states the required *behavior* (testable as written) while flagging that the *mechanism* to read `Retry-After` is blocked pending OD-1. This is the correct, non-blocking handling for `SPECIFICATION`/`SPEC_REVIEW` (resolution belongs to `HUMAN_SPEC_APPROVAL`), matching how US-5.2's spec review treated its own carried-forward Open Decisions — but it is the single highest-impact open item in this spec, since without OD-1's resolution an implementer cannot build FR-12/TK-AC12 at all.
- **[Low] OD-2, OD-3, OD-4, OD-5, OD-6 remain open and carry real (but already-disclosed) ambiguity into build** — Correctly carried forward, unresolved, as Open Questions 2–6 in the spec, each with an explicit citation back to its `open-decisions.md` entry. None is silently resolved or dropped. Each remains a real gap a developer could not act on without an answer (final vs. provisional `category` free-text; reactive-only handling of the 7-day reopen window; `first_response_at` label copy; component/design-system confirmation; edited-resubmission `Idempotency-Key` behavior) — but this is expected, non-blocking handling at this stage, not a defect in the spec's fidelity to the story.

## Contradictions With Original Story

None found. The Background section's correction of the story's stated rationale for the customer-only exclusion — story says (Dependencies & Blockers #1): "`GET /support/tickets` explicitly rejects `tickets:read`/`tickets:write` holders (403)... An agent queue UI is unbuildable until a backend Story adds one"; spec says (Background): "That rejection was retired when US-4.4 (Agent Ticket Queue & Assignment) shipped an agent-branch response on the same route... this Story is customer-only by design, not because the backend still blocks anything else" — corrects a stale *technical justification*, cited to `docs/catalog/stories.yaml`'s recorded US-5.3/US-5.5 split, without changing the actual scope decision (customer-only remains customer-only) or any AC. This is a factual correction with a traceable citation, not a conflict between the spec's requirements and the story's stated behavior or user goal.

## Scope Creep

None found. FR-15 (post-login redirect to `/tickets`, nav entry) is not tied to a numbered AC but is explicitly traceable to the story's own In Scope bullet: "Changes US-5.1's shipped code: the authenticated post-login redirect and home route move from US-5.1's placeholder to `/tickets` (Assumption #7), and `/tickets` is added to the app shell's navigation." No FR, NFR, or Open Question introduces a requirement, field, or system the story does not mention. The Background section's rationale correction (see above) adds no new requirement.

## Missing Edge Cases, Boundary Conditions & Error Handling

- **[Low, phrased as a question] Page size (`limit`) for `GET /support/tickets` is unstated** — The story's own API Contract table gives an explicit range for the detail endpoint's reply page (`?cursor=&limit=` — 1–100, default 50) but no range for the list endpoint's own `?status=&cursor=&limit=`. Neither TK-AC1/FR-1 nor TK-AC2/FR-2 states a page size for the ticket list. Does this Story need to pin a default `limit` for the list request, or is that an implementation-level default left open by the story itself (in which case the spec's silence correctly mirrors the story's own silence)?

No other gaps were found beyond the six Open Decisions already disclosed above (which are themselves the correct mechanism for flagging genuine edge-case ambiguity at this stage, not a spec defect).

## Verdict Rationale

PASS: all 14 ACs are Covered (none Missing or Partially Covered) and no Contradiction was found. The findings above are non-blocking: FR-12's disclosed implementation gap (OD-1) and the five other carried-forward Open Decisions are the expected, correctly-handled deferral to `HUMAN_SPEC_APPROVAL` rather than an unexplained gap or invented resolution, and the one edge-case question (list page size) is minor and mirrors the story's own silence on the point.
