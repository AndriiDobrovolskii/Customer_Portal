---
artifact_type: open_decisions
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-06T06:30:00Z"
updated_at: "2026-09-06T06:30:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
supersedes: null
---

# Open Decisions: US-4.3 Ticket Resolution

**Story:** `docs/stories/US-4.3-ticket-resolution.md` (`TC-AC` prefix)
**Pre-existing spec:** `docs/specifications/US-4.3-spec.md` (drafted 2026-08-22, "Pass with Issues" per `docs/reviews/specifications/US-4.3-spec-review.md`) predates the current codebase and US-4.2's shipped implementation — context only, not evidence this stage already ran (`docs/workflow/workflow-state.yaml` note).
**Logged:** 2026-09-06 (v1)

## OD-1 (Critical) — The story's normative `"reopened"` status contradicts US-4.2's already-shipped reopen transition

**Question:** This story's State Machine table and Data Model Notes require a `"reopened"` status value (`tickets.status ∈ {open, waiting_on_support, waiting_on_customer, resolved, reopened, closed}`), and TC-AC4 states that a customer reply to a resolved ticket transitions status to `"reopened"`. But US-4.2 (this story's own dependency, already specified, designed, implemented, and archived) already builds exactly this transition: `docs/specifications/US-4.2-spec.md` FR-2/FR-6, Resolution OD-8, human-confirmed 2026-09-05T09:00:00Z, ships a customer reply on a `"resolved"` ticket as `201` with status transitioning to `"waiting_on_support"` — verified live in `app/modules/support/service.py:515-518` ("Resolution OD-8: the resolved-ticket case reopens the ticket" → `status_update = "waiting_on_support"`). No `"reopened"` status value exists anywhere in the schema (`Ticket.status` is an unconstrained `String(32)`, `app/modules/support/models.py`) or in any shipped code. US-4.2's own Out of Scope section is explicit that "the auto-close job and boundary constant that would complete [BR-017] are US-4.3's to build" and "No other reopening path is introduced" — meaning US-4.2 already claims ownership of the reply-triggered reopen behavior for this exact scenario.

**Why it can't be inferred:** `docs/product/business-rules.md` BR-017 says only "a customer reply within that window reopens it instead," without naming a status value. `docs/product/business-glossary.md`'s "Support Ticket" entry describes the lifecycle as "`open` → `waiting_on_support`/`waiting_on_customer` → `resolved` → `closed`, with reopen" — it never lists a distinct `"reopened"` state, which is consistent with US-4.2's shipped behavior, not with this story's own Data Model Notes. Nothing in `docs/product/*` resolves whether this story's `"reopened"` value is a defect in the story text (inherited from before US-4.2 existed) or an intentional new state this story must still introduce for other transitions (e.g. a direct `/reopen` call, OD-3).

**Impact if left unresolved:** `story-spec-writer` cannot write FR-4 (TC-AC4) without either contradicting the story's own literal Data Model Notes/State Machine table, or contradicting shipped, archived US-4.2 behavior it cannot silently re-implement differently. `db-designer` cannot decide whether `tickets.status` needs a real `"reopened"` value at all. `test-writer` cannot write a TC-AC4 test without knowing which status the assertion checks.

**Recommendation:** Treat US-4.2's shipped behavior as authoritative precedent (it is already merged and archived) and correct TC-AC4's target status to `"waiting_on_support"`, matching what the running system already does — the story's own Assumptions & Defaults framing ("reopened" as a distinct value) is superseded by the later, more specific decision recorded in `docs/decisions/US-4.2-open-decisions.md` OD-8. Under this reading, `"reopened"` is dropped from `tickets.status`'s value set entirely, and the State Machine table's `resolved → reopen → reopened` rows are re-expressed in terms of `"waiting_on_support"`. This is a product/consistency call, not one this skill should silently make — recommend explicit human confirmation before `SPECIFICATION` commits to it.

## OD-2 (Medium) — "The previously assigned agent" refers to a concept the schema doesn't have

**Question:** TC-AC4 says "the previously assigned agent is notified" when a reply reopens a resolved ticket. But `Ticket` (`app/modules/support/models.py`) has no assignee column, and `docs/decisions/US-4.2-open-decisions.md` OD-2 already established, for the identical notification problem in US-4.2, that "no assignment concept exists" and every ticket is treated as unassigned, with notifications routed to a shared support-queue email address instead.

**Why it can't be inferred:** Nothing in `docs/product/*` or the shipped schema introduces an assignment concept between US-4.2 and this story.

**Impact if left unresolved:** `db-designer` cannot decide whether this story is expected to add an assignment column (widening its own scope, and contradicting US-4.1/US-4.2 precedent of deferring assignment) or whether "assigned agent" should be read as the same queue-notification concept OD-2 already settled. `service-and-router-builder` cannot implement the FR-4-equivalent notification without a defined recipient and channel.

**Recommendation:** Follow the US-4.2 OD-2 precedent directly: notify the same configured support-queue address via the existing `EmailSender` pattern, since no per-ticket agent identity is tracked. Do not add an assignment column.

## OD-3 (Medium) — The `/reopen` endpoint's direct-call success path has no Acceptance Criterion

**Question:** The API Contract and State Machine table both list `POST /v1/support/tickets/{id}/reopen` with a direct-call success path (`resolved → reopen (within 7 days) → reopened, actor: customer or agent`), but no TC-AC describes this endpoint succeeding — TC-AC4 covers reopening only via a reply, and TC-AC5 covers `/reopen` only when called on an already-`"closed"` ticket (409). This gap is entangled with OD-1: the endpoint's stated target status is also `"reopened"`.

**Why it can't be inferred:** No AC exercises the success path; the story's own text is silent on whether this endpoint is in scope for this story's acceptance criteria and tests at all.

**Impact if left unresolved:** `story-spec-writer` cannot write a complete FR for this endpoint's success path (target status, whether `resolved_at` is cleared, notification, `ticket_audit_log` event name). `test-writer` cannot write a passing-case test for `/reopen`.

**Recommendation:** This needs explicit confirmation before `SPECIFICATION`: is `POST /reopen`'s success path in scope for this story at all, and if so, does it target `"waiting_on_support"` (consistent with OD-1's recommended correction) rather than a `"reopened"` value that doesn't exist in the shipped schema?

## OD-4 (Low) — Strict/inclusive boundary comparison assignment is unstated

**Question:** The Non-Functional / Security Requirements state "the reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them," but do not say which of the two (the reply-reopen guard or the auto-close job predicate) uses the strict comparison and which uses the inclusive one.

**Why it can't be inferred:** BR-017 and the business glossary are silent on this; it is a pure implementation-boundary detail with two symmetric answers.

**Impact if left unresolved:** `test-writer` cannot write a boundary-instant test (a reply and the job firing at exactly the 7-day mark) without knowing which predicate wins.

**Recommendation:** Assign the auto-close job predicate the inclusive comparison (`>= 7 days`) and the reply-reopen guard the strict comparison (`< 7 days`), so a reply arriving at the exact boundary instant is treated as "too late" and the job — not the reply — owns that instant. This is a low-stakes, symmetric default; confirm before `SPECIFICATION` finalizes it, but it does not block progress the way OD-1–OD-3 do.

## OD-5 (Medium) — Resolve-eligible states: TC-AC1's "open state" vs. the State Machine table's four source states

**Question:** TC-AC1 restricts agent-resolve to a ticket "in an open state," but the normative State Machine table permits `resolve` from four states (`open`, `waiting_on_support`, `waiting_on_customer`, `reopened`) and separately notes `"open"` is "an entry state only... never the target of a transition." Does FR-1's resolve behavior apply to all states the transition table permits, or only to literal status `"open"` as TC-AC1's wording states?

**Why it can't be inferred:** Both the AC and the table are the story's own normative text; neither cites the other as authoritative, and `docs/product/*` does not resolve which takes precedence.

**Impact if left unresolved:** `test-writer` cannot write TC-AC1-adjacent tests for the other three source states without knowing whether resolve from them is in scope or an illegal-transition case.

**Recommendation:** Treat the State Machine table as authoritative (it is the story's own explicitly "normative" section) and read TC-AC1 as the specific example it names, not an exhaustive restriction — resolve is permitted from all four listed source states. Confirm before `SPECIFICATION`.

## OD-6 (Medium) — Agent-initiated `/close` is not covered by any Acceptance Criterion

**Question:** The API Contract lists `/close` auth as "Requester or `tickets:write`," and the State Machine table names the actor as "requester or agent," but TC-AC2 (the only close-related AC) exercises only the requester path and states "the audit entry records `actor=self`." No AC states what happens, or what `ticket_audit_log` actor value is recorded, when an agent — not the requester — calls `/close`.

**Why it can't be inferred:** Neither `docs/product/*` nor the story's own ACs address this path; `US-4.2`'s reply-audit precedent (`actor=agent:{id}` for agent replies vs. implied `actor=self`/customer for customer replies) is suggestive but not stated for this endpoint.

**Impact if left unresolved:** `test-writer` cannot write an agent-close test case; `story-spec-writer` cannot state the audit-actor value with confidence.

**Recommendation:** Mirror TC-AC1's resolve-audit convention: an agent-initiated close responds `200`/`closed_at` identically to TC-AC2, with the audit entry recording `actor=agent:{id}` (parallel to `event=ticket_resolved, actor=agent:{id}` in TC-AC1) rather than `actor=self`.

## OD-7 (Low) — `closed_by` value is unstated for both closure paths

**Question:** The Data Model Notes' `CHECK ((status = 'closed') = (closed_at IS NOT NULL AND closed_by IS NOT NULL))` requires a `closed_by` value whenever a ticket is closed, but no AC states what value `closed_by` takes for TC-AC2 (customer/agent close) or TC-AC3 (system auto-close).

**Why it can't be inferred:** No AC or business-rules entry addresses this column; it is purely a data-model consequence of the CHECK constraint the story itself states.

**Impact if left unresolved:** `db-designer` cannot decide `closed_by`'s type (a `users.id` FK vs. a nullable-actor-kind sentinel for the system case) without knowing whether `"system"` (a non-UUID sentinel, mirroring `ticket_audit_log`'s `actor=system`) must be representable there.

**Recommendation:** Set `closed_by` to the acting user's id for TC-AC2 (requester or agent), and use a well-known system-actor representation (e.g. a reserved sentinel UUID or a nullable FK with a parallel `closed_by_kind` discriminator) for TC-AC3's auto-close, consistent with `ticket_audit_log`'s existing `actor=system` convention. Confirm the exact representation before `db-designer` runs.

## OD-8 (Low) — TC-AC1's "link to reopen" presumes a working reopen mechanism, entangled with OD-1/OD-3

**Question:** TC-AC1 states the requester is emailed "the resolution note plus a link to reopen." This presumes a working customer-facing reopen mechanism exists by the time this notification is sent, but which mechanism it links to (the `/reopen` endpoint whose success path is itself unspecified per OD-3, or simply instructional text pointing at the reply thread which US-4.2 already reopens per OD-1's precedent) is not stated.

**Why it can't be inferred:** Directly downstream of OD-1 and OD-3; cannot be resolved independently of them.

**Impact if left unresolved:** `openapi-designer`/notification-template authors cannot finalize the email's call-to-action without knowing which mechanism it targets.

**Recommendation:** Resolve after OD-1 and OD-3 — if `/reopen`'s success path is out of scope for this story (OD-3) and reopening happens only via a reply (as US-4.2 already ships), the "link to reopen" most likely just directs the requester to the ticket thread, not a distinct `/reopen` action.

## Carried forward, non-blocking

- **TC-AC5's `allowed_events` response field.** Not an Open Decision — the story's own `## Error Envelope` example names the concrete field (`"allowed_events": []`), resolvable by direct citation. `story-spec-writer` should reproduce that example rather than describing the field only in prose (a gap the pre-existing spec review flagged in the earlier draft).
- **TC-AC7's stray `# consistent with TR-AC4` comment.** Non-blocking; `story-spec-writer` should drop the cross-reference rather than propagate it, consistent with how the pre-existing spec already handled it.
- **Rate limiting / notification delivery mechanism.** No new question — this story reuses the `EmailSender` pattern already established in `app/modules/support/service.py` by US-4.1/US-4.2.

---

## Verdict input

Eight Open Decisions (OD-1 through OD-8) are logged, none resolved yet. OD-1 is
**Critical**: it identifies a direct conflict between this story's own
normative Data Model Notes/State Machine table and already-shipped, archived
US-4.2 behavior, and OD-3/OD-8 cannot be resolved independently of it. None of
these block `CLARIFICATION` itself from passing — per this skill's harness
contract, Open Decisions may remain `OPEN` at this stage and are resolved at
`HUMAN_SPEC_APPROVAL` — but `story-spec-writer` cannot write a coherent FR-4 /
`/reopen` section without at least a working default for OD-1, and human
confirmation is strongly recommended before `SPECIFICATION` proceeds past
those FRs, given the cost of contradicting already-shipped code.
