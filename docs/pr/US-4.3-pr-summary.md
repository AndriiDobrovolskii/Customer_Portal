---
artifact_type: pr_summary
story: US-4.3
version: 1
status: DRAFT
created_at: "2026-09-07T09:30:00Z"
updated_at: "2026-09-07T09:30:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/verification/US-4.3-implementation-verification.md
    version: 1
  - path: docs/reviews/reconciliation/US-4.3-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-4.3-traceability.md
    version: 1
  - path: docs/reviews/security/US-4.3-security-review.md
    version: 1
  - path: docs/evidence/US-4.3-quality-gate-report.md
    version: 1
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
supersedes: null
---

# PR Draft: Ticket Resolution (US-4.3)

## Gate confirmation

All four required upstream gates confirmed **Pass** directly from their reports (not from a verbal summary):

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | Pass | `docs/evidence/US-4.3-quality-gate-report.md` v1 |
| implementation-verifier | Pass | `docs/verification/US-4.3-implementation-verification.md` v1 |
| security-reviewer | Pass | `docs/reviews/security/US-4.3-security-review.md` v1 |
| reconciliation-reviewer | Pass | `docs/reviews/reconciliation/US-4.3-reconciliation.md` v1 |

## PR Title

```
feat: ticket resolution, closure, and auto-close lifecycle (US-4.3)
```

## Summary

Extends `app/modules/support/` (built in US-4.1/US-4.2) with the ticket resolution lifecycle:

- **`POST /v1/support/tickets/{id}/resolve`** — an agent with `tickets:write` marks an open/waiting ticket resolved with a mandatory `resolution_note`; the requester is emailed and an audit entry is written.
- **`POST /v1/support/tickets/{id}/close`** — the requester or an agent closes a ticket (from any non-closed state); `closed_by` and the correct audit actor (`self` vs `agent:{id}`) are recorded.
- **`POST /v1/support/tickets/{id}/reopen`** — direct reopen of a resolved ticket within the 7-day grace window, by requester or agent.
- **Auto-close job** (`scripts/auto_close_resolved_tickets.py`) — closes tickets resolved more than 7 days ago with no reply, via a race-safe conditional `UPDATE` scoped to the ticket still being resolved with the same `resolved_at`.
- **Reply-driven reopen** — the existing US-4.2 `POST .../replies` endpoint now also reopens a resolved ticket (within the window) and writes an audit entry (added during design review, see below).

One Alembic migration adds four nullable `tickets` columns (`resolved_at`, `resolution_note`, `closed_at`, `closed_by`), two `CHECK` constraints, and one partial index — proven via a real `upgrade → downgrade → upgrade` cycle.

**Story:** `docs/stories/US-4.3-ticket-resolution.md`
**Spec:** `docs/specifications/US-4.3-spec.md` (v2)
**Implementation plan:** `docs/plans/US-4.3-implementation-plan.md` (v1)

### Notable, human-approved deviations from the source story's literal text

- Reopen target status is `waiting_on_support` (matching already-shipped US-4.2 behavior), not a new literal `"reopened"` value — OD-1, resolved at the `HUMAN_SPEC_APPROVAL` rejection on spec v1.
- The reply-driven reopen transition (FR-4) now writes an audit entry, matching the direct-`/reopen` path — added during `DESIGN_REVIEW` (DR-4) because the source design had silently left it unaudited, contradicting the project's own "every mutation is audited" NFR.

Both are traced in `docs/reconciliation/US-4.3-traceability.md` and confirmed as approved corrections, not undocumented drift, in `docs/reviews/reconciliation/US-4.3-reconciliation.md`.

## Test Plan

Traceability (`docs/reconciliation/US-4.3-traceability.md`, v1) confirms every spec Acceptance Criterion (TC-AC1–TC-AC9) plus FR-5's source-derived direct-reopen path has a passing test that asserts its actual stated behavior, not just endpoint proximity:

- [x] TC-AC1 — agent resolves ticket → 200, `resolved_at` set, resolution email sent, `ticket_resolved` audit row
- [x] TC-AC2 — requester/agent closes ticket → 200, `closed_at`/`closed_by` set, correct audit actor
- [x] TC-AC3 — auto-close job closes tickets resolved >7 days with no reply, one audit row per ticket, idempotent, reopened tickets survive
- [x] TC-AC4 — reply within 7-day window reopens a resolved ticket to `waiting_on_support`, `resolved_at` cleared, now audited (`ticket_reopened`)
- [x] TC-AC5 — illegal transition on a closed ticket → 409 with `allowed_events`
- [x] TC-AC6 — customer attempting `/resolve` → 403; on an already-closed ticket → 409 (state checked before permission)
- [x] TC-AC7 — acting on another customer's ticket → 404 (all three endpoints)
- [x] TC-AC8 — concurrent resolution → exactly one 200, loser gets 409, first note not overwritten
- [x] TC-AC9 — empty/missing `resolution_note` → 422, ticket left unchanged
- [x] FR-5 — direct `/reopen` within window → 200; outside window → 409; exact-7-day boundary deterministic (seeded via Postgres's own frozen `now()`)
- [x] Auth matrix — no token / malformed / expired / revoked × all 3 routes (401)
- [x] Security cases — all five per-route (`docs/verification/US-4.3-implementation-verification.md` §5)

**Mechanical gate** (`docs/evidence/US-4.3-quality-gate-report.md`): `pre-commit run --all-files`, `mypy app tests`, `lint-imports` (6/6 contracts kept), `pytest --cov=app --cov-fail-under=85` — **774/774 passed, 96.29% coverage** (`support/service.py` 94%, `router.py` 100%). Migration `upgrade → downgrade → upgrade` re-proven independently against live Postgres.

**Security** (`docs/reviews/security/US-4.3-security-review.md`): all six AGENTS.md §7 checklist rows Pass/N/A, no Critical/Major finding. One carried Low advisory (sequential `ticket_number`, pre-existing, not re-triggered by this story).

## Risk / Rollback

- Migration is additive-only (4 nullable columns, 2 `CHECK` constraints, 1 partial index) — safe against existing rows; no prior code path ever wrote `status='resolved'`/`'closed'`. Rollback is the proven `downgrade()`.
- Two non-blocking, documented gaps carried forward for a future story, not this one: the response for a resolved-but-expired-not-yet-auto-closed ticket is undefined by any FR (falls through to 409, the documented default); the `reason` field on `/close`/`/reopen` is accepted but unconstrained and unpersisted.
- The auto-close script is the first in this codebase to combine a business-conditional batch `UPDATE` with a per-row audit write, and the first needing both a Postgres and a Valkey connection — flagged as an operational (scheduling/monitoring) consideration by `ARCHITECTURE_PLANNING`, not a code defect.

## `.env.example`

No new setting introduced by this story — confirmed N/A (`git diff app/core/config.py` is empty; `send_ticket_resolved_email` is a `Protocol`/`LoggingEmailSender` method addition only).

## Commit Hygiene

- All story-relevant changes are confined to `app/modules/support/*`, `app/core/email.py`, `app/main.py` (generic `allowed_events` passthrough in the problem-details handler), `scripts/auto_close_resolved_tickets.py`, the new migration, and the associated tests/docs.
- Four unrelated test fakes (`admin_users`, `email_verification`, `profile`, `users`) needed a matching `send_ticket_resolved_email` stub — mechanical fallout of extending the `EmailSender` Protocol, same ripple pattern US-4.2 already recorded, not a scope violation.
- **Flag:** `docs/docs/hooks/tool-usage.jsonl` is an untracked stray file (a session hook's tool-usage log) with no relation to this story. Recommend excluding it from the commit rather than adding it.
- `.secrets.baseline` diff is the `detect-secrets` hook's own auto-update (one hashed entry's line number shifted) — expected, not a manual change.

## Pre-existing uncommitted state

This story's entire implementation (code, tests, and all upstream workflow artifacts) exists only in the working tree — no commit has been made yet for US-4.3. `docs/reviews/reconciliation/US-4.3-reconciliation.md` (RECONCILIATION, v1) reviewed exactly this working-tree state, so no `stale_reconciliation` condition applies.

---

**This is drafted content only.** Staging, committing, pushing the branch, or opening the Pull Request all require an explicit, separate instruction from the user — none of that has been done as part of preparing this draft.
