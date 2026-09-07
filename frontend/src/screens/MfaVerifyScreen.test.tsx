// Integration test for MfaVerifyScreen (Task T11). FE-AC3's second step
// (TOTP + recovery code), FE-AC9, FE-AC11.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { MfaVerifyScreen } from "./MfaVerifyScreen";

describe("MfaVerifyScreen", () => {
  it("test_mfa_verify_screen_valid_totp_code_completes_login_same_as_login_without_mfa", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          { access_token: "access-token-2", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<MfaVerifyScreen />, { route: "/mfa-verify", mfaToken: "mfa-token-1" });

    // Act
    await user.type(screen.getByLabelText(/code/i), "123456");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/");
  });

  it("test_mfa_verify_screen_valid_recovery_code_completes_login_same_as_login_without_mfa", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          { access_token: "access-token-3", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<MfaVerifyScreen />, { route: "/mfa-verify", mfaToken: "mfa-token-1" });

    // Act
    await user.type(screen.getByLabelText(/code/i), "AAAA-BBBB-CCCC");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/");
  });

  it("test_mfa_verify_screen_blocks_submission_on_empty_code_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () => {
        apiCalled = true;
        return HttpResponse.json({
          access_token: "t",
          expires_in: 900,
          user: { id: "u1", email: "a@example.com" },
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<MfaVerifyScreen />, { route: "/mfa-verify", mfaToken: "mfa-token-1" });

    // Act
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert
    expect(await screen.findByText(/code is required/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_mfa_verify_screen_renders_mapped_message_for_invalid_code", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-mfa-code",
            title: "Invalid code",
            status: 401,
            detail: "The verification code is incorrect or expired.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<MfaVerifyScreen />, { route: "/mfa-verify", mfaToken: "mfa-token-1" });

    // Act
    await user.type(screen.getByLabelText(/code/i), "000000");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert
    expect(await screen.findByText("The verification code is incorrect or expired.")).toBeInTheDocument();
  });

  it("test_mfa_verify_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/mfa/verify", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<MfaVerifyScreen />, { route: "/mfa-verify", mfaToken: "mfa-token-1" });

    // Act
    await user.type(screen.getByLabelText(/code/i), "123456");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_mfa_verify_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<MfaVerifyScreen />, {
      route: "/mfa-verify",
      mfaToken: "mfa-token-1",
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
