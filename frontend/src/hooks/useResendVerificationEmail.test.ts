// Unit test for useResendVerificationEmail (Task T4, FR-4's resend control).
// Calls POST /auth/verify-email/resend with `{email}`. Anti-enumeration
// (the same generic confirmation regardless of whether the address exists)
// is the server's own responsibility (the response body never varies) — this
// hook simply resolves whatever the server returns; the screen-level test
// (EmailVerificationScreen.test.tsx) proves the UI copy is identical for
// both an existing and a non-existing address.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useResendVerificationEmail } from "./useResendVerificationEmail";

describe("useResendVerificationEmail", () => {
  it("test_use_resend_verification_email_resolves_generic_confirmation_for_any_submitted_address", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email/resend", async () =>
        HttpResponse.json(
          { message: "If an account exists for that email, a verification link has been sent." },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useResendVerificationEmail(), {
      isAuthenticated: false,
    });

    // Act
    const response = await result.current.mutateAsync({ email: "someone@example.com" });

    // Assert
    expect(response.message).toMatch(/if an account exists/i);
  });

  it("test_use_resend_verification_email_network_error_surfaces_normalized_network_error", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/verify-email/resend", () => HttpResponse.error()));
    const { result } = renderHookWithProviders(() => useResendVerificationEmail(), {
      isAuthenticated: false,
    });

    // Act / Assert
    await expect(result.current.mutateAsync({ email: "someone@example.com" })).rejects.toMatchObject({
      status: 0,
    });
  });
});
