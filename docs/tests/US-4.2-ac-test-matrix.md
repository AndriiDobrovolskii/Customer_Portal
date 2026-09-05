---
artifact_type: ac_test_matrix
story: US-4.2
version: 3
status: ARCHIVED
created_at: "2026-09-05T17:00:00Z"
updated_at: "2026-09-05T22:45:00Z"
produced_by: test-writer
inputs:
  - path: docs/specifications/US-4.2-spec.md
    version: 6
  - path: docs/designs/api/US-4.2-openapi.yaml
    version: 3
  - path: docs/designs/database/US-4.2-entity-model.md
    version: 3
  - path: docs/plans/US-4.2-implementation-plan.md
    version: 2
supersedes: docs/tests/US-4.2-ac-test-matrix.md (v2)
---

# Traceability Matrix: Ticket Replies (US-4.2 / spec US-4.2)

## Revision Note (v3)

Provenance bump only — no row changes. `IMPLEMENTATION` T4 (`migration-manager`)
exposed a test-setup gap in the three RLS rows' underlying test functions
(`_seed_reply()` seeding internal-visibility replies with no `app.actor_kind`
GUC set, now genuinely rejected by RLS once `app_runtime` enforces it — see
`US-4.2-test-strategy.md` v3's Revision Note for full detail). Fixed in
`test_support_router.py` directly: same test function names, same AC/case
mapping, same file — no row below changes. See
`docs/workflow/history.jsonl` (`HUMAN_REDIRECTED`, 2026-09-05T22:30:00Z).

## Revision Note (v2)

Re-stamped against `implementation_plan` v2 (Architectural Change #12 — the
`app_runtime` runtime role) — see `US-4.2-test-strategy.md`'s own Revision
Note (v2) for why: the role change is infrastructure, not AC-observable
behavior, so no row below changes. Every test function named in this table
was confirmed still present on disk this pass (grep count match against v1).

**Spec:** docs/specifications/US-4.2-spec.md (version 6)
**Status:** written pre-`IMPLEMENTATION` — every function named below exists
in the working tree and asserts the behavior in its "Case" column, but will
fail at import/collection until `IMPLEMENTATION` (T1-T5) lands the
corresponding application code. See `docs/evidence/US-4.2-test-generation-
report.md` for the full red/green accounting.

| AC / FR | Case | Level | Test function | File |
|---|---|---|---|---|
| TR-AC1 / FR-1 | Agent public reply on open ticket: `201`, status → `waiting_on_customer`, `first_response_at` stamped, reply persisted | Integration | `test_create_reply_agent_public_returns_201_and_advances_status` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC1 / FR-1 | Second public agent reply does not re-stamp `first_response_at` | Integration | `test_create_reply_agent_public_second_reply_does_not_restamp_first_response_at` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC1 / FR-1 | Service-level: status → `waiting_on_customer`, requester notified | Unit | `test_create_reply_agent_public_on_open_ticket_sets_waiting_on_customer` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC1 / FR-1 | `first_response_at` stamped exactly once (first reply) | Unit | `test_create_reply_first_response_at_stamped_once_on_first_public_agent_reply` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC1 / FR-1 | `first_response_at` not re-stamped on a second public agent reply | Unit | `test_create_reply_first_response_at_not_restamped_on_second_public_agent_reply` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC1 / FR-1 | Requester notified by email, not the queue | Unit | `test_create_reply_agent_notifies_requester` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC1/FR-1 (OD-1 attachment binding) | Owned, unbound attachment → bound to the reply, not the ticket | Integration | `test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC1/FR-1 (BR-016 attachment-not-owned) | Owned by another user / already bound / unknown → `422 attachment-not-owned` (×3) | Integration | `test_create_reply_attachment_owned_by_other_user_returns_422`, `test_create_reply_attachment_already_bound_to_another_reply_returns_422`, `test_create_reply_attachment_unknown_id_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC1/FR-1 (BR-016) | All three causes raise the identical error at the service layer (indistinguishability at the point it's decided) | Unit | `test_create_reply_attachment_not_owned_raises_indistinguishable_error` (parametrized ×3) | `tests/unit/modules/support/test_support_service.py` |
| TR-AC1/FR-1 (attachment binding) | Owned, unbound attachment bound service-level | Unit | `test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC2 / FR-2 | Customer reply on `waiting_on_customer`: `201`, status → `waiting_on_support` | Integration | `test_create_reply_customer_returns_201_and_reverts_status` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC2 / FR-2 | Service-level: status → `waiting_on_support` | Unit | `test_create_reply_customer_on_waiting_on_customer_sets_waiting_on_support` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC2 / FR-2 (OD-2, queue notification) | Queue notified, not the requester | Unit | `test_create_reply_customer_notifies_queue_not_requester` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC3 / FR-3 | Internal reply absent from customer's `GET`, present (marked internal) on agent's `GET` | Integration | `test_get_ticket_detail_hides_internal_reply_from_customer_but_shows_to_agent` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC3 / FR-3 (NFR — RLS, application filter deliberately disabled) | Customer-context connection alone hides internal rows | Integration | `test_internal_reply_hidden_from_customer_context_by_rls_alone` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC3 / FR-3 (NFR — RLS) | Agent-context connection sees internal rows | Integration | `test_agent_context_sees_internal_reply_via_rls` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC3 / FR-3 (NFR — RLS, fail-closed) | No `app.actor_kind` set this transaction → internal rows hidden | Integration | `test_no_actor_kind_set_defaults_to_hiding_internal_reply` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC3 / FR-3 (service composition) | `GET` returns the ticket plus the thread page, agent sees full thread | Unit | `test_get_ticket_detail_owner_customer_returns_ticket_and_thread`, `test_get_ticket_detail_agent_scopes_thread_query_by_ticket_id` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC4 / FR-4 | Cross-customer `POST` → `404 not-found` | Integration | `test_create_reply_different_customer_returns_404` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 | Cross-customer `GET` → `404 not-found` | Integration | `test_get_ticket_detail_different_customer_returns_404` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 | Unknown ticket `POST` → `404` | Integration | `test_create_reply_unknown_ticket_returns_404` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 (Resolution OD-7) | Agent lacking `tickets:read` → `GET` returns `404`, not `403` | Integration | `test_get_ticket_detail_agent_lacking_tickets_read_returns_404` | `tests/integration/modules/support/test_support_router.py` — not reachable under the shipped role seed for `POST`'s own equivalent case; see Gaps below. |
| TR-AC4 / FR-4 | Service-level: different customer / unknown ticket → `TicketNotFoundError` (`POST` and `GET`) | Unit | `test_create_reply_different_customer_raises_ticket_not_found`, `test_create_reply_unknown_ticket_raises_ticket_not_found`, `test_get_ticket_detail_different_customer_raises_ticket_not_found`, `test_get_ticket_detail_unknown_ticket_raises_ticket_not_found` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC4 / FR-4 (API_DESIGN OQ-2) | Neither ticket owner nor `tickets:write` → `404` (unit-level; not reachable via real HTTP under the shipped seed) | Unit | `test_create_reply_caller_neither_owner_nor_agent_raises_ticket_not_found` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC4 / FR-4 | No token → `401` (`POST`, `GET`) | Integration | `test_create_reply_no_token_returns_401`, `test_get_ticket_detail_no_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 | Malformed token → `401` (`POST`, `GET`) | Integration | `test_create_reply_malformed_token_returns_401`, `test_get_ticket_detail_malformed_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 | Expired token → `401` (`POST`, `GET`) | Integration | `test_create_reply_expired_token_returns_401`, `test_get_ticket_detail_expired_token_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC4 / FR-4 | Revoked session → `401` (`POST`, `GET`) | Integration | `test_create_reply_revoked_session_returns_401`, `test_get_ticket_detail_revoked_session_returns_401` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC5 / FR-5 | Customer submits `visibility: "internal"` → `403 insufficient-permission`, no reply created | Integration | `test_create_reply_customer_visibility_internal_returns_403` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC5 / FR-5 | Customer omits `visibility` → defaults to `"public"` | Integration | `test_create_reply_customer_omitted_visibility_defaults_to_public` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC5 / FR-5 (Resolution OD-6) | Agent posts an internal note → `201`, `visibility="internal"` | Integration | `test_create_reply_agent_internal_note_is_created_visible_to_agent` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC5 / FR-5 | Rejection raised from the service's own check, not a caught `IntegrityError` — no insert attempted | Unit | `test_create_reply_customer_internal_raises_from_service_not_integrity` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC5 / FR-5 | Customer-omitted visibility defaults to `"public"` (service-level) | Unit | `test_create_reply_customer_omitted_visibility_defaults_to_public` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC5 / FR-5 (Resolution OD-6) | Agent-omitted visibility also defaults to `"public"` | Unit | `test_create_reply_agent_omitted_visibility_defaults_to_public` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC5 / FR-5 (isolation from FR-6) | Agent internal note: no status transition regardless of prior status | Unit | `test_create_reply_agent_internal_note_status_unchanged` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC6 / FR-6 | Any actor on a `"closed"` ticket → `409 ticket-closed`, no reply created | Integration | `test_create_reply_on_closed_ticket_returns_409` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC6 / FR-6 (Resolution OD-5) | Agent public reply on `"resolved"` ticket → `201`, status stays `"resolved"` | Integration | `test_create_reply_agent_public_on_resolved_ticket_status_stays_resolved` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC6 / FR-6 (Resolution OD-8) | Customer reply on `"resolved"` ticket → `201`, status → `"waiting_on_support"` (reopens) | Integration | `test_create_reply_customer_on_resolved_ticket_reopens_it` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC6 / FR-6 | Any actor on `"closed"` → `TicketClosedError`, no reply created (service-level, both actor kinds) | Unit | `test_create_reply_any_actor_on_closed_ticket_raises_ticket_closed` (parametrized ×2) | `tests/unit/modules/support/test_support_service.py` |
| TR-AC6 / FR-6 (Resolution OD-5) | Agent public reply on resolved: status unchanged | Unit | `test_create_reply_agent_public_on_resolved_ticket_status_unchanged` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC6 / FR-6 (Resolution OD-8) | Customer reply on resolved: status → `waiting_on_support` | Unit | `test_create_reply_customer_on_resolved_reopens_to_waiting_on_support` | `tests/unit/modules/support/test_support_service.py` |
| TR-AC7 / FR-7 | Empty body → `422 validation-failed`, no reply created | Integration | `test_create_reply_invalid_body_returns_422_and_creates_nothing[empty_body]` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC7 / FR-7 | Body over 5000 chars → `422 validation-failed`, no reply created | Integration | `test_create_reply_invalid_body_returns_422_and_creates_nothing[body_over_5000_chars]` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC7 / FR-7 | Unknown field in request body → `422` (`extra="forbid"`) | Integration | `test_create_reply_rejects_unknown_field_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| TR-AC7 / FR-7 | `CreateReplyRequest` rejects unknown field / empty body / oversized body; accepts the 5000-char boundary | Unit | `test_create_reply_request_rejects_unknown_field`, `test_create_reply_request_rejects_empty_body`, `test_create_reply_request_rejects_body_over_5000_chars`, `test_create_reply_request_accepts_body_at_5000_char_boundary` | `tests/unit/modules/support/test_support_schemas.py` |
| API_DESIGN OQ-1 (carried non-blocking, spec review + `non_blocking_findings`) | Customer reply on `"open"`/`"waiting_on_support"` → `201`, no status write | Integration | `test_create_reply_customer_on_open_ticket_returns_201_with_no_status_change` | `tests/integration/modules/support/test_support_router.py` |
| API_DESIGN OQ-1 | Same, both non-covered statuses, service-level, asserting the no-op explicitly | Unit | `test_create_reply_customer_on_other_status_makes_no_status_write` (parametrized: `open`, `waiting_on_support`) | `tests/unit/modules/support/test_support_service.py` |
| NFR (30/hour reply rate limit) | 31st reply in an hour → `429` with `Retry-After`; first 30 succeed | Integration | `test_create_reply_31st_in_hour_returns_429_with_retry_after` | `tests/integration/modules/support/test_support_router.py` |
| NFR (Risk 6, independence from ticket-creation's rate limit) | Exhausting the 5/hour ticket-creation limit does not block a reply | Integration | `test_reply_rate_limit_independent_of_ticket_creation_rate_limit` | `tests/integration/modules/support/test_support_router.py` |
| NFR | Rate-limit-exceeded raises with `Retry-After`, no reply created (service-level) | Unit | `test_create_reply_rate_limit_exceeded_raises_429_with_retry_after` | `tests/unit/modules/support/test_support_service.py` |
| NFR | At-boundary (30th) still succeeds | Unit | `test_create_reply_at_rate_limit_boundary_succeeds` | `tests/unit/modules/support/test_support_service.py` |
| NFR (Risk 6, key-collision) | `ticket_reply_rate_key`/`ticket_create_rate_key` never collide for the same user | Unit | `test_ticket_reply_rate_key_never_collides_with_ticket_create_rate_key` | `tests/unit/modules/support/test_support_service.py` |
| Resolution OD-3 (GET Thread Pagination) | Cursor pagination, oldest-first, `next_cursor` present when more replies exist | Integration | `test_get_ticket_detail_paginates_reply_thread_oldest_first` | `tests/integration/modules/support/test_support_router.py` |
| Resolution OD-3 | Malformed cursor → `422 validation-failed` | Integration | `test_get_ticket_detail_malformed_cursor_returns_422` | `tests/integration/modules/support/test_support_router.py` |
| Resolution OD-3 (`limit` bound, implementation-plan §10) | Out-of-range `limit` (0, 101) → `422` | Integration | `test_get_ticket_detail_out_of_range_limit_returns_422` (parametrized) | `tests/integration/modules/support/test_support_router.py` |
| `TicketDetailRead`/`ReplyRead`/`ReplyThreadPage` schema shape | `from_attributes=True` reads a real ORM `TicketReply`; `TicketDetailRead` composes a `ReplyThreadPage` via explicit construction (no `relationship()` to `model_validate()` off); no `resolved_at` field exists | Unit | `test_reply_read_from_attributes_reads_a_real_orm_instance`, `test_reply_thread_page_next_cursor_defaults_to_none`, `test_ticket_detail_read_composes_reply_thread_page`, `test_ticket_detail_read_first_response_at_present_once_stamped` | `tests/unit/modules/support/test_support_schemas.py` |
| Transaction boundary (implementation-plan, mirrors US-4.1's own contract) | `create_reply` commits exactly once | Unit | `test_create_reply_commits_exactly_once` | `tests/unit/modules/support/test_support_service.py` |
| Email best-effort (implementation-plan §8) | A dispatch failure does not fail an otherwise-successful reply creation | Unit | `test_create_reply_email_dispatch_failure_does_not_fail_the_request` | `tests/unit/modules/support/test_support_service.py` |
| AGENTS.md §5 (statement-count ceiling, nested-data list endpoint) | `GET`'s reply-thread statement count is independent of reply count (no per-reply query) | Integration | `test_get_ticket_detail_reply_thread_statement_count_independent_of_reply_count` | `tests/integration/modules/support/test_support_router.py` |

## Gaps Not Covered (carried forward, not invented here)

- **API_DESIGN OQ-2's exact `POST`-side "agent-shaped but missing
  `tickets:write`" combination** has no integration-level test — not reachable
  via a real JWT under the shipped role seed (`support_agent`/`admin` always
  hold `tickets:read` and `tickets:write` together; there is no role that
  grants one without the other). Covered at the unit level only
  (`test_create_reply_caller_neither_owner_nor_agent_raises_ticket_not_found`).
  Add an integration case if a future story introduces a role that splits
  these two scopes.
- **`migrations/env.py`'s expected zero-diff** (implementation-plan Risk 4) is
  `migration-manager`'s own confirmation, not a test-writer concern.
- **The RLS DDL's own `upgrade → downgrade → upgrade` reversibility** — proven
  by `migration-manager` (T3), not duplicated here; this suite's RLS tests
  assume the policies already exist, i.e. they are integration tests that
  will only pass once T3's migration has actually been applied by
  `alembic upgrade head` in the test database.
