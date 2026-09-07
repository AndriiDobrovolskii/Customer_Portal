// Unit test for the shared FieldError component (Task T8, FE-AC9's 422 mapping).
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FieldError } from "./FieldError";

describe("FieldError", () => {
  it("test_field_error_renders_the_mapped_message_for_its_field_when_present", () => {
    // Arrange / Act
    render(<FieldError fieldErrors={{ email: "Not a valid email address." }} field="email" />);

    // Assert
    expect(screen.getByText("Not a valid email address.")).toBeInTheDocument();
  });

  it("test_field_error_renders_nothing_when_its_field_has_no_mapped_error", () => {
    // Arrange / Act
    const { container } = render(<FieldError fieldErrors={{ email: "bad" }} field="password" />);

    // Assert
    expect(container).toBeEmptyDOMElement();
  });
});
