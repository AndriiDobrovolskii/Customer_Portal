---
artifact_type: clarification_report
story: US-4.3
version: 1
status: ARCHIVED
created_at: "2026-09-06T06:30:00Z"
updated_at: "2026-09-06T06:30:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
supersedes: null
---

# Clarification Report: US-4.3 Ticket Resolution

**Story:** `docs/stories/US-4.3-ticket-resolution.md`
**Open Decisions:** `docs/decisions/US-4.3-open-decisions.md` (v1, 8 items)

## Business Intent

As a support agent, I want to mark a ticket resolved and have it close itself
if the customer is satisfied, so the queue reflects real outstanding work and
customers can still come back if the fix didn't hold. This is the third and
final slice of Epic 4's ticket lifecycle, following US-4.1 (creation) and
US-4.2 (threaded replies), and it owns the terminal transitions:
`resolve`, `close`, `reopen` (direct and reply-triggered), and the auto-close
job. The actor, trigger, and business value are all explicitly stated in the
story — no inference needed here.

## What's Clear

- The `/resolve`, `/close` endpoints, their core happy paths (TC-AC1, TC-AC2),
  the auto-close job's idempotency/conditional-update requirement (TC-AC3),
  the illegal-transition/permission/ownership negative paths (TC-AC5–TC-AC7),
  the concurrency requirement (TC-AC8), and the resolution-note validation
  rule (TC-AC9) are all fully specified with testable Given/When/Then
  criteria.
- Authorization model is consistent with established scopes: `tickets:write`
  for resolve (BR-010, `docs/product/business-glossary.md`), requester-or-
  agent for close.
- The state-check-before-actor-check ordering (403 vs. 409 precedence) is
  explicitly stated as a security requirement and needs no clarification.
- The 7-day auto-close/reopen-window rule is a recorded business rule
  (BR-017), and this story is its authoritative source per the business rules
  file itself.
- The error envelope shape (RFC 7807 `problem+json`) and its `invalid-state-
  transition` type slug are fully specified with a worked example.

## What's Ambiguous

Eight Open Decisions are logged in `docs/decisions/US-4.3-open-decisions.md`.
The most consequential:

- **OD-1 (Critical):** The story's own Data Model Notes and State Machine
  table require a `"reopened"` `tickets.status` value, and TC-AC4 asserts a
  customer reply reopens a resolved ticket to that value. This directly
  contradicts already-shipped, archived US-4.2 behavior: a customer reply on
  a `"resolved"` ticket transitions status to `"waiting_on_support"` instead
  (`docs/decisions/US-4.2-open-decisions.md` OD-8, verified live in
  `app/modules/support/service.py`). No `"reopened"` value exists anywhere in
  the running system. This is not an inference gap — it is a conflict between
  this story's text and code that has already been built and merged, and it
  cascades into OD-3 (`/reopen`'s undefined success-path target status) and
  OD-8 (what "link to reopen" in TC-AC1 actually points to).
- **OD-2 (Medium):** "The previously assigned agent" (TC-AC4) names a concept
  the schema doesn't have — mirrors an already-resolved US-4.2 precedent
  (OD-2 there).
- **OD-3 (Medium):** `/reopen`'s direct-call success path is listed in the
  API Contract and State Machine table but exercised by no Acceptance
  Criterion.
- **OD-5 (Medium)** and **OD-6 (Medium):** two AC-vs-normative-table scope
  gaps (which states resolve is legal from; what happens on an agent-
  initiated close) of the same shape the pre-existing spec review already
  caught elsewhere in this story.
- **OD-4, OD-7, OD-8 (Low):** boundary-comparison assignment, the `closed_by`
  column's value, and the reopen-link's target mechanism.

Two items from the pre-existing (context-only) spec review are **not**
carried forward as Open Decisions because they resolve by direct citation to
the story's own text: the `allowed_events` error-envelope field name, and
TC-AC7's stray cross-reference comment. Both are noted as non-blocking
carry-forward items in the Open Decisions log instead.

## Dependency Check

- **US-4.1** (create ticket): shipped, archived. This story's `/resolve`,
  `/close`, `/reopen` all operate on tickets US-4.1 already creates; no
  conflict found.
- **US-4.2** (ticket replies): shipped, archived, and **directly load-bearing
  for OD-1** — it already implements one half of BR-017 (the reply-side
  reopen transition) using a status value this story's own text doesn't
  recognize. This story cannot be specified correctly without reconciling
  against what US-4.2 actually built, not just what the story text says.
- `docs/stories/README.md` confirms "US-4.3 depends on US-4.1 and US-4.2" —
  consistent with the above.

## Readiness Verdict

**Ready for Specification**, with 8 Open Decisions carried forward
(`docs/decisions/US-4.3-open-decisions.md`). OD-1 is Critical and should be
confirmed by a human before `story-spec-writer` commits to FR-4's target
status and the `/reopen` endpoint's shape — proceeding on this skill's own
recommended default (retire `"reopened"`, use `"waiting_on_support"`,
matching shipped US-4.2 behavior) is reasonable for drafting purposes but
should not be treated as a final human decision until confirmed at
`HUMAN_SPEC_APPROVAL`.
