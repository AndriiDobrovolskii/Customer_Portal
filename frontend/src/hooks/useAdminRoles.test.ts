import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { ADMIN_ROLES_QUERY_KEY, useAdminRoles } from "./useAdminRoles";

describe("useAdminRoles", () => {
  it("test_use_admin_roles_fetches_the_role_catalogue_once_and_is_not_paginated", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/roles", async () =>
        HttpResponse.json({ roles: [{ name: "admin", permissions: ["users:read"] }] }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAdminRoles());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert: a bare `{roles}` result, no `.pages`/`fetchNextPage`.
    expect(result.current.data).toEqual({ roles: [{ name: "admin", permissions: ["users:read"] }] });
    expect((result.current as unknown as { pages?: unknown }).pages).toBeUndefined();
  });

  it("test_use_admin_roles_is_the_same_query_key_consumed_by_create_and_replace_paths", async () => {
    // Arrange: two independent call sites (standing in for
    // AdminUserCreateScreen.tsx and AdminUserDetailScreen.tsx's role
    // control) reading the exact same query key must dedupe onto a single
    // network request, never a per-screen copy.
    let callCount = 0;
    server.use(
      http.get("/api/v1/admin/roles", async () => {
        callCount += 1;
        return HttpResponse.json(
          { roles: [{ name: "admin", permissions: ["users:read"] }] },
          { status: 200 },
        );
      }),
    );

    // Act
    const { result, queryClient } = renderHookWithProviders(() => ({
      createPath: useAdminRoles(),
      replacePath: useAdminRoles(),
    }));
    await waitFor(() => expect(result.current.createPath.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.replacePath.isSuccess).toBe(true));

    // Assert
    expect(callCount).toBe(1);
    expect(result.current.createPath.data).toBe(result.current.replacePath.data);
    // Pins the property by identity — both call sites' cached result lives
    // under the one exported key, not merely two calls that happened to
    // dedupe within this single renderHook instance.
    expect(queryClient.getQueryData(ADMIN_ROLES_QUERY_KEY)).toBe(result.current.createPath.data);
  });
});
