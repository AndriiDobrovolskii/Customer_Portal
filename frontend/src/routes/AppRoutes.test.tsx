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

  it("test_app_routes_authenticated_user_visiting_login_is_redirected_to_placeholder_home", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/login", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/");
  });

  it("test_app_routes_authenticated_user_visiting_register_is_redirected_to_placeholder_home", async () => {
    // Arrange / Act
    renderWithProviders(<AppRoutes />, { route: "/register", isAuthenticated: true });

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/");
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
  it("test_app_routes_full_mfa_challenge_login_flow_from_credentials_through_verify_to_placeholder_home", async () => {
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
    // lands on the authenticated placeholder home.
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/");
  });
});
