import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { adminUserQueryKey } from "./useAdminUser";
import { useReplaceUserRoles } from "./useReplaceUserRoles";

describe("useReplaceUserRoles", () => {
  it("test_use_replace_user_roles_sends_the_full_replacement_list_via_put", async () => {
    // Arrange
    let receivedMethod: string | null = null;
    let receivedBody: unknown = null;
    server.use(
      http.put("/api/v1/admin/users/user-a/roles", async ({ request }) => {
        receivedMethod = request.method;
        receivedBody = await request.json();
        return HttpResponse.json({ roles: ["admin", "support-agent"] }, { status: 200 });
      }),
    );
    const { result } = renderHookWithProviders(() => useReplaceUserRoles("user-a"));

    // Act
    result.current.mutate({ roles: ["admin", "support-agent"] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedMethod).toBe("PUT");
    expect(receivedBody).toEqual({ roles: ["admin", "support-agent"] });
  });

  it("test_use_replace_user_roles_on_success_invalidates_use_admin_users_query_key_for_that_id", async () => {
    // Arrange (Implementation Plan Risk 3 — targeted invalidation of
    // useAdminUser.ts's detail query for this same user id, not a
    // hand-merged cache patch).
    server.use(
      http.put("/api/v1/admin/users/user-a/roles", async () =>
        HttpResponse.json({ roles: ["admin"] }, { status: 200 }),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useReplaceUserRoles("user-a"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    result.current.mutate({ roles: ["admin"] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(adminUserQueryKey("user-a"));
  });
});
