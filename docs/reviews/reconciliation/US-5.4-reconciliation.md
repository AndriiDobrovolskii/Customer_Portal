---
artifact_type: reconciliation
story: US-5.4
version: 1
status: DRAFT
created_at: "2026-09-13T22:40:00Z"
updated_at: "2026-09-13T22:40:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.4-spec-review.md
    version: 2
  - path: docs/reviews/designs/US-5.4-design-review.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/plans/US-5.4-task-breakdown.md
    version: 2
  - path: docs/reviews/plans/US-5.4-plan-review.md
    version: 2
  - path: docs/tests/US-5.4-test-strategy.md
    version: 1
  - path: docs/tests/US-5.4-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.4-test-generation-report.md
    version: 1
  - path: docs/evidence/US-5.4-implementation-report.md
    version: 2
  - path: docs/verification/US-5.4-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.4-security-review.md
    version: 1
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: null
---

# Reconciliation Report: Admin Console (Frontend)

**Story ID:** US-5.4
**Reviewed:** 2026-09-13
**Overall Verdict:** PASS

## Summary

Every Acceptance Criterion in spec v2 (AD-AC1 through AD-AC8, XC-AC1 through XC-AC4, 12 total) has a row in `ac-test-matrix.md` v1. All 98 named test functions were located, opened, and read in the actual working-tree files (not merely grepped for existence): 4 screen test files, 9 hook test files, `api/adminApi.test.ts`, `api/httpClient.test.ts`, `store/decodeTokenScopes.test.ts`, `layouts/AppShell.test.tsx`, and `routes/AppRoutes.test.tsx`. Every test's assertions were read and confirmed to exercise the real production component/hook/function (via MSW against real network calls, RTL against real rendered DOM — no `vi.mock()` on the units under test) and to assert the AC's actual stated behavior, not merely proximity to it (e.g. the AD-AC5 role-confirmation tests assert the literal Gained/Lost DOM text computed from a reordered seed; the AD-AC7 test is a source-wide static scan across >20 files, verified non-vacuous by a floor assertion). Spot checks of the underlying production source (`AdminUserListScreen.tsx`'s fixed `STATUS_OPTIONS`, `useUpdateAdminUser.ts`'s `UpdateAdminUserRequest` typing that structurally excludes `roles`, `decodeTokenScopes.ts`, `useAuditLogs.ts`) confirm the implementation matches the approved spec with no drift introduced during coding. No spec drift was found; three items are carried as non-blocking observations (one implementation superset, two limitations `test_strategy.md` already recorded as out of Vitest's reach rather than silently skipped).

## AC → Test Reconciliation

| AC ID | Acceptance Criterion (verbatim) | Matrix Row Exists | Test Function | Test Exists | Asserts AC Behavior | Notes |
|---|---|---|---|---|---|---|
| AD-AC1 | "Given an authenticated admin holding users:read on /admin/users Then GET /admin/users renders each user's email, display_name, status, roles, created_at and last_login_at And q / status / role filters re-request the list and reset the cursor And a non-null next_cursor drives a \"Load more\" that appends the next page And no total count or page number is displayed anywhere" | Yes | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_renders_email_display_name_status_roles_created_at_and_last_login_at_per_row`, `::test_admin_user_list_screen_q_status_role_filters_re_request_the_list_and_reset_the_cursor`, `::test_admin_user_list_screen_load_more_appends_the_next_page_and_disappears_when_next_cursor_is_null`, `::test_admin_user_list_screen_never_renders_a_total_count_or_page_number`, plus 4 `hooks/useAdminUsers.test.ts` unit tests | Yes | Yes | All six sub-claims independently asserted: per-row field rendering scoped to the row (`within(row)`), filter re-request via captured request params with cursor asserted `null`, Load-more page-append plus button-disappears-on-null-cursor, and total/page-number absence via negative text queries. |
| AD-AC2 `[gate]` | "GET /admin/users/{id} … ETag … captured … sent as If-Match on the next PATCH for that user" | Yes | `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_get_captures_the_etag_and_echoes_it_as_if_match_on_the_next_patch`; `hooks/useAdminUser.test.ts` (3 tests, incl. the cross-user isolation test) | Yes | Yes | The screen-level test asserts the literal received `If-Match` header equals the seeded `ETag`; the hook test additionally proves the ETag for user A is never readable under user B's cache key (Risk 4), and that a missing header leaves the key unset. |
| AD-AC3 `[gate]` | "…submit email, display_name and roles … POST /admin/users … exactly those fields and no password field … on 201 … new user's detail screen" | Yes | `screens/AdminUserCreateScreen.test.tsx` (4 tests) + `hooks/useCreateAdminUser.test.ts` (3 tests) | Yes | Yes | The screen test asserts `Object.keys(receivedBody)` equals exactly `["email","display_name","roles"]` (stronger than a subset check), a DOM-wide `input[type=password]` absence check, and role options sourced only from the seeded `GET /admin/roles` catalogue (OD-4). Navigation-on-201 test asserts the actual post-navigation route. |
| AD-AC4 `[gate]` | "…non-empty reason required… PATCH … If-Match and the reason… 412 shows a conflict state; an immutable-field problem renders its detail" | Yes | `screens/AdminUserDetailScreen.test.tsx` (3 tests) + `hooks/useUpdateAdminUser.test.ts` (3 tests) | Yes | Yes | Reason-required test asserts `patchCalled === false` (not merely that an error message rendered) and the specific alert text. The 412 test asserts the specific conflict-copy text; the immutable-field test asserts the exact `detail` string is rendered, not merely that an error state exists. |
| AD-AC5 `[gate]` | "…roles never in PATCH body… GET /admin/roles supplies the catalogue and PUT …/roles … full replacement list… role control disabled without roles:write, 403 still renders… confirmation naming gain/loss" | Yes | `screens/AdminUserDetailScreen.test.tsx` (8 tests) + `hooks/useAdminRoles.test.ts` (2) + `hooks/useReplaceUserRoles.test.ts` (2) + `hooks/useUpdateAdminUser.test.ts` (never-includes-roles) | Yes | Yes | `test_..._patch_never_includes_a_roles_field` asserts `receivedBody` lacks `roles` on every field-edit PATCH captured in that screen's tests. `test_..._role_save_hits_put...` asserts the literal PUT method and full replacement body. `test_..._confirmation_computes_gained_and_lost_role_sets_with_a_reordered_seed` uses a catalogue ordered differently from the user's current roles (Risk 6) and asserts the literal Gained/Lost DOM text, not just that a dialog appeared. Save-disabled/enabled tests directly assert button `disabled` state transitions. |
| AD-AC6 `[gate]` | "…deactivate … non-empty reason… POST …/deactivate … status reflected… resend-invite … POST …/resend-invite … generic confirmation" | Yes | `screens/AdminUserDetailScreen.test.tsx` (3 tests) + `hooks/useDeactivateAdminUser.test.ts` (2) + `hooks/useResendInvite.test.ts` (1) | Yes | Yes | Deactivate-reason test asserts `deactivateCalled === false` before a reason is supplied and that the confirmation form gates the action. Status-reflected test asserts the literal rendered "deactivated" text. Resend-invite test asserts the raw 202 body text (`ses message id`) is explicitly absent from the DOM — not merely that *a* confirmation rendered. |
| AD-AC7 `[gate]` | "…no control anywhere issues DELETE /admin/users/{id}" | Yes | `api/adminApi.test.ts::test_no_frontend_source_file_calls_http_delete_against_the_admin_users_path`, `::test_admin_api_ts_does_not_export_a_delete_user_function`; `screens/AdminUserDetailScreen.test.tsx::test_admin_user_detail_screen_never_renders_a_delete_control` | Yes | Yes | The static scan uses Vite's `import.meta.glob(...,{query:"?raw"})` over `/src/**/*.{ts,tsx}`, asserts >20 candidate files (guards against a vacuous pass from a misconfigured glob), and matches a regex tolerant of a generic type argument between `httpDelete` and its call parens. The implementation report separately records this was validated with a negative-control probe (a temporary `httpDelete<void>` call that was confirmed to fail the test, then removed) — this is a genuinely non-vacuous "anywhere" proof, the strongest mechanism available for this AC. |
| AD-AC8 `[gate]` | "…renders occurred_at, actor_id, actor_role, event, target_id, outcome, request_id, ip and user_agent… null values render an explicit placeholder… actor_id/event/target_id/from/to sent as query parameters, start-of-window parameter named \"from\"… non-null next_cursor drives Load more…" | Yes | `screens/AdminAuditLogScreen.test.tsx` (10 tests) + `hooks/useAuditLogs.test.ts` (4) + `api/adminApi.test.ts::test_list_audit_logs_sends_the_start_of_window_parameter_key_literally_as_from_not_from_` | Yes | Yes | All-nine-columns test scopes assertions to the entry's row. Placeholder test seeds 7 of 9 fields null and asserts exactly 7 `"—"` cells in that row (a superset of the spec's 6-field nullable list — `request_id` is also treated as nullable in `types.ts`/tested; this is a defensive superset of AD-AC8's generic "null values render a placeholder" wording, not a contradiction of it — see Spec Drift note below). OD-1 pre-fill test freezes the system clock and asserts the literal ISO-8601 `from`/`to` input values. OD-2 test asserts the `event` control is a plain `<input>` (`tagName === "INPUT"`) with an illustrative placeholder and that no `combobox` role exists. The `from`-not-`from_` unit test is a deliberately paranoid literal-key check. |
| XC-AC1 `[gate]` | "…no admin scopes… no admin nav entry… direct navigation… server's 403 rendered as not-permitted… users:read but not users:write… read screens render, write controls disabled" | Yes | `layouts/AppShell.test.tsx` (3 tests) + one 403/disabled-control test per screen (`AdminUserListScreen`, `AdminUserDetailScreen`, `AdminAuditLogScreen`) | Yes | Yes | Nav-entry tests assert `getByRole("link")`/`queryByRole("link")` presence and absence, not implementation detail. `test_app_shell_clears_admin_nav_entries_after_a_clear_session_dispatch` closes plan_review v2's named Medium finding on the untested `CLEAR_SESSION` scopes-reset branch by driving it through the real logout control end-to-end. `test_admin_user_detail_screen_users_read_only_seed_disables_every_write_control` asserts every one of the five write controls (edit-save, deactivate, resend-invite, roles select, role-save) individually. |
| XC-AC2 `[gate]` | "…4xx application/problem+json … renders its detail… no raw JSON… 422 … errors array maps onto matching form fields" | Yes | `screens/AdminUserListScreen.test.tsx::test_admin_user_list_screen_4xx_problem_json_renders_the_mapped_detail_with_no_raw_json`; `screens/AdminUserCreateScreen.test.tsx::test_admin_user_create_screen_422_validation_error_maps_the_errors_array_onto_the_matching_fields` | Yes | Yes | The 4xx test asserts both the mapped `detail` text renders AND that raw `"type":`/`"title":` JSON fragments are absent — a genuine two-sided assertion, not just a happy-path detail check. |
| XC-AC3 `[gate]` | "…empty/malformed required field… blocked with a field-level error and no API call is made" | Yes | `screens/AdminUserCreateScreen.test.tsx` (2 tests) + shared row with AD-AC4's reason-required test | Yes | Yes | Both tests assert `apiCalled === false` via a handler-side flag, not merely that an error rendered — this is the specific "no API call is made" half of the AC, independently proven. |
| XC-AC4 `[gate]` | "…network error or 5xx… retry-capable error state… never a blank screen, indefinite spinner, or unhandled exception" | Yes | One `network_error` + one `5xx` test per all four screens (8 tests total) | Yes | Yes | Every test asserts a `getByRole("button",{name:/retry/i})` is present, using `HttpResponse.error()` for the network-error case and an explicit `500` for the 5xx case — a real retry affordance, not merely "no crash". |

### Non-numbered but plan-mandated coverage (checked, not part of the 12 ACs)

- `httpPut` wrapper (Architectural Change 2): `api/httpClient.test.ts::test_http_put_sends_a_put_request_with_the_json_body_and_returns_the_parsed_response` — exists, asserts method/body/parsed-return.
- `decodeTokenScopes` (Architectural Change 1): 6 tests in `store/decodeTokenScopes.test.ts` (matrix names 3; 3 additional defensive cases — null/undefined token, non-array `scopes` claim, non-JSON payload — were also found, all passing, a superset of the prescribed minimum, not a gap).
- Routing (`routes/AppRoutes.test.tsx`, 8 tests): all four new routes' render-and-redirect-to-login pairs exist and assert the real rendered heading / redirected location.
- Loading state per screen (4 tests) and console-hygiene NFR (1 test, `AdminAuditLogScreen`): all exist, all assert real DOM/console-spy state.
- a11y bar (3 tests, `AdminUserListScreen`/`AdminUserDetailScreen`/`AdminAuditLogScreen`): all exist and run `axe()` against a fully-rendered, populated screen (not an empty shell).

## Spec Drift

None found. Every spot-checked production file (`AdminUserListScreen.tsx`'s fixed `STATUS_OPTIONS = ["invited","active","deactivated"]`, `adminApi.ts`'s nine functions with no `deleteUser`, `useUpdateAdminUser.ts`'s `UpdateAdminUserRequest` type that structurally excludes `roles`, `decodeTokenScopes.ts`'s never-throws/never-verifies decoder, `useAuditLogs.ts`'s once-per-mount `useRef`-computed default window) matches the approved spec (v2) and implementation plan (v2) exactly, including the four Resolution OD-1–OD-4 behaviors incorporated into FR-3/FR-5/FR-8.

## Non-Blocking Observations

- **[Low] `request_id` is treated as nullable in the shipped implementation; the story's Client State Notes list only `actor_role`, `outcome`, `ip`, `user_agent`, `actor_id`, `target_id` as nullable (not `request_id`).** `frontend/src/api/types.ts:316` types `AuditLogEntry.request_id` as `string | null`, and `AdminAuditLogScreen.test.tsx`'s placeholder test seeds `request_id: null` and asserts 7 placeholder cells (not 6). This is a superset, not drift: AD-AC8's own literal text ("null values render an explicit placeholder rather than an empty cell") is not scoped to a specific field list, so treating one additional field defensively as nullable makes that sentence more true, not false — a genuinely `null` `request_id` from the backend renders correctly rather than as a blank cell or a crash. Not a matrix/test gap and not spec drift; recorded for visibility only.
- **[Low] Production-build console-hygiene NFR only proxy-tested in dev-mode Vitest.** Per `docs/tests/US-5.4-test-strategy.md`'s "Known gaps this pass records rather than papers over": the spec's NFR "No audit-log row content (`ip`, `user_agent`, `request_id`) is written to the browser console in production builds" is asserted by `AdminAuditLogScreen.test.tsx::test_admin_audit_log_screen_console_spy_records_no_call_containing_ip_user_agent_or_request_id` as a console-spy during the normal (dev-mode) Vitest run — a reasonable proxy, but the production-build-specific claim itself is not provable by a Vitest spy alone and was left to `frontend-builder`'s self-check plus `SECURITY_REVIEW` (both of which independently confirmed it via source-grep, per `implementation_verification` v1 and `security_review` v1). An approved, explicitly-recorded limitation, not a new gap discovered at this stage.
- **[Low] Responsive/viewport NFR not Vitest-testable.** Per the same `test_strategy.md` section: the spec's NFR "Responsive from ~375px through desktop; the audit table scrolls horizontally within its own container" has no automated assertion in this Story's test suite, consistent with US-5.3's identical recorded gap — this project has no viewport-emulation tool in its Vitest setup. An approved, explicitly-recorded limitation, not a new gap discovered at this stage.

## Verdict Rationale

All 12 ACs have a matrix row, every one of the 98 named test functions was opened in the real working-tree file and confirmed to exist verbatim, and every test's assertions were read and confirmed to exercise the real production code path (MSW-backed network calls, RTL-rendered real components, no `vi.mock()` on units under test) and to assert the AC's actual stated behavior rather than a weaker proxy for it. No spec drift was found. The three items above are non-blocking observations only — one is a defensive superset of an AC's own generic wording, and two are limitations `test_strategy.md` already recorded and reasoned about at `TEST_WRITING` rather than gaps discovered here. None weakens any test's assertion or contradicts any stated requirement, so none forces `CHANGES_REQUIRED`. Verdict: **PASS**.
