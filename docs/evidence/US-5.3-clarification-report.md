---
artifact_type: clarification_report
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

# US-5.3 — Clarification Report

**Story:** `docs/stories/US-5.3-support-tickets-ui.md` — Support Tickets (Frontend)
**Stage:** CLARIFICATION
**Active-story check:** Confirmed. `docs/workflow/active-story.yaml` names `US-5.3` / `docs/stories/US-5.3-support-tickets-ui.md` as the active Story (`status: IN_PROGRESS`), matching the requested target. `docs/workflow/workflow-state.yaml` independently confirms `story: US-5.3` at `current_stage: CLARIFICATION`/`status: IN_PROGRESS` — the two agree. No mismatch to report.
**Prior Open Decisions log:** None existed for US-5.3 before this run.
**Precondition — `TODO` in the story's front matter:** the harness precondition forbids an unresolved `TODO`/`TBD`/`FIXME` in an `APPROVED` input this stage depends on. The story's front matter carries `issue_number: TODO`. This does not trigger the precondition: per `docs/workflow/artifact-schema.md`'s Story artifact exception, the `story` artifact carries no lifecycle `status` field at all (lifecycle lives in `docs/catalog/stories.yaml`, whose US-5.3 entry is `IN_PROGRESS`, not `APPROVED`) — the `story` input is exempt from the produced-artifact status gate the precondition targets. The `TODO` value itself is also independently resolved: `docs/workflow/active-story.yaml` already records `issue_number: 26`, consistent with the `issue_url` already present in the story's own front matter. This is flagged below as a stale-text finding to correct, not a blocking precondition failure.

## Scope, Actor, and Business Value

**Actor:** the Customer persona (`docs/product/personas.md`), whose stated goal "Raise a support ticket and follow the reply thread to resolution (`US-4.1`, `US-4.2`, `US-4.3`)" and stated frustration "Support tickets that read as a black hole, with no visible status or reply" this Story exists to satisfy from a real browser, not raw API calls.

**Trigger/business value:** stated directly in the User Story — EPIC-4 (US-4.1 create, US-4.2 reply, US-4.3 resolve/close/reopen) is fully delivered and `ARCHIVED` on the backend, but has no customer-facing UI yet. This Story closes that gap, matching the product vision's "user self-service" and "communicate with support" goals.

**In scope:** ticket list with status filter and cursor pagination, create-ticket form, ticket detail + reply thread, posting a public reply, close/reopen, status-driven affordances, 429/4xx/5xx/401 handling, and two changes to already-shipped US-5.1 code (post-login redirect target, nav entry). **Out of scope, and correctly so:** agent queue/internal notes/resolve (staff-only), attachment upload/preview (no backend endpoint), and account/profile/admin screens (separate Stories). The story is explicit and largely unambiguous about this boundary.

**Depends on US-5.1** (auth store, API client, route guards, problem+json rendering): `ARCHIVED`/shipped — a real, satisfied dependency. Its single-flight 401→refresh→retry coordinator (`frontend/src/api/refreshCoordinator.ts`) and dev-proxy same-origin cookie handling (`frontend/vite.config.ts`) are both implemented and directly support TK-AC14, despite `docs/catalog/stories.yaml`'s US-5.1 note describing nine Open Decisions as "remain[ing] open, carried forward" — in practice OD-1 (CORS) and OD-2 (single-flight refresh) were both resolved in the actual shipped code even though not formally closed in that log. Verified directly against source rather than assumed.

## What's Clear (verified directly against source, not just the story's own claims)

Cross-checked the story's API Contract table, Client State Notes, and BR-015 through BR-020 (`docs/product/business-rules.md`) against the live `app/modules/support/{schemas,router,service,exceptions}.py`:

- `CreateTicketRequest` (`subject≤150`, `body≤5000`, `category≤50`, `attachment_ids` defaulting to `[]`), the required `Idempotency-Key` header (`Header(alias=...)`, no default → 422 if missing), and `attachment_ids` being write-only with no read-back on `TicketRead`/`ReplyRead` all match the story's Assumptions #3–#4 exactly.
- `category` is confirmed a bare `str(max_length=50)` with no enum — Assumption #5's free-text default is accurate to the current schema (see OD-2 for whether it's *final*).
- `TicketListResponse`/`ReplyThreadPage` both confirm `items` + `next_cursor` with no total count — Assumption #6 is accurate.
- `TicketRead.status`/`TicketDetailRead.status` are confirmed plain `str`, not an enum — the Client State Notes' "render unrecognized value verbatim" guidance is well-founded.
- TK-AC9's five-status affordance table matches BR-018/BR-019 and the service's `_CLOSE_ELIGIBLE_STATUSES`/`_REOPEN_ELIGIBLE_STATUSES` exactly, including reply being accepted on `resolved` (no side effect) and rejected on `closed`.
- TK-AC11's "404, not 403, for a ticket the caller does not own" is confirmed via `TicketNotFoundError`'s docstring and BR-019.
- `visibility` defaulting to `public` when omitted (TK-AC6) matches `CreateReplyRequest`'s schema (`Literal[...] | None = None`) and BR-018 exactly.
- 429 handling exists on both `create_ticket` and `create_reply` as distinct Valkey-backed counters (`TicketCreationRateLimitError`/`TicketReplyRateLimitError`), each carrying `Retry-After` — but see OD-1 below for a material client-side gap this surfaced.
- The reopen 7-day window's "same 409 as a genuine invalid transition, not distinguishable client-side" (Open Question #3) is confirmed directly in `TicketService.reopen_ticket`.
- No headless-UI/component-library dependency exists in `frontend/package.json` after two shipped frontend Stories; hand-built shared components (`ErrorState`, `FieldError`) already exist and are reusable — a strong, if never formally ratified, precedent (see OD-5).

## What's Ambiguous or Contradicted (logged as Open Decisions)

Six items are recorded in `docs/decisions/US-5.3-open-decisions.md`:

1. **OD-1 (High, new, load-bearing):** TK-AC12 requires reading the `Retry-After` response header on a 429, but `frontend/src/api/httpClient.ts`'s error path (`parseResponse` → `normalizeApiError`) never receives `response.headers` at all — only `status`/`contentType`/`body`. The 429 body carries no retry-after information (a fixed string only); the header is the sole carrier. As the shared client stands today, TK-AC12 cannot be implemented without a change to that error path.
2. **OD-2 (Medium, the story's own Open Question #2, formalized):** `category`'s free-text default rests on US-4.1's still-open OD-3 (`docs/decisions/US-4.1-open-decisions.md`, explicitly flagged there as needing product/stakeholder input, not an inferable answer) — confirmed still open in the most recent archive note.
3. **OD-3 (Medium, the story's own Open Question #3, formalized):** the reopen window's un-exposed deadline is confirmed via source; this entry makes explicit that TK-AC8/TK-AC9 already describe the only viable behavior (offer Reopen on every `resolved` ticket, rely on the 409) so an implementer doesn't try to "improve" it with an unverified client-side heuristic.
4. **OD-4 (Low, the story's own Open Question #4, formalized):** `first_response_at` display copy/framing is unresolved product copy, low risk.
5. **OD-5 (Low, carried forward from US-5.1's OD-9, not new):** the component/design-system choice was never formally ratified, though precedent strongly favors "hand-built, reuse existing shared components."
6. **OD-6 (Medium, new):** editing the composed ticket's fields after a failed create and resubmitting reuses the same `Idempotency-Key` (per Assumption #4's literal rule) against a now-different body, which `IdempotencyKeyReuseError` (422) rejects outright — neither Assumption #4 nor TK-AC4 says whether an edit should instead mint a new key.

**One additional finding, resolved by a cited source rather than logged as an Open Decision:** the story's Dependencies & Blockers #1 (and the closely related Assumption #2 rationale) states `GET /support/tickets` "explicitly rejects `tickets:read`/`tickets:write` holders (403)" via `reject_agent_queue_access`, making an agent queue "unbuildable until a backend Story adds one." This is now stale — `US-4.4` (Agent Ticket Queue & Assignment) merged and archived on 2026-09-08 (`docs/catalog/stories.yaml`, PR 32), *before* this Story's `CLARIFICATION` pass, and the current `app/modules/support/router.py::list_own_tickets` confirms the staff-rejection dependency was retired: the same route now branches on `tickets:read` to return an agent queue (`AgentTicketListResponse`) instead of a 403. The customer-only scope this Story chooses is still correct — `docs/catalog/stories.yaml`'s US-5.3 and US-5.5 entries both independently confirm the customer/agent UI split is deliberate, with US-5.5 as the dedicated (and now technically unblocked) agent-side Story — so this does not change this Story's scope or block `SPECIFICATION`. It only means the story's own stated *reason* for excluding the agent queue is factually outdated and should be corrected (cite the deliberate US-5.3/US-5.5 split instead of a since-resolved technical blocker) before or during `SPECIFICATION`, so a spec-writer doesn't carry the false blocker forward. The story's front matter (`issue_number: TODO`) is similarly stale — `docs/workflow/active-story.yaml` already records `issue_number: 26`, matching the `issue_url` already present in the story — Open Question #1 is effectively answered and should be corrected in the story's front matter, not treated as still open.

## Dependencies

- **US-5.1** (auth store, API client, route guards, problem+json rendering): `ARCHIVED`/shipped, verified working for this Story's needs (single-flight refresh, dev-proxy same-origin cookies) despite its open-decisions log not being formally closed.
- **US-4.1/US-4.2/US-4.3** (create/reply/resolve-close-reopen): all `ARCHIVED`/shipped; this Story's API Contract table was checked line-by-line against the live schemas/router/service and found accurate except where OD-1 through OD-3 above note gaps.
- **US-4.4** (Agent Ticket Queue & Assignment): `ARCHIVED`/shipped, more recently than this Story's own `last_synced_at`. Its retirement of `reject_agent_queue_access` is the source of the stale-rationale finding above; it does not block or expand this Story's own scope.
- **US-5.5** (Agent Console UI): correctly identified by the catalog as the Story that will consume the agent branch this Story deliberately excludes; no circular dependency.

## Readiness Verdict

**PASS — Ready for Specification.** The story's scope, actor, and business value are understood and restated above. Every ambiguity found — whether newly surfaced by direct source inspection or carried forward from the story's own four Open Questions — is either resolved by a cited source (the stale-blocker finding, the front-matter staleness, and OD-5's precedent) or logged as an Open Decision in `docs/decisions/US-5.3-open-decisions.md`; none were silently dropped or silently answered.

Per `docs/workflow/artifact-lifecycle.md`, Open Decisions may remain `OPEN` at this stage — they are resolved at `HUMAN_SPEC_APPROVAL`, not here. Two items are flagged as non-blocking findings in this stage's Result Envelope, in addition to being logged, so they travel with the transition rather than depending on a spec-writer opening this report: **(1)** OD-1 — TK-AC12 is literally unimplementable against the current shared HTTP client without a scoped client-layer change, not merely an unresolved judgment call; **(2)** the stale Dependencies & Blockers #1 / Assumption #2 / API Contract table rationale — `US-4.4` already retired the `reject_agent_queue_access` 403 this Story's own text cites as the reason the agent queue is out of scope; the scope decision itself is unaffected (confirmed by `docs/catalog/stories.yaml`'s deliberate US-5.3/US-5.5 split), but the story's stated justification should be corrected before or during `SPECIFICATION`.
