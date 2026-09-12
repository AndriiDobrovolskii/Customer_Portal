// Full route-table test (Task T16, FE-AC10 both directions). Renders the
// real route tree in a memory router (per implementation-plan's Testing
// Strategy) — never a Vitest module mock of react-router-dom to spy on
// `useNavigate`. This file lives under `routes/`, outside
// `.pre-commit-config.yaml`'s `frontend-vi-mock-in-integration-tests` hook
// (scoped to `^frontend/src/screens/.*\.test\.tsx$`, confirmed by direct
// read); it contains no such call regardless, consistent with AGENTS.md
// §5's "no mocking the unit under test" rule applying repo-wide, not only
// where the hook happens to reach.
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AppRoutes } from "./AppRoutes";

describe("AppRoutes (FE-AC10)", () => {
  it("test_app_routes_unauthenticated_navigation_to_protected_route_redirects_to_login_and_back_after_successful_login", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json(
          { access_token: "access-token-1", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/sessions", isAuthenticated: false });

    // Act: redirected to /login first.
    expect(await screen.findByRole("heading", { name: /log in/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText(/email/i), "a@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    // Assert: lands back on the originally requested route, not the placeholder home.
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/sessions");
  });

  it("test_app_routes_authenticated_user_visiting_login_is_redirected_to_tickets", async () => {
    // Arrange / Act: US-5.3 FR-15/Change 11 — this redirect target moves
    // from the retired PlaceholderHomeScreen's "/" to "/tickets".
    renderWithProviders(<AppRoutes />, { route: "/login", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  it("test_app_routes_authenticated_user_visiting_register_is_redirected_to_tickets", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/register", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  // plan_review's Test-Strategy Realism [Low] finding: impact-analysis
  // implied "at least one full FR-2 login->placeholder-home flow and one
  // full FR-3 MFA-challenge->verify flow" beyond the per-screen/per-route
  // rows above. The FR-2 flow is already fully exercised, continuously,
  // by the first test in this file (unauthenticated -> /login -> submit
  // credentials -> lands back on the real originally-requested route,
  // rendered through the actual route tree, not in isolation). The FR-3
  // flow had no single continuous test anywhere in this pass's suite
  // (LoginScreen.test.tsx only proves the initial MFA-required branch;
  // MfaVerifyScreen.test.tsx only proves the second step in isolation) —
  // closed here, not left as a gap.
  it("test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_tickets", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json({ mfa_token: "mfa-token-1" }, { status: 200 }),
      ),
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          {
            access_token: "access-token-2",
            expires_in: 900,
            user: { id: "u1", email: "mfa-user@example.com" },
          },
          { status: 200 },
        ),
      ),
      // US-5.3: /tickets (the new post-verify landing target) renders
      // TicketListScreen, which calls GET /support/tickets on mount.
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/login", isAuthenticated: false });

    // Act: submit valid credentials for an MFA-enabled account.
    await user.type(screen.getByLabelText(/email/i), "mfa-user@example.com");
    await user.type(screen.getByLabelText(/password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    // Assert: navigated to the MFA-verify screen, mfa_token held only in transient state.
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/mfa-verify");

    // Act: submit a valid TOTP code.
    await user.type(screen.getByLabelText(/code/i), "123456");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert: the flow completes exactly as the non-MFA login flow does —
    // lands on /tickets (US-5.3 FR-15's new authenticated home).
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  // US-5.2 Plan Change 10: new ProtectedRoute-wrapped settings screens.
  it("test_app_routes_settings_profile_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/settings/profile", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  it("test_app_routes_settings_security_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/settings/security", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  it("test_app_routes_settings_deactivate_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/settings/deactivate", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  // US-5.2 Plan Change 10: /verify-email and /confirm-email-change sit
  // outside BOTH ProtectedRoute and GuestOnlyRoute — Plan Risk 9 calls out
  // explicitly that both directions must be asserted, not just one.
  it("test_app_routes_verify_email_renders_for_an_unauthenticated_visitor", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/verify-email?token=t", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/verify-email");
  });

  it("test_app_routes_verify_email_renders_for_an_authenticated_visitor", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/verify-email?token=t", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/verify-email");
  });

  it("test_app_routes_confirm_email_change_renders_for_an_unauthenticated_visitor", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/confirm-email-change?token=t", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/confirm-email-change");
  });

  it("test_app_routes_confirm_email_change_renders_for_an_authenticated_visitor", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/confirm-email-change?token=t", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/confirm-email-change");
  });

  // US-5.3 Change 11 / FR-15: "/" becomes a redirect to "/tickets", and
  // "/tickets", "/tickets/new", "/tickets/:id" become the new authenticated
  // route family, replacing PlaceholderHomeScreen.
  it("test_app_routes_root_redirects_authenticated_visitor_to_tickets", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AppRoutes />, { route: "/", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  it("test_app_routes_tickets_renders_ticket_list_screen", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            items: [
              {
                id: "t-1",
                ticket_number: "TCK-0001",
                subject: "s",
                category: "c",
                status: "open",
                updated_at: "2026-09-01T10:00:00Z",
              },
            ],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<AppRoutes />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
  });

  it("test_app_routes_tickets_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/tickets", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  it("test_app_routes_tickets_new_renders_new_ticket_screen_not_ticket_detail_screen", async () => {
    // Arrange: implementation_plan v2 Risk 9 — React Router v6 ranks the
    // static "/tickets/new" segment above the dynamic "/tickets/:id" when
    // both could match. Proven by rendered content (NewTicketScreen's
    // Subject field), not by a pathname substring match, since
    // "/tickets/new" would also satisfy toHaveTextContent("/tickets").
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/tickets/new", isAuthenticated: true });

    // Assert
    expect(await screen.findByLabelText(/subject/i)).toBeInTheDocument();
  });

  it("test_app_routes_tickets_new_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/tickets/new", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });

  it("test_app_routes_tickets_id_renders_ticket_detail_screen", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          {
            id: "t-1",
            ticket_number: "TCK-0001",
            status: "open",
            requester_id: "u-1",
            subject: "s",
            body: "b",
            category: "c",
            first_response_at: null,
            created_at: "2026-09-01T10:00:00Z",
            updated_at: "2026-09-01T10:00:00Z",
            replies: { items: [], next_cursor: null },
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<AppRoutes />, { route: "/tickets/t-1", isAuthenticated: true });

    // Assert: TicketDetailScreen-specific content renders; NewTicketScreen's
    // Subject field does not (ruling out the reverse misroute).
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
    expect(screen.queryByLabelText(/subject/i)).not.toBeInTheDocument();
  });

  it("test_app_routes_tickets_id_redirects_unauthenticated_visitor_to_login", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/tickets/t-1", isAuthenticated: false });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
  });
});
