// Unit test for useMfaEnroll (Task T4, FR-5's first step). Calls
// POST /auth/mfa/enroll with `{current_password}`, per OD-2's resolution
// (spec FR-5 deviates from PS-AC5's literal silence on a request body).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useMfaEnroll } from "./useMfaEnroll";

describe("useMfaEnroll", () => {
  it("test_use_mfa_enroll_success_resolves_secret_and_otpauth_uri", async () => {
    // Arrange
    let receivedBody: unknown;
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          {
            secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
            otpauth_uri: "otpauth://totp/Portal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
          },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useMfaEnroll(), { isAuthenticated: true });

    // Act
    const response = await result.current.mutateAsync({
      current_password: "correct-password", // pragma: allowlist secret
    });

    // Assert
    expect(receivedBody).toEqual({ current_password: "correct-password" }); // pragma: allowlist secret
    expect(response.secret).toBe("JBSWY3DPEHPK3PXP");
    expect(response.otpauth_uri).toContain("otpauth://totp/");
  });

  it("test_use_mfa_enroll_incorrect_password_surfaces_normalized_error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/enroll", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-credentials",
            title: "Invalid credentials",
            status: 401,
            detail: "Your current password is incorrect.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useMfaEnroll(), { isAuthenticated: true });

    // Act / Assert
    await expect(
      result.current.mutateAsync({ current_password: "wrong-password" }), // pragma: allowlist secret
    ).rejects.toMatchObject({
      status: 401,
      message: "Your current password is incorrect.",
    });
  });
});
