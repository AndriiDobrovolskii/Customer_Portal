---
artifact_type: open_decisions
story: US-4.2
version: 3
status: ARCHIVED
created_at: "2026-09-04T16:30:00Z"
updated_at: "2026-09-05T09:15:00Z"
produced_by: us-clarifier
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
supersedes: docs/decisions/US-4.2-open-decisions.md (v2)
---

# Open Decisions: US-4.2 Ticket Replies

**Story:** `docs/stories/US-4.2-ticket-replies.md` (`TR-AC` prefix)
**Pre-existing spec:** `docs/specifications/US-4.2-spec.md` (drafted 2026-08-22, Pass with Issues per `docs/reviews/specifications/US-4.2-spec-review.md`, predates the current codebase — context only per `docs/catalog/stories.yaml`).
**Logged:** 2026-09-04 (v1); revised 2026-09-04 (v2); revised 2026-09-05 (v3)

## Revision note (v3)

This revision supersedes v2 and formally closes **OD-8**, the last open item.
Unlike OD-1–OD-7 (resolved as a single batch at `HUMAN_SPEC_APPROVAL`,
2026-09-04T18:15:00Z), OD-8 traveled further before resolution: `DESIGN_REVIEW`
v2 (`docs/reviews/designs/US-4.2-design-review.md`) found that `api_design` v2
and `db_design` v2 had both treated OD-8 as "confirmed" on the strength of a
silent, comment-free `HUMAN_SPEC_APPROVAL` approval of specification v5 — not
an actual per-item resolution matching the OD-1–OD-7 pattern — and returned
`BLOCKED`. The user then supplied an explicit resolution directly in-session,
and `story-orchestrator` recorded a `HUMAN_REDIRECTED` event
(`docs/workflow/history.jsonl`, 2026-09-05T09:00:00Z) routing
`DESIGN_REVIEW` → `CLARIFICATION` specifically to formalize it here before
`SPECIFICATION` incorporates it. This corrects the working default this
document's own v1/v2 recommendation carried (a): the actual resolution is
closer to candidate (b) from specification v5's own Open Questions list — the
ticket transitions to an existing status (`"waiting_on_support"`), not a
no-op. Note this also confirms `docs/product/business-glossary.md`'s
"Support Ticket" entry, which already documented the lifecycle as "`open` →
`waiting_on_support`/`waiting_on_customer` → `resolved` → `closed`, with
reopen" — this resolution implements that reopen as a transition back to an
existing status value, not a new one, consistent with the glossary's own
framing. OD-1 through OD-7 are unchanged from v1/v2, having been resolved by
explicit human decision at `HUMAN_SPEC_APPROVAL` on 2026-09-04T18:15:00Z.

## Revision note (v2)

This revision supersedes v1. OD-1 through OD-7 below are unchanged from v1 —
all seven were resolved by explicit human decision at `HUMAN_SPEC_APPROVAL`
on 2026-09-04T18:15:00Z (`docs/workflow/history.jsonl`) and incorporated into
`docs/specifications/US-4.2-spec.md` v3. They are carried forward verbatim as
a record, not reopened.

**OD-8 is new**, added because `SPEC_REVIEW` v3
(`docs/reviews/specifications/US-4.2-spec-review.md`) found specification v3
withdraws FR-6's implementation of the story's own Assumptions & Defaults #5
/ TR-AC6 clause ("a resolved ticket... reply reopens it"), producing a
Partially Covered AC and a Contradiction. `story-orchestrator` routed this
back to `CLARIFICATION` (loop_back key `changes_required_clarification`) to
formalize the gap as a Decision, mirroring OD-1–OD-7. This is a different
question from the already-resolved OD-5 (agent public reply on a resolved
ticket, answered: permitted, status unchanged) — OD-8 concerns a **customer**
reply on a resolved ticket.

## OD-1 (High) — `attachment_ids` on a reply has no binding column to persist it

**Question:** The API Contract accepts `{"body", "visibility"?, "attachment_ids"?}` on `POST /v1/support/tickets/{id}/replies`, and BR-016 already covers a uniform "not owned" error for an `attachment_id` referenced by "a ticket-creation or reply request." But the story's own Data Model Notes list only five `ticket_replies` columns (`id`, `ticket_id`, `author_id`, `author_kind`, `body`, `visibility`, `created_at`) with no attachment reference, and the shipped `Attachment` model (`app/modules/support/models.py`) has only `ticket_id` — no `reply_id` or equivalent. A ticket can receive many replies over time; binding an attachment only at the ticket level cannot say which reply it belongs to.

**Why it can't be inferred:** The story asserts the field exists without saying how it's persisted, and no later story revisits the `attachments` table shape (US-4.3 is resolution/closure, not replies/attachments).

**Impact if left unresolved:** `db-designer` cannot decide whether `attachments` needs a new `reply_id` column (and whether it's a migration on an already-shipped table) or whether reply-level attachment binding is out of scope for this story; `test-writer` cannot write attachment-ownership tests for the replies endpoint without a defined persistence shape.

**Recommendation:** Add a nullable `reply_id` FK to `attachments` (parallel to the existing nullable `ticket_id`, bound once and never reassigned per US-4.1's precedent), reusing the same ownership-check/bind sequence `create_ticket` already establishes in `service.py`. This keeps the uniform "not owned" error (BR-016) working unchanged for replies.

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3 FR-1 (`ticket_reply_id` column).

## OD-2 (Medium) — "The assigned agent (or the queue, if unassigned)" refers to a concept the schema doesn't have

**Question:** TR-AC2/FR-2 say a customer reply notifies "the assigned agent (or the queue, if unassigned)." But `Ticket` (`app/modules/support/models.py`) has no assignee column at all — US-4.1 explicitly put "Agent queue views, assignment and routing" out of scope, and no later story adds it before US-4.2. Under the current schema, every ticket is unconditionally "unassigned," so the assigned-agent branch of TR-AC2 can never fire. Separately, the delivery channel for the "queue" branch is unstated — FR-1 explicitly says "notified by email" (reusing the `EmailSender` pattern already used in `support/service.py`), but FR-2 names no channel at all.

**Why it can't be inferred:** Nothing in `docs/product/*` or the shipped code establishes an assignment concept or a "queue" notification target (a distribution address, an agent group, a polling view) to notify.

**Impact if left unresolved:** `db-designer` cannot decide whether this story adds an assignment column now (widening its own scope) or whether "assigned agent" is dead code path; `openapi-designer`/`service-and-router-builder` cannot implement FR-2's notification without knowing the channel and recipient.

**Recommendation:** Treat every ticket as unassigned for this story (consistent with US-4.1 leaving assignment out of scope) and notify a single configured support-queue mailbox via the existing `EmailSender`, parallel to FR-1's requester notification. Do not add an assignment column — that belongs to whichever future story actually builds queue routing.

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3 FR-2.

## OD-3 (Medium) — `GET /v1/support/tickets/{id}` pagination interface is unspecified

**Question:** The NFR states thread-fetch performance is measured "paginated at 50," implying the endpoint paginates its reply list, but no Acceptance Criterion defines the query parameters, cursor/page semantics, or response shape for retrieving replies beyond the first 50.

**Why it can't be inferred:** No AC addresses this; the spec review already flagged it as a Medium gap the draft spec should have caught but didn't.

**Impact if left unresolved:** `openapi-designer` cannot write the GET response contract's pagination fields; `test-writer` cannot write a beyond-first-page test.

**Recommendation:** Follow the same cursor-pagination convention already established for `GET /v1/support/tickets` (US-4.1, itself following `US-3.1-spec.md` FR-1/FR-4): `cursor`/`limit` query parameters, malformed cursor and out-of-range `limit` both `422 validation-failed`, default/opaque cursor semantics unchanged.

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3 FR-3-adjacent GET contract.

## OD-4 (Medium) — Reply-body rendering NFRs assume rich content that plain-text storage doesn't have

**Question:** The NFR says replies are "sanitised on render as well as on write; strip tracking pixels and remote images from agent-facing views." US-4.1 resolved the equivalent question for ticket bodies (OD-5) by storing plain text only, with no rendering pipeline at all (confirmed: no markdown/sanitisation code exists anywhere under `app/modules/support`) — a plain-text field cannot contain a tracking pixel or a remote image to strip. Does this story follow the same plain-text-only precedent (making "strip tracking pixels/remote images" and the Enforcement Matrix's "No HTML rendering" snapshot test trivially satisfied by construction, same as US-4.1), or does it anticipate reply bodies genuinely carrying rich/HTML content this story must actually sanitise?

**Why it can't be inferred:** The story's own Out of Scope section excludes "Inbound reply-by-email ingestion" (the plausible source of pasted HTML/tracking pixels), which would suggest plain text is sufficient — but the NFR's specific wording ("strip tracking pixels and remote images") only makes sense if some non-plain-text content is expected, and nothing states which is true.

**Impact if left unresolved:** `test-writer` cannot write the Enforcement Matrix's "No HTML rendering" `[gate]` snapshot test without knowing whether there's a render pipeline to snapshot, or whether the test is instead an assertion that the field is stored/returned as opaque plain text.

**Recommendation:** Follow the US-4.1 precedent — plain text only, `String(5000)`, no rendering pipeline — and treat "sanitise on render," "strip tracking pixels," and "No HTML rendering" as satisfied by construction (no HTML is ever stored, so none is ever rendered). Write the Enforcement Matrix's snapshot test as an assertion that a body containing `<script>`/`<img>` markup round-trips as inert literal text.

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3.

## OD-5 (Medium) — Agent public reply on a `"resolved"` ticket is explicitly unresolved by the story itself

**Question:** The story's own Open Questions section asks: "Should an agent's public reply on a resolved ticket be permitted (keeping the status resolved), or should the agent be required to reopen first?" TR-AC6 only defines behavior for `"closed"` tickets; no AC covers a reply attempt while `status = "resolved"`. This endpoint (`POST /v1/support/tickets/{id}/replies`) is owned by this story, not US-4.3, so even though the story text says "see US-4.3," the behavior at *this* endpoint needs an answer before FR-6-equivalent logic can be written completely.

**Why it can't be inferred:** The story flags this as an explicit, unresolved product call and does not default it the way it defaults every other open question in its Assumptions & Defaults table.

**Impact if left unresolved:** `story-spec-writer` cannot write a complete status-gating FR for the replies endpoint; `test-writer` cannot write a resolved-ticket reply test case.

**Recommendation:** This needs a product decision, not an inferred one — recommend deferring to the user/product owner. If forced to default for planning purposes: reject with the same `409 ticket-closed`-shaped response is wrong (the story explicitly distinguishes resolved from closed elsewhere), so an explicit answer here should not be improvised from TR-AC6's closed-ticket pattern.

**Resolution (2026-09-04T18:15:00Z, human):** Permitted; status stays `"resolved"`, no side effect — incorporated into specification v3.

## OD-6 (Low) — Agent-omitted `visibility` default is unstated

**Question:** TR-AC5 states the default is `"public"` only for a customer-submitted reply. Data Model Notes show `visibility ∈ {public, internal}` with no schema-level default called out beyond the CHECK constraint. What does an agent's request default to when `visibility` is omitted?

**Why it can't be inferred:** No AC covers the agent-omission case; the CHECK constraint alone doesn't imply a default.

**Impact if left unresolved:** `schema-builder` cannot set a default value on the field with confidence it matches intended behavior for both actor kinds.

**Recommendation:** Default `"public"` uniformly regardless of actor kind (matches the CHECK constraint's more permissive branch and TR-AC5's customer default; an agent who wants an internal note must say so explicitly, which is the safer default given TR-AC3's stated risk level).

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3.

## OD-7 (Low) — `GET /v1/support/tickets/{id}` auth-failure responses are unstated

**Question:** No Acceptance Criterion states the response for an unauthenticated caller or one lacking `tickets:read`/requester status on this specific endpoint, though the API Contract table names the requirement.

**Why it can't be inferred:** No AC covers it; TR-AC4 covers cross-customer access (404) but not missing/insufficient auth.

**Impact if left unresolved:** `test-writer` cannot write a 401/403 test case for the GET endpoint without a defined expected response.

**Recommendation:** Follow this codebase's established pattern (`US-4.1-spec.md` FR-5, `ST-AC5`): `401` for no valid access token, and — since `tickets:read` failure is a scope check rather than a self/other-ticket distinction — a generic authorization failure rather than TR-AC4's ticket-specific `404` (TR-AC4 applies once the caller is authenticated but the ticket belongs to someone else).

**Resolution (2026-09-04T18:15:00Z, human):** Accepted as recommended — incorporated into specification v3.

## OD-8 (Medium, new in v2) — Does a customer reply on a `"resolved"` ticket reopen it within US-4.2's own scope, or is that transition entirely US-4.3's to build?

**Question:** The story's Assumptions & Defaults #5 states "Customer reply reopens (US-4.3 TC-AC4); closed tickets reject," and TR-AC6 repeats it ("a 'resolved' ticket behaves differently — see US-4.3 TC-AC4 (reply reopens it)"). But this same story's own Out of Scope section excludes "Resolution, closure and reopening transitions (US-4.3)" outright, and `POST /v1/support/tickets/{id}/replies` — the endpoint that would have to perform this transition — is owned entirely by *this* story (US-4.2), not US-4.3. So the story asserts a reopening side effect for its own endpoint while simultaneously scoping reopening logic out of itself.

Two facts complicate a simple "just implement it" reading:
- `docs/product/business-rules.md` BR-017 does document "a customer reply within that window reopens" `[a resolved ticket]` as an established business rule — but BR-017's own **Source** line cites `docs/specifications/US-4.3-spec.md` FR-3/FR-4/NFR, and `docs/catalog/stories.yaml` records US-4.3 as `state: BACKLOG` with the note "Draft specification predates the current codebase" — the same staleness caveat that applied to US-4.2's own pre-existing draft before this story's CLARIFICATION/SPECIFICATION work replaced it. BR-017 is therefore only as reliable as an unvalidated draft, not a verified-against-codebase source.
- The reopen transition US-4.3 defines is not a bare status write: `US-4.3-spec.md` FR-3/FR-4 make it complementary to a 7-day auto-close job with a shared boundary constant ("the reply guard and the job predicate must use complementary strict/inclusive comparisons so the boundary instant belongs to exactly one of them"). US-4.2 building only the reply-side half — with no auto-close job, no shared boundary constant, and no `resolved_at`-clearing logic — would create exactly the "reply attached to a ticket in an inconsistent state" risk US-4.3's own NFRs warn against, and would need re-verification (or reimplementation) once US-4.3 actually ships.

**Why it can't be inferred:** `docs/product/*` does not resolve whether "reopens" is a business rule this story must implement now or a downstream story's responsibility this story should stay agnostic to; the codebase gives no signal either (`Ticket.status` is an unconstrained `String(32)` with no enum — nothing technically blocks writing `"reopened"`, but nothing endorses it as a value this story owns either). This is the same contradiction `SPEC_REVIEW` v3 found between the story's own text and what a codebase-consistent spec can build, not a spec-writer inference gap.

**Impact if left unresolved:** `story-spec-writer` cannot write a complete FR-6-equivalent status-gating clause for the replies endpoint; `test-writer` cannot write a resolved-ticket-plus-customer-reply test case; `db-designer` cannot decide whether this story's migration needs to introduce the `"reopened"` status value and a `resolved_at`-clearing write path, or defer both entirely to US-4.3.

**Recommendation (superseded by Resolution below — retained for the record):** This is a product/sequencing call, not one the harness should default silently — recommend deferring to the user/product owner, the same posture taken for OD-5. If forced to default for planning purposes: **do not implement the reopen transition in US-4.2.** Accept the reply normally (`201`, same as any other reply — no TR-AC6-style rejection, since TR-AC6 only targets `"closed"`), but leave `status` at `"resolved"` unchanged and do not clear `resolved_at`, mirroring how OD-5's already-resolved agent case was handled ("permitted, status unchanged"). This keeps US-4.2 fully self-contained (no half-built US-4.3 state machine, no auto-close job to coordinate with) and lets US-4.3 implement the actual reopen transition — including its 7-day boundary logic and BR-017's complementary auto-close job — as one coherent piece of work when it is built. This default explicitly contradicts the story's own Assumptions & Defaults #5 rationale ("Reopening is the customer's affordance"), which is exactly why it should not be silently adopted without confirmation.

**Status:** RESOLVED

**Resolution (2026-09-05T09:00:00Z, human, sbruhov@gmail.com — supplied directly in-session, not this document's own recommended default):** When a customer replies to a ticket with status `"resolved"`, the system accepts the reply (`201`, same as any other reply — no TR-AC6-style rejection) and the ticket's status transitions to `"waiting_on_support"` (the same target status FR-2's normal `"waiting_on_customer"` → `"waiting_on_support"` case already uses), reopening the ticket. This is candidate (b) from specification v5's own Open Questions list, not candidate (a) (this document's prior recommended default, which both `api_design` v2 and `db_design` v2 had incorrectly treated as already confirmed — see `DESIGN_REVIEW` v2 Finding DR-1). No new `Ticket.status` value is introduced; `"waiting_on_support"` already exists in this codebase's `_TicketStatus` literal (`app/modules/support/router.py`).

**Explicitly out of scope, called out by the human decision and required to be stated by `SPECIFICATION`:** this resolution implements only the reply-side half of BR-017's reopen behavior. BR-017 also describes a 7-day auto-close job and a shared boundary constant coordinating the two; neither exists in this codebase and neither is built by this story. `story-spec-writer` must state this explicitly (not silently) when revising FR-2/FR-6, and reconcile it against the story's own Out of Scope line "Resolution, closure and reopening transitions (US-4.3)" — this story now performs one reopening transition itself, which that line must be narrowed to exclude, not read as still fully accurate.

## Resolved by precedent (not an Open Decision)

- **Rate-limit-exceeded response for replies (30/user/hour).** The pre-existing draft spec raised this as unresolved when written (2026-08-22, before US-4.1 existed). It is now resolved: US-4.1 shipped `429` with a `Retry-After` header for its own rate limit (`US-4.1-spec.md` FR-6 / `ST-AC6`, implemented in `support/service.py`'s `TicketCreationRateLimitCacheProtocol`). `story-spec-writer` should cite this precedent directly rather than re-opening it.

## Carried forward, non-blocking

- **TR-AC6's "the response points the caller to creating a new ticket"** already has a concrete `detail` string in the story's own Error Envelope example; the pre-existing spec review (Low) found the FR text didn't tie back to it. Not an Open Decision — `story-spec-writer` should just reference the example directly.
- **FR-1 doesn't state the attachment-ownership error behavior in its own prose** (per `SPEC_REVIEW` v3, Low) — OD-1's resolution covers it by reference only; `story-spec-writer` should state the BR-016 error explicitly in FR-1's text on the next specification revision.

---

## Verdict input

8 Open Decisions (OD-1 through OD-8) plus one precedent-resolved item and two
non-blocking carry-forward notes are the complete set of ambiguities found for
this story. All eight are now resolved: OD-1 through OD-7 by human decision at
`HUMAN_SPEC_APPROVAL` (2026-09-04T18:15:00Z), already incorporated into
specification v5; **OD-8 by human decision supplied directly in-session**
(2026-09-05T09:00:00Z, `sbruhov@gmail.com`) and formalized in this revision —
see OD-8's own Resolution above. Nothing here is a still-open blocker.
**`SPECIFICATION` must now incorporate OD-8's resolution** into FR-2/FR-6 (the
customer-reply-on-`"resolved"`-ticket case: `201`, `status` →
`"waiting_on_support"`) and the Out of Scope section (narrowed to exclude only
the reopen transition this story now performs, not reopening transitions
generally), with an explicit note that the 7-day auto-close job / shared
boundary constant half of BR-017 remains unbuilt and deferred.
