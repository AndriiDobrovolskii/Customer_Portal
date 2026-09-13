import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { adminUserQueryKey } from "./useAdminUser";
import { useDeactivateAdminUser } from "./useDeactivateAdminUser";

describe("useDeactivateAdminUser", () => {
  it("test_use_deactivate_admin_user_sends_the_required_reason", async () => {
    // Arrange
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/v1/admin/users/user-a/deactivate", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Target User",
            status: "deactivated",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useDeactivateAdminUser("user-a"));

    // Act
    result.current.mutate({ reason: "Left the organization" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedBody).toEqual({ reason: "Left the organization" });
  });

  it("test_use_deactivate_admin_user_on_success_updates_the_cached_status_without_a_full_refetch", async () => {
    // Arrange (Implementation Plan Risk 3)
    server.use(
      http.post("/api/v1/admin/users/user-a/deactivate", async () =>
        HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Target User",
            status: "deactivated",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200 },
        ),
      ),
    );
    let getFetchCount = 0;
    server.use(
      http.get("/api/v1/admin/users/user-a", async () => {
        getFetchCount += 1;
        return HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Target User",
            status: "active",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200 },
        );
      }),
    );
    const { result, queryClient } = renderHookWithProviders(() => useDeactivateAdminUser("user-a"));

    // Act
    result.current.mutate({ reason: "Left the organization" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert: setQueryData reflects the new status directly, and no GET
    // /admin/users/user-a request was ever issued by this mutation.
    expect(queryClient.getQueryData<{ status: string }>(adminUserQueryKey("user-a"))?.status).toBe(
      "deactivated",
    );
    expect(getFetchCount).toBe(0);
  });

  it("test_use_deactivate_admin_user_never_triggers_a_full_refetch_via_invalidate_queries", async () => {
    // Arrange: a stronger, direct assertion of the same Risk-3 property.
    server.use(
      http.post("/api/v1/admin/users/user-a/deactivate", async () =>
        HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Target User",
            status: "deactivated",
            roles: [],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useDeactivateAdminUser("user-a"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    result.current.mutate({ reason: "Left the organization" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
