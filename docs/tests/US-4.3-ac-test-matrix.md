---
artifact_type: ac_test_matrix
story: US-4.3
version: 2
status: ARCHIVED
created_at: "2026-09-06T23:00:00Z"
updated_at: "2026-09-07T03:00:00Z"
produced_by: test-writer
inputs:
  - path: docs/specifications/US-4.3-spec.md
    version: 2
  - path: docs/designs/api/US-4.3-openapi.yaml
    version: 2
  - path: docs/designs/database/US-4.3-entity-model.md
    version: 3
  - path: docs/plans/US-4.3-implementation-plan.md
    version: 1
supersedes: 1
---

# Traceability Matrix: Ticket Resolution (US-4.3 / spec US-4.3)

**v2 (attempt 2):** row content and test function names are unchanged from
v1. `test_reopen_ticket_at_exactly_7_days_boundary_succeeds` and
`test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_
untouched` (OD-4 boundary-pairing rows below) now seed `resolved_at`
server-side instead of from Python's wall clock — a determinism fix routed
via `IMPLEMENTATION.loop_back.changes_required_tests`, not a coverage change.
See `US-4.3-test-strategy.md` v2's "Rework" section and
`US-4.3-test-generation-report.md` v2 for detail.

**Spec:** docs/specifications/US-4.3-spec.md (version 2)
**Status:** written pre-`IMPLEMENTATION` — every function named below exists
in the working tree and asserts the behavior in its "Case" column. The three
files naming a not-yet-built symbol at module scope
(`tests/unit/modules/support/test_support_schemas.py`,
`tests/unit/modules/support/test_support_service.py`,
`tests/integration/scripts/test_auto_close_resolved_tickets.py`) fail at
*import*, before any test in them runs, until `IMPLEMENTATION` (T1-T6) lands
the corresponding code; `tests/integration/modules/support/test_support_router.py`
collects and runs today — its new `/resolve`/`/close`/`/reopen` cases fail at
*runtime* (`404 Not Found`, no such route yet) rather than at collection. See
`docs/evidence/US-4.3-test-generation-report.md` for the full red/green
accounting.

| AC / FR | Case | Level | Test function | File |
|---|---|---|---|---|
| TC-AC1 / FR-1 | Agent resolves from each OD-5-eligible status (`open`, `waiting_on_support`, `waiting_on_customer`): `200`, `resolved_at` set, `resolution_note` persisted, `ticket_resolved` audit row | Integration | `test_resolve_ticket_agent_from_eligible_status_returns_200_and_persists` (parametrized ×3) | `tests/integration/modules/support/test_support_router.py` |
| TC-AC1 / FR-1 | Response omits `resolution_note`/`closed_by` (data-minimization, API_DESIGN Open Questions #5) | Integration | `test_resolve_ticket_agent_from_eligible_status_returns_200_and_persists` (same test, body assertion) | `tests/integration/modules/support/test_support_router.py` |
| TC-AC1 / FR-1 | Service-level: resolves, audits `ticket_resolved` with `actor_id=agent`, emails the requester the resolution note | Unit | `test_resolve_ticket_agent_from_each_eligible_status_succeeds` (parametrized ×3) | `tests/unit/modules/support/test_support_service.py` |
| TC-AC1 / FR-1 | Email dispatch failure does not fail an otherwise-successful resolve (best-effort, after commit) | Unit | `test_resolve_ticket_email_dispatch_failure_does_not_fail_the_request` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC1 / FR-1 | Commits exactly once | Unit | `test_resolve_ticket_commits_exactly_once` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC9 / FR-10 | Empty or absent `resolution_note` → `422 validation-failed`, ticket unchanged | Integration | `test_resolve_ticket_invalid_resolution_note_returns_422_and_leaves_ticket_unchanged` (parametrized: empty, missing) | `tests/integration/modules/support/test_support_router.py` |
| TC-AC9 / FR-10 | `ResolveTicketRequest` rejects unknown field / empty / oversized `resolution_note`; accepts the 5000-char boundary; missing field raises | Unit | `test_resolve_ticket_request_rejects_unknown_field`, `test_resolve_ticket_request_rejects_empty_resolution_note`, `test_resolve_ticket_request_rejects_resolution_note_over_5000_chars`, `test_resolve_ticket_request_accepts_resolution_note_at_5000_char_boundary`, `test_resolve_ticket_request_missing_resolution_note_raises` | `tests/unit/modules/support/test_support_schemas.py` |
| TC-AC6 / FR-7 | Customer resolves an open ticket → `403 insufficient-permission` | Integration | `test_resolve_ticket_customer_on_open_ticket_returns_403` | `tests/integration/modules/support/test_support_router.py` |
| TC-AC6 / FR-7 | Service-level: customer on eligible status → `InsufficientPermissionError`, no transition attempted | Unit | `test_resolve_ticket_customer_on_open_ticket_raises_insufficient_permission` | `tests/unit/modules/support/test_support_service.py` |
| Spec NFR (state before actor) | Customer resolves a **closed** ticket → `409`, never `403` | Integration | `test_resolve_ticket_customer_on_closed_ticket_returns_409_not_403` | `tests/integration/modules/support/test_support_router.py` |
| Spec NFR | Service-level: same check-order proof | Unit | `test_resolve_ticket_customer_on_closed_ticket_raises_409_not_403` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC5 / FR-6 | `/resolve` from `closed`; `/reopen` from `open`/`closed`; `/close` from `closed` → `409 invalid-state-transition` with the exact `allowed_events` per status | Integration | `test_transition_endpoints_ineligible_status_returns_409_with_allowed_events` (parametrized ×4) | `tests/integration/modules/support/test_support_router.py` |
| TC-AC5 / FR-6 | Service-level: same, `/resolve` from `resolved`/`closed`, `/reopen` from all four non-resolved statuses, `/close` from `closed` | Unit | `test_resolve_ticket_ineligible_status_raises_409_with_allowed_events` (×2), `test_reopen_ticket_non_resolved_status_raises_409` (×4), `test_close_ticket_already_closed_raises_409` | `tests/unit/modules/support/test_support_service.py` |
| Risk 2 (Decision 4's table) | `_ALLOWED_EVENTS_BY_STATUS` matches the plan's literal table, all five statuses | Unit | `test_allowed_events_by_status_matches_the_plan_s_stated_table` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC8 / FR-9 | Two agents resolving the same ticket: first succeeds, second gets `409`, first agent's note intact | Integration | `test_resolve_ticket_second_concurrent_caller_returns_409_first_note_intact` | `tests/integration/modules/support/test_support_router.py` |
| TC-AC8 / FR-9 | Service-level: conditional update loses the race → `409` with the pre-check `allowed_events`, no audit write | Unit | `test_resolve_ticket_concurrency_loss_raises_409_not_silent_overwrite` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC7 / FR-8 | Different customer → `404 not-found` on `/resolve`, `/close`, `/reopen` | Integration | `test_transition_endpoints_different_customer_returns_404` (parametrized ×3) | `tests/integration/modules/support/test_support_router.py` |
| TC-AC7 / FR-8 | Service-level: same, all three methods; unknown ticket id | Unit | `test_transition_endpoints_different_customer_raises_404` (parametrized ×3), `test_transition_endpoints_unknown_ticket_raises_404` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC2 / FR-2 | Requester closes: `200`, `closed_at` set, `closed_by=requester.id`, audit `actor_id=requester.id` | Integration | `test_close_ticket_requester_returns_200_and_persists_closed_by` | `tests/integration/modules/support/test_support_router.py` |
| FR-2 (OD-6/OD-7) | Agent closes: `200`, `closed_by=agent.id`, audit `actor_id=agent.id` | Integration | `test_close_ticket_agent_returns_200_and_persists_closed_by_agent` | `tests/integration/modules/support/test_support_router.py` |
| FR-2 | Close from `"resolved"` succeeds (broader source-status scope than FR-1's OD-5 set) | Integration | `test_close_ticket_from_resolved_returns_200` | `tests/integration/modules/support/test_support_router.py` |
| FR-2 | Service-level: requester close audits `actor_id=requester`; agent close audits `actor_id=agent`; close-from-resolved succeeds; commits exactly once | Unit | `test_close_ticket_requester_sets_closed_and_audits_self`, `test_close_ticket_agent_sets_closed_and_audits_agent`, `test_close_ticket_from_resolved_succeeds`, `test_close_ticket_commits_exactly_once` | `tests/unit/modules/support/test_support_service.py` |
| FR-2 (Open Questions #4) | `CloseTicketRequest`/`ReopenTicketRequest`: `reason` optional, unconstrained, defaults to `None`; rejects unknown field | Unit | `test_close_ticket_request_reason_omitted_defaults_to_none`, `test_close_ticket_request_accepts_reason`, `test_close_ticket_request_rejects_unknown_field`, `test_reopen_ticket_request_reason_omitted_defaults_to_none`, `test_reopen_ticket_request_accepts_reason`, `test_reopen_ticket_request_rejects_unknown_field` | `tests/unit/modules/support/test_support_schemas.py` |
| FR-5 | Requester reopens within window: `200`, `waiting_on_support`, `resolved_at` cleared, `ticket_reopened` audit `actor_id=requester.id` | Integration | `test_reopen_ticket_requester_within_window_returns_200_and_clears_resolved_at` | `tests/integration/modules/support/test_support_router.py` |
| FR-5 | Agent reopens within window: `200`, audit `actor_id=agent.id` | Integration | `test_reopen_ticket_agent_within_window_returns_200` | `tests/integration/modules/support/test_support_router.py` |
| FR-5 (API_DESIGN Open Questions #1, DESIGN_REVIEW DR-5) | Outside the window (documented fallthrough) → `409`, ticket unchanged | Integration | `test_reopen_ticket_outside_window_returns_409` | `tests/integration/modules/support/test_support_router.py` |
| OD-4 (boundary pairing — implementation-plan Testing Strategy's own called-out gap) | Exactly 7 days ago → reopen succeeds (inclusive guard) | Integration | `test_reopen_ticket_at_exactly_7_days_boundary_succeeds` | `tests/integration/modules/support/test_support_router.py` |
| FR-5 | Service-level: requester/agent reopen succeed and audit correctly; window-elapsed simulated via `transition_returns_none` → `409` with `allowed_events=["close","reopen"]`; commits exactly once | Unit | `test_reopen_ticket_requester_within_window_succeeds_and_audits_self`, `test_reopen_ticket_agent_succeeds_and_audits_agent`, `test_reopen_ticket_outside_window_raises_409_same_as_invalid_state`, `test_reopen_ticket_commits_exactly_once` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC4 / FR-4 (DESIGN_REVIEW v2 DR-4) | Customer reply on a resolved ticket within the window: reopens **and** writes a `ticket_reopened` audit row (new — previously unaudited) | Integration | `test_create_reply_customer_on_resolved_within_window_writes_reopened_audit_entry` | `tests/integration/modules/support/test_support_router.py` |
| TC-AC4 / FR-4 (implementation-plan Decision 2) | Customer reply on a resolved ticket outside the window: reply still accepted, no status change, no audit write | Integration | `test_create_reply_customer_on_resolved_outside_window_makes_no_status_change` | `tests/integration/modules/support/test_support_router.py` |
| TC-AC4 / FR-4 | Service-level: resolved-ticket reply reopen uses `transition_status(require_resolved_within_window=True, clear_resolved_at=True)` and audits `ticket_reopened`; the ordinary `waiting_on_customer` case is unaffected (still plain `update()`, no audit); window-elapsed reply makes no status write and no audit write | Unit | `test_create_reply_customer_on_resolved_reopens_to_waiting_on_support` (extended), `test_create_reply_customer_on_resolved_outside_window_makes_no_status_write` | `tests/unit/modules/support/test_support_service.py` |
| TC-AC3 / FR-3 (via repository — DB-conditional, `AGENTS.md` §5) | `resolved_at` strictly more than 7 days ago → closed, `closed_by=SYSTEM_ACTOR_ID`; exactly 7 days ago → untouched (OD-4 boundary pairing); within window → untouched; non-`resolved` status → untouched; reopened-since ticket survives despite a stale timestamp | Integration | `test_auto_close_resolved_past_window_closes_ticket_older_than_7_days`, `test_auto_close_resolved_past_window_leaves_ticket_at_exactly_7_days_untouched`, `test_auto_close_resolved_past_window_leaves_recently_resolved_ticket_untouched`, `test_auto_close_resolved_past_window_leaves_non_resolved_ticket_untouched`, `test_auto_close_resolved_past_window_reopened_ticket_survives` | `tests/integration/scripts/test_auto_close_resolved_tickets.py` |
| TC-AC3 / FR-3 (Decision 8 — per-ticket ids, not a count) | Batch of 3 eligible tickets returns exactly their 3 ids | Integration | `test_auto_close_resolved_past_window_returns_one_id_per_ticket_not_a_count` | `tests/integration/scripts/test_auto_close_resolved_tickets.py` |
| TC-AC3 / FR-3 (NFR — idempotent/safe to re-run) | Second immediate run returns `[]`, no double-close | Integration | `test_auto_close_resolved_past_window_is_idempotent_on_rerun` | `tests/integration/scripts/test_auto_close_resolved_tickets.py` |
| TC-AC3 / FR-3 | One `ticket_auto_closed` audit_log row per closed ticket, `actor_id=SYSTEM_ACTOR_ID`, via the same collaborator composition the script itself constructs (DESIGN_REVIEW v3's sentinel-actor confirmation) | Integration | `test_auto_close_job_writes_one_ticket_auto_closed_audit_row_per_ticket` | `tests/integration/scripts/test_auto_close_resolved_tickets.py` |
| `TicketStateRead` schema shape (Open Questions #5) | `from_attributes=True` reads a real ORM `Ticket`; `closed_by`/`resolution_note` never appear; `closed_at` present once closed | Unit | `test_ticket_state_read_from_attributes_excludes_closed_by_and_resolution_note`, `test_ticket_state_read_closed_at_present_once_closed` | `tests/unit/modules/support/test_support_schemas.py` |
| Authentication matrix (`AGENTS.md` §5: no token / malformed / expired / revoked) | All four cases × all three new routes → `401` | Integration | `test_transition_endpoints_auth_matrix_returns_401` (parametrized ×12) | `tests/integration/modules/support/test_support_router.py` |

## Gaps Not Covered (carried forward, not invented here)

- **API_DESIGN Open Questions #1 / DESIGN_REVIEW DR-5's undefined
  resolved-but-expired-not-yet-auto-closed response** — tested as the
  documented `409`-fallthrough behavior (see the matrix rows above), not
  flagged as an open gap in this pass; `implementation_plan.md` Risk 1
  states this default explicitly, so testing it as specified is not
  inventing scope.
- **DR-6 (partial index `CREATE INDEX CONCURRENTLY` mechanics)** and **DR-7
  (`reason` field maxLength)** — both Minor, non-blocking, carried through
  every prior stage without action; not test-writer's to resolve.
- **API_DESIGN Open Questions #4 (`reason` field's purpose/persistence/audit
  visibility)** — the schema accepts it (tested); no FR states it must be
  persisted or audited, so no persistence/audit assertion is made for it.
- **`scripts/auto_close_resolved_tickets.py`'s own `main()` wiring** (its
  from-`get_settings()` engine/Valkey-client construction) — see
  `US-4.3-test-strategy.md` Scope; the repository method and audit
  composition it calls are tested directly instead.
- **`migrations/env.py`'s expected zero-diff** and **`CREATE INDEX
  CONCURRENTLY`'s own reversibility** — `migration-manager`'s concern (T3),
  not duplicated here.
