---
artifact_type: security_review
story: US-4.2
version: 1
status: DRAFT
created_at: "2026-09-06T01:15:00Z"
updated_at: "2026-09-06T01:15:00Z"
produced_by: security-reviewer
supersedes: null
inputs:
  - path: docs/stories/US-4.2-ticket-replies.md
    version: null
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/reviews/specifications/US-4.2-spec-review.md
    version: 6
  - path: docs/impact-analysis/US-4.2-impact-analysis.md
    version: 2
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
  - path: docs/reviews/plans/US-4.2-plan-review.md
    version: 2
  - path: docs/evidence/US-4.2-implementation-report.md
    version: 1
  - path: docs/verification/US-4.2-implementation-verification.md
    version: 1
  - path: docs/designs/api/US-4.2-api-design.md
    version: 3
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: "3"
  - path: docs/designs/database/US-4.2-db-design.md
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/tests/US-4.2-test-strategy.md
    version: 3
  - path: docs/tests/US-4.2-ac-test-matrix.md
    version: 3
  - path: docs/decisions/US-4.2-open-decisions.md
    version: 3
---

# Security Review: Ticket Replies

**Story ID:** US-4.2
**Reviewed:** 2026-09-06
**Overall Verdict:** PASS

## Summary

Reviewed every file this story touches or adds: `app/modules/support/{models,schemas,repository,cache,dependencies,exceptions,service,router}.py`, `app/core/{email,cache_keys,config}.py`, `app/main.py`, `migrations/versions/9132a68b73c8_add_ticket_replies.py`, and `scripts/db/provision_runtime_role.sql` (Architectural Change #12's new `app_runtime` role, added specifically to make this story's `FORCE ROW LEVEL SECURITY` guarantee real rather than bypassed by a superuser connection). All six §7 checklist rows are Pass or N/A. No Critical or Major finding. One Low advisory finding carried, plus one new Low advisory finding specific to this story's new role-provisioning script.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | This story introduces no credential/password field in `app/modules/support/models.py` or any touched file. `scripts/db/provision_runtime_role.sql:20` sets a PostgreSQL role password, not an application credential — see advisory finding below for its own discussion. |
| No plaintext/reversible encryption for credentials | N/A | Same scope as above — no application credential-like field exists anywhere in this story's code. |
| No tokens/hashes/PII in logs; no `print()` | Pass | `app/modules/support/service.py:298` `logger.exception("failed to send ticket created email")` and `:541` `logger.exception("failed to send ticket reply notification")` — static messages, no interpolated token/PII. `app/core/email.py:65,67` `logger.info(...)` calls for the two new ticket-reply methods log only a static string, no `to`/`ticket_number`/token. `email.py:77-80`'s `send_ticket_reply_queue_notification` interpolates `get_settings().support_queue_email` — a configured internal support-queue address, not a token/hash/PII field, and the method's own docstring records this as a deliberate, scoped exception. Grep of `app/modules/support/` and every touched file for `print(` is clean. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | Pass | `app/modules/support/schemas.py:16` `CreateTicketRequest` (unchanged) and `:55` `CreateReplyRequest` both set `model_config = ConfigDict(extra="forbid")`. `CreateReplyRequest`'s fields are `body`/`visibility`/`attachment_ids` only — no `id`, `ticket_id`, `author_id`, or `created_at` (the model's actual system columns, `models.py:100-112`) are client-writable. `visibility` is an enum-constrained `Literal`, not a free-form privilege flag, and its "internal" value is independently re-checked server-side (`service.py:462-466`) rather than trusted from the schema alone. |
| Parameterized SQL only, no string interpolation | Pass | All ORM queries in `app/modules/support/repository.py` use `select`/`update`/`delete`/`.where(...)` with bound values (e.g. `repository.py:51`, `106-108`, `152-158`, `230-245`) — no f-string/`.format()`/`%` SQL. The two `text()` calls in `dependencies.py:90-97` (`get_rls_session`) pass `actor_kind`/`actor_id` as bound parameters (`:actor_kind`, `:actor_id`), not string-interpolated. Migration `9132a68b73c8_add_ticket_replies.py`'s hand-written `op.execute()` calls (`_ENABLE_RLS`, `_FORCE_RLS`, `_CREATE_POLICY_READ/WRITE`, `_DROP_POLICY_READ/WRITE`, lines 46-60) are all compile-time string constants with no interpolated runtime value; the one dynamic lookup (`existing_policies`, line 133-138) uses `sa.text(...)` with a literal, non-interpolated table-name filter. `scripts/db/provision_runtime_role.sql:32` uses `format('GRANT CONNECT ON DATABASE %I TO app_runtime', current_database())` — PostgreSQL's own `%I` identifier-quoting `format()`, not string concatenation, against a server-supplied value (`current_database()`), not user input. |
| Uniform auth-failure response, no differentiation leaked | Pass | Both new routes (`router.py:89`, `120`) authenticate via the unmodified `CurrentUserDep` — this story adds no new authentication path. Within-module: `TicketNotFoundError` (`exceptions.py:84-93`) deliberately returns the same 404 for an unknown ticket id, a different customer's ticket, and an authenticated non-requester/non-agent caller (`service.py:447-455`, `563-564`) — confirmed by both branches raising the identical exception, so the response never confirms a ticket id exists to an unauthorized caller (this is stronger than a differentiated 403/404 split, by explicit design per API_DESIGN Open Question #2). `AttachmentNotOwnedError` (unchanged from US-4.1) still returns one slug for "not found"/"not owned"/"already bound" across both `create_ticket` and `create_reply` (`service.py:243`, `483`). |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] `ticket_number` is sequentially guessable, contrary to the story's own stated intent** — carried unchanged from US-4.1's security review. Not re-triggered by this story (no new endpoint accepts `ticket_number` as a lookup key), but still open as a product decision.
- **[Low] `scripts/db/provision_runtime_role.sql:20` hard-codes a literal role password (`CHANGE_ME_IN_PRODUCTION`)** — not a §7 violation: this is a PostgreSQL server role's password, not an application-level credential in the sense §7 addresses (Argon2id/no-plaintext-credentials governs user-facing password storage), and the script's own comment (lines 12-16) states every real deployment MUST override it via `ALTER ROLE ... WITH PASSWORD '<deploy-secret>'` through the deploy pipeline. It follows the exact same documented-placeholder discipline already established for `Settings.jwt_secret_key` (`app/core/config.py:18`) and `Settings.mfa_secret_encryption_key` (`:35`), and `.env.example:32`'s `RUNTIME_DATABASE_URL` uses the equivalent placeholder (`change-me-in-every-real-environment`) rather than a real value. Worth keeping on a pre-production deployment checklist so the override is never skipped, since unlike the two `Settings` defaults this one is not read from `get_settings()` at runtime and so cannot be flagged by a "still using the default" check the way a `SecretStr` default could be.

## Verdict Rationale

All six §7 checklist rows are Pass or N/A — no row is a Fail — so the Overall Verdict is PASS. Both advisory findings are non-§7 and do not affect the verdict.
