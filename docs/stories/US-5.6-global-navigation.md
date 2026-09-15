---
id: US-5.6
epic: EPIC-5
title: Global Navigation
slug: global-navigation
priority: MEDIUM
track: frontend
source:
  type: local_only
  repository: null
  issue_number: null
  issue_url: null
  last_synced_at: null
---

# Epic 5 — Frontend: Global Navigation

**Story ID:** US-5.6
**Project:** Customer Portal
**Depends on:** US-5.1 (auth store, route guards, `AppShell`), US-5.2 (account self-service screens), US-5.3 (customer ticket screens), US-5.4 (admin console), US-5.5 (agent console) — this Story adds no new screens of its own, it makes the ones already shipped reachable and orients the user inside them

## User Story
As a portal user,
I want a single navigation menu (or a main dashboard) with buttons to reach every module,
So that I can move freely between pages and use the full functionality of the system without typing URLs into the address bar by hand.

_(Original Ukrainian text supplied by the requester is preserved verbatim in this Story's PR/issue history for traceability; the English above is a faithful translation, not a paraphrase that drops a clause.)_

## Current State (why this Story exists)
`AppShell.tsx` already hosts one shared `<nav>` rendered above every authenticated route (`AppRoutes.tsx`'s single `ProtectedRoute`/`AppShell` group), so the "one shell for every page" structure from prior Stories is already correct. Three concrete gaps remain:
1. **Incomplete link set** — the nav lists only `Tickets`, and, scope-gated, `Agent Queue` / `Users` / `Audit Log`. US-5.2's account self-service screens (`/settings/profile`, `/settings/security`, `/settings/deactivate`, `/sessions`) have no nav entry at all today.
2. **No active-state indication** — every link is a plain `react-router-dom` `Link`; nothing marks which one matches the current route.
3. **No "Home"** — `"/"` redirects straight to `/tickets` (US-5.3 Change 11 retired the placeholder home screen); there is no logo or "Home" control a user can click from deep inside e.g. Admin or Agent screens to return to a start page.

## Assumptions & Defaults (confirm or override)
| # | Decision | Default chosen | Rationale |
|---|---|---|---|
| 1 | Scope | Extend the existing `AppShell.tsx` nav; no new routing library, no new layout component | One shell already exists and is correct in structure — this is a completeness/UX fix, not a rebuild |
| 2 | "Home" target | The nav's logo/"Home" control links to `/tickets` (the same destination `"/"` already redirects to) — no new dashboard screen is introduced | Matches US-5.3 Change 11's existing decision that `/tickets` *is* the customer's landing page; inventing a second "home" concept would contradict it. **Open Decision — confirm before IMPLEMENTATION.** |
| 3 | Link set | One nav entry per screen already routed in `AppRoutes.tsx`, each gated by the same scope check (or none) the route/screen itself already enforces cosmetically | AC2 says "existing frontend pages that correspond to shipped backend functionality" — enumerated from `screens/`, not invented |
| 4 | Active-state mechanism | Swap `Link` for React Router's own `NavLink` (`isActive`-driven class), no new state or matching logic | Built into the router already in use; avoids hand-rolled path matching |
| 5 | Permission gating | Cosmetic only, same convention as US-5.4/US-5.5 (`useAuthStore().scopes`) — never the enforcement boundary | Consistent with every existing nav entry; server-side 403 remains authoritative |

## In Scope
- Add nav entries for every existing authenticated screen with no current nav link: Profile (`/settings/profile`), Security (`/settings/security`), Sessions (`/sessions`), Deactivate Account (`/settings/deactivate`)
- Add a "Home"/logo control in the nav that always links to `/tickets`
- Replace `Link` with `NavLink` (or equivalent) across the nav so the current section is visually distinguished from the rest
- Verify every nav `to=` target has a matching route in `AppRoutes.tsx` (no dead links)

## Out of Scope
- Any new screen or backend endpoint
- A dedicated dashboard/landing screen distinct from `/tickets` (see Assumption #2 — Open Decision)
- Restructuring `AppRoutes.tsx`'s existing route groups or guards
- Role-based menu personalization beyond the scope checks already used by US-5.4/US-5.5

## Acceptance Criteria

**GN-AC1 — Nav present on every authenticated page**
```gherkin
Given a signed-in user on any route inside the ProtectedRoute/AppShell group
Then the shared nav is visible, unchanged across route transitions (no full page reload)
```

**GN-AC2 — Full link coverage**
```gherkin
Given a signed-in user viewing the nav
Then every existing frontend screen (Tickets, Sessions, Profile, Security, Deactivate Account,
  and — scope-gated as today — Agent Queue, Users, Audit Log) has a corresponding nav entry
And a user without a gating scope does not see that entry
```

**GN-AC3 — Client-side routing**
```gherkin
Given a signed-in user on any page
When they click a nav entry
Then the target screen renders via client-side routing (no full page reload)
And the browser URL updates to match
```

**GN-AC4 — Return to start**
```gherkin
Given a signed-in user on any page
Then a "Home" control (or clickable logo) is present in the nav
When clicked, it navigates to /tickets
```

**GN-AC5 — Active state**
```gherkin
Given a signed-in user has navigated to a page via a nav entry
Then that entry is visually distinguished (e.g. a distinct class/style) from the others
And the distinction updates correctly as the user navigates further
```

**GN-AC6 — No dead links**
```gherkin
Given every nav entry rendered under any combination of scopes
Then each entry's target resolves to a registered route in AppRoutes.tsx
And none renders a blank screen or a 404
```

## Non-Functional / Security Requirements
- Client-side scope decoding remains cosmetic only; no nav change alters server-side authorization.
- Full keyboard navigation and visible focus on every nav entry; the active entry is programmatically determinable (not colour alone) for screen readers.
- No regression to existing nav entries' behavior, scope gating, or `LogoutControls`/`MfaEnrollmentBanner` placement.

## Enforcement Matrix
| AC | Mechanism | Marker |
|---|---|---|
| GN-AC1, GN-AC3 | Integration test rendering `AppRoutes` in a `MemoryRouter`, asserting the nav persists and the route changes without a full reload | `[gate]` |
| GN-AC2 | Table-driven test over the full link set × scope combinations (including zero-scope) | `[gate]` |
| GN-AC4 | Test clicking Home from a non-`/tickets` route and asserting navigation to `/tickets` | `[gate]` |
| GN-AC5 | Test asserting the current route's nav entry carries the active marker and a different one does not | `[gate]` |
| GN-AC6 | Test cross-checking every nav `to=` against `AppRoutes.tsx`'s registered paths | `[gate]` |
| a11y | Automated a11y check (e.g. axe) on the nav in its authenticated state | `[gate]` |

## Open Questions
1. **Assumption #2 (Home target = `/tickets`, no new dashboard screen)** must be confirmed or overridden before IMPLEMENTATION — it is the one choice that changes this Story's size (a nav-only fix vs. a new landing screen).
2. Should the "Users"/"Audit Log"/"Agent Queue" nav entries be visually grouped (e.g. an "Admin" or "Agent" section) now that the full link set is longer, or kept as a flat list matching today's convention? Left to IMPLEMENTATION unless the requester has a preference.
