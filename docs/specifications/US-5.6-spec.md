---
artifact_type: specification
story: US-5.6
version: 2
status: APPROVED
created_at: "2026-09-15T07:37:55Z"
updated_at: "2026-09-15T08:00:00Z"
produced_by: story-spec-writer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/evidence/US-5.6-clarification-report.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 1
supersedes: null
---

# Specification: Global Navigation

**Source:** docs/stories/US-5.6-global-navigation.md
**Story ID:** US-5.6
**Generated:** 2026-09-15
**Status:** Draft

## Summary

This Story completes the shared navigation already hosted by `AppShell.tsx`: it adds nav entries for the account self-service screens that currently have none, adds a "Home" control that returns the user to a start page, and makes the current section visually distinguishable as the user moves between routes. It adds no new screen or backend endpoint — it makes screens already shipped by prior Stories reachable and orients the user inside them.

## Background

`AppShell.tsx` already hosts one shared `<nav>` rendered above every authenticated route (`AppRoutes.tsx`'s single `ProtectedRoute`/`AppShell` group), so the "one shell for every page" structure from prior Stories is already correct. Three concrete gaps remain: the nav lists only `Tickets`, and, scope-gated, `Agent Queue` / `Users` / `Audit Log` — US-5.2's account self-service screens (`/settings/profile`, `/settings/security`, `/settings/deactivate`, `/sessions`) have no nav entry at all today; every link is a plain `react-router-dom` `Link`, so nothing marks which one matches the current route; and `"/"` redirects straight to `/tickets` with no logo or "Home" control a user can click from deep inside e.g. Admin or Agent screens to return to a start page.

## Functional Requirements

### FR-1: Persistent shared navigation

A signed-in user on any route inside the `ProtectedRoute`/`AppShell` group sees the shared nav, and it remains visible and unchanged across route transitions — transitioning between routes does not trigger a full page reload.

**Derived from:** GN-AC1

### FR-2: Full nav link coverage with existing scope gating

The nav presents one entry for every existing frontend screen: Tickets, Sessions, Profile, Security, Deactivate Account, and — scope-gated exactly as today — Agent Queue, Users, and Audit Log. A signed-in user who lacks the gating scope for a given entry does not see that entry. The navigation entries are rendered as a flat list, without nested dropdowns or explicitly grouped sections, matching the current UI convention.

**Derived from:** GN-AC2; flat-list rendering resolves OD-3 (see Open Questions)

### FR-3: Client-side routing on nav activation

When a signed-in user clicks a nav entry, the target screen renders via client-side routing — no full page reload occurs — and the browser URL updates to match the target screen.

**Derived from:** GN-AC3

### FR-4: Return-to-start ("Home") control

A "Home" control (or clickable logo) is present in the nav on every page a signed-in user can reach. Clicking it navigates to `/tickets`.

**Boundary Condition:** For staff-only accounts (e.g., pure admin or auditor) lacking `tickets:*` scopes, navigating to `/tickets` renders an empty customer-branch ticket list. This is expected behavior for this iteration and must not throw a 404/403 or require a new dashboard screen.

**Derived from:** GN-AC4; target confirmed at `HUMAN_SPEC_APPROVAL` (resolves OD-1, see Open Questions)

### FR-5: Active-state indication for the current nav entry

Once a signed-in user has navigated to a page via a nav entry, that entry is visually distinguished (e.g., a distinct class or style) from the other nav entries. This distinction updates correctly as the user continues to navigate.

**Home Exception:** The "Home"/logo control is exempt from this mechanism and never shows an active state, even when on `/tickets`, ensuring only the "Tickets" text entry carries the active marker.

**Nested Routes:** Parent nav entries (e.g., "Tickets," "Users") remain active when the user is on nested child/detail routes (e.g., `/tickets/:id`, `/admin/users/new`) via prefix matching.

**Derived from:** GN-AC5; Home Exception resolves OD-2, Nested Routes resolves OD-4 (see Open Questions)

### FR-6: No dead nav links

For every nav entry, under any combination of scopes, the entry's target resolves to a route registered in `AppRoutes.tsx`. No nav entry renders a blank screen or a 404.

**Derived from:** GN-AC6

## API / Persistence Impact

This Story explicitly changes no public API behavior — no new or modified endpoint, request/response schema — and no persistence behavior: it extends only `AppShell.tsx`'s existing nav using screens and routes prior Stories already shipped.

**Derived from:** Out of Scope section of the source Story ("Any new screen or backend endpoint"; "Restructuring `AppRoutes.tsx`'s existing route groups or guards"), corroborated by the clarification report's Dependency Check ("No backend Story is a dependency; this Story changes no API/DB").

## Validation and Error Handling

The source Story states no input-validation rules (the nav presents fixed, route-derived entries; there is no user input to validate) and no error-handling behavior beyond GN-AC6's requirement that no nav entry render a blank screen or a 404.

**Derived from:** GN-AC6; absence of any other validation/error-handling statement in the source Story.

## Non-Functional Requirements

- Client-side scope decoding used to show/hide nav entries remains cosmetic only; no nav change alters server-side authorization.
- Full keyboard navigation and visible focus are provided on every nav entry; the active entry must be programmatically determinable (not by colour alone) for screen readers.
- No regression to existing nav entries' behavior, scope gating, or `LogoutControls`/`MfaEnrollmentBanner` placement.

**Derived from:** Non-Functional / Security Requirements section of the source Story.

## Out of Scope

- Any new screen or backend endpoint
- A dedicated dashboard/landing screen distinct from `/tickets` (confirmed by OD-1's resolution — see Open Questions)
- Restructuring `AppRoutes.tsx`'s existing route groups or guards
- Role-based menu personalization beyond the scope checks already used by prior Stories (US-5.4/US-5.5)

**Derived from:** Out of Scope section of the source Story.

## Open Questions

The source Story's own Assumptions & Defaults and Open Questions, together with `us-clarifier`'s clarification pass, identified four Open Decisions. All four were **resolved at `HUMAN_SPEC_APPROVAL`** and written back into the Functional Requirements above (not left only in this table), per the precedent flagged in `docs/reviews/specifications/US-5.6-spec-review.md`.

1. **OD-1 (High) — "Home" control target — RESOLVED.** The nav's "Home"/logo control links to `/tickets`, matching what `"/"` already redirects to (Story's Assumption #2); no distinct landing screen is introduced. For staff-only accounts without `tickets:*` scopes, this renders an empty ticket list — expected, not an error. See FR-4's Boundary Condition; full analysis in `docs/decisions/US-5.6-open-decisions.md`, OD-1.

2. **OD-2 (Medium) — Does "Home" itself carry active-state styling? — RESOLVED.** "Home" is exempt from the active-state mechanism and never shows active, even on `/tickets`; only "Tickets" carries the marker there. See FR-5's Home Exception; full analysis in `docs/decisions/US-5.6-open-decisions.md`, OD-2.

3. **OD-3 (Low) — Nav entry grouping vs. flat list — RESOLVED.** The nav remains a flat list, matching today's convention; no grouped/sectioned admin/agent entries. See FR-2; full analysis in `docs/decisions/US-5.6-open-decisions.md`, OD-3.

4. **OD-4 (Low) — Parent nav entry active state on nested child/detail routes — RESOLVED.** A parent nav entry (e.g., "Tickets," "Users") stays active on its nested child/detail routes via prefix matching. See FR-5's Nested Routes; full analysis in `docs/decisions/US-5.6-open-decisions.md`, OD-4.

## Verification

The source Story's own Enforcement Matrix names the intended verification mechanism per Acceptance Criterion; reproduced here so it travels forward to Test Writing (this is a `track: frontend` Story, so this Specification is the reference artifact `test-writer` uses — there is no separate API/DB design artifact).

| AC | Mechanism | Marker |
|---|---|---|
| GN-AC1, GN-AC3 | Integration test rendering `AppRoutes` in a `MemoryRouter`, asserting the nav persists and the route changes without a full reload | `[gate]` |
| GN-AC2 | Table-driven test over the full link set × scope combinations (including zero-scope) | `[gate]` |
| GN-AC4 | Test clicking Home from a non-`/tickets` route and asserting navigation to `/tickets` | `[gate]` |
| GN-AC5 | Test asserting the current route's nav entry carries the active marker and a different one does not | `[gate]` |
| GN-AC6 | Test cross-checking every nav `to=` against `AppRoutes.tsx`'s registered paths | `[gate]` |
| a11y | Automated a11y check (e.g. axe) on the nav in its authenticated state | `[gate]` |
| a11y-keyboard | Manual or integration test asserting that Tab/Shift-Tab focus reaches every visible nav entry in order, and Enter activates the link | `[gate]` |

**Derived from:** Enforcement Matrix section of the source Story.

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| GN-AC1 | "Given a signed-in user on any route inside the ProtectedRoute/AppShell group / Then the shared nav is visible, unchanged across route transitions (no full page reload)" | FR-1 |
| GN-AC2 | "Given a signed-in user viewing the nav / Then every existing frontend screen (Tickets, Sessions, Profile, Security, Deactivate Account, and — scope-gated as today — Agent Queue, Users, Audit Log) has a corresponding nav entry / And a user without a gating scope does not see that entry" | FR-2 |
| GN-AC3 | "Given a signed-in user on any page / When they click a nav entry / Then the target screen renders via client-side routing (no full page reload) / And the browser URL updates to match" | FR-3 |
| GN-AC4 | "Given a signed-in user on any page / Then a \"Home\" control (or clickable logo) is present in the nav / When clicked, it navigates to /tickets" | FR-4 (target choice resolved as OD-1) |
| GN-AC5 | "Given a signed-in user has navigated to a page via a nav entry / Then that entry is visually distinguished (e.g. a distinct class/style) from the others / And the distinction updates correctly as the user navigates further" | FR-5 ("Home"/shared-target and parent/child-route edge cases resolved as OD-2, OD-4) |
| GN-AC6 | "Given every nav entry rendered under any combination of scopes / Then each entry's target resolves to a registered route in AppRoutes.tsx / And none renders a blank screen or a 404" | FR-6 |

<!-- Every AC from the source appears above exactly once. GN-AC4 and GN-AC5 are each covered by an FR, but their unresolved edge cases (Home's shared-target styling, dashboard-vs-/tickets target) are additionally flagged against the relevant Open Question rather than silently decided. -->
