// Unit/integration test for GuestOnlyRoute (Task T7, FE-AC10's converse half).
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/test-utils";
import { GuestOnlyRoute } from "./GuestOnlyRoute";

describe("GuestOnlyRoute", () => {
  it("test_guest_only_route_authenticated_user_is_redirected_to_placeholder_home", () => {
    // Arrange / Act
    renderWithProviders(
      <GuestOnlyRoute>
        <div>Login form</div>
      </GuestOnlyRoute>,
      { route: "/login", isAuthenticated: true },
    );

    // Assert
    expect(screen.queryByText("Login form")).not.toBeInTheDocument();
    expect(screen.getByTestId("route-location").textContent).toBe("/");
  });

  it("test_guest_only_route_unauthenticated_visitor_renders_the_guest_children", () => {
    // Arrange / Act
    renderWithProviders(
      <GuestOnlyRoute>
        <div>Login form</div>
      </GuestOnlyRoute>,
      { route: "/login", isAuthenticated: false },
    );

    // Assert
    expect(screen.getByText("Login form")).toBeInTheDocument();
  });
});
