import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useAdminUsers } from "./useAdminUsers";

function user(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "u-1",
    email: "user@example.com",
    display_name: "User One",
    status: "active",
    roles: ["support-agent"],
    created_at: "2026-09-01T00:00:00Z",
    last_login_at: "2026-09-02T00:00:00Z",
    ...overrides,
  };
}

describe("useAdminUsers", () => {
  it("test_use_admin_users_first_page_has_next_page_true_when_next_cursor_is_present", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [user()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAdminUsers());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.hasNextPage).toBe(true);
  });

  it("test_use_admin_users_has_next_page_false_when_next_cursor_is_null", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [user()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAdminUsers());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.hasNextPage).toBe(false);
  });

  it("test_use_admin_users_q_status_role_filters_are_sent_as_query_parameters", async () => {
    // Arrange
    let received: { q: string | null; status: string | null; role: string | null } | null = null;
    server.use(
      http.get("/api/v1/admin/users", async ({ request }) => {
        const url = new URL(request.url);
        received = {
          q: url.searchParams.get("q"),
          status: url.searchParams.get("status"),
          role: url.searchParams.get("role"),
        };
        return HttpResponse.json({ items: [user()], next_cursor: null }, { status: 200 });
      }),
    );

    // Act
    const { result } = renderHookWithProviders(() =>
      useAdminUsers({ q: "jane", status: "active", role: "admin" }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(received).toEqual({ q: "jane", status: "active", role: "admin" });
  });

  it("test_use_admin_users_changing_a_filter_resets_pagination_to_a_single_page", async () => {
    // Arrange: a filter change is a query-key change in TanStack Query, so
    // the previously-fetched second page must not survive into the new
    // filter's result set.
    server.use(
      http.get("/api/v1/admin/users", async ({ request }) => {
        const url = new URL(request.url);
        const status = url.searchParams.get("status");
        const cursor = url.searchParams.get("cursor");
        if (!status && !cursor) {
          return HttpResponse.json(
            { items: [user({ id: "u-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        if (!status && cursor === "cursor-2") {
          return HttpResponse.json({ items: [user({ id: "u-2" })], next_cursor: null }, { status: 200 });
        }
        return HttpResponse.json(
          { items: [user({ id: "u-3", status })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const statusRef: { current: string | undefined } = { current: undefined };
    const { result, rerender } = renderHookWithProviders(() => useAdminUsers({ status: statusRef.current }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));

    // Act
    statusRef.current = "deactivated";
    rerender();

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pages).toHaveLength(1);
  });
});
