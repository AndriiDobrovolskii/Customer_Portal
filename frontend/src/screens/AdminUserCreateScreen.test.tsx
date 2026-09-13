// AD-AC3/FR-3 (Resolution OD-4), XC-AC2 (this screen's 422 slice),
// XC-AC3 (this screen's slice), XC-AC4 (this screen's slice), loading state.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AdminUserCreateScreen } from "./AdminUserCreateScreen";

function seedRoles() {
  server.use(
    http.get("/api/v1/admin/roles", async () =>
      HttpResponse.json(
        {
          roles: [
            { name: "billing-admin", permissions: [] },
            { name: "support-agent", permissions: [] },
          ],
        },
        { status: 200 },
      ),
    ),
  );
}

describe("AdminUserCreateScreen", () => {
  it("test_admin_user_create_screen_submits_exactly_email_display_name_and_roles", async () => {
    // Arrange
    seedRoles();
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
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    await screen.findByTestId("route-location");
    expect(receivedBody).toEqual({
      email: "new@example.com",
      display_name: "New User",
      roles: ["support-agent"],
    });
    expect(Object.keys(receivedBody as Record<string, unknown>)).toEqual(["email", "display_name", "roles"]);
  });

  it("test_admin_user_create_screen_never_renders_a_password_field_anywhere_in_the_dom", async () => {
    // Arrange
    seedRoles();

    // Act
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Assert
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("test_admin_user_create_screen_roles_options_are_sourced_only_from_get_admin_roles_no_free_text_entry", async () => {
    // Arrange (Resolution OD-4)
    seedRoles();

    // Act
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    const rolesSelect = await screen.findByLabelText(/^roles$/i);

    // Assert
    const optionLabels = within(rolesSelect)
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(optionLabels).toEqual(["billing-admin", "support-agent"]);
    expect(screen.queryByRole("textbox", { name: /role/i })).not.toBeInTheDocument();
  });

  it("test_admin_user_create_screen_on_201_navigates_to_the_new_users_detail_screen", async () => {
    // Arrange
    seedRoles();
    server.use(
      http.post("/api/v1/admin/users", async () =>
        HttpResponse.json(
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
        ),
      ),
      http.get("/api/v1/admin/users/new-u1", async () =>
        HttpResponse.json(
          {
            id: "new-u1",
            email: "new@example.com",
            display_name: "New User",
            status: "invited",
            roles: ["support-agent"],
            created_at: "2026-09-01T00:00:00Z",
            last_login_at: null,
          },
          { status: 200, headers: { ETag: "etag-1" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/admin/users/new-u1");
  });

  it("test_admin_user_create_screen_422_validation_error_maps_the_errors_array_onto_the_matching_fields", async () => {
    // Arrange
    seedRoles();
    server.use(
      http.post("/api/v1/admin/users", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            detail: "Validation failed.",
            errors: [{ field: "email", message: "This email is already registered." }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "taken@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    expect(await screen.findByText("This email is already registered.")).toBeInTheDocument();
  });

  it("test_admin_user_create_screen_blocks_submission_on_invalid_email_shape_without_calling_the_api", async () => {
    // Arrange
    seedRoles();
    let apiCalled = false;
    server.use(
      http.post("/api/v1/admin/users", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "x" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "not-an-email");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid email/i);
    expect(apiCalled).toBe(false);
  });

  it("test_admin_user_create_screen_blocks_submission_on_an_empty_role_selection_without_calling_the_api", async () => {
    // Arrange
    seedRoles();
    let apiCalled = false;
    server.use(
      http.post("/api/v1/admin/users", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "x" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    expect(await screen.findByRole("alert")).toHaveTextContent(/select at least one role/i);
    expect(apiCalled).toBe(false);
  });

  it("test_admin_user_create_screen_network_error_shows_a_retry_capable_error_state", async () => {
    // Arrange
    seedRoles();
    server.use(http.post("/api/v1/admin/users", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });
    await screen.findByLabelText(/^roles$/i);

    // Act
    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/display name/i), "New User");
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);
    await user.click(screen.getByRole("button", { name: /create user/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_user_create_screen_renders_a_distinct_loading_state_before_the_role_catalogue_resolves", () => {
    // Arrange / Act: no override — the default baseline handler resolves
    // asynchronously, so the pending state is observable first.
    renderWithProviders(<AdminUserCreateScreen />, {
      route: "/admin/users/new",
      isAuthenticated: true,
      scopes: ["users:write"],
    });

    // Assert
    expect(screen.getByText(/loading role catalogue/i)).toBeInTheDocument();
  });
});
