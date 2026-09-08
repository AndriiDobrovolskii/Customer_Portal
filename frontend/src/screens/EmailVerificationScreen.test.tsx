// Integration test for EmailVerificationScreen (Task T7). PS-AC4/FR-4: on
// mount, the `?token=` query param drives an automatic POST /auth/verify-email
// call (same "read token from query params" convention as
// ResetPasswordScreen); success/expired/invalid each render a distinct
// outcome. A separate "resend verification email" form (an "Email" field per
// this pass's own field-label assumption, docs/tests/US-5.2-test-strategy.md)
// calls POST /auth/verify-email/resend and shows one generic confirmation
// regardless of whether the address exists. XC-AC1/FR-8, XC-AC2/FR-9,
// XC-AC3/FR-10, a11y bar.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { EmailVerificationScreen } from "./EmailVerificationScreen";

describe("EmailVerificationScreen", () => {
  it("test_email_verification_screen_valid_token_renders_success_outcome", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json({ email_verified: true }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=valid-token" });

    // Assert
    expect(await screen.findByText(/verified/i)).toBeInTheDocument();
  });

  it("test_email_verification_screen_expired_token_renders_expired_outcome", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/verification-token-expired",
            title: "Token expired",
            status: 400,
            detail: "This verification link has expired.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=expired-token" });

    // Assert
    expect(await screen.findByText("This verification link has expired.")).toBeInTheDocument();
  });

  it("test_email_verification_screen_invalid_token_renders_invalid_outcome", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/verification-token-invalid",
            title: "Token invalid",
            status: 400,
            detail: "This verification link is not valid.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=bad-token" });

    // Assert
    expect(await screen.findByText("This verification link is not valid.")).toBeInTheDocument();
  });

  it("test_email_verification_screen_resend_control_shows_generic_confirmation_when_address_exists", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json(
          { type: "x", title: "x", status: 400, detail: "This verification link has expired." },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
      http.post("/api/v1/auth/verify-email/resend", async () =>
        HttpResponse.json(
          { message: "If an account exists for that email, a verification link has been sent." },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=expired-token" });
    await screen.findByText(/expired/i);

    // Act
    await user.type(screen.getByLabelText(/email/i), "exists@example.com");
    await user.click(screen.getByRole("button", { name: /resend/i }));

    // Assert
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });

  it("test_email_verification_screen_resend_control_shows_the_same_generic_confirmation_when_address_does_not_exist", async () => {
    // Arrange: same generic response body regardless of enumeration outcome.
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json(
          { type: "x", title: "x", status: 400, detail: "This verification link has expired." },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
      http.post("/api/v1/auth/verify-email/resend", async () =>
        HttpResponse.json(
          { message: "If an account exists for that email, a verification link has been sent." },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=expired-token" });
    await screen.findByText(/expired/i);

    // Act
    await user.type(screen.getByLabelText(/email/i), "nobody@example.com");
    await user.click(screen.getByRole("button", { name: /resend/i }));

    // Assert
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });

  it("test_email_verification_screen_resend_blocks_invalid_email_shape_without_calling_api", async () => {
    // Arrange
    let resendCalled = false;
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json(
          { type: "x", title: "x", status: 400, detail: "This verification link has expired." },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
      http.post("/api/v1/auth/verify-email/resend", async () => {
        resendCalled = true;
        return HttpResponse.json({ message: "sent" }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=expired-token" });
    await screen.findByText(/expired/i);

    // Act
    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.click(screen.getByRole("button", { name: /resend/i }));

    // Assert
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(resendCalled).toBe(false);
  });

  it("test_email_verification_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/verify-email", () => HttpResponse.error()));

    // Act
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=any-token" });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_email_verification_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/verify-email", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderWithProviders(<EmailVerificationScreen />, { route: "/verify-email?token=any-token" });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_email_verification_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json({ email_verified: true }, { status: 200 }),
      ),
    );
    const { container } = renderWithProviders(<EmailVerificationScreen />, {
      route: "/verify-email?token=valid-token",
    });
    await screen.findByText(/verified/i);

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
