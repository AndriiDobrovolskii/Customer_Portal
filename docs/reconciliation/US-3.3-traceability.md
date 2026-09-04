---
artifact_type: traceability
story: US-3.3
version: 1
status: ARCHIVED
created_at: 2026-09-03T00:00:00Z
updated_at: 2026-09-03T06:00:00Z
produced_by: reconciliation-reviewer
inputs:
  - path: docs/reviews/reconciliation/US-3.3-reconciliation.md
    version: 1
  - path: docs/tests/US-3.3-ac-test-matrix.md
    version: null
supersedes: null
note: >
  Backfilled 2026-09-03 by story-orchestrator during /so:archive. US-3.3 ran
  under the pre-migration stage vocabulary, where reconciliation-reviewer's
  AC-to-test cross-check was recorded only inside the combined reconciliation
  report and never split into this separate registry artifact. This file
  reproduces that same, already-approved AC to Test Reconciliation table
  verbatim (post gap-closure state) rather than re-deriving or re-judging it.
---

# Traceability Matrix: View Audit Information (US-3.3)

Source of record: `docs/reviews/reconciliation/US-3.3-reconciliation.md`
("AC → Test Reconciliation" section, post gap-closure state, 2026-09-03).
Reproduced here unmodified to satisfy the `traceability` registry artifact.

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| AU-AC1 | "Given an authenticated actor holding the audit:read permission When GET /v1/admin/audit-logs?actor_id=…&event=login_failed&from=…&to=…&limit=50 is called Then respond 200 with a cursor-paginated, newest-first list And each entry contains occurred_at, actor_id, actor_role, event, target_id, request_id, ip, user_agent, and an outcome" | Yes | `test_list_audit_logs_filtered_query_returns_200_newest_first`, `test_list_audit_logs_historical_rows_null_pad_unavailable_fields`, `test_list_audit_logs_no_matches_returns_empty_list`, `test_list_audit_logs_limit_over_max_returns_422`, `test_list_audit_logs_invalid_cursor_returns_422`, `test_list_audit_logs_applies_filters_and_pagination`, `test_list_audit_logs_response_entry_includes_all_nine_fields` | Yes (all 7) | Yes | Gap closed 2026-09-03 — new `test_list_audit_logs_response_entry_includes_all_nine_fields` (`test_audit_router.py`) inserts one `audit_log`-native row with every field populated and asserts all 9 response-entry fields match. |
| AU-AC2 | "Given any successful call to GET /v1/admin/audit-logs When the response is returned Then an audit entry is written (event=audit_log_viewed) recording the actor and the exact filter parameters used" | Yes | `test_list_audit_logs_success_writes_self_audit_entry`, `test_record_self_audit_writes_actor_and_filters` | Yes | Yes | Gap closed 2026-09-03 — test now supplies `actor_id`/`target_id`/`limit` filters and asserts all 7 `payload` keys the service writes. |
| AU-AC3 | "Given an authenticated support agent, who does not hold audit:read When GET /v1/admin/audit-logs is called Then respond 403 with type \".../errors/insufficient-permission\" And the denied attempt is itself recorded in the audit log" | Yes | `test_list_audit_logs_missing_scope_returns_403_and_audits_denial`, `test_record_access_denied_writes_entry` | Yes | Yes | Full AC coverage; asserts 403 + type slug + denial row's `actor_id`/`actor_role`/`outcome`. |
| AU-AC4 | "Given any actor, including an administrator When PATCH, PUT or DELETE is attempted on /v1/admin/audit-logs or any entry Then respond 405 Method Not Allowed" (amended — DB-grant clause moved to OD-12 follow-up) | Yes | `test_patch_audit_logs_returns_405`, `test_put_audit_logs_returns_405`, `test_delete_audit_logs_returns_405` | Yes (all 3) | Yes | Matches the story's amended, narrowed scope (API-level 405 only; DB-grant enforcement deferred per OD-12). |
| AU-AC5 | "Given a request whose from/to range exceeds 90 days, or which omits both bounds When GET /v1/admin/audit-logs is called Then respond 422 with type \".../errors/range-too-wide\" And the message states the maximum window and suggests the asynchronous export instead" | Yes | `test_list_audit_logs_window_over_90_days_returns_422_range_too_wide`, `test_list_audit_logs_both_bounds_omitted_returns_422_range_too_wide`, `test_list_audit_logs_single_missing_bound_returns_422`, `test_validate_window_rejects_over_90_days_and_both_omitted`, `test_validate_window_rejects_single_missing_bound` | Yes (all 5) | Yes | Gap closed 2026-09-03 — test now also asserts `response.json()["detail"]` contains "90 days" and "export". |
| AU-AC6 | "Given any audit entry of any event type When it is returned or inspected directly in storage Then no password, password hash, raw token, session cookie or full payment identifier appears in any field And fields marked sensitive are stored redacted..." | Yes | `test_list_audit_logs_response_contains_no_named_secrets`, `test_no_secret_shaped_literals_in_audit_write_call_sites` | Yes | Yes | AST scan (`tests/unit/test_audit_write_call_site_scan.py`) is the real, story-scoped mechanism; the integration test is a regression guard, honestly disclosed as such. |
| AU-AC7 | "Given every audit entry carries a previous_hash computed by a PostgreSQL BEFORE INSERT trigger... When the chain verification job runs... Then it reports 'intact' for an untouched chain And when any historical row is altered or removed by any means, the job reports the exact row at which the chain breaks And the hash column is computed server-side only" | Yes | `test_verify_audit_chain_untouched_partition_reports_intact`, `test_verify_audit_chain_mutated_row_reports_exact_break`, `test_audit_log_schema_has_no_hash_input_fields`, `test_verify_chain_detects_break_in_hash_sequence` | Yes (all 4) | Yes | Matrix-accuracy fix 2026-09-03: row corrected to name the real function (`test_verify_chain_detects_break_in_hash_sequence`, no `_audit` infix). Tail-row-deletion gap disclosed as not testable as scoped. |
| AU-AC8 | "Given a user account permanently deleted or anonymised... Then the entries remain, with actor_id retained as an opaque UUID And every direct identifier they contained (email, display_name, ip) is redacted or anonymised" | Yes | `test_anonymize_erased_user_anonymizes_users_row_and_redacts_auth_audit_ip`, `test_anonymize_erased_user_does_not_remove_audit_entries`, `test_anonymize_erased_user_leaves_profile_audit_log_untouched` | Yes (all 3) | Yes | Matrix-accuracy fix 2026-09-03: row updated to name the existing negative-proof test. `profile_audit_log` redaction itself remains out of scope per OD-20 (DB-enforced append-only trigger makes the original UPDATE-based mechanism technically impossible). |
| AU-AC9 | "Given an audit entry older than the 400-day retention period... Then the entry is moved to cold storage... And the job's own execution is recorded" | Yes | — | N/A | N/A | Out of scope for US-3.3 (OD-18, user-resolved 2026-09-02), blocked on OD-9's pending legal/DPO sign-off. Deliberate, user-approved scope narrowing, not a missing-coverage gap. |

## Spec Drift

None found. Every divergence from the AC's literal text traces to an explicit,
user-approved Open Decision (OD-10/OD-12/OD-13/OD-18/OD-20), disclosed in both
the spec's own Traceability Matrix and `docs/decisions/US-3.3-open-decisions.md`.

## Verdict

**Pass** — see `docs/reviews/reconciliation/US-3.3-reconciliation.md` for the
full verdict rationale and the two-pass gap-closure history.
