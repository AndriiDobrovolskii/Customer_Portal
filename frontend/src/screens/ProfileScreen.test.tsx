// Integration test for ProfileScreen (Task T6). PS-AC1 (deferred, FR-1 — no
// GET /profile exists, so this screen starts blank rather than pre-populated
// per Assumption #3/FR-2), PS-AC2/FR-2 (field edit + If-Match/ETag/412),
// PS-AC3/FR-3 (email change + 202 pending state), XC-AC1/FR-8,
// XC-AC2/FR-9, XC-AC3/FR-10, a11y bar.
//
// Field-label collaborator-shape assumptions (no design doc fixes a form
// layout — API/DB design are NOT_APPLICABLE; recorded here and in
// docs/tests/US-5.2-test-strategy.md): "Display name", "Locale" (a <select>
// with `en-US`/`en-GB` options, Change 7), "Timezone" (a combobox accepting
// a typed IANA name, validated against `Intl.supportedValuesOf("timeZone")`,
// Change 8), "Avatar URL", a "Save profile" submit button for the field-edit
// form; "New email"/"Current password" fields with a "Change email" submit
// button for the separate email-change form (FR-3); a "changed elsewhere"
// conflict state exposing a "Reload" button (FR-2's 412 case).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { ProfileScreen } from "./ProfileScreen";

const profileReadFixture = {
  id: "u1",
  email: "user@example.com",
  pending_email: null,
  display_name: "Updated Name",
  locale: "en-GB",
  timezone: "Europe/London",
  avatar_url: null,
  email_verified: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("ProfileScreen", () => {
  it("test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values", () => {
    // Arrange / Act — pins FR-1's deferral: no GET /profile exists, so
    // nothing pre-populates the form.
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Assert
    expect(screen.getByLabelText(/display name/i)).toHaveValue("");
  });

  it("test_profile_screen_submits_only_changed_fields_on_save", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> | undefined;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Updated Name");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    await screen.findByText(/updated name/i);
    expect(receivedBody).toEqual({ display_name: "Updated Name" });
  });

  it("test_profile_screen_first_write_in_session_sends_if_match_asterisk", async () => {
    // Arrange
    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Updated Name");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    await screen.findByText(/updated name/i);
    expect(receivedIfMatch).toBe("*");
  });

  it("test_profile_screen_second_write_in_session_echoes_captured_etag", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });
    await user.type(screen.getByLabelText(/display name/i), "Updated Name");
    await user.click(screen.getByRole("button", { name: /save profile/i }));
    await screen.findByText(/updated name/i);

    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-2" } });
      }),
    );

    // Act
    await user.clear(screen.getByLabelText(/display name/i));
    await user.type(screen.getByLabelText(/display name/i), "Another Name");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    await screen.findByText(/another name|updated name/i);
    expect(receivedIfMatch).toBe("etag-1");
  });

  it("test_profile_screen_412_response_renders_changed_elsewhere_reload_conflict_state", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/precondition-failed",
            title: "Precondition failed",
            status: 412,
            detail: "The profile has changed elsewhere.",
          },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Stale Edit");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByText(/changed elsewhere/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
  });

  it("test_profile_screen_email_change_submission_shows_pending_confirmation_state_on_202", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> | undefined;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { ...profileReadFixture, pending_email: "new@example.com" },
          { status: 202 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/new email/i), "new@example.com");
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /change email/i }));

    // Assert
    expect(await screen.findByText(/confirm.*new@example\.com/i)).toBeInTheDocument();
    expect(receivedBody).toEqual({
      email: "new@example.com",
      current_password: "correct-password", // pragma: allowlist secret
    });
  });

  it("test_profile_screen_blocks_submission_with_invalid_email_shape_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.patch("/api/v1/profile", async () => {
        apiCalled = true;
        return HttpResponse.json(profileReadFixture, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/new email/i), "not-an-email");
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /change email/i }));

    // Assert
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_profile_screen_blocks_submission_with_unrecognized_timezone_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.patch("/api/v1/profile", async () => {
        apiCalled = true;
        return HttpResponse.json(profileReadFixture, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByRole("combobox", { name: /timezone/i }), "Not/ARealZone");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByText(/valid timezone/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_profile_screen_422_validation_error_maps_errors_array_onto_matching_fields", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            errors: [{ field: "display_name", message: "Display name is too long.", code: "too_long" }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "x".repeat(200));
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByText("Display name is too long.")).toBeInTheDocument();
  });

  it("test_profile_screen_4xx_problem_json_renders_mapped_detail_message_with_no_raw_json", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-locale",
            title: "Invalid locale",
            status: 400,
            detail: "The selected locale is not supported.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Someone");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByText("The selected locale is not supported.")).toBeInTheDocument();
    expect(screen.queryByText(/"type":|"title":/)).not.toBeInTheDocument();
  });

  it("test_profile_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.patch("/api/v1/profile", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Someone");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_profile_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.patch("/api/v1/profile", async () => new HttpResponse(null, { status: 500 })));
    const user = userEvent.setup();
    renderWithProviders(<ProfileScreen />, { route: "/settings/profile", isAuthenticated: true });

    // Act
    await user.type(screen.getByLabelText(/display name/i), "Someone");
    await user.click(screen.getByRole("button", { name: /save profile/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_profile_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<ProfileScreen />, {
      route: "/settings/profile",
      isAuthenticated: true,
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
