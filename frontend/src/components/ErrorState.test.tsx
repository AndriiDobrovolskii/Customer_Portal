// Unit test for the shared ErrorState component (Task T8, FE-AC11).
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("test_error_state_renders_a_generic_retry_capable_message_for_a_network_error", () => {
    // Arrange / Act
    render(<ErrorState kind="network" onRetry={() => {}} />);

    // Assert
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("test_error_state_renders_a_generic_retry_capable_message_for_a_5xx_response", () => {
    // Arrange / Act
    render(<ErrorState kind="server" onRetry={() => {}} />);

    // Assert
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it("test_error_state_retry_button_invokes_the_provided_callback", async () => {
    // Arrange
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<ErrorState kind="network" onRetry={onRetry} />);

    // Act
    await user.click(screen.getByRole("button", { name: /retry/i }));

    // Assert
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
