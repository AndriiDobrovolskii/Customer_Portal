---
artifact_type: security_review
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-07T07:00:00Z"
updated_at: "2026-09-07T07:00:00Z"
produced_by: security-reviewer
supersedes: null
inputs:
  - path: docs/stories/US-4.3-ticket-resolution.md
    version: null
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/reviews/specifications/US-4.3-spec-review.md
    version: 3
  - path: docs/impact-analysis/US-4.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
  - path: docs/reviews/plans/US-4.3-plan-review.md
    version: 1
  - path: docs/evidence/US-4.3-implementation-report.md
    version: 1
  - path: docs/verification/US-4.3-implementation-verification.md
    version: 1
  - path: docs/designs/api/US-4.3-api-design.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: "2"
  - path: docs/designs/database/US-4.3-db-design.md
    version: 3
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/tests/US-4.3-test-strategy.md
    version: 2
  - path: docs/tests/US-4.3-ac-test-matrix.md
    version: 2
  - path: docs/decisions/US-4.3-open-decisions.md
    version: 1
---

# Security Review: Ticket Resolution

**Story ID:** US-4.3
**Reviewed:** 2026-09-07
**Overall Verdict:** PASS

## Summary

Reviewed every file this story touches or adds: `app/modules/support/{models,schemas,repository,service,router,dependencies,exceptions}.py`, `app/core/email.py`, `app/main.py`, `migrations/versions/242e0dba5ba2_add_ticket_resolution_columns.py`, and `scripts/auto_close_resolved_tickets.py`. This story adds no authentication path, no credential field, and no new logging call that carries dynamic content. All six §7 checklist rows are Pass or N/A. No Critical or Major finding. One Low finding carried forward unchanged from US-4.1/US-4.2's security reviews.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | This story introduces no credential/password field. `app/modules/support/models.py`'s four new columns (`resolved_at`, `resolution_note`, `closed_at`, `closed_by`) are timestamps, free text, and an actor-id UUID — none is a credential. |
| No plaintext/reversible encryption for credentials | N/A | Same scope as above — no credential-like field exists anywhere in this story's diff. |
| No tokens/hashes/PII in logs; no `print()` | Pass | `app/modules/support/service.py:452` `logger.exception("failed to send ticket resolved email")` is a static message with no interpolated `resolution_note`/email/token — same discipline as this file's pre-existing `:330` and `:746` calls. `app/core/email.py:86-94` `send_ticket_resolved_email`'s `logger.info("ticket resolved email dispatched")` is a bare static string; its own comment (`email.py:88-90`) records the deliberate choice never to log `to` or `resolution_note` (customer-authored/visible content). `scripts/auto_close_resolved_tickets.py:73` `logger.info("auto_close_resolved_tickets complete: closed %d ticket(s)", len(closed_ids))` logs only a count, no ticket ids/PII. Grep of every touched file for `print(` is clean. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | Pass | `schemas.py:116` `ResolveTicketRequest`, `:127` `CloseTicketRequest`, `:137` `ReopenTicketRequest` all set `model_config = ConfigDict(extra="forbid")`. Their fields (`resolution_note`; `reason` on the latter two) carry no system/privilege column — `status`, `resolved_at`, `closed_at`, `closed_by` (the model's actual system columns, `models.py:81,96,102,108`) are not client-writable anywhere in this story: `resolve_ticket`/`close_ticket`/`reopen_ticket` (`service.py:393-539`) compute every transition field server-side and pass them positionally to `repository.transition_status`, never from request body values. `TicketStateRead` (`schemas.py:142-155`) deliberately omits `closed_by`/`resolution_note` from the response (data-minimization, API_DESIGN Open Questions #5). |
| Parameterized SQL only, no string interpolation | Pass | `repository.py`'s new `transition_status` (`:117-162`) and `auto_close_resolved_past_window` (`:164-183`) both build their `UPDATE` via SQLAlchemy's `update(...).where(...).values(...)`  with bound values and `func.now()`/`func.make_interval(...)`/`literal(_RESOLUTION_WINDOW_DAYS)` constructs — no f-string/`.format()`/`%` SQL. Migration `242e0dba5ba2_add_ticket_resolution_columns.py`'s `op.create_check_constraint`/`op.create_index` calls (`:58-79`) pass fixed, compile-time string constants for the constraint/index expressions — no runtime value is interpolated into any of them. |
| Uniform auth-failure response, no differentiation leaked | Pass | `resolve_ticket`/`close_ticket`/`reopen_ticket` (`router.py:151-215`) authenticate via the unmodified `CurrentUserDep` — this story adds no new authentication path. Within-module: all three service methods raise the identical `TicketNotFoundError` (404) for an unknown ticket id and for a different customer's ticket (`service.py:406-410`, `463-467`, `506-510`), so the response never confirms a ticket id exists to an unauthorized caller. `/resolve`'s customer-vs-agent case is a literal 403 (`InsufficientPermissionError`, `service.py:417-418`) only after the 404 ownership gate and the 409 transition-validity gate have both passed, per the API design's required check order — it never leaks state information ahead of the ownership check. `/close` and `/reopen` intentionally share one success path between the requester and any agent (no permission differential beyond ownership, `service.py:456-540`), the same IDOR-preventing shape `TicketReplyService.create_reply` already established and confirmed by IMPLEMENTATION_VERIFICATION's own 12-case auth-matrix testing. |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] `ticket_number` is sequentially guessable, contrary to the story's own stated intent** — carried forward unchanged from US-4.1/US-4.2's security reviews. Not re-triggered by this story (no new endpoint accepts `ticket_number` as a lookup key; all three new routes use the internal UUID `id`), but still open as a product decision.

## Verdict Rationale

All six §7 checklist rows are Pass or N/A — no row is a Fail — so the Overall Verdict is PASS. The one carried Low finding is non-§7 and does not affect the verdict.
