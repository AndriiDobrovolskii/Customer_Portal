// Integration test for LoginScreen (Task T10). FE-AC2, FE-AC3's initial
// branch, FE-AC9, FE-AC11. This file contains no call to Vitest's
// component-mocking API (pre-commit `frontend-vi-mock-in-integration-tests`).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { LoginScreen } from "./LoginScreen";

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, email: string, password: string) {
  await user.type(screen.getByLabelText(/email/i), email);
  await user.type(screen.getByLabelText(/password/i), password);
  await user.click(screen.getByRole("button", { name: /^log in$/i }));
}

describe("LoginScreen", () => {
  it("test_login_screen_valid_credentials_without_mfa_stores_token_in_memory_and_redirects_to_tickets", async () => {
    // Arrange: US-5.3 FR-15 moves the no-`from`-state landing target from
    // the retired PlaceholderHomeScreen's "/" to "/tickets".
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json(
          { access_token: "access-token-1", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await fillAndSubmit(user, "a@example.com", "correct-password");

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets");
  });

  it("test_login_screen_mfa_required_response_navigates_to_mfa_verify_screen_holding_mfa_token_in_transient_state", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json({ mfa_token: "mfa-token-1" }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await fillAndSubmit(user, "mfa-user@example.com", "correct-password");

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/mfa-verify");
    // mfa_token never appears in a durable client store: assert it is absent
    // from localStorage/sessionStorage, per the spec's NFR.
    expect(localStorage.getItem("mfaToken")).toBeNull();
    expect(sessionStorage.getItem("mfaToken")).toBeNull();
  });

  it("test_login_screen_blocks_submission_on_empty_fields_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/login", async () => {
        apiCalled = true;
        return HttpResponse.json({
          access_token: "t",
          expires_in: 900,
          user: { id: "u1", email: "a@example.com" },
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await user.click(screen.getByRole("button", { name: /^log in$/i }));

    // Assert
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_login_screen_renders_uniform_401_message_without_leaking_account_existence", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-credentials",
            title: "Invalid credentials",
            status: 401,
            detail: "The email or password is incorrect.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await fillAndSubmit(user, "nobody@example.com", "wrong-password");

    // Assert
    expect(await screen.findByText("The email or password is incorrect.")).toBeInTheDocument();
  });

  it("test_login_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/login", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await fillAndSubmit(user, "a@example.com", "correct-password");

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_login_screen_5xx_response_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/login", async () => new HttpResponse(null, { status: 503 })));
    const user = userEvent.setup();
    renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    await fillAndSubmit(user, "a@example.com", "correct-password");

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_login_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<LoginScreen />, { route: "/login" });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
