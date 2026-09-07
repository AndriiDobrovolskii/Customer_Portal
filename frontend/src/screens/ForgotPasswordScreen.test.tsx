// Integration test for ForgotPasswordScreen (Task T12). FE-AC7's request
// half, FE-AC8, FE-AC9, FE-AC11.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { ForgotPasswordScreen } from "./ForgotPasswordScreen";

describe("ForgotPasswordScreen", () => {
  it("test_forgot_password_screen_submits_email_and_shows_generic_message_regardless_of_account_existence", async () => {
    // Arrange: the backend's own anti-enumeration behavior — identical
    // response whether or not the account exists.
    server.use(
      http.post("/api/v1/auth/password-reset/request", async () =>
        HttpResponse.json(
          { message: "If an account exists for that email, a reset link has been sent." },
          { status: 202 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordScreen />, { route: "/forgot-password" });

    // Act
    await user.type(screen.getByLabelText(/email/i), "anyone@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    // Assert
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });

  it("test_forgot_password_screen_blocks_submission_on_malformed_email_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/password-reset/request", async () => {
        apiCalled = true;
        return HttpResponse.json({ message: "ok" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordScreen />, { route: "/forgot-password" });

    // Act
    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    // Assert
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_forgot_password_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/password-reset/request", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordScreen />, { route: "/forgot-password" });

    // Act
    await user.type(screen.getByLabelText(/email/i), "anyone@example.com");
    await user.click(screen.getByRole("button", { name: /send reset link/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_forgot_password_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<ForgotPasswordScreen />, { route: "/forgot-password" });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
