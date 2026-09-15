---
artifact_type: traceability
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T10:51:51Z"
updated_at: "2026-09-15T16:00:00Z"
produced_by: reconciliation-reviewer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/reviews/designs/US-5.6-design-review.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.6-task-breakdown.md
    version: 1
  - path: docs/tests/US-5.6-ac-test-matrix.md
    version: 1
  - path: docs/evidence/US-5.6-implementation-report.md
    version: 1
  - path: docs/verification/US-5.6-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.6-security-review.md
    version: 1
supersedes: null
---

# Traceability: Global Navigation (Frontend) — US-5.6

End-to-end AC → specification → design → test → code mapping. Every test function named below was
opened and confirmed present at the cited file:line in the current working tree this session (not
taken from `docs/tests/US-5.6-ac-test-matrix.md` v1 on trust), and its assertions were read in full.
`api_design`/`database_design`/`entity_model` are `NOT_APPLICABLE` for this Story
(`docs/reviews/designs/US-5.6-design-review.md` v1's own Overall Verdict is `NOT_APPLICABLE` — a
pure nav-markup change with no backend/API/DB surface) — no design column applies below. See the
companion review, `docs/reviews/reconciliation/US-5.6-reconciliation.md` v1, for full method, the
OD-3 assessment, and verdict rationale.

Coverage legend: **Full** = every clause of the AC text is directly asserted by at least one test.

| AC ID | Spec (FR) | Plan (Architectural Change) | Test file(s) : function(s) | Production code | Coverage |
|---|---|---|---|---|---|
| GN-AC1 | FR-1 | Change 3 (`Link`→`NavLink` conversion; nav markup unaffected by route transitions) | `routes/AppRoutes.test.tsx::test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` | `frontend/src/layouts/AppShell.tsx` (nav markup, unchanged shell across `<Outlet/>` transitions) | Full |
| GN-AC2 | FR-2 | Change 1 (four new ungated entries), Change 3 (`NavLink` conversion) | `layouts/AppShell.test.tsx::test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href`, `::test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope` (extended), `::test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope` (extended), `::test_app_shell_renders_the_users_and_audit_log_nav_entries_when_scopes_include_users_read_and_audit_read` (pre-existing, unmodified), `::test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read` (pre-existing, unmodified) | `frontend/src/layouts/AppShell.tsx` | Full — the nav's 8 unique targets were independently cross-checked against `frontend/src/routes/AppRoutes.tsx:77-111`'s top-level (non-child) route set this session and found to match exactly, confirming completeness, not just each entry's individual validity |
| GN-AC3 | FR-3 | Change 3 | `routes/AppRoutes.test.tsx::test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav` | `frontend/src/layouts/AppShell.tsx`, `frontend/src/routes/AppRoutes.tsx` (unmodified — route table already registered every target) | Full |
| GN-AC4 | FR-4 (Boundary Condition: empty ticket list for staff-only accounts, resolves OD-1) | Change 2 (plain `Link`, not `NavLink`/`button`) | `layouts/AppShell.test.tsx::test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route` | `frontend/src/layouts/AppShell.tsx:49` (`<Link to="/tickets">Home</Link>`) | Full |
| GN-AC5 | FR-5 (Home Exception resolves OD-2; Nested Routes resolves OD-4) | Change 3 (`NavLink` default `aria-current`, no `end` prop; Home excluded) | `layouts/AppShell.test.tsx::test_app_shell_current_route_nav_entry_carries_aria_current_while_a_different_entry_does_not`, `::test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets`, `::test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route`, `::test_app_shell_active_nav_entry_updates_after_navigating_to_a_different_entry` | `frontend/src/layouts/AppShell.tsx:50-57` (nine `NavLink`s, no `end` prop) | Full |
| GN-AC6 | FR-6 | Change 5 (behavioral cross-check, not a hardcoded parallel list) | `layouts/AppShell.test.tsx::test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope` | `frontend/src/layouts/AppShell.tsx`, `frontend/src/routes/AppRoutes.tsx` (unmodified) | Full |

## Verification-table rows (no numbered AC; NFR/a11y, per spec v2's own Verification table)

| Row | Spec section | Test file : function | Production code | Coverage |
|---|---|---|---|---|
| a11y | Non-Functional Requirements / Verification table | `layouts/AppShell.test.tsx::test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped` | `frontend/src/layouts/AppShell.tsx` | Full — zero `axe` violations asserted on the fully-scoped, authenticated nav |
| a11y-keyboard | Non-Functional Requirements / Verification table | `layouts/AppShell.test.tsx::test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry` | `frontend/src/layouts/AppShell.tsx` | Full — Tab/Shift-Tab order over all 9 entries and Enter-activation both independently re-executed and confirmed passing this session (see companion reconciliation report's Method section) |

## Non-AC coverage confirmed present (technical/DoD-adjacent, not reconciled against a numbered AC)

| Item | Test / evidence | Status |
|---|---|---|
| No dead nav links across the full 8-target set | `test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope` collects all 8 unique `href`s (Home/Tickets dedupe to one) and renders each via `AppRoutes` | Present |
| Nav not remounted across a real client-side transition | `test_app_routes_clicking_a_nav_entry_routes_client_side_without_remounting_the_shared_nav`'s DOM-node-identity assertion | Present |
| Flat-list structure (OD-3) — negative assertion (no wrapping `<section>`/`role="menu"`) | — | **Absent** (Low, non-blocking; see companion reconciliation report's OD-3 Assessment — GN-AC2 itself remains fully covered) |

## Summary

All 6 ACs (GN-AC1 through GN-AC6) plus both Verification-table rows (`a11y`, `a11y-keyboard`) have
Full coverage against their stated behavior, independently re-verified against the current working
tree and re-executed test suite this session (`AppShell.test.tsx` 19/19, `AppRoutes.test.tsx`
31/31 — 50/50 total). No spec drift found comparing the shipped `AppShell.tsx` against spec v2 and
implementation plan v1. See `docs/reviews/reconciliation/US-5.6-reconciliation.md` v1 for full
findings, the OD-3 assessment, the a11y-keyboard re-execution evidence, and verdict rationale.
