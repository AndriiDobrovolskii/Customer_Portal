---
artifact_type: pr_summary
story: US-4.2
version: 1
status: DRAFT
created_at: "2026-09-06T02:15:00Z"
updated_at: "2026-09-06T02:15:00Z"
produced_by: pr-preparer
supersedes: null
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/evidence/US-4.2-implementation-report.md
    version: 1
  - path: docs/verification/US-4.2-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-4.2-security-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-4.2-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-4.2-traceability.md
    version: 1
---

# PR Summary: Ticket Replies (US-4.2)

## Gate confirmation

All four required upstream reviews are Pass, read directly from their reports:

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer (QUALITY_GATE) | PASS | `docs/evidence/US-4.2-quality-gate-report.md` v1 |
| implementation-verifier | PASS | `docs/verification/US-4.2-implementation-verification.md` v1 |
| security-reviewer | PASS | `docs/reviews/security/US-4.2-security-review.md` v1 |
| reconciliation-reviewer | PASS | `docs/reviews/reconciliation/US-4.2-reconciliation.md` v1 |

`HUMAN_PR_APPROVAL` was approved by `sbruhov@gmail.com` on 2026-09-06T02:00:00Z.

## Suggested PR title

```
feat: ticket replies with RLS-enforced internal visibility (US-4.2)
```

## Suggested PR description

### Summary

- Adds two endpoints to the support module: `POST /api/v1/support/tickets/{id}/replies` (create a reply, `201 ReplyRead`) and `GET /api/v1/support/tickets/{id}` (ticket detail with a keyset-paginated reply thread, `200 TicketDetailRead`).
- Replies carry a `visibility` of `public` or `internal`; only agents may post `internal`, and PostgreSQL Row-Level Security (not just an application-layer filter) guarantees a customer can never see an internal reply, even if the app forgets to filter — enforced by new `ticket_replies_read`/`ticket_replies_write` policies on the new `ticket_replies` table.
- A reply advances ticket status per the rules in the spec: an agent's public reply moves an open ticket to `waiting_on_customer` and stamps `first_response_at` on the first one; a customer's reply moves it to `waiting_on_support`, including reopening a `resolved` ticket (an agent's reply on `resolved` leaves it unchanged).
- Attachments can be bound to a reply (`AttachmentRepository.bind_to_reply`), reusing US-4.1's ownership/not-owned indistinguishability guarantee.
- Because the deployment database role (`postgres`) is a superuser and unconditionally bypasses Row-Level Security, this PR also provisions a dedicated non-superuser `app_runtime` role (`scripts/db/provision_runtime_role.sql`) and switches the application's own request-serving DB connection to it (`app/main.py`, `app/core/config.py: runtime_database_url`), so the RLS guarantee above is real rather than silently bypassed. Alembic migrations still run as the existing owner role — `migrations/env.py` is unchanged.

Full requirements: `docs/specifications/US-4.2-spec.md` (v6). Story: `docs/stories/US-4.2-ticket-replies.md`. Architectural rationale for the runtime-role change: `docs/plans/US-4.2-implementation-plan.md` (v2, Architectural Change #12).

### What changed

- **New:** `app/modules/support/models.py` (`TicketReply`, `Ticket.first_response_at`, `Attachment.ticket_reply_id`), `migrations/versions/9132a68b73c8_add_ticket_replies.py`, `scripts/db/provision_runtime_role.sql`.
- **Extended:** `app/modules/support/{schemas,repository,cache,service,router,dependencies,exceptions}.py`, `app/core/{email,cache_keys,config}.py`, `app/main.py`, `.env.example` (`SUPPORT_QUEUE_EMAIL`, `RUNTIME_DATABASE_URL`).
- **Test infrastructure:** `tests/conftest.py`'s `_database` fixture now provisions and serves through the `app_runtime` role; four other modules' `FakeEmailSender` test doubles gained stub methods for the `EmailSender` Protocol's two new methods (mechanical, no behavior change).
- Full file-by-file detail: `docs/evidence/US-4.2-implementation-report.md` (v1).

### Test plan

Traceability (`docs/reconciliation/US-4.2-traceability.md` v1) maps all seven ACs to tests; reconciliation (`docs/reviews/reconciliation/US-4.2-reconciliation.md` v1) confirmed each named test exists and asserts the AC's actual behavior, not just proximity to it.

- [x] TR-AC1 — agent public reply: `201`, status → `waiting_on_customer`, `first_response_at` stamped once, requester notified, attachment binding + BR-016 indistinguishability.
- [x] TR-AC2 — customer reply: `201`, status → `waiting_on_support`, queue notified (not requester).
- [x] TR-AC3 — internal-reply visibility enforced by RLS, including a test that bypasses the app layer entirely and queries through a raw customer-context connection.
- [x] TR-AC4 — `404` (never `403`) for unowned/unknown tickets and scope-lacking agents; full `401` matrix (no token / expired / malformed / revoked) on both routes.
- [x] TR-AC5 — `403 insufficient-permission` for a customer requesting `internal`; visibility defaults to `public` when omitted.
- [x] TR-AC6 — `409 ticket-closed` on a closed ticket; divergent resolved-ticket behavior (agent reply: unchanged; customer reply: reopens).
- [x] TR-AC7 — `422 validation-failed` on empty/over-5000-char body and unknown fields.
- [x] Full repository suite: 688/688 passed, 96.30% coverage (`support/service.py` 95%, `support/router.py` 100%).
- [x] `pre-commit run --all-files`, `mypy app tests` (146 files), `lint-imports` (6/6 contracts, zero `pyproject.toml` drift) all clean.
- [x] Migration `upgrade → downgrade → upgrade` re-proven fresh at `QUALITY_GATE`.
- [x] `app_runtime` role provisioning proven idempotent (run twice) and its GRANT list proven complete (full 261-test non-support suite + 26 support non-reply tests pass unchanged under it).

Two known, documented gaps (not defects): API_DESIGN Open Question #2's exact scope-split combination is unit-tested only, not reachable via real HTTP under the shipped role seed; migration reversibility is `migration-manager`'s domain, tracked separately.

### Risk / rollback

- **New non-superuser DB role is now load-bearing for RLS.** If `scripts/db/provision_runtime_role.sql` is not run against a target environment (or its `GRANT`s drift from what a future migration needs), the app fails to connect/query under `RUNTIME_DATABASE_URL` rather than silently falling back to the superuser bypass — a hard failure, not a silent security regression. Must be run once per environment before deploying this change; a placeholder password (`CHANGE_ME_IN_PRODUCTION`) must be overridden via the deploy pipeline (flagged as a Low advisory in `docs/reviews/security/US-4.2-security-review.md`).
- **Additive schema only.** New table + two additive/nullable columns; `downgrade()` is real and was proven (`upgrade → downgrade → upgrade`), so the migration itself is safely revertible. Reverting the PR also requires reverting the `app_runtime` role's use in `app/main.py`/`app/core/config.py`, or the app will fail to start without `RUNTIME_DATABASE_URL` configured.
- **Full-suite regression run required** on any future story that adds a new table/column touched by `app_runtime`'s request path, to confirm the role's `GRANT` list still covers it (per implementation-plan v2 Risk 7).

### Config

`.env.example` updated and confirmed current: `SUPPORT_QUEUE_EMAIL` (new setting, queue-notification mailbox) and `RUNTIME_DATABASE_URL` (new setting, `app_runtime`-credentialed connection string) both present, matching `app/core/config.py`'s new `Settings` fields.

## Commit hygiene

Working tree scope reviewed against `AGENTS.md` §7.8 (no unrelated files, no drive-by refactors):

- All `app/`, `tests/`, `migrations/`, and `scripts/db/` changes trace to this story's implementation_plan v2 (including Architectural Change #12's wider footprint — `app/main.py`, `tests/conftest.py`, `app/core/config.py`'s `runtime_database_url` — which `plan-reviewer` v2 confirmed is traced to the recorded `HUMAN_REDIRECTED` decision and TR-AC3, not untraced scope creep).
- The four `FakeEmailSender` stub additions in `admin_users`/`email_verification`/`profile`/`users` unit tests are a mechanical consequence of the `EmailSender` Protocol gaining two methods, not unrelated edits (6 lines each, no logic change).
- `AGENTS.md`'s two additions (RLS-seeding rule; the `created_at` tie-break determinism rule) and `docs/workflow/stage-map.yaml`'s new `changes_required_tests` loop-back key both codify lessons this story's own `HUMAN_REDIRECTED` test-fix cycles produced — in scope as harness/process learning from this delivery, consistent with how `workflow-state.yaml`'s history already records them.
- **Flagged, not blocking:** `.gitignore`'s addition of `docs/knowledge` has no traceable connection to this story's spec, plan, or impact analysis. Confirm before merge whether it belongs in this PR or was staged from unrelated work.
- All `docs/workflow/*.yaml`, `docs/catalog/stories.yaml`, and the story's own `docs/specifications/`, `docs/reviews/`, `docs/plans/`, `docs/tests/`, `docs/evidence/`, `docs/verification/`, `docs/reconciliation/`, `docs/impact-analysis/`, `docs/designs/`, `docs/decisions/` artifacts are the harness's own workflow/evidence trail for this delivery.

---

**This is drafted content only.** Pushing the branch or opening the Pull Request requires an explicit separate instruction to run `git push` / `gh pr create`.
