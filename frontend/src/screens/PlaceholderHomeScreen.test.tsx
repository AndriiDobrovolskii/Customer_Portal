// Integration test for PlaceholderHomeScreen (Task T15). Post-login landing
// render (FE-AC2/FE-AC3's redirect target); MfaEnrollmentBanner surfaced
// when mfa_enrollment_deadline is present (story Assumption #6, OD-7 gates
// the banner's exact copy only, not its existence).
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { renderWithProviders } from "../test/test-utils";
import { PlaceholderHomeScreen } from "./PlaceholderHomeScreen";

describe("PlaceholderHomeScreen", () => {
  it("test_placeholder_home_screen_renders_for_an_authenticated_user", () => {
    // Arrange / Act
    renderWithProviders(<PlaceholderHomeScreen />, {
      route: "/",
      isAuthenticated: true,
      user: { id: "u1", email: "a@example.com" },
    });

    // Assert
    expect(screen.getByRole("heading")).toBeInTheDocument();
  });

  it("test_placeholder_home_screen_surfaces_mfa_enrollment_banner_when_deadline_present", () => {
    // Arrange / Act
    renderWithProviders(<PlaceholderHomeScreen />, {
      route: "/",
      isAuthenticated: true,
      user: { id: "u1", email: "a@example.com" },
      mfaEnrollmentDeadline: "2026-09-20T00:00:00Z",
    });

    // Assert
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("test_placeholder_home_screen_omits_mfa_enrollment_banner_when_deadline_absent", () => {
    // Arrange / Act
    renderWithProviders(<PlaceholderHomeScreen />, {
      route: "/",
      isAuthenticated: true,
      user: { id: "u1", email: "a@example.com" },
      mfaEnrollmentDeadline: null,
    });

    // Assert
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("test_placeholder_home_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<PlaceholderHomeScreen />, {
      route: "/",
      isAuthenticated: true,
      user: { id: "u1", email: "a@example.com" },
      mfaEnrollmentDeadline: "2026-09-20T00:00:00Z",
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
