// Unit test for the useLogout hook (Task T5, FE-AC5's "Log out" branch).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useLogout } from "./useLogout";
import { useAuthStore } from "../store/authStore";

describe("useLogout", () => {
  it("test_use_logout_calls_logout_endpoint_and_clears_session_on_success", async () => {
    // Arrange
    server.use(http.post("/api/v1/auth/logout", async () => new HttpResponse(null, { status: 204 })));
    const { result } = renderHookWithProviders(() => ({
      logout: useLogout(),
      store: useAuthStore(),
    }));
    result.current.store.setSession({ accessToken: "tok", user: { id: "u1", email: "a@example.com" } });

    // Act
    await result.current.logout.mutateAsync();

    // Assert
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(false));
    expect(result.current.store.accessToken).toBeNull();
  });
});
