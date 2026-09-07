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
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
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
