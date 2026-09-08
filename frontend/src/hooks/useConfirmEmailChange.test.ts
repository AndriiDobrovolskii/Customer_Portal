// Unit test for useConfirmEmailChange (Task T4, FR-3's confirmation half).
// Callable signed-in or signed-out, per PS-AC3 — does not assume an
// authenticated hook context; calls POST /profile/confirm-email-change with
// `{token}` regardless of the caller's auth state (the endpoint itself
// accepts an optional Authorization header, per the spec's API Contract
// table).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useConfirmEmailChange } from "./useConfirmEmailChange";

describe("useConfirmEmailChange", () => {
  it("test_use_confirm_email_change_success_resolves_confirm_email_change_response", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json({ email: "new@example.com" }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useConfirmEmailChange(), { isAuthenticated: false });

    // Act
    const response = await result.current.mutateAsync({ token: "valid-token" });

    // Assert
    expect(response).toEqual({ email: "new@example.com" });
  });

  it("test_use_confirm_email_change_succeeds_identically_when_rendered_authenticated", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/profile/confirm-email-change", async () =>
        HttpResponse.json({ email: "new@example.com" }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useConfirmEmailChange(), { isAuthenticated: true });

    // Act
    const response = await result.current.mutateAsync({ token: "valid-token" });

    // Assert
    expect(response).toEqual({ email: "new@example.com" });
  });

  it("test_use_confirm_email_change_invalid_or_expired_token_surfaces_normalized_error", async () => {
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
    const { result } = renderHookWithProviders(() => useConfirmEmailChange(), { isAuthenticated: false });

    // Act / Assert
    await expect(result.current.mutateAsync({ token: "expired-token" })).rejects.toMatchObject({
      status: 400,
      message: "This confirmation link is invalid or has expired.",
    });
  });
});
