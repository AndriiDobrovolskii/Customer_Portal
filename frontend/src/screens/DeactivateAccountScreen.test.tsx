// Integration test for DeactivateAccountScreen (Task T10). PS-AC7/FR-7:
// `current_password` unconditionally required (OD-4's resolution), an
// explicit non-accidental confirmation step naming the consequence, and on
// 200 all in-memory auth state clears and the user lands on /login with a
// confirmation message. XC-AC1/FR-8, XC-AC2/FR-9, XC-AC3/FR-10, a11y bar.
//
// Field-label assumption (docs/tests/US-5.2-test-strategy.md): a "Current
// password" field, a "Deactivate account" trigger revealing a confirmation
// step naming the consequence, and a "Yes, deactivate my account" confirm
// button — the real route tree via a memory router, never a mocked
// `react-router-dom` module (Plan Testing Strategy).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AppRoutes } from "../routes/AppRoutes";
import { DeactivateAccountScreen } from "./DeactivateAccountScreen";

describe("DeactivateAccountScreen", () => {
  it("test_deactivate_account_screen_requires_current_password_unconditionally_and_blocks_submission_when_empty", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/account/deactivate", async () => {
        apiCalled = true;
        return HttpResponse.json(
          { status: "deactivated", deactivated_at: "2026-09-08T10:00:00Z" },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<DeactivateAccountScreen />, {
      route: "/settings/deactivate",
      isAuthenticated: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /deactivate account/i }));
    await user.click(screen.getByRole("button", { name: /yes, deactivate my account/i }));

    // Assert
    expect(await screen.findByText(/current password is required/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_deactivate_account_screen_confirmation_step_names_the_consequence_before_final_submit", async () => {
    // Arrange
    const user = userEvent.setup();
    renderWithProviders(<DeactivateAccountScreen />, {
      route: "/settings/deactivate",
      isAuthenticated: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /deactivate account/i }));

    // Assert
    // A broad /deactivat/i query is structurally ambiguous here: the <h1>
    // "Deactivate account", `renderWithProviders`'s own always-rendered
    // route-location probe ("/settings/deactivate"), and the "Yes,
    // deactivate my account" button below all match it too. Target the
    // consequence wording itself with the shortest fragment that stays
    // unique against those three, so minor copy wording elsewhere keeps
    // this test passing (test-strategy's documented "loose enough to
    // tolerate minor wording differences" matcher policy).
    expect(screen.getByText(/sign you out/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /yes, deactivate my account/i })).toBeInTheDocument();
  });

  it("test_deactivate_account_screen_successful_deactivation_clears_auth_state_and_lands_on_login_with_confirmation_message", async () => {
    // Arrange: rendered through the real route tree (Plan Testing Strategy note).
    server.use(
      http.post("/api/v1/account/deactivate", async () =>
        HttpResponse.json({ status: "deactivated", deactivated_at: "2026-09-08T10:00:00Z" }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AppRoutes />, { route: "/settings/deactivate", isAuthenticated: true });

    // Act
    await user.click(screen.getByRole("button", { name: /deactivate account/i }));
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /yes, deactivate my account/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
    expect(await screen.findByText(/deactivat/i)).toBeInTheDocument();
  });

  it("test_deactivate_account_screen_incorrect_password_renders_mapped_error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/account/deactivate", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-credentials",
            title: "Invalid credentials",
            status: 401,
            detail: "Your current password is incorrect.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<DeactivateAccountScreen />, {
      route: "/settings/deactivate",
      isAuthenticated: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /deactivate account/i }));
    await user.type(screen.getByLabelText(/current password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /yes, deactivate my account/i }));

    // Assert
    expect(await screen.findByText("Your current password is incorrect.")).toBeInTheDocument();
  });

  it("test_deactivate_account_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/account/deactivate", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<DeactivateAccountScreen />, {
      route: "/settings/deactivate",
      isAuthenticated: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /deactivate account/i }));
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /yes, deactivate my account/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_deactivate_account_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<DeactivateAccountScreen />, {
      route: "/settings/deactivate",
      isAuthenticated: true,
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
