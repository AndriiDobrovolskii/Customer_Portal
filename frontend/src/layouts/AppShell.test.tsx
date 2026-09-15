// Test for AppShell's logout/logout-all trigger (Task T7, FE-AC5).
// Layering note (docs/reviews/plans/US-5.1-plan-review.md's Low finding):
// AppShell's logout control is treated here as consuming `useLogout`/
// `useLogoutAll` (the `hooks/` layer) the same way a `screens/` component
// would — plan-reviewer flagged this as a categorization question for
// `AGENTS.md` §3's `routes/ (guards + layout)` row (which does not list
// `hooks/`), not a blocking defect, and left it for confirmation before
// IMPLEMENTATION. This test exercises the observable behavior only; it does
// not resolve which import-table row `AppShell.tsx` should ultimately sit
// under, since that is an IMPLEMENTATION/`AGENTS.md` §3 categorization
// decision, not a testable AC condition.
import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders, waitFor } from "../test/test-utils";
import { AppShell } from "./AppShell";
import { AppRoutes } from "../routes/AppRoutes";

describe("AppShell logout controls", () => {
  it("test_app_shell_log_out_calls_logout_endpoint_clears_session_and_lands_on_login", async () => {
    // Arrange
    let logoutCalled = false;
    server.use(
      http.post("/api/v1/auth/logout", async () => {
        logoutCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, { route: "/", isAuthenticated: true });

    // Act
    await user.click(screen.getByRole("button", { name: /^log out$/i }));

    // Assert
    expect(logoutCalled).toBe(true);
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  it("test_app_shell_log_out_everywhere_calls_logout_all_endpoint_with_same_client_effect", async () => {
    // Arrange
    let logoutAllCalled = false;
    server.use(
      http.post("/api/v1/auth/logout-all", async () => {
        logoutAllCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, { route: "/", isAuthenticated: true });

    // Act
    await user.click(screen.getByRole("button", { name: /log out everywhere/i }));

    // Assert
    expect(logoutAllCalled).toBe(true);
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });
});

// US-5.3 implementation_plan v2 Architectural Change 7: FR-15 adds a
// "/tickets" nav link (this file's first nav assertion — AppShell has no nav
// element at all before this Story), and MfaEnrollmentBanner's render site
// relocates here from the now-deleted PlaceholderHomeScreen.tsx, reading
// `mfaEnrollmentDeadline` off `useAuthStore()` directly (same store read
// PlaceholderHomeScreen used).
describe("AppShell navigation and MFA enrollment banner (US-5.3)", () => {
  // Isolates each test here from `mfaEnrollmentBannerDismissed` persistence
  // any other test in this suite may have written — the same sessionStorage
  // key MfaEnrollmentBanner.test.tsx's own tests write to (US-5.2 attempt-2
  // report's defect #2: a sibling test inheriting dismissed=true).
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("test_app_shell_renders_a_tickets_nav_link", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(screen.getByRole("link", { name: /tickets/i })).toHaveAttribute("href", "/tickets");
  });

  it("test_app_shell_renders_the_mfa_enrollment_banner_when_a_deadline_is_present", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      mfaEnrollmentDeadline: "2026-09-20T00:00:00Z",
    });

    // Assert
    expect(screen.getByRole("status")).toHaveTextContent(/2026-09-20|deadline/i);
  });

  it("test_app_shell_renders_no_banner_when_no_deadline_is_present", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      mfaEnrollmentDeadline: null,
    });

    // Assert
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

// US-5.4 FR-9/XC-AC1: scope-derived admin navigation (Task T17).
describe("AppShell admin navigation (US-5.4)", () => {
  it("test_app_shell_renders_the_users_and_audit_log_nav_entries_when_scopes_include_users_read_and_audit_read", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read"],
    });

    // Assert
    expect(screen.getByRole("link", { name: /^users$/i })).toHaveAttribute("href", "/admin/users");
    expect(screen.getByRole("link", { name: /audit log/i })).toHaveAttribute("href", "/admin/audit-logs");
  });

  it("test_app_shell_renders_no_admin_nav_entry_when_scopes_carry_no_admin_scope", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: [],
    });

    // Assert
    expect(screen.queryByRole("link", { name: /^users$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /audit log/i })).not.toBeInTheDocument();
    // US-5.6 GN-AC2: the five ungated entries (Tickets plus the four new
    // account self-service links) remain present at zero scope — extending,
    // not replacing, this case's existing negative assertions above.
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("href", "/tickets");
    expect(screen.getByRole("link", { name: /^sessions$/i })).toHaveAttribute("href", "/sessions");
    expect(screen.getByRole("link", { name: /^profile$/i })).toHaveAttribute("href", "/settings/profile");
    expect(screen.getByRole("link", { name: /^security$/i })).toHaveAttribute("href", "/settings/security");
    expect(screen.getByRole("link", { name: /deactivate account/i })).toHaveAttribute(
      "href",
      "/settings/deactivate",
    );
  });

  it("test_app_shell_renders_the_agent_queue_nav_entry_when_scopes_include_tickets_read", () => {
    // Arrange / Act: US-5.5 FR-11/Resolution OD-4.
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["tickets:read"],
    });

    // Assert
    expect(screen.getByRole("link", { name: /agent queue/i })).toHaveAttribute("href", "/agent/tickets");
  });

  it("test_app_shell_renders_no_agent_queue_nav_entry_when_scopes_carry_no_tickets_read_scope", () => {
    // Arrange / Act
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: [],
    });

    // Assert
    expect(screen.queryByRole("link", { name: /agent queue/i })).not.toBeInTheDocument();
    // US-5.6 GN-AC2: same extension as this describe block's admin-scope
    // sibling — the five ungated entries remain present at zero scope.
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("href", "/tickets");
    expect(screen.getByRole("link", { name: /^sessions$/i })).toHaveAttribute("href", "/sessions");
    expect(screen.getByRole("link", { name: /^profile$/i })).toHaveAttribute("href", "/settings/profile");
    expect(screen.getByRole("link", { name: /^security$/i })).toHaveAttribute("href", "/settings/security");
    expect(screen.getByRole("link", { name: /deactivate account/i })).toHaveAttribute(
      "href",
      "/settings/deactivate",
    );
  });

  it("test_app_shell_clears_admin_nav_entries_after_a_clear_session_dispatch", async () => {
    // Arrange: closes docs/reviews/plans/US-5.4-plan-review.md's Medium
    // finding that authStore.tsx's CLEAR_SESSION branch (scopes reset to
    // []) has no dedicated unit test — exercised here directly via the
    // existing logout control, which dispatches CLEAR_SESSION.
    server.use(http.post("/api/v1/auth/logout", async () => new HttpResponse(null, { status: 204 })));
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read"],
    });
    expect(screen.getByRole("link", { name: /^users$/i })).toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /^log out$/i }));

    // Assert
    await waitFor(() => expect(screen.queryByRole("link", { name: /^users$/i })).not.toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /audit log/i })).not.toBeInTheDocument();
  });
});

// US-5.6: completes the shared nav — account self-service entries, a "Home"
// control, active-state indication, and a dead-link cross-check. No new
// screen/route/backend behavior (spec v2 "API / Persistence Impact");
// FR/AC/OD references below trace to docs/specifications/US-5.6-spec.md v2.
describe("AppShell global navigation (US-5.6)", () => {
  it("test_app_shell_renders_all_four_new_ungated_nav_entries_by_accessible_name_and_href", () => {
    // Arrange / Act: FR-2/GN-AC2 — a representative granted-scope
    // combination (all three admin/agent gates open), so this proves the
    // four new ungated entries coexist with the gated ones, not merely that
    // they appear in isolation.
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read", "tickets:read"],
    });

    // Assert
    expect(screen.getByRole("link", { name: /^sessions$/i })).toHaveAttribute("href", "/sessions");
    expect(screen.getByRole("link", { name: /^profile$/i })).toHaveAttribute("href", "/settings/profile");
    expect(screen.getByRole("link", { name: /^security$/i })).toHaveAttribute("href", "/settings/security");
    expect(screen.getByRole("link", { name: /deactivate account/i })).toHaveAttribute(
      "href",
      "/settings/deactivate",
    );
  });

  it("test_app_shell_home_control_navigates_to_tickets_from_a_non_tickets_route", async () => {
    // Arrange: FR-4/GN-AC4, resolving OD-1 — Home always targets /tickets,
    // clicked here from a page deep inside account self-service.
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.click(screen.getByRole("link", { name: /^home$/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  it("test_app_shell_current_route_nav_entry_carries_aria_current_while_a_different_entry_does_not", () => {
    // Arrange / Act: FR-5/GN-AC5 — NavLink's own default marker is the
    // programmatically-determinable distinction the NFR requires (not
    // colour alone).
    renderWithProviders(<AppShell />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /^sessions$/i })).not.toHaveAttribute("aria-current");
  });

  it("test_app_shell_home_control_never_carries_aria_current_even_while_on_tickets", () => {
    // Arrange / Act: FR-5's Home Exception, resolving OD-2 — Home and
    // Tickets share the identical href="/tickets", so this assertion keys
    // on accessible name (role+name), not href, to tell them apart; only
    // "Tickets" may show the active marker here.
    renderWithProviders(<AppShell />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(screen.getByRole("link", { name: /^home$/i })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("aria-current", "page");
  });

  it("test_app_shell_tickets_nav_entry_stays_active_on_a_nested_ticket_detail_route", () => {
    // Arrange / Act: FR-5's Nested Routes, resolving OD-4 — a parent entry
    // stays active on its nested child/detail route via prefix matching
    // (NavLink's default, no `end` prop).
    renderWithProviders(<AppShell />, { route: "/tickets/42", isAuthenticated: true });

    // Assert
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("aria-current", "page");
  });

  it("test_app_shell_active_nav_entry_updates_after_navigating_to_a_different_entry", async () => {
    // Arrange: FR-5/GN-AC5 — "the distinction updates correctly as the user
    // continues to navigate," not just a one-shot render assertion.
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, { route: "/tickets", isAuthenticated: true });
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveAttribute("aria-current", "page");

    // Act
    await user.click(screen.getByRole("link", { name: /^sessions$/i }));

    // Assert
    expect(await screen.findByRole("link", { name: /^sessions$/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /^tickets$/i })).not.toHaveAttribute("aria-current");
  });

  it("test_app_shell_every_nav_href_resolves_to_a_real_registered_screen_under_full_scope", async () => {
    // Arrange: FR-6/GN-AC6, Architectural Change 5's behavioral cross-check
    // — render AppShell with every gate granted (Risk 5: a no-scope render
    // would silently never visit the gated entries), collect every nav
    // `href` from the rendered DOM (Home and Tickets share "/tickets", so
    // the Set below naturally dedupes to eight unique targets).
    const { unmount } = renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read", "tickets:read"],
    });
    const hrefs = new Set(
      screen
        .getAllByRole("link")
        .map((link) => link.getAttribute("href"))
        .filter((href): href is string => href !== null),
    );
    unmount();

    // Act / Assert: render AppRoutes at each collected href (authenticated,
    // same full scope set) and assert a real screen renders inside the
    // shared shell — not a blank body, and not a login-redirect artifact.
    // `route-location` alone cannot rule either out: it echoes
    // `initialEntries` even when nothing matched (blank body case), and an
    // unauthenticated-style redirect would still update it to a real path
    // (`/login`). The `navigation` landmark is unique to `AppShell.tsx` in
    // this codebase (confirmed by direct search — no other screen/layout
    // renders a `<nav>`), including `AuthLayout.tsx`'s `LoginScreen` render
    // site, so its presence is the discriminator: it can only be in the DOM
    // if the route matched *and* rendered inside the ProtectedRoute/AppShell
    // group, ruling out both a blank/404 render and a login-redirect.
    // mswHandlers.ts's baseline handlers already cover every on-mount fetch
    // these screens issue (docs/reviews/plans/US-5.6-plan-review.md's
    // Risk-Realism note).
    for (const href of hrefs) {
      const { unmount: unmountRoutes } = renderWithProviders(<AppRoutes />, {
        route: href,
        isAuthenticated: true,
        scopes: ["users:read", "audit:read", "tickets:read"],
      });
      expect(await screen.findByTestId("route-location")).toHaveTextContent(href);
      expect(screen.getByRole("navigation")).toBeInTheDocument();
      unmountRoutes();
    }

    // Assert: exactly eight unique nav targets were exercised above — Home
    // and Tickets share "/tickets", so the Set naturally dedupes to eight.
    // Asserted after the loop (not before) so the loop itself runs, and is
    // proven correct, against whatever hrefs AppShell renders today — this
    // count assertion is the only part of this test expected to fail before
    // IMPLEMENTATION adds the four new ungated entries and Home.
    expect(hrefs.size).toBe(8);
  });

  it("test_app_shell_nav_has_no_detectable_accessibility_violations_when_fully_scoped", async () => {
    // Arrange: Spec Verification's `a11y` row — automated axe check on the
    // nav in its authenticated, fully scoped state (net-new wiring in this
    // file, per Implementation Plan Risk 3).
    const { container } = renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read", "tickets:read"],
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });

  it("test_app_shell_nav_supports_full_keyboard_navigation_and_enter_activates_a_focused_entry", async () => {
    // Arrange: Spec Verification's `a11y-keyboard` row — Tab/Shift-Tab
    // reaches every visible nav entry in document order, and Enter
    // activates the focused link (RegisterScreen.test.tsx's existing
    // keyboard-floor pattern, extended with Enter-activation).
    const user = userEvent.setup();
    renderWithProviders(<AppShell />, {
      route: "/tickets",
      isAuthenticated: true,
      scopes: ["users:read", "audit:read", "tickets:read"],
    });

    // Act / Assert: forward order.
    await user.tab();
    expect(screen.getByRole("link", { name: /^home$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^tickets$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^sessions$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^profile$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^security$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /deactivate account/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /agent queue/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /^users$/i })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: /audit log/i })).toHaveFocus();

    // Act / Assert: Shift-Tab returns focus to the previous entry.
    await user.tab({ shift: true });
    expect(screen.getByRole("link", { name: /^users$/i })).toHaveFocus();

    // Act: Enter activates the currently focused entry (Users).
    await user.keyboard("{Enter}");

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/admin/users");
  });
});
