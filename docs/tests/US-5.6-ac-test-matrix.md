---
artifact_type: ac_test_matrix
story: US-5.6
version: 1
status: DRAFT
created_at: "2026-09-15T10:21:26Z"
updated_at: "2026-09-15T10:21:26Z"
produced_by: test-writer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
supersedes: null
---

# AC → Test Traceability Matrix: Global Navigation (US-5.6)

| AC ID | Acceptance Criterion (summary) | Test function(s) | File | Level |
|---|---|---|---|---|
| GN-AC1 | Shared nav visible and unchanged across route transitions, no full page reload | `test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` | `frontend/src/routes/AppRoutes.test.tsx` | Integration |
| GN-AC2 | Every existing screen has a nav entry; a user without the gating scope does not see it | `test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` (extended), `test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope` (extended), `test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href`, plus the four pre-existing US-5.4/US-5.5 admin-nav cases (`test_app_shell_renders_the_users_and_audit_log_nav_entries_when_scopes_include_users_read_and_audit_read`, `test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read`) which this Story leaves unmodified | `frontend/src/layouts/AppShell.test.tsx` | Integration |
| GN-AC3 | Clicking a nav entry renders the target via client-side routing and updates the URL | `test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` | `frontend/src/routes/AppRoutes.test.tsx` | Integration |
| GN-AC4 | A "Home" control is present and navigates to `/tickets` when clicked | `test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route` | `frontend/src/layouts/AppShell.test.tsx` | Integration |
| GN-AC5 | The current nav entry is visually/programmatically distinguished; the distinction updates as navigation continues | `test_app_shell_current_route_nav_entry_carries_aria_current_while_a_different_entry_does_not`, `test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets` (Home Exception / OD-2), `test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route` (Nested Routes / OD-4), `test_app_shell_active_nav_entry_updates_after_navigating_to_a_different_entry` | `frontend/src/layouts/AppShell.test.tsx` | Integration |
| GN-AC6 | Every nav entry's target resolves to a registered route; none renders a blank screen or a 404 | `test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope` | `frontend/src/layouts/AppShell.test.tsx` | Integration |
| a11y (Verification table) | Automated a11y check (axe) on the nav in its authenticated state | `test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped` | `frontend/src/layouts/AppShell.test.tsx` | Integration |
| a11y-keyboard (Verification table) | Tab/Shift-Tab reaches every visible nav entry in order; Enter activates the focused link | `test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry` | `frontend/src/layouts/AppShell.test.tsx` | Integration |

## Open Decisions Traced

- **OD-1** (Home target = `/tickets`, no dashboard) — asserted directly by
  `test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route` (GN-AC4 row).
- **OD-2** (Home exempt from active-state) — asserted directly by
  `test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets` (GN-AC5 row).
- **OD-3** (flat list, no grouping) — not independently testable as a DOM assertion (absence
  of a wrapping section element is a structural, not behavioral, property); the four new
  entries' presence as plain siblings is exercised by
  `test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href` and
  the two extended zero-scope cases, which query them by role/name without assuming any
  grouping container.
- **OD-4** (parent entries stay active on nested child/detail routes) — asserted directly by
  `test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route` (GN-AC5 row).

## Coverage Confirmation

Every AC in `docs/specifications/US-5.6-spec.md` v2's Traceability Matrix (GN-AC1 through
GN-AC6) and every row in its Verification table (including the two non-AC-numbered `a11y`/
`a11y-keyboard` rows) has at least one test function above. No AC is covered only implicitly
via prose; every row names an actual test function that exists in the repository (confirmed
by running `npx vitest run src/layouts/AppShell.test.tsx src/routes/AppRoutes.test.tsx` —
see `docs/evidence/US-5.6-test-generation-report.md` for the full run result).
