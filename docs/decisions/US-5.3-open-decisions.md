---
artifact_type: open_decisions
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-08T16:44:04Z"
updated_at: "2026-09-08T16:44:04Z"
produced_by: us-clarifier
inputs:
  - path: docs/product/product-vision.md
    version: null
  - path: docs/product/personas.md
    version: null
  - path: docs/product/business-rules.md
    version: null
  - path: docs/product/business-glossary.md
    version: null
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/workflow/active-story.yaml
    version: null
supersedes: null
---

# US-5.3 — Open Decisions

**Story:** `docs/stories/US-5.3-support-tickets-ui.md` — Support Tickets (Frontend)
**Stage:** CLARIFICATION
**Status of this log:** First clarification pass for US-5.3 — no prior `US-5.3-open-decisions.md` existed to reconcile against.

Each entry: the question, why it can't be reliably inferred from `docs/product/*`, the story, or the current backend/frontend source, and the concrete impact of leaving it unresolved.

---

## OD-1 (High) — TK-AC12's `Retry-After` signal is not reachable through the shared `httpClient`'s error path today

**Question:** TK-AC12 requires the UI to show "a message naming when the customer may retry" on a 429 from `POST /support/tickets` or `POST /{id}/replies`. Given the retry-after value only ever exists in the `Retry-After` HTTP response header — never in the JSON body — should `httpClient.ts`'s error path be extended to carry response headers into `ApiError` (and if so, on every error response or just 429), or is some other mechanism intended?

**Why it can't be inferred:** Confirmed directly against both layers:
- Backend: `app/modules/support/exceptions.py` — `TicketCreationRateLimitError` and `TicketReplyRateLimitError` both set `status = 429` and `self.headers = {"Retry-After": str(retry_after_seconds)}`; their `detail` is a fixed string ("Too many tickets created recently. Try again later.") carrying no seconds/timestamp. The `Retry-After` header is the *only* place the retry-after value exists.
- Frontend: `frontend/src/api/httpClient.ts`'s `parseResponse()` (used by `httpGet`/`httpPost`/`httpDelete` — every endpoint this Story calls except the unrelated `httpPatch`) builds the thrown `ApiError` by calling `normalizeApiError({ status: response.status, contentType, body })` — `response.headers` is never passed in. `frontend/src/api/errorNormalization.ts`'s `NormalizeApiErrorInput`/`normalizeApiError` likewise has no `headers` field and reads only `status`/`contentType`/`body`. The one place in this codebase that *does* thread response headers through (`parseResponseWithMeta`, added in US-5.2 for `httpPatch`'s `ETag`) only does so on the `response.ok` success path — its own error branch still calls the header-less `normalizeApiError`.

**Impact if unresolved:** As the client layer stands today, a 429 from either endpoint in this Story surfaces to the UI as an `ApiError` with no way to read `Retry-After` at all. TK-AC12 as literally written cannot be implemented without a change to the shared HTTP client's error-handling path (not something this Story is otherwise scoped to touch, per its own In Scope list). A spec-writer needs this decided now — e.g., extend `ApiError` to optionally carry `retryAfterSeconds` sourced from the header, parsed generically or only for `status === 429` — rather than an implementer discovering the gap mid-build and improvising a shape no other screen or test expects.

---

## OD-2 (Medium) — `category`'s valid value list remains an unresolved product decision (US-4.1 OD-3, still open)

**Question:** Should `SPECIFICATION` proceed on this Story's own default (a free-text field, `maxLength=50`, no enum — Assumption #5), or does this Story need to wait on / re-raise US-4.1's still-open OD-3 (a stakeholder-supplied category value list) before the create-ticket form's `category` control is finalized?

**Why it can't be inferred:** `docs/decisions/US-4.1-open-decisions.md` OD-3 states plainly this "needs a product decision... not an inferred one," and `docs/product/business-rules.md`'s note on `US-4.1` (`docs/catalog/stories.yaml` line 156-157) confirms it "remain[s] open, carried forward" as of the most recent archive. `docs/product/business-glossary.md` and `business-rules.md` are both silent on ticket categories. This Story's own Assumption #5 already picks the free-text default and cites the same open item, but does not commit to whether that default is final or provisional.

**Impact if unresolved:** If free-text ships now and product later supplies an enum, the create-ticket form needs a follow-up change (free-text → dropdown/autocomplete) with no forward-compatible seam built in today. Carrying this forward rather than silently treating Assumption #5 as a final answer keeps the decision visible for `HUMAN_SPEC_APPROVAL`.

---

## OD-3 (Medium) — Reopen's 7-day window is genuinely unknowable client-side; confirm reactive-only handling is acceptable

**Question:** The story's own Open Question #3 asks whether it's acceptable that "Reopen" cannot be pre-disabled for a `resolved` ticket outside its 7-day reopen window, surfacing the resulting `409` reactively instead. Is that acceptable, or should a backend Story be raised to expose the deadline (e.g. a `reopen_eligible_until` field) so the UI can disable the control proactively?

**Why it can't be inferred:** Confirmed in `app/modules/support/service.py::reopen_ticket` (around line 720-735): a `resolved` ticket outside the inclusive 7-day window is rejected with the *same* `InvalidStateTransitionError` (409) a genuinely wrong-status ticket gets — the docstring itself says this is "not resolved here" (implementation-plan Risk 1, US-4.3). No field on `TicketDetailRead`, `TicketRead`, or `TicketStateRead` exposes `resolved_at` plus a derivable deadline in a way the client could safely compute (`TicketDetailRead` does not even carry `resolved_at`).

**Impact if unresolved:** Left undecided, an implementer must guess whether "Reopen" is always offered on every `resolved` ticket (matching TK-AC9's literal table) and relies entirely on the 409 to communicate ineligibility, or whether some client-side heuristic (e.g. comparing `updated_at` against a hard-coded 7 days, which is not verified equivalent to the server's `resolved_at`-based window) should be attempted. The former is what the story's Acceptance Criteria actually describe (TK-AC8's second clause); this entry exists to make the trade-off explicit and prevent an implementer from silently trying to "improve" it with an unverified client-side calculation.

---

## OD-4 (Low) — `first_response_at` display: plain timestamp confirmed accurate, but framing/copy is still undecided

**Question:** The story's own Open Question #4 asks for confirmation that `first_response_at` should render as a plain timestamp with no SLA framing (no "responded within X hours," no target/deadline language). Is that confirmed, and if so, what exact label/copy should the ticket-detail header use for it (e.g. "First response:", "Agent replied:")?

**Why it can't be inferred:** `docs/product/business-rules.md` and `business-glossary.md` do not mention `first_response_at` or any SLA target at all; `docs/product/personas.md`'s Customer/Support Agent goals describe reply/resolution behavior but no SLA commitment. The field exists on `TicketDetailRead` (confirmed, `app/modules/support/schemas.py`) purely as a timestamp with no paired target value anywhere in the schema or database design to frame it against.

**Impact if unresolved:** Low risk technically (the field is optional and a plain-timestamp rendering cannot itself be wrong), but the exact label is still an invented product-copy decision if left to the implementer, and a later product decision to add real SLA framing would require revisiting this same UI element. Carried forward rather than silently authored into the spec.

---

## OD-5 (Low, carried forward from US-5.1, not new to this Story) — No component/design-system decision has ever been formally re-affirmed

**Question:** Should this Story continue the hand-built-components convention already established by US-5.1 and US-5.2 (no headless-UI/component-library dependency in `frontend/package.json`; shared primitives like `components/ErrorState.tsx`, `components/FieldError.tsx` already exist and are reusable), or does introducing several new interactive surfaces (status filter, cursor-paginated list, reply composer, close/reopen confirmation) change the calculus?

**Why it can't be inferred:** US-5.1's OD-9 raised this and was never formally resolved as `RESOLVED` in that story's own open-decisions log; `docs/catalog/stories.yaml`'s US-5.1 note states "Nine Open Decisions (OD-1..OD-9) remain open, carried forward." In practice, `frontend/package.json` shows no Radix/Headless UI/MUI/Chakra dependency after two shipped Stories, and reusable primitives (`ErrorState`, `FieldError`) already exist — a strong de facto precedent, but never an explicit product/architecture decision.

**Impact if unresolved:** Low — precedent is strong enough that a spec-writer can reasonably treat "hand-built, reusing existing shared components" as the answer without further stakeholder input (unlike OD-1 through OD-4 above). Recorded here only so this Story doesn't silently re-decide it differently from its two predecessors; not expected to block `HUMAN_SPEC_APPROVAL`.

---

## OD-6 (Medium) — Editing and resubmitting a composed ticket after a failed create reuses the same `Idempotency-Key` with a changed body, which the backend rejects outright

**Question:** Assumption #4 mints the `Idempotency-Key` once per composed ticket and reuses it "on every retry of that submission," minting a new value only "for a genuinely new ticket." Neither Assumption #4 nor TK-AC4 addresses the case in between: the customer's create submission fails (network error/5xx), they *edit* the subject/body/category before resubmitting rather than retrying verbatim, and the client — per Assumption #4's literal rule — still sends the original key with the now-different body. Should that edited resubmission be treated as "the same submission" (same key, and the resulting `422` mapped to specific, user-actionable copy), or does any edit to the form fields count as starting "a genuinely new ticket" (mint a new key)?

**Why it can't be inferred:** `app/modules/support/exceptions.py`'s `IdempotencyKeyReuseError` (`422`, slug `idempotency-key-reuse`) fires specifically when "the same `Idempotency-Key` was reused with a different request body" (stored `request_hash` mismatch) — confirmed as the service's actual conflict-detection mechanism (FR-4). Its `detail` string ("This idempotency key was already used with a different request.") is generic and not obviously mappable to a helpful recovery action by TK-AC11's generic problem+json rendering alone. Neither the story's Assumptions & Defaults table, TK-AC3, nor TK-AC4 states whether a field edit invalidates the in-flight key.

**Impact if unresolved:** If an implementer follows Assumption #4 literally (key persists for the lifetime of "one composition," and an edit is still the same composition), every edit-then-resubmit after a failed create hard-fails with a 422 the customer cannot self-resolve except by starting an entirely new composition (which the UI gives no explicit affordance for triggering, since TK-AC4 only defines "starting a new ticket composition" abstractly). This is a real, reachable path through the happy-path retry flow the story otherwise treats as its primary resilience mechanism (TK-AC4, TK-AC13), not a corner case.

---

## Summary

| # | Severity | Topic | Source of ambiguity |
|---|---|---|---|
| OD-1 | High | `Retry-After` header unreachable through `httpClient`'s error path | `app/modules/support/exceptions.py` vs. `frontend/src/api/httpClient.ts` + `errorNormalization.ts` vs. TK-AC12 |
| OD-2 | Medium | `category` value list still an open product decision (US-4.1 OD-3) | `docs/decisions/US-4.1-open-decisions.md` OD-3 vs. Story Assumption #5 |
| OD-3 | Medium | Reopen 7-day window unknowable client-side; confirm reactive-only handling | `app/modules/support/service.py::reopen_ticket` vs. Story's own Open Question #3 |
| OD-4 | Low | `first_response_at` display copy/framing | Story's own Open Question #4 |
| OD-5 | Low | Component/design-system choice, carried forward, not newly raised | `docs/decisions/US-5.1-open-decisions.md` OD-9 vs. established de facto precedent |
| OD-6 | Medium | Edited resubmission after a failed create reuses a now-stale `Idempotency-Key`, hitting a 422 not addressed by Assumption #4/TK-AC4 | `app/modules/support/exceptions.py`'s `IdempotencyKeyReuseError` vs. Story Assumption #4, TK-AC4 |

A seventh item — the story's Dependencies & Blockers #1 rationale ("no staff ticket-list endpoint... unbuildable until a backend Story adds one") being stale now that `US-4.4` shipped an agent branch on the same `GET /support/tickets` route — is **not** logged as an Open Decision here because it *is* resolved by a cited source: `docs/catalog/stories.yaml`'s US-5.3 and US-5.5 entries already confirm the customer/agent UI split is deliberate (US-5.5 is the dedicated agent-side Story), independent of whether the endpoint itself was still blocked. See the Clarification Report's "What's Ambiguous or Contradicted" section for the citation and the recommended text correction.

None of the six items above are resolved by this pass — resolution happens at `HUMAN_SPEC_APPROVAL`, not here.
