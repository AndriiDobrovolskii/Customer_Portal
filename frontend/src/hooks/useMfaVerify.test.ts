// Unit test for the useMfaVerify hook (Task T5, FE-AC3's second step).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useMfaVerify } from "./useMfaVerify";
import { useAuthStore } from "../store/authStore";

describe("useMfaVerify", () => {
  it("test_use_mfa_verify_success_with_totp_code_updates_session_same_as_login_without_mfa", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          { access_token: "access-token-2", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      verify: useMfaVerify(),
      store: useAuthStore(),
    }));

    // Act
    await result.current.verify.mutateAsync({ mfa_token: "mfa-token-1", code: "123456" });

    // Assert
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(true));
    expect(result.current.store.accessToken).toBe("access-token-2");
  });

  it("test_use_mfa_verify_success_with_recovery_code_updates_session_same_as_login_without_mfa", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          { access_token: "access-token-3", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      verify: useMfaVerify(),
      store: useAuthStore(),
    }));

    // Act
    await result.current.verify.mutateAsync({ mfa_token: "mfa-token-1", code: "AAAA-BBBB-CCCC" });

    // Assert
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(true));
  });

  it("test_use_mfa_verify_invalid_code_surfaces_normalized_error_and_leaves_session_unauthenticated", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/verify", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-mfa-code",
            title: "Invalid code",
            status: 401,
            detail: "The verification code is incorrect or expired.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      verify: useMfaVerify(),
      store: useAuthStore(),
    }));

    // Act / Assert
    await expect(
      result.current.verify.mutateAsync({ mfa_token: "mfa-token-1", code: "000000" }),
    ).rejects.toMatchObject({ status: 401 });
    expect(result.current.store.isAuthenticated).toBe(false);
  });
});
