// Integration test for ResetPasswordScreen (Task T13). FE-AC7's confirm
// half, FE-AC8 (12-char client rule, PLUS the explicit test that
// breach-check/differs-from-current are NOT simulated client-side per
// implementation-plan Architectural Change 7), FE-AC9, FE-AC11.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { ResetPasswordScreen } from "./ResetPasswordScreen";

describe("ResetPasswordScreen", () => {
  it("test_reset_password_screen_valid_token_and_policy_compliant_password_succeeds_and_lands_on_login_with_success_message", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () => new HttpResponse(null, { status: 200 })),
    );
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=valid-token" });

    // Act
    await user.type(screen.getByLabelText(/new password/i), "Correct-Horse-Battery-Staple-9!");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
    expect(await screen.findByText(/password.*reset/i)).toBeInTheDocument();
  });

  it("test_reset_password_screen_blocks_submission_below_12_char_minimum_without_calling_api", async () => {
    // Arrange: confirmed server policy (app/modules/users/service.py
    // `confirm_password_reset`): minimum 12 characters, checkable client-side.
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () => {
        apiCalled = true;
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=valid-token" });

    // Act
    await user.type(screen.getByLabelText(/new password/i), "Short1!");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert
    expect(await screen.findByText(/at least 12 characters/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_reset_password_screen_does_not_simulate_breach_check_client_side_and_falls_through_to_server_error", async () => {
    // Arrange: a 12+-char password that is well-formed but breached — the
    // client cannot know this (server-only check, OD-5) and must submit,
    // letting the server's rejection render via FE-AC9.
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/breached-password",
            title: "Password compromised",
            status: 422,
            detail: "This password has appeared in a known data breach.",
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=valid-token" });

    // Act: a password that is 12+ chars and well-formed, so no client rule blocks it.
    await user.type(screen.getByLabelText(/new password/i), "correcthorsebattery");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert: request WAS made (no client-side pre-emption of the breach check);
    // the server's rejection is what renders.
    expect(await screen.findByText("This password has appeared in a known data breach.")).toBeInTheDocument();
  });

  it("test_reset_password_screen_does_not_simulate_differs_from_current_check_client_side_and_falls_through_to_server_error", async () => {
    // Arrange: differs-from-current is checked against the stored hash,
    // which the client never has (OD-5) — must submit and let the server reject.
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/same-as-current-password",
            title: "Password unchanged",
            status: 422,
            detail: "The new password must differ from your current password.",
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=valid-token" });

    // Act
    await user.type(screen.getByLabelText(/new password/i), "SameAsCurrentPassw0rd!");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert
    expect(
      await screen.findByText("The new password must differ from your current password."),
    ).toBeInTheDocument();
  });

  it("test_reset_password_screen_invalid_or_expired_token_renders_mapped_error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-reset-token",
            title: "Invalid or expired token",
            status: 400,
            detail: "This password reset link is invalid or has expired.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=expired-token" });

    // Act
    await user.type(screen.getByLabelText(/new password/i), "Correct-Horse-Battery-Staple-9!");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert
    expect(
      await screen.findByText("This password reset link is invalid or has expired."),
    ).toBeInTheDocument();
  });

  it("test_reset_password_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/password-reset/confirm", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<ResetPasswordScreen />, { route: "/reset-password?token=valid-token" });

    // Act
    await user.type(screen.getByLabelText(/new password/i), "Correct-Horse-Battery-Staple-9!");
    await user.click(screen.getByRole("button", { name: /reset password/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_reset_password_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<ResetPasswordScreen />, {
      route: "/reset-password?token=valid-token",
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
