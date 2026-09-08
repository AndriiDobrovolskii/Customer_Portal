---
artifact_type: security_review
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-07T22:15:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/reviews/specifications/US-4.4-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/reviews/plans/US-4.4-plan-review.md
    version: 1
  - path: docs/evidence/US-4.4-implementation-report.md
    version: 2
  - path: docs/verification/US-4.4-implementation-verification.md
    version: 1
  - path: docs/designs/api/US-4.4-api-design.md
    version: 1
  - path: docs/designs/api/US-4.4-openapi.yaml
    version: 1
  - path: docs/designs/database/US-4.4-db-design.md
    version: 1
  - path: docs/designs/database/US-4.4-entity-model.md
    version: 1
  - path: docs/tests/US-4.4-test-strategy.md
    version: 2
  - path: docs/tests/US-4.4-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-4.4-open-decisions.md
    version: 1
supersedes: null
---

# Security Review: Agent Ticket Queue & Assignment

**Story ID:** US-4.4
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

This story is `track: backend` and touches `app/modules/support/{models,repository,service,router,dependencies,schemas,exceptions}.py` plus migration `55d8d34a9753_add_ticket_assignee_column.py`. All six AGENTS.md §7 non-negotiable rules were independently checked against the implemented code (not restated from `implementation-verifier`'s report, which covered response-shape isolation and the standard 401 matrix separately) — no plaintext/reversible-credential handling was introduced (this story adds no credential field), no token/PII/print() appears in any touched log call and `assignee_id` (the field §7's "never logged or returned" rule most directly implicates here) is confirmed absent from every customer-facing response shape both by schema inspection and by a runtime field-set-equality test, the one new inbound schema (`AssignTicketRequest`) sets `extra="forbid"` and accepts only the operation's own target field, every repository write (including `assign_ticket`'s `IS NOT DISTINCT FROM` conditional update and the migration's index predicates) uses bound SQLAlchemy constructs with no string interpolation, and the two new routes' authentication-failure path (`CurrentUserDep` → `UnauthenticatedError`) is the same single, undifferentiated 401 used everywhere else in the codebase, unmodified by this story. All six rows pass; verdict is **PASS**. One Medium and one Low advisory finding are carried forward (a distinguishable-message oracle in the two `assign_ticket` 422 branches, and a stale open-decision reference in a test comment) — neither is a §7 violation.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | This story introduces no password/credential field or authentication endpoint. `git diff`-visible files (`models.py`, `repository.py`, `service.py`, `router.py`, `dependencies.py`, `schemas.py`, `exceptions.py`, the migration) contain no password/hash column or hashing call; `Ticket.assignee_id` (models.py:150) is a plain FK to `users.id`, not a credential. |
| No plaintext/reversible encryption for credentials | N/A | Same reasoning — no credential-like field exists anywhere in this diff to encrypt or hash. |
| No tokens/hashes/PII in logs; no `print()` | PASS | **Logged:** `grep -n "logger\.\|print(" app/modules/support` returns exactly three hits, all pre-existing best-effort email-dispatch failure logs unrelated to this story's new code paths: `service.py:368`, `674`, `968`, each a bare `logger.exception("failed to send ... email/notification")` with no interpolated token, hash, or request body. `assign_ticket`/`unassign_ticket` (service.py:500-613) contain zero logging calls of any kind — the audit trail for these two operations is written only to `audit_log` via `AuditServiceProtocol.record_event` (a DB write, not a log call), with `payload=None` (service.py:567, 610) carrying no sensitive data even there. No `print()` anywhere in the module. **Returned (AGENTS.md §7's "never logged *or returned*" half, this story's own central NFR):** `assignee_id` is this story's one new PII-adjacent field and it must never reach a customer-facing response. `TicketRead` (schemas.py:24-46) and `TicketStateRead` (schemas.py:142-156) — returned by the customer branch of `GET /support/tickets` and by `/resolve`/`/close`/`/reopen` (all customer-reachable) — were re-read and confirmed to carry no `assignee_id` field; OD-1 (APPROVED) is exactly the decision that kept these two classes untouched rather than widening them. `GET /support/tickets`'s single route declares `response_model=TicketListResponse | AgentTicketListResponse` (router.py:62) and branches purely in Python on `tickets:read` (router.py:87-98) before either schema is constructed — but the union `response_model` itself also fails safe: `AgentTicketRead.assignee_id: uuid.UUID | None` (schemas.py:190) has no default, so a `TicketRead`-shaped ORM object can never validate against the `AgentTicketRead` arm of the union, and Pydantic's smart-union resolution cannot silently promote a customer payload into the agent shape. Runtime-proven, not just schema-inspected: `test_list_own_tickets_customer_branch_response_has_no_assignee_id_field` (`tests/integration/modules/support/test_support_router.py:2559-2576`) asserts `set(body["items"][0].keys()) == _CUSTOMER_TICKET_READ_FIELDS` — a byte-identical field-set equality, not merely "no `assignee_id` key present." OD-2 (APPROVED) additionally confirms `GET /support/tickets/{id}` (`TicketDetailRead`) was deliberately left unextended, so no third response shape was missed. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | PASS | The one new inbound schema, `AssignTicketRequest` (schemas.py:158-167), sets `model_config = ConfigDict(extra="forbid")` (line 165) and declares exactly one field, `assignee_id: uuid.UUID` (line 167) — the action's own target, not a system/privilege field. Cross-checked against `Ticket`'s full column list (models.py:103-150: `id`, `ticket_number`, `requester_id`, `subject`, `body`, `category`, `status`, `created_at`, `updated_at`, `first_response_at`, `resolved_at`, `resolution_note`, `closed_at`, `closed_by`, `assignee_id`) — none of `status`, `closed_by`, `resolved_at`, `resolution_note`, or any other server-owned column is client-settable through this schema. All five other inbound schemas in the file (`CreateTicketRequest`, `CreateReplyRequest`, `ResolveTicketRequest`, `CloseTicketRequest`, `ReopenTicketRequest`) were re-confirmed unchanged and still set `extra="forbid"`. |
| Parameterized SQL only, no string interpolation | PASS | `repository.py`'s new/changed methods (`list_for_agent_queue` lines 93-168, `assign_ticket` lines 241-279, `unassign_ticket` lines 281-307) build every predicate through SQLAlchemy Core (`select`/`update`/`.where`/`.values`/`Ticket.assignee_id.is_not_distinct_from(...)`) with no f-string/`.format()`/`%` construction of SQL text anywhere. The migration's three `postgresql_where=sa.text("status != 'closed'")` calls (models.py:80, migration lines 64, 110) and the two `set_config` calls in `dependencies.py:80-87` (pre-existing, not touched by this story) are fixed literal DDL/SQL fragments with values passed as bound parameters (`{"actor_kind": actor_kind}`, `{"actor_id": str(current_user.user_id)}`) — no runtime value is ever spliced into the `text()` string itself. |
| Uniform auth-failure response, no differentiation leaked | PASS | Both new routes (`POST`/`DELETE /support/tickets/{id}/assign`) depend on `CurrentUserDep` → `get_current_user` (`app/modules/users/dependencies.py:73-79`), unmodified by this story: `UserService.get_authenticated_user` returns `None` for a missing, malformed, expired, or revoked token alike, and the dependency raises the single `UnauthenticatedError` regardless of which case applied — no token-failure-kind ever reaches a distinguishable status/body. Independently confirmed by `test_assign_and_unassign_auth_matrix_returns_401` (`tests/integration/modules/support/test_support_router.py:3066-3095`, parametrized over `no_token`/`malformed`/`expired`/`revoked` × `POST`/`DELETE`, asserting a bare `401` for all 8 combinations) — read directly, not inferred from the test name. The separate 404-vs-403 split for a caller who *is* authenticated but lacks `tickets:write` (`service.py:519-522`, `584-587`; AQ-AC7) is an authorization-scope distinction specified by the story itself for IDOR-prevention reasons ("never confirming the ticket id exists" to a caller with no ticket-queue visibility at all) — the same shape as this module's pre-existing `TicketNotFoundError`/`InsufficientPermissionError` split on `/replies` and `/resolve`/`/close`/`/reopen`, not an authentication-failure case §7's rule targets. |

## Advisory Findings (non-§7, does not force a Fail)

- **[Medium] `assign_ticket`'s two 422 branches are distinguishable, letting a `tickets:write` holder enumerate an arbitrary user's account status** — `service.py:531-553` raises `ValidationFailedError` with two different `FieldError.message` values depending on which check failed: `"assignee_id does not hold tickets:write."` (line 537) vs. `"assignee_id's account is deactivated."` (line 549). `app/main.py`'s `problem_error_handler` (lines 59-86) serializes `FieldError.message` verbatim into the response body's `errors[].message` (line 70) — this is not a message that stays server-side; it reaches the wire. `docs/decisions/US-4.4-open-decisions.md`'s "Carried forward" section (line 74) confirms an unknown/non-existent `assignee_id` falls into the *first* branch's message alongside a real-but-`tickets:read`-only user, so the *second*, distinct message is a working oracle: any authenticated `tickets:write` holder can submit an arbitrary UUID to `POST .../assign` against any open ticket and learn, from the message text alone, whether that UUID belongs to a real user who holds `tickets:write` but is currently deactivated — without needing `users:read` or any other privilege. The audience is authenticated staff only (not an unauthenticated or customer-facing surface), and the underlying reject-a-deactivated-target behavior is exactly what OD-4 (APPROVED) calls for — but OD-4's approval covers the 422 *outcome*, not this specific distinguishing wording, and the story's own AQ-AC8 rationale ("a ticket assigned to someone who cannot act on it is an invisible dead end") does not call for the account-status fact to be independently discoverable via message text. Recommend collapsing both branches to one shared, non-distinguishing message (matching `AttachmentNotOwnedError`'s own explicit precedent in this same module, exceptions.py:33-42: "one slug for all three, since the response must never reveal which applied") if this is tightened in a follow-up; not raised as a §7 violation since no credential/token/hash is disclosed, and does not block this stage.

- **[Low] Stale open-decision status in a test comment** — `tests/integration/modules/support/test_support_router.py:2784-2786`, the comment above `test_assign_ticket_deactivated_target_returns_422` states "Not yet human-confirmed (docs/decisions/US-4.4-open-decisions.md OD-4)", but `docs/decisions/US-4.4-open-decisions.md` (front matter `status: APPROVED`, OD-4's own `Resolution` line) shows OD-4 was approved by the human stakeholder on 2026-09-07T17:25:48Z. The implemented behavior (422 rejection of a deactivated assign-target, `service.py:543-553`) is correct and matches the approved decision — this is a documentation-freshness gap in a test comment, not a functional or security defect, and does not affect the test's validity.

## Verdict Rationale

All six §7 rows are PASS or N/A with no violation found: no credential-handling code exists in this diff, no sensitive value reaches a log call or `print()`, the new inbound schema is `extra="forbid"`-locked to its own non-privileged target field, all SQL is parameter-bound including the migration's raw-text index predicates, and the two new routes' authentication-failure path is the single pre-existing, unmodified `UnauthenticatedError` shared by every route in the codebase. The 404/403 split for insufficient scope is a deliberate, spec-mandated authorization (not authentication) distinction and does not implicate the uniform-auth-failure rule. Verdict: **PASS**.
