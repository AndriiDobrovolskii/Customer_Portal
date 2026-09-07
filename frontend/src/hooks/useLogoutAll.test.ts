// Unit test for the useLogoutAll hook (Task T5, FE-AC5's "Log out everywhere" branch).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useLogoutAll } from "./useLogoutAll";
import { useAuthStore } from "../store/authStore";

describe("useLogoutAll", () => {
  it("test_use_logout_all_calls_logout_all_endpoint_and_clears_session_on_success", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/logout-all", async () => new HttpResponse(null, { status: 204 })));
    const { result } = renderHookWithProviders(() => ({
      logoutAll: useLogoutAll(),
      store: useAuthStore(),
    }));
    result.current.store.setSession({ accessToken: "tok", user: { id: "u1", email: "a@example.com" } });

    // Act
    await result.current.logoutAll.mutateAsync();

    // Assert: same client-side effect as single-session logout (FE-AC5).
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(false));
    expect(result.current.store.accessToken).toBeNull();
  });
});
