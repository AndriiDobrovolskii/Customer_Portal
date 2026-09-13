---
artifact_type: traceability
story: US-5.4
version: 1
status: DRAFT
created_at: "2026-09-13T22:40:00Z"
updated_at: "2026-09-13T22:40:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/designs/US-5.4-design-review.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/tests/US-5.4-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.4-implementation-report.md
    version: 2
supersedes: null
---

# Traceability: Admin Console (Frontend) — US-5.4

End-to-end AC -> specification -> design -> test -> code mapping. `api_design` /
`openapi` / `database_design` / `entity_model` are `NOT_APPLICABLE` for this
Story (pure frontend consumer of already-shipped EPIC-3 endpoints) and are
omitted from the Design column accordingly.

| AC ID | Spec FR | Design | Task(s) | Test Function(s) | Production Code |
|---|---|---|---|---|---|
| AD-AC1 | FR-1 (User List) | N/A (no API/DB change) | T8, T18 | `hooks/useAdminUsers.test.ts` (4), `screens/AdminUserListScreen.test.tsx` (5) | `hooks/useAdminUsers.ts`, `screens/AdminUserListScreen.tsx` |
| AD-AC2 `[gate]` | FR-2 (ETag Capture) | N/A | T2, T9, T20 | `hooks/useAdminUser.test.ts` (3), `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_get_captures_the_etag_and_echoes_it_as_if_match_on_the_next_patch` | `api/httpClient.ts` (`httpGetWithMeta`), `hooks/useAdminUser.ts`, `screens/AdminUserDetailScreen.tsx` |
| AD-AC3 `[gate]` | FR-3 (Create User, OD-4) | N/A | T5, T10, T11, T19 | `screens/AdminUserCreateScreen.test.tsx` (4), `hooks/useCreateAdminUser.test.ts` (3) | `api/adminApi.ts` (`createUser`), `hooks/useAdminRoles.ts`, `hooks/useCreateAdminUser.ts`, `screens/AdminUserCreateScreen.tsx` |
| AD-AC4 `[gate]` | FR-4 (Edit Requires Reason) | N/A | T5, T12, T20 | `screens/AdminUserDetailScreen.test.tsx` (3), `hooks/useUpdateAdminUser.test.ts` (3) | `api/adminApi.ts` (`updateUser`), `hooks/useUpdateAdminUser.ts`, `screens/AdminUserDetailScreen.tsx` |
| AD-AC5 `[gate]` | FR-5 (Roles Separate Save Path, OD-3) | N/A | T10, T13, T20 | `screens/AdminUserDetailScreen.test.tsx` (8), `hooks/useAdminRoles.test.ts` (2), `hooks/useReplaceUserRoles.test.ts` (2), `hooks/useUpdateAdminUser.test.ts::test_use_update_admin_user_never_includes_roles_in_the_patch_body` | `api/adminApi.ts` (`listRoles`, `replaceUserRoles`), `hooks/useAdminRoles.ts`, `hooks/useReplaceUserRoles.ts`, `screens/AdminUserDetailScreen.tsx` |
| AD-AC6 `[gate]` | FR-6 (Deactivate / Resend Invite) | N/A | T14, T15, T20 | `screens/AdminUserDetailScreen.test.tsx` (3), `hooks/useDeactivateAdminUser.test.ts` (2), `hooks/useResendInvite.test.ts` (1) | `api/adminApi.ts` (`deactivateUser`, `resendInvite`), `hooks/useDeactivateAdminUser.ts`, `hooks/useResendInvite.ts`, `screens/AdminUserDetailScreen.tsx` |
| AD-AC7 `[gate]` | FR-7 (No Delete Affordance) | N/A | T5, T20 | `api/adminApi.test.ts` (2, incl. the source-wide static scan), `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_never_renders_a_delete_control` | `api/adminApi.ts` (no `deleteUser` export — proven by omission) |
| AD-AC8 `[gate]` | FR-8 (Audit Log Viewer, OD-1/OD-2) | N/A | T5, T16, T21 | `screens/AdminAuditLogScreen.test.tsx` (10), `hooks/useAuditLogs.test.ts` (4), `api/adminApi.test.ts::test_list_audit_logs_sends_the_start_of_window_parameter_key_literally_as_from_not_from_` | `api/adminApi.ts` (`listAuditLogs`), `hooks/useAuditLogs.ts`, `screens/AdminAuditLogScreen.tsx` |
| XC-AC1 `[gate]` | FR-9 (Scope-Derived Nav) | N/A | T3, T4, T17 | `layouts/AppShell.test.tsx` (3), one 403/disabled-control test per screen (`AdminUserListScreen.test.tsx`, `AdminUserDetailScreen.test.tsx`, `AdminAuditLogScreen.test.tsx`) | `store/decodeTokenScopes.ts`, `store/authStore.tsx`, `layouts/AppShell.tsx` |
| XC-AC2 `[gate]` | FR-10 (problem+json Rendering) | N/A | T18, T19 | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_4xx_problem_json_renders_the_mapped_detail_with_no_raw_json`, `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_422_validation_error_maps_the_errors_array_onto_the_matching_fields` | `api/errorNormalization.ts` (pre-existing, reused), all four screens |
| XC-AC3 `[gate]` | FR-11 (Client-Side Validation) | N/A | T19, T20 | `screens/AdminUserCreateScreen.test.tsx` (2), shared row with AD-AC4 in `screens/AdminUserDetailScreen.test.tsx` | `screens/AdminUserCreateScreen.tsx`, `screens/AdminUserDetailScreen.tsx` |
| XC-AC4 `[gate]` | FR-12 (Network / Server Failure) | N/A | T18, T19, T20, T21 | Network-error + 5xx test pair per screen, all four screens (8 tests) | All four screens' error-state rendering |

## Supporting infrastructure (underlies multiple ACs, not itself a numbered AC)

| Item | Task | Test Function(s) | Production Code |
|---|---|---|---|
| `httpPut` wrapper (underlies AD-AC5) | T2 | `api/httpClient.test.ts::test_http_put_sends_a_put_request_with_the_json_body_and_returns_the_parsed_response` | `api/httpClient.ts` |
| `httpGetWithMeta` (underlies AD-AC2; additive beyond plan's named exports, per gate-enforcer non_blocking_findings) | T2 | `api/httpClient.test.ts` (2 tests) | `api/httpClient.ts` |
| `decodeTokenScopes` (underlies FR-9/XC-AC1) | T3 | `store/decodeTokenScopes.test.ts` (6 tests) | `store/decodeTokenScopes.ts` |
| Routing (underlies every screen being reachable) | T22 | `routes/AppRoutes.test.tsx` (8 tests) | `routes/AppRoutes.tsx` |
| Explicit loading state per screen (spec NFR) | T18-T21 | One test per screen (4 tests) | All four screens |
| Console hygiene (spec NFR) | T21 | `screens/AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_console_spy_records_no_call_containing_ip_user_agent_or_request_id` | `screens/AdminAuditLogScreen.tsx` |
| a11y bar (Enforcement Matrix `[gate]` row) | T18, T20, T21 | One `axe()` test per named screen (3 tests) | `AdminUserListScreen.tsx`, `AdminUserDetailScreen.tsx`, `AdminAuditLogScreen.tsx` |

## Coverage Summary

- 12/12 spec ACs (AD-AC1–AD-AC8, XC-AC1–XC-AC4) have a matrix row, a confirmed-existing test, and a confirmed behavior-matching assertion.
- 98/98 test functions named in `ac-test-matrix.md` v1 were found verbatim in the working tree across 17 test files.
- `api_design`/`openapi`/`database_design`/`entity_model` are `NOT_APPLICABLE` for this Story; no design-artifact column entries apply.
- Zero spec drift found. Three Low-severity, non-blocking observations (`request_id` treated as nullable beyond the story's literal Client State Notes list; the production-build console-hygiene NFR and the responsive/viewport NFR, both explicitly recorded as out of Vitest's reach by `test_strategy.md`) are carried in `docs/reviews/reconciliation/US-5.4-reconciliation.md`'s Non-Blocking Observations section — none is a coverage gap.
