---
artifact_type: reconciliation
story: US-4.1
version: 2
status: ARCHIVED
created_at: "2026-09-04T03:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: reconciliation-reviewer
supersedes: 1
inputs:
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/reviews/designs/US-4.1-design-review.md
    version: 3
  - path: docs/impact-analysis/US-4.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-4.1-task-breakdown.md
    version: 1
  - path: docs/reviews/plans/US-4.1-plan-review.md
    version: 1
  - path: docs/tests/US-4.1-test-strategy.md
    version: 5
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
  - path: docs/evidence/US-4.1-test-generation-report.md
    version: 5
  - path: docs/evidence/US-4.1-implementation-report.md
    version: 5
  - path: docs/verification/US-4.1-implementation-verification.md
    version: 3
  - path: docs/reviews/security/US-4.1-security-review.md
    version: 2
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
---

# Reconciliation Report: Support Tickets (Create)

**Story ID:** US-4.1
**Reviewed:** 2026-09-04
**Overall Verdict:** PASS

## Summary

Re-run against `ac_test_matrix`/`test_strategy`/`test_generation_report` v5, `implementation_report` v5, `implementation_verification` v3, and `security_review` v2 — v1 (`CHANGES_REQUIRED`, `test_gap`) is now superseded. `TEST_WRITING` attempt 5 added `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests), closing the one gap v1 found: ST-AC7's 24-hour unbound-attachment purge clause. All 4 new tests were opened and confirmed to exist and assert the exact behavior claimed. No application code changed since v1's review (`implementation_report` v5 and `implementation_verification` v3 both confirm this by direct re-read); the two disclosed Spec Drift items and ST-AC3's OD-3-blocked gap are unchanged and carried forward, non-blocking. All 7 ACs now have full matrix-row, test-existence, and behavior-assertion coverage except the one item explicitly blocked on a stakeholder decision (ST-AC3/OD-3), which no pipeline skill can close.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| ST-AC1 | "Given an authenticated, active customer / When POST /v1/support/tickets is called with {subject, body, category} and an Idempotency-Key header / Then respond 201 with the ticket, including a human-readable ticket_number / And status is \"open\" and requester_id is the caller / And no SLA target field is written / And a confirmation email containing the ticket number is queued to the requester / And a ticket_audit_log entry is written (event=ticket_created)" | Yes | `test_create_ticket_returns_201_and_persists_row`, `test_create_ticket_happy_path_writes_audit_event_and_queues_email`, `test_create_ticket_no_email_on_file_skips_dispatch_without_failing`, `test_create_ticket_email_dispatch_failure_does_not_fail_the_request`, `test_create_ticket_commits_exactly_once_with_attachment_bound` | Yes (all 5) | Yes | Unchanged since v1; re-confirmed no application code changed (`implementation_report` v5). See Spec Drift below for the audit-destination naming difference (disclosed, not a gap). |
| ST-AC2 | "Given an authenticated customer with existing tickets / When GET /v1/support/tickets is called / Then respond 200 with only that customer's tickets, newest first / And a support agent calling the same endpoint sees the queue their permissions allow, not other customers' private views" | Yes | `test_list_own_tickets_returns_only_callers_tickets_newest_first`, `test_list_own_tickets_malformed_cursor_returns_422`, `test_list_own_tickets_agent_scope_caller_returns_403`, `test_list_own_tickets_scopes_to_requester_and_passes_through_paging` | Yes (all 4) | Yes | Unchanged since v1. OD-4-resolved behavior (customer-only scope this story) approved by `SPEC_REVIEW`/`DESIGN_REVIEW`, not undisclosed drift. |
| ST-AC3 | "Given a request with an empty subject, a subject over 150 characters, a body over 5000 characters, or an unknown category / When POST /v1/support/tickets is called / Then respond 422 with type \".../errors/validation-failed\" / And the errors array names each offending field / And no ticket is created" | Yes | `test_create_ticket_invalid_input_returns_422_and_creates_nothing` (parametrized ×3: `empty_subject`, `subject_over_150_chars`, `body_over_5000_chars`) | Yes | Yes (3 of 4 sub-cases) | The 4th sub-case ("unknown category") still has **no matrix row with a test function** (`ac_test_matrix.md` v5 row: `— (gap)`) — explicitly blocked on OD-3 (no category enum exists yet; a stakeholder decision, not inferable). Non-blocking, unchanged since v1: cannot be closed by re-invoking any pipeline skill. |
| ST-AC4 | "Given a request that is retried with the same Idempotency-Key within 24 hours / When POST /v1/support/tickets is called again / Then respond 201 with the ORIGINAL ticket, and no second ticket exists / Given the same key is reused with a different body / Then respond 422 with type \".../errors/idempotency-key-reuse\"" | Yes | `test_create_ticket_replay_same_key_returns_original_ticket`, `test_create_ticket_key_reused_with_different_body_returns_422`, `test_create_ticket_missing_idempotency_key_returns_422`, `test_create_ticket_replay_returns_original_ticket_without_second_write`, `test_create_ticket_idempotency_key_reused_with_different_body_raises`, `test_create_ticket_idempotency_poll_exhausted_propagates_unhandled` | Yes (all 6) | Yes | Unchanged since v1. Poll-exhaustion path matches the DB design's and implementation plan's stated behavior (carried, disclosed, non-blocking). |
| ST-AC5 | "Given a request with no valid access token / Then respond 401 / Given an authenticated user whose account is deactivated / Then respond 403 with type \".../errors/account-deactivated\"" | Yes | 8 `_401` tests (both routes) plus `test_create_ticket_deactivated_account_returns_403`, `test_create_ticket_deactivated_account_raises_before_any_write`, `test_create_ticket_active_account_proceeds` | Yes (all 11) | Yes | Unchanged since v1. |
| ST-AC6 | "Given a customer who has created 5 tickets in the last hour / When POST /v1/support/tickets is called again / Then respond 429 with a Retry-After header / And the existing open tickets are unaffected" | Yes | `test_create_ticket_sixth_in_hour_returns_429_and_existing_tickets_unaffected`, `test_create_ticket_rate_limit_exceeded_raises_429_and_releases_the_claimed_key`, `test_create_ticket_within_rate_limit_succeeds` | Yes (all 3) | Yes | Unchanged since v1. |
| ST-AC7 | "Given a request containing an attachment_id that was uploaded by a different user, is already bound to another ticket, or does not exist / When POST /v1/support/tickets (or a reply, US-4.2) is called / Then respond 422 with type \".../errors/attachment-not-owned\" / And no ticket or reply is created, and the response does not reveal which of the three cases applied / Given an attachment_id uploaded by the caller and not yet bound / Then it is bound to this ticket and becomes immutable / And unbound attachments older than 24 hours are purged by a scheduled job" | Yes | `test_create_ticket_attachment_owned_by_other_user_returns_422`, `test_create_ticket_attachment_already_bound_returns_422`, `test_create_ticket_attachment_unknown_id_returns_422`, `test_create_ticket_attachment_owned_and_unbound_is_bound_and_immutable`, `test_create_ticket_attachment_not_owned_raises_indistinguishable_error` (×3 parametrized), `test_create_ticket_attachment_owned_and_unbound_is_bound`, **`test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h`, `test_purge_unbound_attachments_leaves_unbound_attachment_within_24h_untouched`, `test_purge_unbound_attachments_leaves_bound_attachment_older_than_24h_untouched`, `test_purge_unbound_attachments_purge_of_empty_candidate_list_deletes_nothing`** | Yes (all 10) | Yes — **now including the purge sub-clause** | The three not-owned causes and binding behavior unchanged since v1. **New this pass:** `tests/integration/scripts/test_purge_unbound_attachments.py` (4 tests, opened and read in full) exercises `AttachmentRepository.find_unbound_older_than`/`.purge` — the exact repository methods `scripts/purge_unbound_attachments.py`'s `main()` composes. `test_purge_unbound_attachments_deletes_unbound_attachment_older_than_24h` seeds an attachment 24h+1min old and unbound, asserts it is returned as a candidate, `purge()` returns count 1, and a re-query confirms the row is gone. `_leaves_unbound_attachment_within_24h_untouched` and `_leaves_bound_attachment_older_than_24h_untouched` each assert the counter-case (recent-but-unbound, and old-but-bound) is excluded from candidates and survives. `_purge_of_empty_candidate_list_deletes_nothing` asserts `purge([])` returns 0. This closes v1's sole Fail-forcing gap. |

## Spec Drift

- **[Low] `ticket_number`'s shipped format is sequentially guessable, in tension with FR-1's stated non-guessability requirement.** FR-1 says: "a human-readable `ticket_number` ... that is sequential in presentation but MUST NOT be guessable or enumerable as an API identifier — this non-guessability is a deliberate security property of the identifier, not just an example format." Shipped code (`migrations/versions/37c89e98a86f_add_support_tickets.py:42-49`) computes `ticket_number` as `'CP-' || year || '-' || lpad(nextval('ticket_number_seq')::text, 7, '0')` — a plain incrementing sequence, guessable by construction. This divergence originates at design, not `IMPLEMENTATION`: `US-4.1-db-design.md` v3 (lines 86-94) specifies this exact format and states it is a deliberate display-only reading of FR-1's self-contradictory clause; `DESIGN_REVIEW` v3 explicitly reviewed and passed this choice. `security-reviewer` (v1 and v2, unchanged) independently confirmed it is not currently exploitable: no endpoint accepts `ticket_number` as a lookup key. Not Fail-forcing — the design and every downstream gate reviewed and accepted this reading in good faith, and there is no current exploitation path — but named explicitly for `HUMAN_PR_APPROVAL`, since a future story keying a lookup on `ticket_number` would reopen this as a live IDOR/enumeration risk. Unchanged since v1.
- **[Disclosed, non-blocking] Audit destination differs from FR-1's literal text, by design.** FR-1 says a "`ticket_audit_log` entry is written." Shipped code writes to the existing `audit_log` table (`category="tickets"`, `event="ticket_created"`) instead, per `DESIGN_REVIEW`'s critical finding DR-1 (v1→v2), which required routing this event into the existing table rather than a new one. `US-4.1-spec.md`'s FR-1 prose was never reconciled after that fix — the spec still says `ticket_audit_log` literally — but the design's resolution is correct, reviewed, and exactly what the tests assert. A wording-only completeness gap in the spec text, not a code defect. Unchanged since v1.

## Confirmed as Acceptable (previously carried as open items)

- **FR-1's email-collaborator emergent scope** (`EmailSender.send_ticket_created_email`, `UserService.get_email_for_user`) — confirmed resolved at v1, not re-litigated here: FR-1's actual observable requirement is satisfied and directly tested; both additions are additive, read-only, cross-module-by-service, and independently cleared by `IMPLEMENTATION_VERIFICATION`/`SECURITY_REVIEW`.

## Verdict Rationale

`PASS`. Every AC has a matrix row and every named test function was independently confirmed to exist and assert its claimed behavior — no partial-assertion or missing-function gap anywhere in ST-AC1, ST-AC2, ST-AC4, ST-AC5, ST-AC6, or ST-AC7 (all 7 of ST-AC7's sub-clauses now covered, including the purge job). ST-AC3's "unknown category" sub-case remains open but does not force the verdict: it is blocked on OD-3, a stakeholder decision no pipeline skill can resolve, carried forward as a disclosed, non-blocking item for `HUMAN_PR_APPROVAL` — consistent with every prior stage's treatment. The two Spec Drift items are named for the human record and do not themselves force the verdict; both trace to approved, reviewed design decisions rather than undisclosed implementation drift.
