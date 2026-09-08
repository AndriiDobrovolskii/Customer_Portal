// Unit test for useAccountDeactivate (Task T4, FR-7). Calls
// POST /account/deactivate with `{current_password}` (unconditionally
// required per OD-4's resolution). On success, `onSuccess` calls
// `authStore.clearSession()`, the same pattern `useLogout.ts` already uses.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useAccountDeactivate } from "./useAccountDeactivate";
import { useAuthStore } from "../store/authStore";

describe("useAccountDeactivate", () => {
  it("test_use_account_deactivate_success_clears_auth_session_state", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/account/deactivate", async () =>
        HttpResponse.json({ status: "deactivated", deactivated_at: "2026-09-08T10:00:00Z" }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(
      () => ({ deactivate: useAccountDeactivate(), store: useAuthStore() }),
      { isAuthenticated: true },
    );

    // Act
    const response = await result.current.deactivate.mutateAsync({
      current_password: "correct-password", // pragma: allowlist secret
    });

    // Assert
    expect(response.status).toBe("deactivated");
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(false));
    expect(result.current.store.accessToken).toBeNull();
  });

  it("test_use_account_deactivate_incorrect_password_surfaces_normalized_error_and_leaves_session_intact", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/account/deactivate", async () =>
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
    const { result } = renderHookWithProviders(
      () => ({ deactivate: useAccountDeactivate(), store: useAuthStore() }),
      { isAuthenticated: true },
    );

    // Act / Assert
    await expect(
      result.current.deactivate.mutateAsync({
        current_password: "wrong-password", // pragma: allowlist secret
      }),
    ).rejects.toMatchObject({ status: 401 });
    expect(result.current.store.isAuthenticated).toBe(true);
  });
});
