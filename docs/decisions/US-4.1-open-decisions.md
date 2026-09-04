---
artifact_type: open_decisions
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

# Open Decisions: US-4.1 Support Tickets (Create)

**Story:** `docs/stories/US-4.1-create-ticket.md` (`ST-AC` prefix)
**Pre-existing spec:** `docs/specifications/US-4.1-spec.md` (drafted 2026-08-22, Pass with Issues per `docs/reviews/specifications/US-4.1-spec-review.md`, predates the current codebase — context only per `docs/catalog/stories.yaml`).
**Logged:** 2026-09-03

## Corroboration from the pre-existing draft

The 2026-08-22 draft spec and its review independently raised five of the six gaps below (attachment interim handling, missing-header behavior, idempotency comparison scope, agent queue scope, category enum, GET query parameters) as their own Open Questions / findings. This run re-verified each against the current codebase and product docs rather than trusting the stale draft, and confirmed none has since been resolved — no `support`/`tickets`/`attachments` module exists yet (`app/modules/` has no such directory), and no category enum or Idempotency-Key precedent exists anywhere in `docs/product/*` or a shipped spec.

## OD-1 (High) — No attachment-upload story exists; the story gives conflicting interim defaults

**Question:** The story's Assumptions & Defaults table (#6) says `attachment_ids` reference "already-uploaded objects, bound at creation," implying an `attachments` table with ownership tracking already exists. But its own Open Questions section says: "The attachment-upload story must be scheduled ahead of this one; until it lands, `attachment_ids` should be rejected rather than silently ignored. Needs an owner." `docs/stories/README.md` confirms: "US-4.1 is blocked by an as-yet-unwritten attachment-upload story." No `attachments` table, upload endpoint, or upload story exists in this codebase today.

Does this story (a) create a minimal `attachments` table now — enough for FK/ownership tracking and ST-AC7's IDOR check — while leaving the upload *endpoint* itself out of scope (as the story's own Out of Scope section already says), or (b) reject every request that includes a non-empty `attachment_ids` with a defined error (422, and which `type` slug — the existing `attachment-not-owned`, or a new one), deferring all attachment-binding code, including ST-AC7's tests, to whenever the upload story ships?

**Why it can't be inferred:** The story states both defaults in the same document without reconciling them, and product docs have no attachment-upload story to check against for precedent.

**Impact if left unresolved:** `db-designer` cannot decide whether `attachments` is in this story's database design at all; `test-writer` cannot write ST-AC7's tests without knowing whether attachment binding is real code or a stubbed rejection; `openapi-designer` cannot decide whether `attachment_ids` is a live field or omitted from the contract.

**Recommendation:** Build the minimal `attachments` table and the ownership/binding logic now (option a) — ST-AC7 is a `[gate]`-marked Acceptance Criterion the Enforcement Matrix requires tests for, and the story's Data Model Notes already specify the exact columns needed (`attachments.ticket_id`, nullable until bound). This does not require building the upload *endpoint*; attachments can be seeded directly for tests, matching how the story already scopes "Attachment upload... — separate story" out while keeping binding in.

## OD-2 (Medium) — Idempotency-Key mechanics are under-specified in three ways

**Question:**
1. Is the Valkey key scoped per user (e.g. `idempotency:{user_id}:{key}`) or global (`idempotency:{key}`)? The Data Model Notes show only `idempotency:{key}`, which would let one customer's key collide with another's.
2. What is the response when `Idempotency-Key` is omitted entirely? The Assumptions table marks it "required," but no AC states the status code or error type for a missing header.
3. Does the "reused with a different body" comparison (ST-AC4) hash the full request payload (`subject`, `body`, `category`, `attachment_ids`) or only `body`? The `(request_hash, response)` shape in Data Model Notes suggests full-payload, but this is not stated.

**Why it can't be inferred:** This is the first story in the codebase to use `Idempotency-Key` (no existing pattern to follow), and none of the three sub-questions is addressed by the story, `business-rules.md`, or `business-glossary.md`.

**Impact if left unresolved:** `db-designer`/`data-layer-builder` cannot finalize the Valkey key shape; `test-writer` cannot write ST-AC4's "missing header" and "reused key" cases without a defined expected response; a global (non-per-user) key is also a latent cross-customer collision risk worth deciding deliberately rather than by omission, consistent with this project's IDOR-conscious posture (BR-016).

**Recommendation:** Scope the key per user (`idempotency:{user_id}:{key}`) — consistent with every other per-user Valkey key in this codebase (`revoke_before:{user_id}`, `perm_epoch:{user_id}`). Hash the full request payload for the reuse comparison, matching the `(request_hash, response)` shape already specified. Treat a missing header as `422` with type `.../errors/validation-failed`, consistent with FR-3's existing validation-failure pattern rather than inventing a new type.

## OD-3 (Medium) — `category` has no enumerated value set anywhere

**Question:** ST-AC3 and the story's API Contract both reference `category` as a request field subject to an "unknown category" `422`, but no valid value list exists in the story, `business-glossary.md`, or `business-rules.md`.

**Why it can't be inferred:** Ticket categorization is not covered by any existing product document; this is the first story to introduce it.

**Impact if left unresolved:** `story-spec-writer` cannot write a testable FR-3, and `test-writer` cannot write concrete "unknown category" test cases without a defined enum.

**Recommendation:** This needs a product decision (a stakeholder-supplied category list), not an inferred one — recommend deferring to the user/product owner rather than the harness guessing domain categories (e.g. "billing", "technical", "account", "other").

## OD-4 (Medium) — `GET /v1/support/tickets` scope conflicts with the story's own Out of Scope section, and its query parameters are unspecified

**Question:** The story's In Scope list includes `GET /v1/support/tickets — list the caller's own tickets`, and ST-AC2 requires that "a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views." But the Out of Scope section explicitly excludes "Agent queue views, assignment and routing." What does this endpoint actually return when called by a `support_agent`-scoped caller in *this* story — a full permission-scoped queue (contradicting Out of Scope), a fixed minimal behavior (e.g. all open tickets, unfiltered), or a `403` until US-4.2/US-4.3 build queue views? Separately, the API Contract table names `status`, `cursor`, and `limit` as query parameters, but no AC states the accepted `status` values, a maximum `limit`, or the response to a malformed/expired `cursor`.

**Why it can't be inferred:** The In Scope and Out of Scope sections of the same story directly conflict on agent-facing behavior; `business-rules.md`/`business-glossary.md` establish that agents hold `tickets:read` (BR-010) but not what "the queue their permissions allow" concretely returns absent the queue-view story.

**Impact if left unresolved:** `openapi-designer` cannot write the response contract for an agent caller; `test-writer` cannot write ST-AC2's agent-visibility assertion or any pagination/filter edge case.

**Recommendation:** Scope this story's `GET /v1/support/tickets` to customer callers only (their own tickets, matching the endpoint's In Scope description literally) and have an agent-scoped caller receive `403` for now, with a one-line note that full agent queue behavior is Out of Scope and belongs to a not-yet-written queue-view story — resolving the conflict by taking Out of Scope as authoritative over ST-AC2's second clause. For pagination, follow the cursor-pagination convention already established by `US-3.1-spec.md` FR-1/FR-4 (malformed cursor and out-of-range `limit` both `422 validation-failed`).

## OD-5 (Low) — "plain text or sanitised Markdown" leaves the actual rendering choice undecided

**Question:** The story's NFR says ticket bodies are "rendered as plain text or sanitised Markdown" — an either/or that a spec must resolve to one concrete behavior (and, if Markdown, which sanitizer/allowed-tag set) to be testable.

**Why it can't be inferred:** No prior story in this codebase renders user-supplied rich text; there is no established pattern to reuse.

**Impact if left unresolved:** The Enforcement Matrix's "No HTML rendering" `[gate]` snapshot test cannot be written without knowing what a body renders to.

**Recommendation:** Store the body as plain text at this layer (no Markdown rendering pipeline in scope for US-4.1) and defer a Markdown-rendering decision to whichever story first needs it — the NFR's actual hard requirement ("never render user-supplied HTML") is satisfied trivially by plain-text storage/display, and this avoids introducing a new sanitisation dependency for a story that doesn't otherwise need one.

## Carried forward, non-blocking

- **`ticket_number` non-guessability must be stated as an explicit requirement, not just an example format.** The story's Assumptions table states this as a deliberate security decision (parallel to the attachment-id anti-enumeration requirement), and the pre-existing spec review already flagged (Medium) that FR-1 lost this property in translation. Not an Open Decision — the intent is already clear — but `story-spec-writer` should state it as its own testable requirement rather than repeating the mistake the reviewed draft made.

---

## Verdict input

5 Open Decisions (OD-1 through OD-5) plus one non-blocking carry-forward note are believed to be the complete set of ambiguities. OD-3 (category enum) is flagged as needing product/stakeholder input specifically, not an inferable harness decision.
