import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useCreateAdminUser } from "./useCreateAdminUser";

describe("useCreateAdminUser", () => {
  it("test_use_create_admin_user_sends_exactly_email_display_name_and_roles", async () => {
    // Arrange
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/v1/admin/users", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          {
            id: "new-u1",
            email: "new@example.com",
            display_name: "New User",
            status: "invited",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 201 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateAdminUser());

    // Act
    result.current.mutate({ email: "new@example.com", display_name: "New User", roles: ["support-agent"] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedBody).toEqual({
      email: "new@example.com",
      display_name: "New User",
      roles: ["support-agent"],
    });
    expect(Object.keys(receivedBody as Record<string, unknown>)).toEqual(["email", "display_name", "roles"]);
  });

  it("test_use_create_admin_user_never_sends_a_password_field", async () => {
    // Arrange
    let receivedBody: unknown = null;
    server.use(
      http.post("/api/v1/admin/users", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(
          {
            id: "new-u1",
            email: "new@example.com",
            display_name: "New User",
            status: "invited",
            roles: [],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 201 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateAdminUser());

    // Act
    result.current.mutate({ email: "new@example.com", display_name: "New User", roles: [] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedBody).not.toHaveProperty("password");
  });

  it("test_use_create_admin_user_on_success_resolves_with_the_new_users_id_for_navigation", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/admin/users", async () =>
        HttpResponse.json(
          {
            id: "new-u1",
            email: "new@example.com",
            display_name: "New User",
            status: "invited",
            roles: [],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 201 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useCreateAdminUser());

    // Act
    result.current.mutate({ email: "new@example.com", display_name: "New User", roles: [] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.data?.id).toBe("new-u1");
  });
});
