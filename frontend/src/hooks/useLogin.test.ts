// Unit test for the useLogin hook (Task T5, FE-AC2/FE-AC3's initial call).
// Collaborator-shape assumption: `useLogin()` wraps `authApi.login`; on a
// `LoginResponse` success it calls `authStore.setSession(...)` in `onSuccess`
// (never inside the calling screen, per implementation-plan's Files To
// Create note on hooks/); on an `MfaRequiredResponse` it returns the payload
// unmodified for the screen to branch on (mfa_token is stored by the screen
// via `authStore.setMfaToken`, not by this hook, since the hook cannot know
// which branch happened without inspecting the response shape itself).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useLogin } from "./useLogin";
import { useAuthStore } from "../store/authStore";

describe("useLogin", () => {
  it("test_use_login_success_without_mfa_updates_session_and_returns_login_response", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json(
          { access_token: "access-token-1", expires_in: 900, user: { id: "u1", email: "a@example.com" } },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      login: useLogin(),
      store: useAuthStore(),
    }));

    // Act
    const response = await result.current.login.mutateAsync({
      email: "a@example.com",
      password: "correct-password", // pragma: allowlist secret
    });

    // Assert
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(true));
    expect(result.current.store.accessToken).toBe("access-token-1");
    expect(response).toMatchObject({ access_token: "access-token-1" });
  });

  it("test_use_login_mfa_required_response_does_not_update_session_and_returns_mfa_token", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json({ mfa_token: "mfa-token-1" }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      login: useLogin(),
      store: useAuthStore(),
    }));

    // Act
    const response = await result.current.login.mutateAsync({
      email: "mfa-user@example.com",
      password: "correct-password", // pragma: allowlist secret
    });

    // Assert
    expect(response).toEqual({ mfa_token: "mfa-token-1" });
    expect(result.current.store.isAuthenticated).toBe(false);
    expect(result.current.store.accessToken).toBeNull();
  });

  it("test_use_login_invalid_credentials_surfaces_normalized_401_error_without_leaking_account_existence", async () => {
    // Arrange: uniform 401 regardless of whether the email exists (backend anti-enumeration).
    server.use(
      http.post("/api/v1/auth/login", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-credentials",
            title: "Invalid credentials",
            status: 401,
            detail: "The email or password is incorrect.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useLogin());

    // Act / Assert
    await expect(
      result.current.mutateAsync({ email: "nobody@example.com", password: "wrong" }), // pragma: allowlist secret
    ).rejects.toMatchObject({ status: 401, message: "The email or password is incorrect." });
  });
});
