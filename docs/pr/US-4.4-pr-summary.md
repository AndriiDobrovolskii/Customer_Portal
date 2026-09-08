---
artifact_type: pr_summary
story: US-4.4
version: 1
status: ARCHIVED
created_at: "2026-09-08T00:40:00Z"
updated_at: "2026-09-08T09:30:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/stories/US-4.4-agent-ticket-queue-and-assignment.md
    version: null
  - path: docs/specifications/US-4.4-spec.md
    version: 1
  - path: docs/impact-analysis/US-4.4-impact-analysis.md
    version: 1
  - path: docs/plans/US-4.4-implementation-plan.md
    version: 1
  - path: docs/evidence/US-4.4-implementation-report.md
    version: 2
  - path: docs/verification/US-4.4-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-4.4-security-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-4.4-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-4.4-traceability.md
    version: 1
supersedes: null
---

# PR Draft: Agent Ticket Queue & Assignment (US-4.4)

**This is drafted content only.** No commit, branch, or Pull Request has been
created. Pushing the branch and opening the PR requires an explicit separate
instruction to run `git push` / `gh pr create`.

## Gate confirmation (read directly from each artifact, not assumed)

| Gate | Artifact | Version | Verdict |
|---|---|---|---|
| `gate-enforcer` (QUALITY_GATE) | `docs/evidence/US-4.4-quality-gate-report.md` | v2 | **PASS** — pre-commit 11/11, mypy 0 errors/147 files, lint-imports 6/6 kept, pytest 836/836 (96.39% cov, floor 85%), migration upgrade/downgrade/upgrade re-proven |
| `implementation-verifier` | `docs/verification/US-4.4-implementation-verification.md` | v1 (APPROVED) | **PASS** |
| `security-reviewer` | `docs/reviews/security/US-4.4-security-review.md` | v1 (APPROVED) | **PASS** |
| `reconciliation-reviewer` | `docs/reviews/reconciliation/US-4.4-reconciliation.md` + `docs/reconciliation/US-4.4-traceability.md` | v1 (APPROVED) | **PASS** |
| `HUMAN_PR_APPROVAL` | `docs/workflow/workflow-state.yaml` | — | **APPROVED** by sbruhov@gmail.com |

Working tree (`git status --porcelain`) matches exactly the file set every
upstream report claims: 7 modified `app/modules/support/` files, 2 modified
test files, 1 new migration. No drift since RECONCILIATION ran — the
`stale_reconciliation` loop-back does not apply.

---

## Suggested PR Title

```
feat: agent ticket queue and assignment (US-4.4)
```

## Suggested PR Description

### Summary

- Turns the already-granted `tickets:read` scope into a working agent queue:
  `GET /v1/support/tickets` gains an agent branch (filters on `status`,
  `category`, `assignee_id` incl. `me`/`none`, cursor-paginated, oldest
  `updated_at` first), replacing the previous unconditional 403
  (`reject_agent_queue_access` removed).
- Adds `POST /v1/support/tickets/{id}/assign` and
  `DELETE /v1/support/tickets/{id}/assign` (both `tickets:write`), covering
  first assignment, self-assignment, re-assignment, and unassignment, each
  audited (`ticket_assigned` / `ticket_unassigned`) in the same transaction
  as the write, and protected against a concurrent-assignment race via an
  `IS NOT DISTINCT FROM` conditional update (409 on conflict, not a silent
  overwrite).
- Adds `tickets.assignee_id` (nullable FK to `users.id`, no cascade) plus
  three supporting indexes (default-queue partial index, status/assignee
  composite indexes) via migration `55d8d34a9753_add_ticket_assignee_column`.
- `assignee_id` is exposed only on new agent-facing shapes
  (`AgentTicketRead`, `AgentTicketListResponse`, `AgentTicketStateRead`);
  the existing customer-facing `TicketRead`/`TicketListResponse`/
  `TicketStateRead` are byte-for-byte unchanged and were proven (not just
  asserted) to carry no `assignee_id`.

**Story:** `docs/stories/US-4.4-agent-ticket-queue-and-assignment.md`
**Specification:** `docs/specifications/US-4.4-spec.md` (v1, APPROVED)
**Implementation plan:** `docs/plans/US-4.4-implementation-plan.md` (v1, APPROVED)
**Traceability:** `docs/reconciliation/US-4.4-traceability.md` (v1, APPROVED)

### Why

`tickets:read` existed in the permission catalogue and was granted to
`support_agent`/`admin` since US-4.1 but was used only to reject agent
callers from the queue — an agent had no reachable listing endpoint and
could only touch a ticket by guessing its UUID. This story is also a
blocker for US-5.5 (Agent Console frontend), which has no reachable
backend surface without it.

### Test Plan

All ten Acceptance Criteria (AQ-AC1–AQ-AC10) are covered by both a unit
test (`tests/unit/modules/support/test_support_service.py`) and an
integration test against real PostgreSQL
(`tests/integration/modules/support/test_support_router.py`), confirmed
present and asserting the AC's actual behavior — not just proximity — by
`reconciliation-reviewer`'s traceability matrix:

- [x] **AQ-AC1** Agent sees the queue (200, non-closed, oldest-`updated_at`-first, `assignee_id` on every item, cursor pagination, no total count)
- [x] **AQ-AC2** Queue filters (`status`/`category`/`assignee_id` incl. `me`/`none`; `status=closed` is the only way a closed ticket appears)
- [x] **AQ-AC3** Assign (200, `assignee_id` set, audit row `ticket_assigned`, re-assign replaces + re-audits)
- [x] **AQ-AC4** Unassign (200, `assignee_id` null, audit row `ticket_unassigned`, idempotent on an already-unassigned ticket)
- [x] **AQ-AC5** Customer branch unchanged (byte-identical field set to US-4.1, no `assignee_id`)
- [x] **AQ-AC6** Agent-only query params ignored for a customer caller (result set identical with/without them present)
- [x] **AQ-AC7** Assignment requires `tickets:write` (404 for a customer — indistinguishable from unknown id; 403 for a `tickets:read`-only agent; full 401 auth matrix: no token / expired / malformed / revoked, both routes)
- [x] **AQ-AC8** Assignee must hold `tickets:write` / must not be deactivated (422, OD-4's adopted default)
- [x] **AQ-AC9** Assigning a closed ticket (409 `invalid-state-transition`, `assignee_id` unchanged)
- [x] **AQ-AC10** Concurrent assignment (conditional-update race proven at the repository layer: one caller wins, the loser gets 409, no silent overwrite)

Mechanical gate (`docs/evidence/US-4.4-quality-gate-report.md` v2, full
re-run from scratch against real Docker Postgres/Valkey):
- [x] `pre-commit run --all-files` — 11/11 hooks passed
- [x] `mypy app tests` — 0 errors, 147 source files
- [x] `lint-imports` — 6/6 contracts kept, 0 broken
- [x] `pytest --cov=app --cov-fail-under=85` — 836/836 passing, 96.39% coverage (floor 85%; every touched module held or gained coverage vs. the pre-fix baseline)
- [x] Migration `upgrade → downgrade → upgrade` — independently re-proven against real PostgreSQL (column/FK/all three indexes cleanly removed and restored; pre-existing indexes untouched)
- [x] Runtime rules (§6.6): ORM never crosses service→router; no eager-loading/cache-TTL gap (N/A — plain scalar FK, no cache.py diff); cross-module `RoleService` access is Protocol-only, never a direct import
- [x] Contract/security spot-check (§6.7): `response_model`+`status_code` on every route; `AssignTicketRequest` is `extra="forbid"` with no privilege field; no sensitive field added to any customer-facing `*Read`; `.env.example` correctly unchanged (no new settings)

Security (`docs/reviews/security/US-4.4-security-review.md` v1, PASS,
independent AGENTS.md §7 audit):
- [x] No credential-handling code introduced
- [x] No token/PII/`assignee_id` in any log call; `assignee_id`'s absence from every customer-facing shape proven by a runtime field-set-equality test, not just schema inspection
- [x] All SQL parameter-bound, including the `IS NOT DISTINCT FROM` concurrency check and the migration's partial-index predicates
- [x] Uniform 401 for all four unauthenticated-token cases on both new routes

**Non-blocking items carried forward (do not block this PR, tracked for a
future pass):**
- **[Medium, security-reviewer]** `assign_ticket`'s two 422 branches use
  distinguishable message text, letting a `tickets:write` holder infer
  whether an arbitrary UUID belongs to a deactivated `tickets:write`
  account. Staff-only audience, no credential/token/hash disclosed;
  recommend collapsing to one shared message in a follow-up.
- **[Low, security-reviewer]** A stale test comment in
  `test_support_router.py` (near `test_assign_ticket_deactivated_target_returns_422`)
  still says OD-4 is "not yet human-confirmed"; OD-4 is APPROVED and the
  implemented behavior is correct — comment-freshness only.
- **[Info, gate-enforcer]** One intermittent, non-reproducible flake in
  `tests/integration/modules/audit/test_audit_router.py` (a file untouched
  by this story, last changed 2026-09-03) — passed standalone and on
  immediate re-run; not a US-4.4 defect.
- **[Info, reconciliation-reviewer]** No test independently exercises
  FR-1's `id` tiebreak or pools tickets from multiple requesters in one
  queue response — not a gap against any AC's literal text, flagged as a
  tightening opportunity for `test-writer` if revisited.

### `.env.example`

No new setting was introduced by this story. Confirmed independently by
`gate-enforcer`, `implementation-verifier`, and this review:
`git diff --stat HEAD -- .env.example` produces no output. No update needed.

### Commit Hygiene

In scope for this story (matches every upstream evidence report exactly):
- `app/modules/support/{dependencies,exceptions,models,repository,router,schemas,service}.py`
- `tests/unit/modules/support/test_support_service.py`
- `tests/integration/modules/support/test_support_router.py`
- `migrations/versions/55d8d34a9753_add_ticket_assignee_column.py`
- `docs/**/US-4.4-*` governance artifacts (spec, designs, plans, evidence, reviews, reconciliation, traceability)

**Flagged, not silently included:** the current working tree also carries
uncommitted changes to three files with no apparent connection to US-4.4's
scope —
`.claude/commands/so/next.md`,
`.claude/skills/story-orchestrator/SKILL.md`,
`.claude/skills/story-orchestrator/references/continue-flow.md`,
and `docs/workflow/stages.md`. None of these appear in any US-4.4 evidence,
verification, security, or reconciliation report's claimed diff scope. If
these are unrelated harness/skill maintenance, they should be committed
separately from this story's PR rather than bundled in, per AGENTS.md
§7.8's no-unrelated-files rule. If they are in fact required for the
harness to correctly track US-4.4 (e.g. workflow-state bookkeeping), that's
expected and fine to include — but the "which is it" call belongs to the
human preparing the actual commit, not this draft.

### Risks / Rollback (from `implementation-plan.md`'s Risks section)

- **Union `response_model` on `GET /v1/support/tickets`** — first use of
  this pattern in this router; mitigated by each branch's service method
  returning its own concrete Pydantic type (never a shared dict) and an
  integration test asserting byte-identical customer-branch output.
  Proven in place.
- **Contract change for `tickets:read`/`tickets:write` callers on
  `GET /v1/support/tickets`** — this is an intentional, not merely
  additive, behavior change (403 → 200 with real data) for exactly the
  caller kind previously rejected. No other consumer relying on the old
  403 was found (`impact-analyzer`).
- **Rollback:** the migration is purely additive (nullable column + 3
  indexes, no backfill, no destructive step) — `downgrade()` cleanly drops
  the FK, all three indexes, then the column, independently re-proven
  against real PostgreSQL. Reverting the code change requires no data
  migration beyond running `alembic downgrade -1`.

---

*Drafted by `pr-preparer`. All four upstream gates (`gate-enforcer`,
`implementation-verifier`, `security-reviewer`, `reconciliation-reviewer`)
independently confirmed PASS from their own artifacts, and `HUMAN_PR_APPROVAL`
was confirmed APPROVED in `docs/workflow/workflow-state.yaml`. This file
does not push, open, or merge anything — a human (or an explicit
`git push` / `gh pr create` instruction) is required to act on it.*
