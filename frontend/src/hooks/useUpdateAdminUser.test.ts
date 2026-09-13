import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { adminUserEtagQueryKey } from "./useAdminUser";
import { useUpdateAdminUser } from "./useUpdateAdminUser";

describe("useUpdateAdminUser", () => {
  it("test_use_update_admin_user_sends_if_match_using_the_cached_etag_for_that_user", async () => {
    // Arrange
    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/admin/users/user-a", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Updated Name",
            status: "active",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200, headers: { ETag: "new-etag" } },
        );
      }),
    );
    const { result, queryClient } = renderHookWithProviders(() => useUpdateAdminUser("user-a"));
    queryClient.setQueryData(adminUserEtagQueryKey("user-a"), "cached-etag-1");

    // Act
    result.current.mutate({ display_name: "Updated Name", reason: "typo fix" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedIfMatch).toBe("cached-etag-1");
  });

  it("test_use_update_admin_user_412_sets_conflict_true", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/precondition-failed",
            title: "Precondition failed",
            status: 412,
            detail: "This user has changed since you last loaded it.",
          },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useUpdateAdminUser("user-a"));

    // Act
    result.current.mutate({ display_name: "Updated Name", reason: "typo fix" });
    await waitFor(() => expect(result.current.isError).toBe(true));

    // Assert
    expect(result.current.conflict).toBe(true);
  });

  it("test_use_update_admin_user_immutable_field_error_surfaces_the_problems_detail", async () => {
    // Arrange: should-be-unreachable in practice (FR-5 guarantees `roles` is
    // never sent to PATCH), but the hook must still surface this shape's
    // `detail` if the server ever returns it.
    server.use(
      http.patch("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(
          {
            type: "immutable-field",
            title: "Immutable field",
            status: 422,
            detail: "roles is immutable and cannot be updated via PATCH.",
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useUpdateAdminUser("user-a"));

    // Act
    result.current.mutate({ display_name: "Updated Name", reason: "typo fix" });
    await waitFor(() => expect(result.current.isError).toBe(true));

    // Assert
    expect(result.current.immutableFieldDetail).toBe("roles is immutable and cannot be updated via PATCH.");
  });

  it("test_use_update_admin_user_never_includes_roles_in_the_patch_body", async () => {
    // Arrange
    let receivedBody: unknown = null;
    server.use(
      http.patch("/api/v1/admin/users/user-a", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          {
            id: "user-a",
            email: "target@example.com",
            display_name: "Updated Name",
            status: "active",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useUpdateAdminUser("user-a"));

    // Act
    result.current.mutate({ display_name: "Updated Name", reason: "typo fix" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedBody).not.toHaveProperty("roles");
  });
});
