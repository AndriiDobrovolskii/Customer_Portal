---
artifact_type: reconciliation
story: US-5.5
version: 2
status: APPROVED
created_at: "2026-09-14T13:30:00Z"
updated_at: "2026-09-14T16:45:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.5-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.5-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.5-plan-review.md
    version: 2
  - path: docs/tests/US-5.5-test-strategy.md
    version: 1
  - path: docs/tests/US-5.5-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.5-test-generation-report.md
    version: 1
  - path: docs/evidence/US-5.5-implementation-report.md
    version: 3
  - path: docs/verification/US-5.5-implementation-verification.md
    version: 2
  - path: docs/reviews/security/US-5.5-security-review.md
    version: 2
  - path: docs/reviews/designs/US-5.5-design-review.md
    version: 2
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/reviews/reconciliation/US-5.5-reconciliation.md (v1)
---

# Reconciliation Review: Agent Console (Frontend) — US-5.5

**Story ID:** US-5.5
**Reviewed:** 2026-09-14 (re-run, attempt 2)
**Overall Verdict:** PASS

## Preconditions

`implementation-verifier` (`docs/verification/US-5.5-implementation-verification.md` **v2**) and
`security-reviewer` (`docs/reviews/security/US-5.5-security-review.md` **v2**) both recorded **PASS** against
the current working tree, both explicitly framed as re-runs (not diff checks) against `quality_gate_report` v3.
Every one of the fifteen consumed artifacts' front-matter `version`/`status` was read directly off disk this
session (not taken from the task brief's resolved-path list) and matches the version recorded in this
report's own `inputs:` above — `specification` v2/APPROVED, `specification_review` v2/APPROVED,
`impact_analysis` v2/DRAFT, `implementation_plan` v2/DRAFT, `task_breakdown` v2/DRAFT, `plan_review`
v2/DRAFT, `test_strategy` v1/DRAFT, `ac_test_matrix` v1/DRAFT, `test_generation_report` v1/DRAFT,
`implementation_report` v3/DRAFT, `implementation_verification` v2/DRAFT, `security_review` v2/DRAFT,
`design_review` v2/APPROVED, `open_decisions` v2/DRAFT — none is `SUPERSEDED` or `ARCHIVED`; the non-`APPROVED`
statuses on `DRAFT` artifacts are expected per `artifact-lifecycle.md` §1 until a human gate bumps them.
`docs/decisions/US-5.5-open-decisions.md` v2 was read in full this session and confirms OD-1 through OD-5
each individually marked `RESOLVED` in their own section headers. `api_design`/`database_design`/
`entity_model` remain `NOT_APPLICABLE` per the story's own Assumption #7 and `design_review` v2; there is no
backend/API/DB surface in this diff to reconcile. `docs/workflow/stage-map.yaml`'s own `RECONCILIATION` entry
was read this session and confirms `next: HUMAN_PR_APPROVAL`, matching this report's Result Envelope.

## Method

Per this skill's own required reading order: `docs/specifications/US-5.5-spec.md` v2 (the nine ACs,
AG-AC1–AG-AC9, and FR-11), `docs/tests/US-5.5-ac-test-matrix.md` v1 (unchanged since attempt 1 — still
prescriptive, not as-built), then every test file it names — opened and read in full again this session, not
taken on attempt 1's word or `implementation_verification`/`security_review`'s summaries — then
`docs/plans/US-5.5-implementation-plan.md` v2. Re-opened in full this session: `frontend/src/screens/
AgentTicketQueueScreen.test.tsx` (612+ lines, 24 `it`/`it.each` cases), `AgentTicketDetailScreen.test.tsx`
(860+ lines, 33 `it`/`it.each` cases), both production screens (`AgentTicketQueueScreen.tsx`,
`AgentTicketDetailScreen.tsx`), `frontend/src/screens/agentTicketHelpers.ts`, `frontend/src/components/
apiErrorHelpers.ts`, `frontend/src/components/FieldError.tsx`. Confirmed against the actual current-tree
line numbers (which shifted from attempt 1's citations because of the new tests inserted), not against v1's
or the prior traceability table's line numbers.

**Scope of this re-run.** Attempt 1 found one blocking gap (AG-AC7/FR-8's 422 `errors[]`-to-form-field
mapping, `implementation_drift` → `IMPLEMENTATION`) and four non-blocking test-coverage gaps (AG-AC1
ordering/no-count, AG-AC2 row-reflects-new-assignee, AG-AC4 no-status-change converse, AG-AC5 5000-char
bound). `frontend-builder` closed all five in one pass (`docs/evidence/US-5.5-implementation-report.md` v3,
"attempt 3"); `gate-enforcer`, `implementation-verifier`, and `security-reviewer` have each re-passed since.
This re-run independently re-verifies every one of the five closed items against the current working tree —
not against the prior attempt's or any other stage's claim that they are closed — and separately resolves
the specific AC-compliance question `implementation_verification` v2 flagged for this stage's attention (see
"AG-AC7 Special Determination" below).

## AG-AC7 Special Determination — does suppressing the generic `detail` paragraph when field errors render still satisfy AG-AC7?

`implementation_verification` v2's Non-blocking finding 3 flags that wiring `getFieldErrors()`/`FieldError`
into both agent screens also gated the pre-existing generic top-level error paragraph on the corresponding
`fieldErrors` object being absent (`AgentTicketQueueScreen.tsx:115` `!assignFieldErrors`, `:216`
`!fieldErrors`; `AgentTicketDetailScreen.tsx:261` `!assignFieldErrors`, `:340` `!replyFieldErrors`, `:368`
`!resolveFieldErrors` — all re-confirmed present at these exact lines this session). Consequently a 422
carrying a `fieldErrors` entry renders **only** the field-scoped message, not both it and the generic
`detail` string. Independently re-read AG-AC7's verbatim spec text (`docs/specifications/US-5.5-spec.md`
v2, FR-8/Traceability Matrix row AG-AC7):

> "Given any request in this Story returns a 4xx `application/problem+json` body Then the UI renders its
> detail (**or a mapped, user-friendly message keyed by `type`**) — with no raw JSON or stack trace And a
> `422` validation-failure response's `errors` array is mapped onto the matching form fields."

This is two clauses joined by "And," not one compound rendering requirement, and each has its own,
independent test coverage — the question is not whether either clause is untested, but whether it is
acceptable for them not to fire on the *same* response:

1. **Clause 1 ("renders its detail... with no raw JSON") is proven on its own, by tests where
   `fieldErrors` is undefined and only `detail` can possibly render.**
   `test_agent_ticket_queue_screen_assign_409_closed_ticket_renders_problem_json_detail`
   (`AgentTicketQueueScreen.test.tsx:328-355`, a 409 with no `errors[]` array at all) and
   `test_agent_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json`
   (`AgentTicketDetailScreen.test.tsx:745-767`, a 403 with no `errors[]` array, which additionally asserts
   `screen.queryByText(/"type":|"title":/)` is absent) both exercise the plain `detail`-rendering path
   directly, independent of the 422/field-mapping path entirely. Clause 1 does not depend on, and is not
   weakened by, anything the field-mapping wiring does.
2. **Clause 2 ("a `422`... maps its `errors` array onto the matching form fields") is proven by the two new
   mapping tests** (`AgentTicketQueueScreen.test.tsx:387-424`,
   `AgentTicketDetailScreen.test.tsx:580-615`), each posting a 422 whose `errors[]` entry carries a field
   message deliberately distinct from `detail`, and asserting the field-scoped `<p data-field="...">`
   renders it.

**Nothing in AG-AC7's text requires both clauses to render simultaneously on the same response.** The spec
says "renders its detail (or a mapped, user-friendly message keyed by `type`)" for the general 4xx case, and
separately states the 422 `errors[]`-mapping requirement — it does not say "and also keeps rendering
`detail` underneath the field mapping." Reading in a joint-rendering requirement neither clause's own text
states would be a stricter rule than the spec actually asks for.

**Adopting the house convention is the opposite of drift.** The identical
`apiError && !errorKind && !fieldErrors && <p role="alert">` suppression guard already exists, byte-for-byte
the same shape, on seven pre-existing screens — independently re-confirmed this session, not taken on the
security review's or implementation report's word:
`grep -n "fieldErrors &&\|!fieldErrors\|FieldErrors &&" frontend/src/screens/*.tsx` matches
`AdminUserCreateScreen.tsx:130`, `AdminUserDetailScreen.tsx:279,379`, `DeactivateAccountScreen.tsx:80`,
`NewTicketScreen.tsx:95`, `ProfileScreen.tsx:204`, `SecurityScreen.tsx:151,190,222`,
`RegisterScreen.tsx:102`, in addition to both new US-5.5 screens. Reconciliation's own remit is to flag
*drift* introduced during coding — conforming to the established, project-wide pattern for this exact
clause pair is the non-drifting choice; forcing the two new screens to diverge from it (or refactoring all
nine to render both simultaneously) would itself be the kind of opportunistic cross-story change
`AGENTS.md` §7.8 and this plan's own Architectural Change 6 rationale already reject. Both new mapping
tests additionally assert this *is* the deliberate, intended behavior, not an accidental side effect: each
explicitly asserts `screen.queryByText("Validation failed.")` (the `detail` string) is **absent** once the
field-scoped message renders, using deliberately distinct `detail`/field-message strings specifically so
the assertion cannot pass by string coincidence.

**Test-naming observation (non-blocking, noted for completeness).**
`test_agent_ticket_queue_screen_assign_422_assignee_not_an_agent_renders_problem_json_detail`
(`AgentTicketQueueScreen.test.tsx:357-385`) sets `detail` and `errors[0].message` to the identical string
("The target user does not hold tickets:write."). Under the current code this test's `findByText` match is
satisfied by the field-scoped `<FieldError>` render, not by the generic `detail` paragraph the test's name
claims to prove — the two happen to coincide, so the assertion still passes, but it does not independently
exercise clause 1 the way its name implies. This is redundant with, not a gap alongside,
`AgentTicketQueueScreen.test.tsx:328`'s 409 case and `AgentTicketDetailScreen.test.tsx:745`'s 403 case,
which do genuinely exercise clause 1 with no `errors[]` present at all — so clause 1 remains fully proven
overall. Recorded as a test-naming precision note, not a coverage gap.

**Determination: AG-AC7 is fully satisfied.** Both clauses have independent, genuine test coverage; nothing
in the spec's text requires them to co-render on one response; and the suppression pattern is the
established, non-drifting convention this codebase already applies everywhere this clause pair appears.
This is not a gap and does not affect the verdict below.

## Findings

### AG-AC7/FR-8 blocking gap from attempt 1 — closed, re-verified

`AgentTicketQueueScreen.tsx` and `AgentTicketDetailScreen.tsx` now both import and call `getFieldErrors`
(`components/apiErrorHelpers.ts`, unmodified) and render its result through `FieldError`
(`components/FieldError.tsx`, unmodified) — re-confirmed by direct read this session at
`AgentTicketQueueScreen.tsx:24,49,149,210,114`, `AgentTicketDetailScreen.tsx:38,153,157,162,259,307,358`.
Two new tests assert the exact clause: `test_agent_ticket_queue_screen_assign_422_maps_the_errors_array_
onto_the_assignee_id_field` (`AgentTicketQueueScreen.test.tsx:387`) and `test_agent_ticket_detail_screen_
422_validation_failed_maps_the_errors_array_onto_the_matching_form_fields`
(`AgentTicketDetailScreen.test.tsx:580`) — both opened and read in full this session, both post a 422 whose
`errors[]` entry carries a field message distinct from `detail`, and both assert the field-scoped `<p
data-field="...">` renders the field message specifically (`toHaveAttribute("data-field", "assignee_id" /
"body")`). No parallel/reinvented field-error mechanism exists — `getFieldErrors`/`FieldError` are the
same, unmodified functions seven other screens already use. Gap closed.

### AG-AC1 non-blocking gap — closed, re-verified

`test_agent_ticket_queue_screen_renders_tickets_in_the_servers_returned_order_and_shows_no_total_count_or_
page_number` (`AgentTicketQueueScreen.test.tsx:463-493`, read in full this session) returns three tickets
from the mock in ascending-`updated_at` order, asserts `screen.getAllByRole("button", {name:
/^TCK-\d{4}$/})` renders in that exact order (`["TCK-0001","TCK-0002","TCK-0003"]`), and separately asserts
`screen.queryByText(/total|page\s*\d|\d+\s*of\s*\d+/i)` is absent. Both of AG-AC1's previously-unasserted
clauses ("oldest-updated first," "no total count or page number is displayed") are now directly asserted.
Gap closed.

### AG-AC2 non-blocking gap — closed, re-verified

`test_agent_ticket_queue_screen_assign_to_me_updates_the_row_to_reflect_the_new_assignee_after_success`
(`AgentTicketQueueScreen.test.tsx:426-461`, read in full this session) asserts `"Unassigned"` renders before
the assign click, then `"agent-me"` renders and `"Unassigned"` no longer does after a successful assign —
the DOM value change, not merely the outgoing request. Gap closed.

### AG-AC4 non-blocking gap — closed, re-verified

The existing internal-note test (`AgentTicketDetailScreen.test.tsx:299-336`, read in full this session) now
explicitly asserts `screen.getByText("open")` still holds after an internal-note submission — the AC's
converse case ("with no status change expected") is directly asserted, not merely left unasserted-but-true.
Gap closed.

### AG-AC5 non-blocking gap — closed, re-verified

`test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_a_note_over_5000_characters`
(`AgentTicketDetailScreen.test.tsx:552-578`, read in full this session) submits a 5001-character note via
`fireEvent.change`, asserts the `maxLength: 5000` client-side message renders, and asserts the resolve
endpoint is never called (`resolveCalled` stays `false`). The 5000-character upper bound is now directly
tested, alongside the already-covered empty/whitespace-only lower-bound cases. Gap closed.

## Full AC re-verification (not limited to the five closed items)

Re-checked this session, not carried forward from attempt 1's table on trust:

- **AG-AC3** — `agentTicketHelpers.ts::describeAssignee` (re-read: undefined→`"—"`/`aria-label="Assignee
  unknown"`; null→`"Unassigned"`; string→first-8-hex-chars) matches Resolution OD-1/OD-3 and Architectural
  Change 8 exactly; its three unit cases (`AgentTicketDetailScreen.test.tsx:106-116`) and the screen-level
  handoff/direct-URL/internal-style tests (`:153-216`) were read in full and assert the stated behavior.
  Full.
- **AG-AC6** — `agentTicketHelpers.ts::offeredAgentActionsForStatus` re-read and compared field-by-field
  against FR-6's table: matches exactly (`open`/`waiting_on_support`/`waiting_on_customer` → reply, assign,
  resolve, close; `resolved` → reply, assign, close, reopen; `closed`/unrecognized → none, fail-closed). The
  `it.each` unit table (`:81-92`) and the screen-level `it.each` wiring test (`:645-672`) both assert this
  exactly, and the `tickets:write`-absent disabled-control test (`:674-689`) confirms the read-only-view
  clause on both screens. Full.
- **AG-AC7** — see the Special Determination above. Full.
- **AG-AC8** — `test_agent_ticket_detail_screen_reply_429_shows_retry_time_disables_submit_and_fires_
  exactly_once` (`:769-795`, read in full) asserts the retry-time message, the disabled submit button, and
  `replyRequestCount === 1` after the click — no auto-retry loop. Full.
- **AG-AC9** — all four network/5xx tests (`AgentTicketQueueScreen.test.tsx:609-631`,
  `AgentTicketDetailScreen.test.tsx:797-817`) read in full; each asserts a retry-capable `ErrorState`
  renders, never a blank screen or unhandled exception. Full.

## Spec drift check

Compared the current implementation against `docs/specifications/US-5.5-spec.md` v2's FR-1 through FR-11
directly: no field was renamed, no validation rule loosened or tightened beyond what FR-5's 1–5000 bound and
FR-8's field-mapping clause state, no error code changed from what the spec/FR-8 describes, and no
architectural decision (OD-1 through OD-5, Architectural Changes 1–8 in the plan) was implemented
differently from its stated text. The only production change since attempt 1's review is the
`getFieldErrors()`/`FieldError` wiring itself, which implements FR-8's previously-missing clause using the
project's own established mechanism — this is gap closure, not drift.

## Non-Blocking Findings (carried forward, do not affect the verdict)

- **Queue screen's own `GET /support/tickets` has no dedicated forced-403 test** — carried forward
  unchanged from attempt 1 and from `docs/verification/US-5.5-implementation-verification.md` v1/v2. NFR-
  sourced ("every screen handles a server 403"), not itself a numbered AC clause; the underlying mechanism
  is shared and status-agnostic and is proven correct on the sibling detail screen and for 409/422 on this
  same screen. Not re-litigated or escalated here.
- **FR-11's "both nav entries together / no role switcher" has no single combined test.** Unchanged from
  attempt 1. Spec v2's own Traceability Matrix states FR-11 "has no corresponding row... no AC in this
  Story tests navigation placement" — out of AC reconciliation scope by the spec's own statement.
- **Full assignee UUID exposed via a `title` tooltip attribute** (`AgentTicketQueueScreen.tsx:80`) —
  carried forward unchanged, re-confirmed present and unchanged by `docs/reviews/security/
  US-5.5-security-review.md` v2's own Advisory Finding. Not an AC or business-requirement compliance
  matter.
- **No stylesheet backs the internal-note "distinct styling" class names** — carried forward, re-confirmed
  by `implementation_verification` v2, still present project-wide. NFR/technical-DoD concern, not an AC
  wording gap (the class name plus the literal "Internal" text label both exist, satisfying "distinct
  styling *and* a text label, never colour alone" as a code-level assertion; the visual rule itself is
  outside this Story and every prior Story's scope).

## AC-by-AC Summary

| AC ID | Matrix row(s) present | Test(s) exist | Assertion matches AC text | Verdict |
|---|---|---|---|---|
| AG-AC1 | Yes | Yes | Full — ordering and "no count/page number" now directly asserted | Pass |
| AG-AC2 | Yes | Yes | Full — "row reflects new assignee" now directly asserted | Pass |
| AG-AC3 | Yes | Yes | Full | Pass |
| AG-AC4 | Yes | Yes | Full — "no status change" converse now directly asserted | Pass |
| AG-AC5 | Yes | Yes | Full — 5000-char upper bound now directly tested | Pass |
| AG-AC6 | Yes | Yes | Full | Pass |
| AG-AC7 | Yes | Yes | Full — both clauses independently tested (detail-only path on a 409/403 with no `errors[]`; field-mapping path on a 422 with `errors[]`); no co-rendering requirement exists in the AC text (see Special Determination) | Pass |
| AG-AC8 | Yes | Yes | Full | Pass |
| AG-AC9 | Yes | Yes | Full | Pass |

## Verdict Rationale

Every AC has a matrix row, an existing test at the location cited, and that test's assertions were read in
full this session and confirmed to match the AC's stated behavior — not taken on any prior stage's or prior
reconciliation attempt's word. All five of attempt 1's named gaps (one blocking, four non-blocking) are
independently confirmed closed against the current working tree. The one open AC-compliance question left
to this stage by `implementation_verification` v2 — whether suppressing the generic `detail` paragraph when
a field-scoped message renders still satisfies AG-AC7 — is resolved: AG-AC7's own text is disjunctive
("renders its detail (**or** a mapped... message)"), the field-scoped message satisfies that "or" branch,
the behavior is the established convention identical across seven pre-existing screens, and it is
deliberately tested rather than an unnoticed side effect. No AC-level gap, no confirmed spec drift, no
missing or non-asserting test remains. Verdict: **PASS**.
