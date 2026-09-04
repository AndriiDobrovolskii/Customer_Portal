---
artifact_type: security_review
story: US-4.1
version: 2
status: ARCHIVED
created_at: "2026-09-04T02:00:00Z"
updated_at: "2026-09-04T15:00:00Z"
produced_by: security-reviewer
supersedes: 1
inputs:
  - path: docs/stories/US-4.1-create-ticket.md
    version: null
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.1-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-4.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
  - path: docs/reviews/plans/US-4.1-plan-review.md
    version: 1
  - path: docs/evidence/US-4.1-implementation-report.md
    version: 5
  - path: docs/verification/US-4.1-implementation-verification.md
    version: 3
  - path: docs/designs/api/US-4.1-api-design.md
    version: 3
  - path: docs/designs/api/US-4.1-openapi.yaml
    version: "3"
  - path: docs/designs/database/US-4.1-db-design.md
    version: 3
  - path: docs/designs/database/US-4.1-entity-model.md
    version: 3
  - path: docs/tests/US-4.1-test-strategy.md
    version: 5
  - path: docs/tests/US-4.1-ac-test-matrix.md
    version: 5
  - path: docs/decisions/US-4.1-open-decisions.md
    version: 1
---

# Security Review: Create Support Ticket

**Story ID:** US-4.1
**Reviewed:** 2026-09-04
**Overall Verdict:** PASS

## Summary

Re-run triggered by staleness only: v1's recorded `implementation_verification` (v2), `implementation_report` (v4), `test_strategy`/`ac_test_matrix` (v4) inputs are behind the v3/v5/v5/v5 now on disk (RECONCILIATION v1's `test_gap` loop-back added `tests/integration/scripts/test_purge_unbound_attachments.py` via TEST_WRITING attempt 5; no application code changed in that pass). Re-read `app/modules/support/{models,schemas,repository,cache,dependencies,exceptions,service,router}.py`, the ripple into `app/modules/audit/{repository,service}.py` and `app/modules/users/service.py`, `app/core/email.py`'s `EmailSender` Protocol, and migration `37c89e98a86f` directly from disk rather than trusting v1: byte-identical to what v1 reviewed. All six §7 checklist rows re-confirmed Pass or N/A; no Critical or Major finding. The same one non-§7 advisory finding is carried forward.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | This story introduces no credential/password field anywhere in `app/modules/support/models.py` or the touched files; no auth mechanism is added or modified. |
| No plaintext/reversible encryption for credentials | N/A | Same scope as above — no credential-like field exists in this story's code. |
| No tokens/hashes/PII in logs; no `print()` | Pass | Only one log call in scope: `app/modules/support/service.py:275` `logger.exception("failed to send ticket created email")` — static message, no interpolated token/PII. `app/core/email.py:58` `logger.info("ticket created email dispatched")` — same, no `to`/`ticket_number` interpolated. No `print()` anywhere under `app/modules/support/` or the touched files (grep clean, re-run this pass). The new `tests/integration/scripts/test_purge_unbound_attachments.py` (TEST_WRITING v5) is test code, out of this checklist's scope. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | Pass | `app/modules/support/schemas.py:15` `CreateTicketRequest.model_config = ConfigDict(extra="forbid")`; fields are `subject`/`body`/`category`/`attachment_ids` only — no `id`, `requester_id`, `status`, or `ticket_number` (the model's actual privilege/system columns) are client-writable. Unchanged since v1. |
| Parameterized SQL only, no string interpolation | Pass | All queries in `app/modules/support/repository.py` use SQLAlchemy `select`/`update`/`delete` with bound values (`repository.py:51`, `112-117`, `136-138`) — no f-string/`.format()`/`%` SQL anywhere. Migration `migrations/versions/37c89e98a86f_add_support_tickets.py:42-49` contains the only raw `op.execute()` calls in scope; both strings (`_CREATE_SEQUENCE`, `_SET_TICKET_NUMBER_DEFAULT`) are compile-time constants with no interpolated value. Unchanged since v1. |
| Uniform auth-failure response, no differentiation leaked | Pass | Both routes (`app/modules/support/router.py:19`, `47`) authenticate via the unmodified `CurrentUserDep`; this story adds no new authentication path. Within-module: `AttachmentNotOwnedError` (`app/modules/support/exceptions.py`) deliberately returns one `type_slug` for "not found," "not owned," and "already bound" (IDOR prevention per BR-016), confirmed by the single code path producing it (`service.py:213-221`). Unchanged since v1. |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] `ticket_number` is sequentially guessable, contrary to the story's own stated intent** — carried unchanged from v1. `docs/decisions/US-4.1-open-decisions.md`'s "Carried forward, non-blocking" note states `ticket_number` non-guessability should be an explicit requirement. The shipped format (`migrations/versions/37c89e98a86f_add_support_tickets.py:42-49`: `CP-{year}-{lpad(nextval(seq),7,'0')}`) is a plain incrementing sequence, not non-guessable. Not currently exploitable — no endpoint in this story accepts `ticket_number` as a lookup key (`TicketRepository.get_by_id` takes the UUID primary key; `GET /v1/support/tickets` only lists the caller's own tickets by `requester_id`). Worth a product decision before any future story adds a ticket-number-keyed lookup.

## Verdict Rationale

All six §7 checklist rows are Pass or N/A (no §7 row is a Fail), so the Overall Verdict is PASS. The one advisory finding is non-§7, unchanged from v1, and does not affect the verdict.
