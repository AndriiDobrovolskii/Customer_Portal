// Integration test for ConfirmEmailChangeScreen (Task T8). PS-AC3/FR-3's
// confirmation-link landing target: on mount, the `?token=` query param
// drives an automatic POST /profile/confirm-email-change call that "succeeds
// whether or not they are signed in" — the two-directions assertion Plan
// Risk 9 calls out explicitly, tested here both rendered with an
// authenticated test-utils wrapper and rendered without one. XC-AC1/FR-8,
// XC-AC3/FR-10, a11y bar.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { ConfirmEmailChangeScreen } from "./ConfirmEmailChangeScreen";

describe("ConfirmEmailChangeScreen", () => {
  it("test_confirm_email_change_screen_succeeds_when_rendered_unauthenticated", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json({ email: "new@example.com" }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<ConfirmEmailChangeScreen />, {
      route: "/confirm-email-change?token=valid-token",
      isAuthenticated: false,
    });

    // Assert
    expect(await screen.findByText(/confirmed|new@example\.com/i)).toBeInTheDocument();
  });

  it("test_confirm_email_change_screen_succeeds_when_rendered_authenticated", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json({ email: "new@example.com" }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<ConfirmEmailChangeScreen />, {
      route: "/confirm-email-change?token=valid-token",
      isAuthenticated: true,
    });

    // Assert
    expect(await screen.findByText(/confirmed|new@example\.com/i)).toBeInTheDocument();
  });

  it("test_confirm_email_change_screen_invalid_or_expired_token_renders_mapped_error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-token",
            title: "Invalid token",
            status: 400,
            detail: "This confirmation link is invalid or has expired.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<ConfirmEmailChangeScreen />, {
      route: "/confirm-email-change?token=expired-token",
      isAuthenticated: false,
    });

    // Assert
    expect(await screen.findByText("This confirmation link is invalid or has expired.")).toBeInTheDocument();
  });

  it("test_confirm_email_change_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/profile/confirm-email-change", () => HttpResponse.error()));

    // Act
    renderWithProviders(<ConfirmEmailChangeScreen />, {
      route: "/confirm-email-change?token=any-token",
      isAuthenticated: false,
    });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_confirm_email_change_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json({ email: "new@example.com" }, { status: 200 }),
      ),
    );
    const { container } = renderWithProviders(<ConfirmEmailChangeScreen />, {
      route: "/confirm-email-change?token=valid-token",
      isAuthenticated: false,
    });
    await screen.findByText(/confirmed|new@example\.com/i);

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
