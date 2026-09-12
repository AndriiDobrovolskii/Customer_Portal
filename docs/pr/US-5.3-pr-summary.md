---
artifact_type: pr_summary
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-12T18:30:00Z"
updated_at: "2026-09-12T18:30:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/verification/US-5.3-implementation-verification.md
    version: 1
  - path: docs/reviews/reconciliation/US-5.3-reconciliation.md
    version: 1
  - path: docs/reviews/security/US-5.3-security-review.md
    version: 1
  - path: docs/reconciliation/US-5.3-traceability.md
    version: 1
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/evidence/US-5.3-implementation-report.md
    version: 2
  - path: docs/evidence/US-5.3-quality-gate-report.md
    version: 2
supersedes: null
---

# Pull Request: Support Tickets — Frontend (US-5.3)

**Overall Verdict (this stage): PASS** — drafted for human submission, not yet pushed or opened.

## Gate confirmation

All four required upstream gates are confirmed Pass, read directly from their own reports (not taken on a verbal say-so):

| Gate | Verdict | Source |
|---|---|---|
| `gate-enforcer` | PASS (2nd dispatch) | `docs/evidence/US-5.3-quality-gate-report.md` v2 (read directly — "Final Verdict: PASS"), corroborated in `docs/workflow/workflow-state.yaml`'s `non_blocking_findings` log ("QUALITY_GATE (gate-enforcer, 2nd dispatch): PASS") — lint/format:check/type-check/test:coverage all green (291/291 tests; coverage 97.47%/95.29%/87.39%/97.47% stmt/branch/func/line vs. an 85% floor), Part B′ runtime-rule checks pass |
| `implementation-verifier` | PASS | `docs/verification/US-5.3-implementation-verification.md` v1 |
| `reconciliation-reviewer` | PASS | `docs/reviews/reconciliation/US-5.3-reconciliation.md` v1 |
| `security-reviewer` | PASS | `docs/reviews/security/US-5.3-security-review.md` v1 |

The story's human gate (`HUMAN_PR_APPROVAL`) was also recorded APPROVED (2026-09-12T18:25:25Z, sbruhov@gmail.com) per `docs/workflow/workflow-state.yaml`.

**Reconciliation-staleness check (this stage's only loop-back condition):** independently
re-verified by filesystem timestamp, not inferred from the file-set match alone — no file
under `frontend/src/` or `frontend/.eslintrc.cjs` carries a modification time newer than
`docs/reviews/reconciliation/US-5.3-reconciliation.md` itself. The working tree has not
moved since `RECONCILIATION` ran; its PASS verdict still describes what would ship.
`loop_back_stage: stale_reconciliation` does not apply.

## Suggested PR Title

`feat: support tickets UI (US-5.3)`

## Summary

Adds the customer-facing support-ticket surface to the Customer Portal frontend: a
status-filterable, cursor-paginated ticket list; ticket creation with a stable,
per-composition `Idempotency-Key`; ticket detail with an independently
cursor-paginated reply thread; posting a public reply; closing and reopening a
ticket; status-driven action affordances (with "Resolve" never offered to a
customer); client-side field validation; problem+json error rendering including a
dedicated 404 state; 429 rate-limit handling built on a new first-class
`ApiError.retryAfterSeconds` field; and the existing 401 silent-refresh
interaction. It also moves the authenticated home route and post-login redirect
from `/` to `/tickets` and adds `/tickets` to the app shell's navigation
(`PlaceholderHomeScreen` is retired).

This is a **frontend-only** change against six already-shipped
`app/modules/support` backend endpoints (EPIC-4, US-4.1–US-4.4) — no backend,
API, or database change of any kind (`API_DESIGN`/`DB_DESIGN` both
`NOT_APPLICABLE`).

- **Story:** `docs/stories/US-5.3-support-tickets-ui.md`
- **Specification:** `docs/specifications/US-5.3-spec.md` (v1, APPROVED) — FR-1
  through FR-15
- **Implementation plan:** `docs/plans/US-5.3-implementation-plan.md` (v2,
  APPROVED) — v2 incorporates the human's binding resolutions for OD-1 through
  OD-6 (429 `Retry-After` handling, free-text `category`, non-proactive reopen
  disable, plain-text `first_response_at`, no new UI library, and
  idempotency-key rotation-on-edit) as firm architecture

**Reviewer note on the spec link above:** `docs/specifications/US-5.3-spec.md`'s
own "Open Questions" section and its FR-12 prose still read OD-1 through OD-6 as
unresolved (FR-12 literally says the `Retry-After` mechanism "is not yet
decided"). That prose is stale — the human supplied binding resolutions for all
six after the spec was written, and `implementation_plan` v2 (linked above)
states and implements them as firm architecture. This PR builds against plan v2's
resolutions, not the spec's now-stale Open Questions text. `docs/workflow/workflow-state.yaml`
records this staleness explicitly; it is out of this stage's ownership to edit
the spec itself.

## What changed

**New:**
- `frontend/src/api/supportApi.ts` — one typed function per ticket operation
- `frontend/src/hooks/{useTickets,useTicketDetail,useCreateTicket,useReplyToTicket,useCloseTicket,useReopenTicket,useRetryAfterCountdown}.ts`
  (+ their tests)
- `frontend/src/screens/{TicketListScreen,NewTicketScreen,TicketDetailScreen}.tsx`
  (+ their tests)

**Modified:**
- `frontend/src/api/httpClient.ts` — additive `idempotencyKey` option on
  `httpPost`; `ApiError` gains a first-class `retryAfterSeconds?: number` field,
  populated only from a `429`'s `Retry-After` header
- `frontend/src/api/types.ts` — additive ticket/reply DTOs
- `frontend/src/components/apiErrorHelpers.ts` — additive `getRetryAfterSeconds`
  getter (keeps `ApiError` out of screen-level imports)
- `frontend/src/layouts/AppShell.tsx` — new `/tickets` nav entry;
  `MfaEnrollmentBanner` render site moves here from the retired home screen so it
  stays visible on every authenticated screen
- `frontend/src/routes/AppRoutes.tsx`, `GuestOnlyRoute.tsx`,
  `screens/LoginScreen.tsx`, `screens/MfaVerifyScreen.tsx` — post-login/guest/MFA
  redirect targets move from `/` to `/tickets`; `/` becomes
  `<Navigate to="/tickets" replace>`
- `frontend/src/test/mswHandlers.ts` — one new MSW handler per ticket endpoint

**Deleted:**
- `frontend/src/screens/PlaceholderHomeScreen.tsx` (+ its test) — superseded by
  `TicketListScreen` as the authenticated home

**Config (human-approved, disclosed below):**
- `frontend/.eslintrc.cjs`

No new dependency was added and no new environment/config setting was introduced
(see `.env.example` confirmation below).

## Test Plan

Built from `docs/reconciliation/US-5.3-traceability.md` v1 and the gate/verification
reports (291/291 tests passing; coverage 97.47% statements / 95.29% branches /
87.39% functions / 97.47% lines, all above the 85% floor).

- [x] TK-AC1 — ticket list renders fields; "Load more" pagination; empty-state CTA
      — `screens/TicketListScreen.test.tsx`, `hooks/useTickets.test.ts`
- [x] TK-AC2 — status filter re-issues the request with a reset cursor —
      `useTickets.test.ts::test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page`
- [x] TK-AC3 — create sends `Idempotency-Key` + `attachment_ids: []`; `201` lands
      on detail — `screens/NewTicketScreen.test.tsx`, `hooks/useCreateTicket.test.ts`
- [x] TK-AC4 — verbatim retry reuses the key; a new composition mints a different
      one (OD-6) — `screens/NewTicketScreen.test.tsx`, `hooks/useCreateTicket.test.ts`
- [x] TK-AC5 — detail renders header + reply thread with an independent cursor —
      `screens/TicketDetailScreen.test.tsx`, `hooks/useTicketDetail.test.ts`
      (verified: `["ticket", id]`/`["ticket-replies", id]` share no key prefix)
- [x] TK-AC6 — reply omits `visibility`, sends `attachment_ids: []`, detail
      genuinely refetches (not just an optimistic append) —
      `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reply_submission_sends_no_visibility_and_attachment_ids_empty_appends_and_clears`
      (read in full; asserts a real second `GET` call)
- [x] TK-AC7 — close from any eligible status, screen reflects `closed` —
      `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_close_ticket_from_%s_calls_close_endpoint_and_reflects_closed`
- [x] TK-AC8 — reopen from `resolved` is never pre-disabled; `409` renders
      `detail` — `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reopen_from_resolved_is_clickable_calls_endpoint_and_reflects_waiting_on_support`
- [x] TK-AC9 — only valid actions offered per status; "Resolve" never offered —
      `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered`
      (parametrized over all five statuses)
- [x] TK-AC10 — empty/over-length fields block submission client-side, no API
      call — `screens/NewTicketScreen.test.tsx`
- [x] TK-AC11 — 4xx problem+json renders `detail`; `422` maps `errors[]`; `404`
      shows "not found" — `screens/{TicketListScreen,NewTicketScreen,TicketDetailScreen}.test.tsx`
- [x] TK-AC12 — `429` shows retry time, disables submit, no auto-retry loop
      (largest single-AC test set — OD-1's full resolution chain) —
      `screens/NewTicketScreen.test.tsx`, `screens/TicketDetailScreen.test.tsx`,
      `api/httpClient.test.ts`, `components/apiErrorHelpers.test.ts`,
      `hooks/useRetryAfterCountdown.test.ts`
- [x] TK-AC13 — network/5xx shows a retry-capable error, never blank/unhandled —
      all three new screens
- [x] TK-AC14 — `401` reuses the existing refresh coordinator; deactivated-account
      `403` renders `detail` — `screens/{TicketListScreen,NewTicketScreen}.test.tsx`
- [x] FR-15 — `/` → `/tickets` redirect; nav link added —
      `routes/AppRoutes.test.tsx` (+ renamed cases in `GuestOnlyRoute.test.tsx`,
      `LoginScreen.test.tsx`, `MfaVerifyScreen.test.tsx`, `layouts/AppShell.test.tsx`)
- [x] Security: HTML-bearing ticket/reply body renders as escaped text, never
      executes (no `dangerouslySetInnerHTML` anywhere in the diff) —
      `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes`
      (asserted via DOM structure, not a string-contains check)
- [x] Route guards — the three new `/tickets*` routes redirect an unauthenticated
      visitor to `/login` — `routes/AppRoutes.test.tsx`
- [x] Full suite / gates — `npm run lint`, `format:check`, `type-check`,
      `test:coverage` all green (291/291 tests; 97.47/95.29/87.39/97.47%
      stmt/branch/func/line vs. 85% floor)

All 14 numbered TK-ACs plus FR-15 have a traceability-matrix row; every row's
referenced test function was independently confirmed to exist and to assert the
AC's actual stated behavior (not name-proximity only) by `reconciliation-reviewer`,
with the highest-judgment rows (TK-AC6/7/8/9) read in full.

## Risks / Rollback

From `implementation_plan` v2's Risks section:

- `httpClient.ts` is shared, load-bearing infrastructure for every already-shipped
  US-5.1/US-5.2 screen; both changes to it (the `idempotencyKey` option and
  `ApiError.retryAfterSeconds`) are additive-only — no existing call site's
  request/error-handling shape changes. Verified: no existing `httpPost` caller
  passes the new option, and `retryAfterSeconds` is `undefined` everywhere except
  a parsed `429`.
- Cursor pagination via `useInfiniteQuery` is a first for this codebase (no prior
  in-repo pagination pattern to diverge from); `useTicketDetail.ts`'s two sibling
  query keys (`["ticket", id]` / `["ticket-replies", id]`) are deliberately
  non-nested so a detail invalidation cannot silently discard already-fetched
  reply pages.
- FR-9's status-driven affordance table is customer-facing security surface:
  `offeredActionsForStatus` has no `resolve` key at all (structural, not a
  runtime check) and fails closed (zero actions) on an unrecognized status.
- Deleting `PlaceholderHomeScreen.tsx` touches an already-shipped US-5.1 file;
  confirmed as its sole caller (`AppRoutes.tsx`) before removal.
- **Rollback:** revert this PR's commit(s). No migration, no backend/DB state,
  and no new dependency is introduced, so rollback is a plain frontend revert
  with no data or schema implications.

## `.env.example` Confirmation

No new setting was introduced by this story (OD-5: no new dependency; confirmed
directly — `git status` shows `.env.example`, `frontend/.env.example`,
`frontend/package.json`, and `frontend/package-lock.json` all unchanged on this
branch). `.env.example` is current; no action needed.

## Commit Hygiene

The working tree's diff (`git status --porcelain -- frontend/`) was checked
file-by-file against `implementation_plan` v2's declared Files To
Create/Modify/Delete list. Every path maps cleanly onto that declared scope,
with three disclosed exceptions:

1. **`frontend/.eslintrc.cjs`** — a human-approved, intentional configuration
   change, not an unexplained drive-by edit. It adds a scoped override for
   `src/screens/TicketDetailScreen.tsx` turning off
   `react-refresh/only-export-components`, mirroring the pre-existing
   `src/store/**/*.tsx` exception. This was required because TK-AC9 mandates a
   second named export (`offeredActionsForStatus`) from that screen, which the
   rule otherwise flags with no code-side fix. Approved 2026-09-12 per
   `docs/workflow/workflow-state.yaml`'s recorded human sign-off; independently
   confirmed `npm run lint --max-warnings=0` is clean (0 errors, 0 warnings)
   with the override in place.
2. **`frontend/src/screens/ProfileScreen.test.tsx`** — a US-5.2 file, not in this
   story's `task_breakdown` v2 file set. Modified during this story's
   `TEST_WRITING` loop-back (attempt 3) to fix a full-suite timing flake in
   `test_profile_screen_422_validation_error_maps_errors_array_onto_matching_fields`
   (a 200-char `user.type()` call replaced with `fireEvent.change`) — the same
   class of fix already applied to this story's own `NewTicketScreen.test.tsx`.
   One line, behavior-preserving: no assertion weakened, no US-5.2 implementation
   file touched, no US-5.2 AC reinterpreted (confirmed by both
   `implementation-verifier` and `reconciliation-reviewer`). Disclosed here per
   `AGENTS.md` §7.8 rather than left as an unexplained edit in this PR's diff.
3. **`frontend/tsconfig.app.tsbuildinfo`** — TypeScript's incremental build
   cache, regenerated as a side effect of running `type-check` during this
   story's work. Not application code and carries no behavioral change; flagged
   for awareness only, not a scope concern. Reviewer may choose to leave it out
   of the final commit if this repo does not track it as project convention
   elsewhere (it is already a tracked file on this branch's base).

No other unrelated file and no other drive-by refactor was found in scope.

## Known Non-Blocking Items (disclosed, not blockers)

- **`TicketDetailScreen.tsx`'s hardcoded `en-US` date format.** The "Created"
  timestamp uses a fixed `Intl.DateTimeFormat('en-US', ...)` rather than
  respecting the signed-in customer's own `locale` setting (`ProfileScreen`
  supports `en-US`/`en-GB`). No FR/AC in `docs/specifications/US-5.3-spec.md`
  requires locale-aware timestamp formatting anywhere in this story's scope, so
  this is **not** a Definition-of-Done violation and not AC drift
  (`implementation-verifier` and `reconciliation-reviewer` both confirmed this).
  It is a real, if minor, UX inconsistency — recommended as a candidate follow-up
  backlog item if app-wide locale-consistent formatting is wanted, not a blocker
  for this PR.
- **`TicketListScreen.tsx`'s invented status-filter labels** (e.g. "Awaiting
  support reply" instead of the raw `TicketStatus` string) — presentation-only,
  with a stated rationale (avoiding a DOM text-search collision with raw
  `ticket.status` text on the same screen); the underlying `value` sent to the
  API/query param stays the raw status. No AC impact.

## Statement

This is **drafted content only**. Pushing this branch or opening the pull
request requires an explicit, separate user instruction to run `git push` /
`gh pr create` — this skill does not execute either action itself.
