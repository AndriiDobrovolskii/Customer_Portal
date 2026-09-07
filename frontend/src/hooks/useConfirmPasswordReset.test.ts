// Unit test for the useConfirmPasswordReset hook (Task T5, FE-AC7's confirm half).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useConfirmPasswordReset } from "./useConfirmPasswordReset";

describe("useConfirmPasswordReset", () => {
  it("test_use_confirm_password_reset_valid_token_and_password_succeeds_with_empty_body", async () => {
    // Arrange: per the story's API Contract table, 200 with an empty body.
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () => new HttpResponse(null, { status: 200 })),
    );
    const { result } = renderHookWithProviders(() => useConfirmPasswordReset());

    // Act
    await result.current.mutateAsync({
      token: "valid-token",
      new_password: "Correct-Horse-Battery-Staple-9!", // pragma: allowlist secret
    });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });

  it("test_use_confirm_password_reset_invalid_token_surfaces_normalized_error", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/password-reset/confirm", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-reset-token",
            title: "Invalid or expired token",
            status: 400,
            detail: "This password reset link is invalid or has expired.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useConfirmPasswordReset());

    // Act / Assert
    await expect(
      result.current.mutateAsync({ token: "bad-token", new_password: "Correct-Horse-Battery-Staple-9!" }), // pragma: allowlist secret
    ).rejects.toMatchObject({ status: 400 });
  });
});
