// Unit test for useVerifyEmail (Task T4, FR-4's landing call). Calls
// POST /auth/verify-email with `{token}`. The three distinct outcomes
// PS-AC4 requires (success / expired / invalid) are asserted at the screen
// level (EmailVerificationScreen.test.tsx), where the rendered copy per
// outcome actually matters — this hook-level suite proves only that success
// resolves and that a failure surfaces the server's own normalized message
// unmodified, which is all the hook itself is responsible for.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useVerifyEmail } from "./useVerifyEmail";

describe("useVerifyEmail", () => {
  it("test_use_verify_email_success_resolves_verify_email_response", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/verify-email", async () =>
        HttpResponse.json({ email_verified: true }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useVerifyEmail(), { isAuthenticated: false });

    // Act
    const response = await result.current.mutateAsync({ token: "valid-token" });

    // Assert
    expect(response).toEqual({ email_verified: true });
  });

  it("test_use_verify_email_expired_token_surfaces_the_servers_normalized_expired_message", async () => {
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
    const { result } = renderHookWithProviders(() => useVerifyEmail(), { isAuthenticated: false });

    // Act / Assert
    await expect(result.current.mutateAsync({ token: "expired-token" })).rejects.toMatchObject({
      status: 400,
      message: "This verification link has expired.",
    });
  });

  it("test_use_verify_email_invalid_token_surfaces_the_servers_normalized_invalid_message", async () => {
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
    const { result } = renderHookWithProviders(() => useVerifyEmail(), { isAuthenticated: false });

    // Act / Assert
    await expect(result.current.mutateAsync({ token: "bad-token" })).rejects.toMatchObject({
      status: 400,
      message: "This verification link is not valid.",
    });
  });
});
