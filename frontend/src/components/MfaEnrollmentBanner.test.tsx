// Unit test for the MfaEnrollmentBanner component (Task T8). Copy/exact
// dismissal-persistence rule are gated by OD-7 (OPEN, per
// docs/decisions/US-5.1-open-decisions.md); this test asserts only the
// structural behavior the implementation plan's default fixes (Architectural
// Change 6/story Assumption #6): the banner surfaces the deadline when
// present, is dismissible, and dismissal persists via sessionStorage — not
// OD-7's still-open exact copy/re-appearance semantics.
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MfaEnrollmentBanner } from "./MfaEnrollmentBanner";

describe("MfaEnrollmentBanner", () => {
  it("test_mfa_enrollment_banner_renders_the_deadline_when_present", () => {
    // Arrange / Act
    render(<MfaEnrollmentBanner deadline="2026-09-20T00:00:00Z" />);

    // Assert
    expect(screen.getByRole("status")).toHaveTextContent(/2026-09-20|deadline/i);
  });

  it("test_mfa_enrollment_banner_renders_nothing_when_deadline_is_absent", () => {
    // Arrange / Act
    const { container } = render(<MfaEnrollmentBanner deadline={null} />);

    // Assert
    expect(container).toBeEmptyDOMElement();
  });

  it("test_mfa_enrollment_banner_dismiss_control_hides_the_banner_and_persists_via_session_storage", async () => {
    // Arrange
    sessionStorage.clear();
    const user = userEvent.setup();
    render(<MfaEnrollmentBanner deadline="2026-09-20T00:00:00Z" />);

    // Act
    await user.click(screen.getByRole("button", { name: /dismiss/i }));

    // Assert
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(sessionStorage.getItem("mfaEnrollmentBannerDismissed")).toBe("true");
  });
});
