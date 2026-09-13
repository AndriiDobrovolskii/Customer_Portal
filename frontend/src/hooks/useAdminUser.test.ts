import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useAdminUser, adminUserEtagQueryKey } from "./useAdminUser";

function adminUser(id: string, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id,
    email: "target@example.com",
    display_name: "Target User",
    status: "active",
    roles: ["support-agent"],
    created_at: "2026-09-01T00:00:00Z",
    last_login_at: "2026-09-02T00:00:00Z",
    ...overrides,
  };
}

describe("useAdminUser", () => {
  it("test_use_admin_user_captures_the_etag_response_header_into_the_per_user_cache_key", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser("user-a"), { status: 200, headers: { ETag: "etag-a" } }),
      ),
    );

    // Act
    const { result, queryClient } = renderHookWithProviders(() => useAdminUser("user-a"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(queryClient.getQueryData(adminUserEtagQueryKey("user-a"))).toBe("etag-a");
  });

  it("test_use_admin_user_etag_for_user_a_is_never_read_under_user_bs_cache_key", async () => {
    // Arrange (Implementation Plan Risk 4)
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser("user-a"), { status: 200, headers: { ETag: "etag-a" } }),
      ),
    );

    // Act
    const { result, queryClient } = renderHookWithProviders(() => useAdminUser("user-a"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(queryClient.getQueryData(adminUserEtagQueryKey("user-b"))).toBeUndefined();
  });

  it("test_use_admin_user_missing_etag_header_leaves_the_cache_key_unset", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users/user-c", async () =>
        HttpResponse.json(adminUser("user-c"), { status: 200 }),
      ),
    );

    // Act
    const { result, queryClient } = renderHookWithProviders(() => useAdminUser("user-c"));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(queryClient.getQueryData(adminUserEtagQueryKey("user-c"))).toBeUndefined();
  });
});
