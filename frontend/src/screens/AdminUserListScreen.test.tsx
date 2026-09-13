// AD-AC1/FR-1, XC-AC1 (this screen's slice), XC-AC2/XC-AC4, a11y bar.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AdminUserListScreen } from "./AdminUserListScreen";

function adminUser(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "u-1",
    email: "jane@example.com",
    display_name: "Jane Doe",
    status: "active",
    roles: ["support-agent"],
    created_at: "2026-09-01T10:00:00Z",
    last_login_at: "2026-09-02T10:00:00Z",
    ...overrides,
  };
}

describe("AdminUserListScreen", () => {
  it("test_admin_user_list_screen_renders_email_display_name_status_roles_created_at_and_last_login_at_per_row", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [adminUser()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    const row = (await screen.findByText("jane@example.com")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Jane Doe")).toBeInTheDocument();
    expect(within(row).getByText("active")).toBeInTheDocument();
    expect(within(row).getByText("support-agent")).toBeInTheDocument();
    expect(within(row).getByText(/2026-09-01/)).toBeInTheDocument();
    expect(within(row).getByText(/2026-09-02/)).toBeInTheDocument();
  });

  it("test_admin_user_list_screen_q_status_role_filters_re_request_the_list_and_reset_the_cursor", async () => {
    // Arrange
    const receivedRequests: {
      q: string | null;
      status: string | null;
      role: string | null;
      cursor: string | null;
    }[] = [];
    server.use(
      http.get("/api/v1/admin/users", async ({ request }) => {
        const url = new URL(request.url);
        receivedRequests.push({
          q: url.searchParams.get("q"),
          status: url.searchParams.get("status"),
          role: url.searchParams.get("role"),
          cursor: url.searchParams.get("cursor"),
        });
        if (receivedRequests.length === 1) {
          return HttpResponse.json({ items: [adminUser()], next_cursor: "cursor-2" }, { status: 200 });
        }
        return HttpResponse.json({ items: [adminUser({ id: "u-2" })], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });
    await screen.findByText("jane@example.com");

    // Act
    await user.selectOptions(screen.getByLabelText(/^status$/i), "active");

    // Assert
    const lastRequest = receivedRequests[receivedRequests.length - 1];
    expect(lastRequest).toEqual({ q: null, status: "active", role: null, cursor: null });
  });

  it("test_admin_user_list_screen_load_more_appends_the_next_page_and_disappears_when_next_cursor_is_null", async () => {
    // Arrange
    const receivedCursors: (string | null)[] = [];
    server.use(
      http.get("/api/v1/admin/users", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        receivedCursors.push(cursor);
        if (!cursor) {
          return HttpResponse.json(
            { items: [adminUser({ id: "u-1", email: "first@example.com" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json(
          { items: [adminUser({ id: "u-2", email: "second@example.com" })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });
    await screen.findByText("first@example.com");

    // Act
    await user.click(screen.getByRole("button", { name: /load more/i }));

    // Assert
    expect(await screen.findByText("second@example.com")).toBeInTheDocument();
    expect(receivedCursors).toEqual([null, "cursor-2"]);
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
  });

  it("test_admin_user_list_screen_never_renders_a_total_count_or_page_number", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [adminUser()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });
    await screen.findByText("jane@example.com");

    // Assert
    expect(screen.queryByText(/total/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/page \d+/i)).not.toBeInTheDocument();
  });

  it("test_admin_user_list_screen_renders_an_unrecognized_status_or_roles_value_verbatim", async () => {
    // Arrange (Implementation Plan Risk 7)
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json(
          {
            items: [adminUser({ status: "pending_legal_review", roles: ["temp-contractor-role"] })],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    expect(await screen.findByText("pending_legal_review")).toBeInTheDocument();
    expect(screen.getByText("temp-contractor-role")).toBeInTheDocument();
  });

  it("test_admin_user_list_screen_forced_403_from_the_server_renders_the_not_permitted_state_not_a_blank_screen_or_spinner", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "You do not have permission to view this page.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: [],
    });

    // Assert
    expect(await screen.findByRole("alert")).toHaveTextContent(/permission/i);
  });

  it("test_admin_user_list_screen_users_write_less_seed_disables_or_hides_the_create_user_control", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [adminUser()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });
    await screen.findByText("jane@example.com");

    // Assert
    expect(screen.queryByRole("link", { name: /create user/i })).not.toBeInTheDocument();
  });

  it("test_admin_user_list_screen_4xx_problem_json_renders_the_mapped_detail_with_no_raw_json", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/bad-request",
            title: "Bad request",
            status: 400,
            detail: "The role filter is not recognized.",
          },
          { status: 400, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    expect(await screen.findByText("The role filter is not recognized.")).toBeInTheDocument();
    expect(screen.queryByText(/"type":|"title":/)).not.toBeInTheDocument();
  });

  it("test_admin_user_list_screen_network_error_shows_a_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/admin/users", () => HttpResponse.error()));

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_user_list_screen_5xx_response_shows_a_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/admin/users", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_user_list_screen_renders_a_distinct_loading_state_before_the_query_resolves", async () => {
    // Arrange: no handler override — the default baseline handler resolves
    // asynchronously, so the pending state is observable first.
    // Act
    renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read"],
    });

    // Assert
    expect(screen.getByText(/loading users/i)).toBeInTheDocument();
  });

  it("test_admin_user_list_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users", async () =>
        HttpResponse.json({ items: [adminUser()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );
    const { container } = renderWithProviders(<AdminUserListScreen />, {
      route: "/admin/users",
      isAuthenticated: true,
      scopes: ["users:read", "users:write"],
    });
    await screen.findByText("jane@example.com");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
