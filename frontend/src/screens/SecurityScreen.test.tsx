// Integration test for SecurityScreen (Task T9). PS-AC5/FR-5 (enroll ->
// activate -> one-time recovery codes), PS-AC6/FR-6 (disable), Plan Change 6
// (authStore.mfaEnabled picks the enroll-vs-disable branch — never
// defaulting to enroll for an already-enrolled session), XC-AC1/FR-8,
// XC-AC2/FR-9, XC-AC3/FR-10, a11y bar.
//
// Field-label collaborator-shape assumptions (docs/tests/US-5.2-test-strategy.md):
// enroll flow — "Current password" field + "Start enrollment" button, then a
// rendered QR (`<QrCode>`) + visible "secret" text + "Code" field + an
// "Activate" button, then `<RecoveryCodesDisplay>` (Copy/Download/"saved"
// checkbox/"Continue"); disable flow — a "Disable MFA" trigger revealing a
// confirmation naming session revocation, "Current password" + "Code"
// fields, and a "Yes, disable MFA" confirm button. This whole file fails at
// module-resolution until `qrcode.react` (Task T5, human-approved per
// HUMAN_PLAN_APPROVAL) lands in `frontend/package.json` and `QrCode.tsx`
// exists — expected RED, see the generation report.
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { SecurityScreen } from "./SecurityScreen";

async function enrollAndActivate(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/current password/i), "correct-password");
  await user.click(screen.getByRole("button", { name: /start enrollment/i }));
  await screen.findByText(/JBSWY3DPEHPK3PXP/i);
  await user.type(screen.getByLabelText(/code/i), "123456");
  await user.click(screen.getByRole("button", { name: /activate/i }));
  await screen.findByText("AAAA-1111");
}

describe("SecurityScreen", () => {
  it("test_security_screen_mfa_disabled_session_shows_enroll_flow", () => {
    // Arrange / Act
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Assert
    expect(screen.getByRole("button", { name: /start enrollment/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /disable mfa/i })).not.toBeInTheDocument();
  });

  it("test_security_screen_mfa_enabled_session_shows_disable_flow_directly_not_defaulting_to_enroll", () => {
    // Arrange / Act
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Assert
    expect(screen.getByRole("button", { name: /disable mfa/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start enrollment/i })).not.toBeInTheDocument();
  });

  it("test_security_screen_enroll_start_calls_mfa_enroll_with_current_password_and_renders_qr_and_manual_secret", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> | undefined;
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /start enrollment/i }));

    // Assert
    expect(await screen.findByText(/JBSWY3DPEHPK3PXP/i)).toBeInTheDocument();
    expect(receivedBody).toEqual({ current_password: "correct-password" }); // pragma: allowlist secret
  });

  it("test_security_screen_enroll_blocks_submission_when_current_password_empty_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () => {
        apiCalled = true;
        return HttpResponse.json({ secret: "x", otpauth_uri: "otpauth://totp/x" }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /start enrollment/i }));

    // Assert
    expect(await screen.findByText(/current password is required/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_security_screen_enroll_activate_with_valid_6_digit_code_displays_recovery_codes_exactly_once", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        ),
      ),
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await enrollAndActivate(user);

    // Assert
    expect(screen.getByText("AAAA-1111")).toBeInTheDocument();
    expect(screen.getAllByText("AAAA-1111")).toHaveLength(1);
  });

  it("test_security_screen_enroll_blocks_submission_with_non_6_digit_code_without_calling_api", async () => {
    // Arrange
    let activateCalled = false;
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        ),
      ),
      http.post("/api/v1/auth/mfa/activate", async () => {
        activateCalled = true;
        return HttpResponse.json({ recovery_codes: ["AAAA-1111"] }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /start enrollment/i }));
    await screen.findByText(/JBSWY3DPEHPK3PXP/i);

    // Act
    await user.type(screen.getByLabelText(/code/i), "12345");
    await user.click(screen.getByRole("button", { name: /activate/i }));

    // Assert
    expect(await screen.findByText(/6.digit/i)).toBeInTheDocument();
    expect(activateCalled).toBe(false);
  });

  it("test_security_screen_enroll_flow_cannot_complete_until_save_confirmation_checked", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        ),
      ),
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });
    await enrollAndActivate(user);

    // Act / Assert: cannot complete before checking the confirmation.
    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /saved/i }));
    expect(screen.getByRole("button", { name: /continue/i })).toBeEnabled();
  });

  it("test_security_screen_enroll_secret_otpauth_uri_and_recovery_codes_never_reach_storage_console_or_third_party", async () => {
    // Arrange
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        ),
      ),
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await enrollAndActivate(user);

    // Assert
    expect(setItemSpy).not.toHaveBeenCalled();
    for (const spy of [consoleLogSpy, consoleErrorSpy]) {
      for (const call of spy.mock.calls) {
        expect(call.join(" ")).not.toMatch(/JBSWY3DPEHPK3PXP|AAAA-1111|BBBB-2222/);
      }
    }
  });

  it("test_security_screen_completing_enrollment_flips_the_screen_to_the_disable_flow", async () => {
    // Arrange: proves activation's `authStore.setMfaEnabled(true)` (Plan
    // Change 6) actually reaches this screen's own branch, observed via the
    // rendered outcome rather than reaching into store internals.
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        ),
      ),
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });
    await enrollAndActivate(user);

    // Act
    await user.click(screen.getByRole("checkbox", { name: /saved/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /disable mfa/i })).toBeInTheDocument();
  });

  it("test_security_screen_disable_requires_current_password_and_code", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.delete("/api/v1/auth/mfa", async () => {
        apiCalled = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /disable mfa/i }));
    await user.click(screen.getByRole("button", { name: /yes, disable mfa/i }));

    // Assert
    expect(await screen.findByText(/current password is required/i)).toBeInTheDocument();
    expect(await screen.findByText(/code is required|6.digit/i)).toBeInTheDocument();
    expect(apiCalled).toBe(false);
  });

  it("test_security_screen_disable_confirmation_names_session_revocation_consequence", async () => {
    // Arrange
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /disable mfa/i }));

    // Assert
    expect(screen.getByText(/session/i)).toBeInTheDocument();
    expect(screen.getByText(/revok/i)).toBeInTheDocument();
  });

  it("test_security_screen_successful_disable_calls_mfa_disable_and_the_screen_reflects_mfa_as_disabled", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> | undefined;
    server.use(
      http.delete("/api/v1/auth/mfa", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Act
    await user.click(screen.getByRole("button", { name: /disable mfa/i }));
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.type(screen.getByLabelText(/code/i), "123456");
    await user.click(screen.getByRole("button", { name: /yes, disable mfa/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /start enrollment/i })).toBeInTheDocument();
    expect(receivedBody).toEqual({
      current_password: "correct-password", // pragma: allowlist secret
      code: "123456",
    });
  });

  it("test_security_screen_422_validation_error_maps_errors_onto_matching_fields", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            errors: [
              { field: "current_password", message: "Current password is incorrect.", code: "invalid" },
            ],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await user.type(screen.getByLabelText(/current password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /start enrollment/i }));

    // Assert
    expect(await screen.findByText("Current password is incorrect.")).toBeInTheDocument();
  });

  it("test_security_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/mfa/enroll", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    await user.type(screen.getByLabelText(/current password/i), "correct-password");
    await user.click(screen.getByRole("button", { name: /start enrollment/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_security_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<SecurityScreen />, {
      route: "/settings/security",
      isAuthenticated: true,
      mfaEnabled: false,
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
