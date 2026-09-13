// AD-AC2/AD-AC4/AD-AC5/AD-AC6/AD-AC7, XC-AC1 (this screen's slice),
// XC-AC3 (shared with AD-AC4), XC-AC4 (this screen's slice), a11y bar.
//
// implementation_plan v2 Risk 2 precedent (TicketDetailScreen.test.tsx):
// test-utils.tsx has no built-in URL-param route; this file wraps `ui` in
// its own local <Routes><Route path="/admin/users/:id" .../></Routes>
// rather than changing test-utils.tsx's signature.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders, waitFor } from "../test/test-utils";
import { AdminUserDetailScreen } from "./AdminUserDetailScreen";

function renderDetail(id = "user-a", scopes: string[] = ["users:read", "users:write", "roles:write"]) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/users/:id" element={<AdminUserDetailScreen />} />
    </Routes>,
    { route: `/admin/users/${id}`, isAuthenticated: true, scopes },
  );
}

function adminUser(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "user-a",
    email: "target@example.com",
    display_name: "Target User",
    status: "active",
    roles: ["support-agent"],
    created_at: "2026-09-01T00:00:00Z",
    last_login_at: "2026-09-02T00:00:00Z",
    ...overrides,
  };
}

function seedRoleCatalogue(roles: string[] = ["support-agent", "billing-admin", "admin"]) {
  server.use(
    http.get("/api/v1/admin/roles", async () =>
      HttpResponse.json({ roles: roles.map((name) => ({ name, permissions: [] })) }, { status: 200 }),
    ),
  );
}

describe("AdminUserDetailScreen", () => {
  it("test_admin_user_detail_screen_get_captures_the_etag_and_echoes_it_as_if_match_on_the_next_patch", async () => {
    // Arrange
    seedRoleCatalogue();
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser(), { status: 200, headers: { ETag: "etag-user-a" } }),
      ),
    );
    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/admin/users/user-a", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(adminUser({ display_name: "Renamed" }), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    const editForm = screen.getByRole("form", { name: /edit user details/i });
    await user.clear(within(editForm).getByLabelText(/display name/i));
    await user.type(within(editForm).getByLabelText(/display name/i), "Renamed");
    await user.type(within(editForm).getByLabelText(/^reason$/i), "typo fix");
    await user.click(within(editForm).getByRole("button", { name: /save changes/i }));

    // Assert
    await waitFor(() => expect(receivedIfMatch).toBe("etag-user-a"));
  });

  it("test_admin_user_detail_screen_requires_a_non_empty_reason_before_a_field_edit_can_be_submitted", async () => {
    // Arrange (AD-AC4, XC-AC3)
    seedRoleCatalogue();
    let patchCalled = false;
    server.use(
      http.patch("/api/v1/admin/users/user-a", async () => {
        patchCalled = true;
        return HttpResponse.json(adminUser(), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });
    const editForm = screen.getByRole("form", { name: /edit user details/i });

    // Act
    await user.clear(within(editForm).getByLabelText(/display name/i));
    await user.type(within(editForm).getByLabelText(/display name/i), "Renamed");
    await user.click(within(editForm).getByRole("button", { name: /save changes/i }));

    // Assert
    expect(await within(editForm).findByRole("alert")).toHaveTextContent(/reason is required/i);
    expect(patchCalled).toBe(false);
  });

  it("test_admin_user_detail_screen_412_renders_a_conflict_state", async () => {
    // Arrange
    seedRoleCatalogue();
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
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });
    const editForm = screen.getByRole("form", { name: /edit user details/i });

    // Act
    await user.type(within(editForm).getByLabelText(/^reason$/i), "typo fix");
    await user.click(within(editForm).getByRole("button", { name: /save changes/i }));

    // Assert
    expect(await screen.findByText(/changed elsewhere/i)).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_immutable_field_problem_renders_its_own_detail", async () => {
    // Arrange: should-be-unreachable in practice (FR-5 guarantees `roles` is
    // never sent to PATCH), but the screen must still surface this shape's
    // detail if the server ever returns it.
    seedRoleCatalogue();
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
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });
    const editForm = screen.getByRole("form", { name: /edit user details/i });

    // Act
    await user.type(within(editForm).getByLabelText(/^reason$/i), "typo fix");
    await user.click(within(editForm).getByRole("button", { name: /save changes/i }));

    // Assert
    expect(
      await screen.findByText("roles is immutable and cannot be updated via PATCH."),
    ).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_patch_never_includes_a_roles_field", async () => {
    // Arrange
    seedRoleCatalogue();
    let receivedBody: unknown = null;
    server.use(
      http.patch("/api/v1/admin/users/user-a", async ({ request }) => {
        receivedBody = await request.json();
        return HttpResponse.json(adminUser(), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });
    const editForm = screen.getByRole("form", { name: /edit user details/i });

    // Act
    await user.type(within(editForm).getByLabelText(/^reason$/i), "typo fix");
    await user.click(within(editForm).getByRole("button", { name: /save changes/i }));

    // Assert
    await waitFor(() => expect(receivedBody).not.toBeNull());
    expect(receivedBody).not.toHaveProperty("roles");
  });

  it("test_admin_user_detail_screen_role_save_hits_put_users_id_roles_with_the_full_replacement_list", async () => {
    // Arrange
    seedRoleCatalogue(["support-agent", "billing-admin"]);
    let receivedMethod: string | null = null;
    let receivedBody: unknown = null;
    server.use(
      http.put("/api/v1/admin/users/user-a/roles", async ({ request }) => {
        receivedMethod = request.method;
        receivedBody = await request.json();
        return HttpResponse.json({ roles: ["support-agent", "billing-admin"] }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent", "billing-admin"]);
    await user.click(screen.getByRole("button", { name: /save role changes/i }));
    await user.click(screen.getByRole("button", { name: /confirm role changes/i }));

    // Assert
    await waitFor(() => expect(receivedBody).not.toBeNull());
    expect(receivedMethod).toBe("PUT");
    expect(receivedBody).toEqual({ roles: ["support-agent", "billing-admin"] });
  });

  it("test_admin_user_detail_screen_role_control_is_disabled_without_roles_write", async () => {
    // Arrange
    seedRoleCatalogue();

    // Act
    renderDetail("user-a", ["users:read", "users:write"]);
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Assert
    expect(screen.getByLabelText(/^roles$/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /save role changes/i })).toBeDisabled();
  });

  it("test_admin_user_detail_screen_forced_403_on_a_role_save_attempt_still_renders_correctly", async () => {
    // Arrange
    seedRoleCatalogue(["support-agent", "billing-admin"]);
    server.use(
      http.put("/api/v1/admin/users/user-a/roles", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "You do not have permission to change roles.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent", "billing-admin"]);
    await user.click(screen.getByRole("button", { name: /save role changes/i }));
    await user.click(screen.getByRole("button", { name: /confirm role changes/i }));

    // Assert
    expect(await screen.findByText("You do not have permission to change roles.")).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_confirmation_computes_gained_and_lost_role_sets_with_a_reordered_seed", async () => {
    // Arrange (Resolution OD-3, Implementation Plan Risk 6): the catalogue
    // returns roles in a different order than the user's current roles.
    seedRoleCatalogue(["admin", "billing-admin", "support-agent"]);
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser({ roles: ["support-agent", "billing-admin"] }), { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act: deselect billing-admin, select admin — net gain "admin", net loss
    // "billing-admin", "support-agent" unchanged. `selectOptions` only adds
    // to the current multi-select selection (it never deselects an
    // already-selected option on its own), so `billing-admin` must be
    // explicitly deselected first.
    await user.deselectOptions(screen.getByLabelText(/^roles$/i), ["billing-admin"]);
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["admin"]);
    await user.click(screen.getByRole("button", { name: /save role changes/i }));

    // Assert
    const gainedHeading = screen.getByRole("heading", { name: /gained roles/i });
    const lostHeading = screen.getByRole("heading", { name: /lost roles/i });
    expect(gainedHeading.nextElementSibling).toHaveTextContent("admin");
    expect(lostHeading.nextElementSibling).toHaveTextContent("billing-admin");
  });

  it("test_admin_user_detail_screen_save_is_disabled_when_the_selected_role_set_equals_the_current_set", async () => {
    // Arrange
    seedRoleCatalogue(["billing-admin", "support-agent"]);
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser({ roles: ["support-agent", "billing-admin"] }), { status: 200 }),
      ),
    );

    // Act
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Assert: selection is initialized from the current roles, so the sets
    // are equal before any change — Save must start disabled.
    expect(screen.getByRole("button", { name: /save role changes/i })).toBeDisabled();
  });

  it("test_admin_user_detail_screen_save_becomes_enabled_the_moment_either_set_differs", async () => {
    // Arrange
    seedRoleCatalogue(["billing-admin", "support-agent"]);
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser({ roles: ["support-agent"] }), { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });
    expect(screen.getByRole("button", { name: /save role changes/i })).toBeDisabled();

    // Act
    await user.selectOptions(screen.getByLabelText(/^roles$/i), ["support-agent", "billing-admin"]);

    // Assert
    expect(screen.getByRole("button", { name: /save role changes/i })).not.toBeDisabled();
  });

  it("test_admin_user_detail_screen_blocks_an_empty_role_selection_as_a_separate_always_blocking_case", async () => {
    // Arrange
    seedRoleCatalogue(["support-agent"]);
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
        HttpResponse.json(adminUser({ roles: ["support-agent"] }), { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act: deselect every role.
    await user.deselectOptions(screen.getByLabelText(/^roles$/i), ["support-agent"]);

    // Assert
    expect(screen.getByRole("button", { name: /save role changes/i })).toBeDisabled();
    expect(screen.getByText(/select at least one role/i)).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_deactivate_requires_a_non_empty_reason_and_sits_behind_confirmation", async () => {
    // Arrange
    seedRoleCatalogue();
    let deactivateCalled = false;
    server.use(
      http.post("/api/v1/admin/users/user-a/deactivate", async () => {
        deactivateCalled = true;
        return HttpResponse.json(adminUser({ status: "deactivated" }), { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act: the confirmation step must appear before any form is visible.
    expect(screen.queryByRole("form", { name: /deactivate user/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^deactivate$/i }));
    const deactivateForm = await screen.findByRole("form", { name: /deactivate user/i });
    await user.click(within(deactivateForm).getByRole("button", { name: /confirm deactivation/i }));

    // Assert
    expect(await within(deactivateForm).findByRole("alert")).toHaveTextContent(/reason is required/i);
    expect(deactivateCalled).toBe(false);
  });

  it("test_admin_user_detail_screen_deactivate_success_reflects_the_returned_status", async () => {
    // Arrange
    seedRoleCatalogue();
    server.use(
      http.post("/api/v1/admin/users/user-a/deactivate", async () =>
        HttpResponse.json(adminUser({ status: "deactivated" }), { status: 200 }),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    await user.click(screen.getByRole("button", { name: /^deactivate$/i }));
    const deactivateForm = await screen.findByRole("form", { name: /deactivate user/i });
    await user.type(within(deactivateForm).getByLabelText(/^reason$/i), "Left the organization");
    await user.click(within(deactivateForm).getByRole("button", { name: /confirm deactivation/i }));

    // Assert
    expect(await screen.findByText("deactivated")).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_resend_invite_shows_a_generic_confirmation_and_never_displays_the_202_body", async () => {
    // Arrange
    seedRoleCatalogue();
    server.use(
      http.post("/api/v1/admin/users/user-a/resend-invite", async () =>
        HttpResponse.json(
          { message: "Invite resent to target@example.com via SES message id abc123." },
          { status: 202 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    await user.click(screen.getByRole("button", { name: /resend invite/i }));

    // Assert
    expect(await screen.findByRole("status")).toHaveTextContent(/invite resent/i);
    expect(screen.queryByText(/ses message id/i)).not.toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_never_renders_a_delete_control", async () => {
    // Arrange
    seedRoleCatalogue();

    // Act
    renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Assert
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_users_read_only_seed_disables_every_write_control", async () => {
    // Arrange
    seedRoleCatalogue();

    // Act
    renderDetail("user-a", ["users:read"]);
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Assert
    const editForm = screen.getByRole("form", { name: /edit user details/i });
    expect(within(editForm).getByRole("button", { name: /save changes/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^deactivate$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /resend invite/i })).toBeDisabled();
    expect(screen.getByLabelText(/^roles$/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /save role changes/i })).toBeDisabled();
  });

  it("test_admin_user_detail_screen_forced_403_on_a_scope_less_direct_navigation_renders_not_permitted_never_blank_or_spinner", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/users/user-a", async () =>
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
    renderDetail("user-a", []);

    // Assert
    expect(await screen.findByRole("alert")).toHaveTextContent(/permission/i);
  });

  it("test_admin_user_detail_screen_network_error_shows_a_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/admin/users/user-a", () => HttpResponse.error()));

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_renders_a_distinct_loading_state_before_the_user_query_resolves", () => {
    // Arrange / Act
    renderDetail();

    // Assert
    expect(screen.getByText(/loading user/i)).toBeInTheDocument();
  });

  it("test_admin_user_detail_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    seedRoleCatalogue();
    const { container } = renderDetail();
    await screen.findByRole("heading", { name: /target@example.com/i });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
