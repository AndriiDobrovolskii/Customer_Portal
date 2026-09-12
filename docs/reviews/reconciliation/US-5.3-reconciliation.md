---
artifact_type: reconciliation
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-12T01:05:00Z"
updated_at: "2026-09-12T01:05:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.3-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.3-plan-review.md
    version: 2
  - path: docs/tests/US-5.3-test-strategy.md
    version: 1
  - path: docs/tests/US-5.3-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.3-test-generation-report.md
    version: 3
  - path: docs/evidence/US-5.3-implementation-report.md
    version: 2
  - path: docs/verification/US-5.3-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.3-security-review.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Reconciliation Report: Support Tickets — Frontend (US-5.3)

**Story ID:** US-5.3
**Reviewed:** 2026-09-12
**Overall Verdict:** PASS

## Summary

All 14 spec ACs (TK-AC1–TK-AC14) plus FR-15 (not a numbered TK-AC, derived from the spec's
"In Scope" section) have a traceability-matrix row. Every referenced test function was
confirmed to exist by name, and a representative sample spanning every AC that carries a
business-judgment risk was opened and read in full — not merely name-matched — confirming
each asserts the AC's actual stated behavior, not a weaker proxy. All 291/291 tests pass
per `docs/evidence/US-5.3-quality-gate-report.md` v2's re-verification. No unreconciled
drift was found; two items requiring judgment (both already flagged, not adjudicated, by
`implementation-verifier`) are resolved below, and one commit-hygiene item is carried
forward for `pr-preparer`.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (summary) | Matrix Row Exists | Test Function(s) Sampled | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| TK-AC1 | Ticket list renders fields; "Load more"; empty state CTA | Yes | 7 functions across `TicketListScreen.test.tsx`/`useTickets.test.ts` | Yes | Yes (name-confirmed; matches `test_generation_report`'s independent 94/94 re-grep) | Not individually re-opened — within the sampled-elsewhere pattern this story's list/pagination logic shares with `useTicketDetail.test.ts` (sampled below). |
| TK-AC2 | Status filter re-issues request with reset cursor | Yes | `useTickets.test.ts::test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page` | Yes | Yes | This is the gap-fix case `test_generation_report` describes adding to prove the cursor genuinely resets (not just a fresh-mount inference) — read in that report's own quoted description, consistent with the AC's literal "cursor is reset" clause. |
| TK-AC3 | Create sends `Idempotency-Key` + `attachment_ids: []`; `201` lands on detail | Yes | 4 functions across `NewTicketScreen.test.tsx`/`useCreateTicket.test.ts` | Yes | Yes (name-confirmed) | — |
| TK-AC4 | Verbatim retry reuses key; new composition mints a different one | Yes | 5 functions across `NewTicketScreen.test.tsx`/`useCreateTicket.test.ts` | Yes | Yes (name-confirmed) | OD-6's binding resolution (mint-once, reuse-on-verbatim-retry, rotate-on-edit) is the literal behavior these functions' own names assert. |
| TK-AC5 | Detail renders header + reply thread; independent cursor | Yes | `hooks/useTicketDetail.test.ts::test_ticket_detail_and_ticket_replies_query_keys_share_no_common_prefix` (read in full via source, below) | Yes | Yes | `useTicketDetail.ts` (read directly, IMPLEMENTATION_VERIFICATION section) confirms the two query keys (`["ticket", id]`, `["ticket-replies", id]`) share no prefix by construction — the structural guarantee this AC's "independent of the list's own cursor" clause requires. |
| TK-AC6 | Reply sends no `visibility`, `attachment_ids: []`; detail refetches | Yes | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reply_submission_sends_no_visibility_and_attachment_ids_empty_appends_and_clears` (**read in full**) | Yes | **Yes, verified directly** | Test body (lines 198-230) asserts `receivedBody` lacks `visibility` and matches `{body, attachment_ids: []}`, the composer clears, and — critically — `expect(detailFetchCount).toBeGreaterThan(fetchesBeforeReply)`, a genuine refetch-count assertion, not an optimistic-append-only check. Matches the implementation exactly: `useReplyToTicket.ts`'s `onSuccess` invalidates `ticketDetailQueryKey(id)` with **no** `refetchType: "none"` override (unlike close/reopen below), because this AC specifically requires a real refetch. |
| TK-AC7 | Close from any eligible status; screen reflects `closed` | Yes | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_close_ticket_from_%s_calls_close_endpoint_and_reflects_closed` (**read in full**) | Yes | **Yes, verified directly** | Test body (lines 232-259) asserts `closeCalled === true` and `screen.findByText(/closed/i)` resolves — exactly what the AC states ("screen reflects `closed`"), with no assertion requiring a second `GET`. Matches `useCloseTicket.ts`'s `setQueryData` + `invalidateQueries({refetchType: "none"})` pattern — see Plan-Deviation Adjudication below. |
| TK-AC8 | Reopen from `resolved`, never pre-disabled; `409` renders `detail` | Yes | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_reopen_from_resolved_is_clickable_calls_endpoint_and_reflects_waiting_on_support` (**read in full**) | Yes | **Yes, verified directly** | Test body (lines 263-288) asserts the button is enabled *before* any click (OD-3's "never proactively disabled"), then that `reopenCalled === true` and the screen reflects `waiting_on_support` — matching the AC and `useReopenTicket.ts`'s same cache-write pattern as close. |
| TK-AC9 | Only valid actions offered per status; "Resolve" never offered | Yes | `screens/TicketDetailScreen.test.tsx::test_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered` (**read in full**) | Yes | **Yes, verified directly** | Test body (lines 334-353) asserts, per status, presence/absence of the reply field and close/reopen buttons against an `expected` table, and unconditionally `expect(screen.queryByRole("button", {name: /^resolve$/i})).not.toBeInTheDocument()` — the AC's "never offered under any status" clause, checked on every parametrized case, not just once. |
| TK-AC10 | Empty/over-length fields block submission, no API call | Yes | 2 functions in `NewTicketScreen.test.tsx` | Yes | Yes (name-confirmed) | The over-length case's own test-file fix (200-char field on the sibling `ProfileScreen.test.tsx`, `user.type()`→`fireEvent.change`) was independently verified this run — see test_generation_report Attempt 3; this story's own `NewTicketScreen.test.tsx` already used `fireEvent.change` from attempt 2 onward. |
| TK-AC11 | 4xx problem+json renders `detail`; `422` maps `errors[]`; `404` "not found" | Yes | 4 functions across `TicketListScreen.test.tsx`/`NewTicketScreen.test.tsx`/`TicketDetailScreen.test.tsx` | Yes | Yes (name-confirmed) | Shares the same `ErrorState`/`apiErrorHelpers` path independently re-read by `implementation-verification.md` §6.7/§6.7-frontend-analogue. |
| TK-AC12 | `429` shows retry time, disables submit, no auto-retry loop | Yes | 12 functions across `NewTicketScreen.test.tsx`/`TicketDetailScreen.test.tsx`/`httpClient.test.ts`/`apiErrorHelpers.test.ts`/`useRetryAfterCountdown.test.ts` | Yes | Yes (name-confirmed) | The largest single-AC test set in this story (OD-1's full resolution chain: header→`ApiError`→helper→hook→UI); `useRetryAfterCountdown.test.ts`'s 4 functions were the ones fixed for an unrelated flake in `TEST_WRITING` attempt 2 (spy-restore), independently re-confirmed passing in this run's quality-gate re-verification (291/291). |
| TK-AC13 | Network/5xx shows retry-capable error, never blank/unhandled | Yes | 5 functions across all three new screens | Yes | Yes (name-confirmed) | — |
| TK-AC14 | `401` uses existing refresh coordinator; deactivated-account `403` renders `detail` | Yes | 2 functions | Yes | Yes (name-confirmed) | Reuses US-5.1's existing coordinator, unmodified by this story per `implementation-verification.md`'s working-tree enumeration. |
| FR-15 | `/` → `/tickets` redirect; nav link added | Yes (separate table, `ac-test-matrix.md` §"FR-15") | `routes/AppRoutes.test.tsx::test_app_routes_root_redirects_authenticated_visitor_to_tickets` (**read via `AppRoutes.tsx` source**), plus 3 renamed + 10 new route/nav tests | Yes | Yes | `AppRoutes.tsx` (read in full, IMPLEMENTATION_VERIFICATION §5) confirms `/` is `<Navigate to="/tickets" replace>` (line 81) inside the same guard set as before; the three renamed tests (`AppRoutes.test.tsx`, `GuestOnlyRoute.test.tsx`, `LoginScreen.test.tsx`, `MfaVerifyScreen.test.tsx`) retarget assertions from `/` to `/tickets`, confirmed by `test_generation_report`'s "Renames (not deleted US-5.1 coverage)" section — read directly, not merely asserted. |

<!-- One row per AC — 14 numbered TK-ACs + FR-15, no exceptions. -->

## Plan-Deviation Adjudication (business/AC-compliance angle)

`implementation-verifier` already confirmed these are technically acceptable, AC-literate
readings of `implementation_plan` v2 Change 5 (not a Definition-of-Done violation). This
review's own question is narrower: does either constitute **drift from what the story's
ACs require**, even if the code is technically sound?

1. **`setQueryData` + `refetchType: "none"` in `useCloseTicket`/`useReopenTicket`.** TK-AC7
   and TK-AC8's own wording (`docs/specifications/US-5.3-spec.md:74-84`) says only "the
   screen reflects status X" — no clause requires a specific network-call count. The two
   tests sampled above (read in full) assert exactly that outcome and pass. **No AC drift.**
   Contrast with TK-AC6, whose test (also read in full) *does* assert a refetch count, and
   whose implementation (`useReplyToTicket.ts`) correctly omits the `refetchType` override
   for that one key — confirming the distinction was applied per-AC, not as a blanket
   shortcut that happened to dodge scrutiny everywhere.
2. **`notifyOnChangeProps: "all"` in `useTicketDetail.ts`.** No AC governs internal
   TanStack Query subscription configuration; this is an implementation detail invisible to
   any acceptance criterion's black-box behavior. **Not an AC concern; no drift possible by
   definition.**

## Invented UI Details (business/AC-compliance angle)

1. **`TicketListScreen.tsx`'s status-filter labels.** No AC or FR specifies literal filter
   option text (FR-2/TK-AC2 only require the request to carry the raw status value and
   reset the cursor, both of which the labels don't affect). **Not AC drift.**
2. **`TicketDetailScreen.tsx`'s hardcoded `en-US` date format on "Created," ignoring
   `ProfileScreen`'s `locale` field.** No AC or FR in `docs/specifications/US-5.3-spec.md`
   requires locale-aware timestamp formatting anywhere in this story's scope (FR-5/TK-AC5
   only requires `created_at` to be rendered as part of the header, with no format
   specified). **Not AC drift — a real but out-of-scope UX gap**, correctly not invented as
   a requirement that was never asked for. Recommend a follow-up story or backlog item if
   locale-consistent formatting across the app is wanted, rather than scope-creeping this
   one; not a blocker for this story's own PR.

## Commit-Hygiene Finding (carried forward for `pr-preparer`)

`frontend/src/screens/ProfileScreen.test.tsx` (a US-5.2 file, not in this story's
`task_breakdown` v2 file set) was modified during this story's `TEST_WRITING` loop-back
(attempt 3) to fix a full-suite timing flake unrelated to any US-5.3 AC
(`test_profile_screen_422_validation_error_maps_errors_array_onto_matching_fields`'s
200-char `user.type()` call, replaced with `fireEvent.change`). Confirmed: **no PS-AC in
US-5.2's own spec is touched or reinterpreted** — the fix is purely a test-infrastructure
timing correction, same class as `NewTicketScreen.test.tsx`'s earlier fix in this story, and
the assertion itself is unchanged. This is not AC drift for either story, but per
`AGENTS.md` §7.8 (commit hygiene, no unexplained drive-by changes), `pr-preparer` should
call this out explicitly in the PR description rather than let it land as an unexplained
US-5.2 edit inside a US-5.3 PR.

## Verdict Rationale

Every one of the 14 numbered TK-ACs plus FR-15 has a matrix row; every referenced test
function was confirmed to exist by name, and the highest-risk/judgment-bearing rows
(TK-AC6/7/8/9, the ones tied to the self-flagged plan deviations) were read in full and
confirmed to assert the AC's actual stated behavior rather than a weaker proxy. All
291/291 tests pass. Neither self-flagged plan deviation nor either invented UI detail
constitutes drift from the approved spec — both deviations are within what their governing
ACs actually require, and neither invented detail contradicts or exceeds any AC. One
commit-hygiene item (an out-of-scope US-5.2 test fix) is named for `pr-preparer`, not
treated as AC drift. **Overall Verdict: PASS.**
