---
artifact_type: pr_summary
story: US-4.1
version: 1
status: DRAFT
created_at: "2026-09-04T12:00:00Z"
updated_at: "2026-09-04T12:00:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/verification/US-4.1-implementation-verification.md
    version: 3
  - path: docs/reviews/reconciliation/US-4.1-reconciliation.md
    version: 2
  - path: docs/reviews/security/US-4.1-security-review.md
    version: 2
  - path: docs/evidence/US-4.1-quality-gate-report.md
    version: 5
  - path: docs/specifications/US-4.1-spec.md
    version: 1
  - path: docs/plans/US-4.1-implementation-plan.md
    version: 1
supersedes: null
---

# PR Summary: US-4.1 — Support Tickets (Create)

## Gate Confirmation

All four required upstream gates confirmed **Pass** by direct read of their reports:

| Gate | Verdict | Report |
|---|---|---|
| gate-enforcer | PASS (v5) | `docs/evidence/US-4.1-quality-gate-report.md` |
| implementation-verifier | PASS (v3) | `docs/verification/US-4.1-implementation-verification.md` |
| security-reviewer | PASS (v2) | `docs/reviews/security/US-4.1-security-review.md` |
| reconciliation-reviewer | PASS (v2) | `docs/reviews/reconciliation/US-4.1-reconciliation.md` |

`HUMAN_PR_APPROVAL` was approved 2026-09-04T11:00:00Z by sbruhov@gmail.com.

## Suggested PR Title

`feat: add self-service support ticket creation (US-4.1)`

## Summary

Adds a new `app/modules/support/` module implementing self-service support ticket creation and listing for authenticated customers:

- `POST /v1/support/tickets` — idempotent ticket creation (`Idempotency-Key` header, atomic `SET NX EX` claim/replay gate with bounded poll), a human-readable `ticket_number`, input validation (subject ≤150 chars, body ≤5000 chars), a per-user rate limit (5/hour, `429` + `Retry-After`), optional attachment binding with an ownership (IDOR-safe) check, a queued confirmation email, and a `ticket_created` audit entry written into the existing `audit_log` table in the same transaction as the ticket insert.
- `GET /v1/support/tickets` — cursor-paginated listing of the caller's own tickets, newest first; a caller holding `tickets:read`/`tickets:write` scope is rejected (agent-queue views are out of scope for this story).
- `scripts/purge_unbound_attachments.py` — scheduled purge of unbound attachments older than 24 hours.
- New migration `37c89e98a86f` (`tickets`, `attachments` tables, `ticket_number_seq`), no existing table altered.
- Cross-module additions: `AuditLogService.record_event` (non-self-committing, so the ticket insert/attachment bind/audit write commit atomically together), `UserService.get_account_status_for_user` (FR-5's account-deactivated `403` gate) and `UserService.get_email_for_user`, `EmailSender.send_ticket_created_email`.

Linked story: `docs/stories/US-4.1-create-ticket.md`
Linked spec: `docs/specifications/US-4.1-spec.md` (v1)
Linked plan: `docs/plans/US-4.1-implementation-plan.md` (v1)

## Test Plan

Per `docs/reconciliation/US-4.1-traceability.md` (v2) and `docs/evidence/US-4.1-quality-gate-report.md` (v5):

- [x] All 7 ACs (ST-AC1–ST-AC7) have a traceability-matrix row with an existing, behavior-asserting test — independently confirmed by `reconciliation-reviewer`.
- [x] `pytest --cov=app --cov-fail-under=85`: 603 passed (318 unit + 285 integration, including `tests/integration/modules/support/` and `tests/integration/scripts/test_purge_unbound_attachments.py` against real PostgreSQL/Valkey via testcontainers), 96.18% total coverage, no touched module below the 85% floor.
- [x] Full AGENTS.md §5 security-case matrix (no-token / expired / malformed / revoked / insufficient-permissions, as applicable) on both protected routes — 10 cell functions, independently re-confirmed present.
- [x] Migration cycle (`upgrade head → downgrade -1 → upgrade head`) proven fresh against a live PostgreSQL database.
- [x] `pre-commit run --all-files`: all 7 hooks green (ruff lint/format, mypy strict, import-linter, unit tests, no-mock-in-integration, detect-secrets).
- [x] `mypy app tests --strict`: 0 errors across 145 files. `lint-imports`: 6/6 contracts kept, no new `ignore_imports`/`exhaustive=false`.

**Known, non-blocking gap:** ST-AC3's "unknown category" sub-case has no test — blocked on OD-3 (no category enum exists yet; a stakeholder decision, not pipeline-fixable). Carried explicitly through every gate to this point.

## Risk / Rollback

Per `docs/plans/US-4.1-implementation-plan.md`'s Risks section:

1. **Transaction-boundary asymmetry** — the new `AuditLogService.record_event` deliberately does not self-commit (unlike the module's two existing audit methods); a future caller assuming it commits would silently lose the audit write. Mitigated by a docstring and a dedicated unit test asserting no `commit()` call.
2. **Idempotency bounded-poll latency** — a concurrent mid-flight replay can approach the p95 ≤400ms budget; accepted as expected behavior for a genuine double-submit, not a regression.
3. **`migrations/env.py` edit** — one-line model-registration import, same pattern as 6 prior stories; no functional risk.
4. **Migration is additive only** (`tickets`, `attachments`, `ticket_number_seq` — no existing table altered), so rollback is a straightforward `alembic downgrade -1`, proven in this pass.

No feature flag; this is a net-new module and route pair, safe to roll back via the migration's `downgrade()` and reverting the router registration in `app/api/v1/router.py`.

## Open Items Carried to This Gate (disclosed, non-blocking)

- **OD-3** — `tickets.category` has no DB-level `CHECK`/`ENUM` constraint pending a stakeholder decision on allowed values; ST-AC3's "unknown category" sub-case is untestable until resolved.
- **BR-007** — `requester_id`/`uploaded_by` FK `ondelete` defaults to `RESTRICT` pending the account-erasure job's mechanics (legal/DPO sign-off pending).
- **Idempotency poll-exhaustion 500** — the concurrent-replay poll's exhaustion path returns an undocumented `500` (no contract slug); confirmed as designed implementation behavior, not a gap.
- **[Low, Spec Drift] `ticket_number` format** — sequentially guessable (`CP-{year}-{seq:07d}` via a plain `SEQUENCE`), in tension with FR-1's own non-guessability clause. Traces to an approved, `DESIGN_REVIEW`-passed design decision, not undisclosed drift. Not currently exploitable — no endpoint accepts `ticket_number` as a lookup key. Worth a product decision before any future story adds one.
- **[Disclosed, non-blocking] Audit destination wording** — FR-1's spec text says "`ticket_audit_log`"; shipped code correctly writes to the existing `audit_log` table (`category="tickets"`) per `DESIGN_REVIEW`'s DR-1 fix. Spec-text-only gap, not a code defect.

## `.env.example`

No new `Settings` field introduced by this story (confirmed by `implementation-verifier` v3 and `gate-enforcer` v5: no `os.getenv`/`core.config` reference under `app/modules/support/`, `.env.example` unchanged). N/A — no update needed.

## Commit Hygiene — Flagged for Human Review

The working tree currently contains changes **outside this story's scope** that should be split out of, or excluded from, the PR branch before it is opened:

1. **Unrelated to US-4.1, appear to belong to a separate US-3.3 delivery:** `docs/evidence/US-3.3-delivery-summary.md`, `docs/evidence/US-3.3-implementation-report.md`, `docs/evidence/US-3.3-quality-gate-report.md`, `docs/reviews/designs/US-3.3-design-review.md`, `docs/reconciliation/US-3.3-traceability.md` (all untracked).
2. **Unrelated tooling artifacts, should not be committed:** `.claude/settings.json.graphify-bak` (untracked backup file), `graphify-out/` (untracked directory).
3. **`.gitignore` change removes an unrelated `*`/`!src/` block** (a graphify-tooling ignore rule) — not connected to this story's module additions; confirm intent before including.
4. `.secrets.baseline` modification is in-scope (a `detect-secrets` line-number shift from this story's own test-file edits, already noted as the documented remediation, not a bypass, in `docs/evidence/US-4.1-quality-gate-report.md`).

Everything else in the working tree (`app/modules/support/`, the migration, `app/api/v1/router.py`, `app/core/cache_keys.py`, `app/core/email.py`, `app/modules/audit/{repository,service}.py`, `app/modules/users/service.py`, `scripts/purge_unbound_attachments.py`, the new/modified test files, and this story's own `docs/` artifacts) is within this story's declared blast radius per `docs/impact-analysis/US-4.1-impact-analysis.md` and `docs/plans/US-4.1-implementation-plan.md`.

---

**This is drafted content only.** Pushing the branch or opening the Pull Request requires an explicit separate instruction to run `git push` / `gh pr create`.
