// Integration test for SessionsScreen (Task T14). FE-AC6: list+revoke,
// current-session marker, revoke-affordance per the OD-6 default in force
// (this suite asserts the "disable the current-session row's revoke
// control" default — see docs/tests/US-5.1-test-strategy.md for the OD-6
// decision this pass records), FE-AC11.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { SessionsScreen } from "./SessionsScreen";

const sessionsFixture = {
  sessions: [
    {
      family_id: "fam-1",
      device_label: "Chrome on Windows",
      location: "Kyiv, UA",
      last_used_at: "2026-09-06T10:00:00Z",
      is_current: true,
    },
    {
      family_id: "fam-2",
      device_label: "Safari on iPhone",
      location: null,
      last_used_at: "2026-09-05T08:00:00Z",
      is_current: false,
    },
  ],
};

describe("SessionsScreen", () => {
  it("test_sessions_screen_renders_device_label_location_last_used_and_marks_current_session", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/auth/sessions", async () => HttpResponse.json(sessionsFixture, { status: 200 })),
    );
    renderWithProviders(<SessionsScreen />, { route: "/sessions" });

    // Act / Assert
    expect(await screen.findByText("Chrome on Windows")).toBeInTheDocument();
    expect(screen.getByText("Kyiv, UA")).toBeInTheDocument();
    expect(screen.getByText("Safari on iPhone")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem");
    const currentRow = rows.find((row) => row.textContent?.includes("Chrome on Windows"));
    expect(currentRow).toHaveTextContent(/current/i);
  });

  it("test_sessions_screen_revoke_non_current_session_removes_row_without_affecting_current_session", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/auth/sessions", async () => HttpResponse.json(sessionsFixture, { status: 200 })),
      http.delete("/api/v1/auth/sessions/fam-2", async () => new HttpResponse(null, { status: 204 })),
    );
    const user = userEvent.setup();
    renderWithProviders(<SessionsScreen />, { route: "/sessions" });
    await screen.findByText("Safari on iPhone");

    // Act
    await user.click(screen.getByRole("button", { name: /revoke.*safari on iphone/i }));

    // Assert
    await screen.findByText("Chrome on Windows");
    expect(screen.queryByText("Safari on iPhone")).not.toBeInTheDocument();
    expect(screen.getByText("Chrome on Windows")).toBeInTheDocument();
  });

  it("test_sessions_screen_current_session_row_revoke_control_is_disabled_per_od_6_default", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/auth/sessions", async () => HttpResponse.json(sessionsFixture, { status: 200 })),
    );
    renderWithProviders(<SessionsScreen />, { route: "/sessions" });

    // Act / Assert
    await screen.findByText("Chrome on Windows");
    expect(screen.getByRole("button", { name: /revoke.*chrome on windows/i })).toBeDisabled();
  });

  it("test_sessions_screen_network_error_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/auth/sessions", () => HttpResponse.error()));
    renderWithProviders(<SessionsScreen />, { route: "/sessions" });

    // Act / Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_sessions_screen_5xx_response_shows_generic_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/auth/sessions", async () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<SessionsScreen />, { route: "/sessions" });

    // Act / Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_sessions_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange: assert against the loaded (non-loading, non-error) state,
    // since that is the screen's primary interactive surface.
    server.use(
      http.get("/api/v1/auth/sessions", async () => HttpResponse.json(sessionsFixture, { status: 200 })),
    );
    const { container } = renderWithProviders(<SessionsScreen />, { route: "/sessions" });
    await screen.findByText("Chrome on Windows");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
