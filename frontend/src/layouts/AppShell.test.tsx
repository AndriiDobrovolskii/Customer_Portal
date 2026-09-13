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
import { server } from "../test/mswServer";
import { renderWithProviders, waitFor } from "../test/test-utils";
import { AppShell } from "./AppShell";

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
