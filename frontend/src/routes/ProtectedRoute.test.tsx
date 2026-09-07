// Unit/integration test for ProtectedRoute (Task T7, FE-AC10's first half).
// Collaborator-shape assumption: `ProtectedRoute` reads `useAuthStore()`
// (read-only, per AGENTS.md §3's `routes/` row) and either renders its
// `children`/`<Outlet />` or a `<Navigate to="/login" state={{ from: location }} />`.
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/test-utils";
import { ProtectedRoute } from "./ProtectedRoute";

describe("ProtectedRoute", () => {
  it("test_protected_route_unauthenticated_visitor_is_redirected_to_login", () => {
    // Arrange / Act
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { route: "/sessions", isAuthenticated: false },
    );

    // Assert
    expect(screen.queryByText("Secret content")).not.toBeInTheDocument();
    expect(screen.getByTestId("route-location").textContent).toBe("/login");
  });

  it("test_protected_route_remembers_the_originally_requested_route_for_post_login_return", () => {
    // Arrange / Act
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { route: "/sessions", isAuthenticated: false },
    );

    // Assert: the redirect's location state carries the original path so a
    // successful login can return the visitor there (asserted end-to-end in
    // routes/AppRoutes.test.tsx; here we assert the state is present).
    expect(screen.getByTestId("route-location-state").textContent).toBe("/sessions");
  });

  it("test_protected_route_authenticated_visitor_renders_the_protected_children", () => {
    // Arrange / Act
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { route: "/sessions", isAuthenticated: true },
    );

    // Assert
    expect(screen.getByText("Secret content")).toBeInTheDocument();
  });
});
