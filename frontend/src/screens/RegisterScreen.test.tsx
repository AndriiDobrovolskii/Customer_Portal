// Integration test for RegisterScreen (Task T9). FE-AC1, FE-AC8 (email/
// password client rules), FE-AC9 (Register's two non-RFC7807 shapes, OD-4),
// FE-AC11. This file contains no call to Vitest's component-mocking API —
// banned under this path by `.pre-commit-config.yaml`'s
// `frontend-vi-mock-in-integration-tests` hook; MSW is the only
// substitution, per AGENTS.md §5's Frontend subsection.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { RegisterScreen } from "./RegisterScreen";

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>, email: string, password: string) {
  await user.type(screen.getByLabelText(/email/i), email);
  await user.type(screen.getByLabelText(/password/i), password);
  await user.click(screen.getByRole("button", { name: /register/i }));
}

describe("RegisterScreen", () => {
  it("test_register_screen_submits_valid_data_and_redirects_to_login_with_success_message", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/register", async () =>
        HttpResponse.json({ id: "u1", email: "new@example.com" }, { status: 201 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "new@example.com", "Sup3r$ecret!");

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/login");
    expect(await screen.findByText(/registration successful/i)).toBeInTheDocument();
  });

  it("test_register_screen_blocks_submission_on_empty_fields_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/register", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "u1", email: "x@example.com" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await user.click(screen.getByRole("button", { name: /register/i }));

    // Assert
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_register_screen_blocks_submission_on_malformed_email_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/register", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "u1", email: "x@example.com" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "not-an-email", "Sup3r$ecret!");

    // Assert
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_register_screen_blocks_submission_on_password_missing_required_character_classes_without_calling_api", async () => {
    // Arrange: Register's confirmed policy (app/modules/users/service.py
    // `_validate_password`): min 8 chars, upper+lower+digit+punctuation.
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/register", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "u1", email: "x@example.com" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "new@example.com", "alllowercase");

    // Assert
    expect(await screen.findByText(/must contain/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_register_screen_renders_mapped_message_for_register_400_validation_error_shape", async () => {
    // Arrange: RegistrationValidationError — 400, {"errors":[...]}, plain
    // application/json, no RFC 7807 envelope (OD-4).
    server.use(
      http.post("/api/v1/auth/register", async () =>
        HttpResponse.json(
          {
            errors: [{ field: "password", message: "Password must contain a digit.", code: "weak_password" }],
          },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "new@example.com", "Sup3r$ecretNoDigits!");

    // Assert
    expect(await screen.findByText("Password must contain a digit.")).toBeInTheDocument();
    expect(screen.queryByText(/\{.*"errors".*\}/)).not.toBeInTheDocument();
  });

  it("test_register_screen_renders_mapped_message_for_register_409_duplicate_email_shape", async () => {
    // Arrange: DuplicateEmailError — 409, {"detail": "..."}, plain
    // application/json, no RFC 7807 envelope (OD-4).
    server.use(
      http.post("/api/v1/auth/register", async () =>
        HttpResponse.json({ detail: "Email is already registered." }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "dup@example.com", "Sup3r$ecret!");

    // Assert
    expect(await screen.findByText("Email is already registered.")).toBeInTheDocument();
  });

  it("test_register_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/register", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "new@example.com", "Sup3r$ecret!");

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_register_screen_5xx_response_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/register", async () => new HttpResponse(null, { status: 500 })));
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await fillAndSubmit(user, "new@example.com", "Sup3r$ecret!");

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_register_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange: a11y bar's automated half (Risk 1's dependency sign-off for
    // vitest-axe was granted — see docs/tests/US-5.1-test-strategy.md).
    const { container } = renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });

  it("test_register_screen_supports_full_keyboard_navigation_across_its_fields_and_submit_control", async () => {
    // Arrange: a11y bar's dependency-free floor.
    const user = userEvent.setup();
    renderWithProviders(<RegisterScreen />, { route: "/register" });

    // Act
    await user.tab();
    // Assert
    expect(screen.getByLabelText(/email/i)).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText(/password/i)).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: /register/i })).toHaveFocus();
  });
});
