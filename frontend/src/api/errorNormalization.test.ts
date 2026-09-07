// Unit tests for the error-normalization layer (Task T2, FE-AC9 / OD-4).
// Collaborator-shape assumption: `normalizeApiError(input: { status: number;
// body: unknown; contentType: string | null }): NormalizedApiError` where
// `NormalizedApiError = { status: number; message: string; fieldErrors?:
// Record<string, string> }`. This is Architectural Change 8 of
// docs/plans/US-5.1-implementation-plan.md — it absorbs OD-4's two
// non-RFC7807 Register shapes into the same internal shape every screen's
// error rendering consumes.
//
// Expected to fail at collection/import time until IMPLEMENTATION lands
// `frontend/src/api/errorNormalization.ts`.
import { describe, it, expect } from "vitest";
import { normalizeApiError } from "./errorNormalization";

describe("normalizeApiError", () => {
  it("test_normalize_api_error_maps_rfc7807_problem_json_detail_to_message", () => {
    // Arrange
    const input = {
      status: 401,
      contentType: "application/problem+json",
      body: {
        type: "https://errors.example/invalid-credentials",
        title: "Invalid credentials",
        status: 401,
        detail: "The email or password is incorrect.",
      },
    };

    // Act
    const result = normalizeApiError(input);

    // Assert
    expect(result.status).toBe(401);
    expect(result.message).toBe("The email or password is incorrect.");
    expect(result.fieldErrors).toBeUndefined();
  });

  it("test_normalize_api_error_maps_422_errors_array_to_field_errors", () => {
    // Arrange
    const input = {
      status: 422,
      contentType: "application/problem+json",
      body: {
        type: "https://errors.example/validation-failed",
        title: "Validation failed",
        status: 422,
        detail: "One or more fields are invalid.",
        errors: [
          { field: "email", message: "Not a valid email address.", code: "invalid_format" },
          { field: "password", message: "Password is too short.", code: "too_short" },
        ],
      },
    };

    // Act
    const result = normalizeApiError(input);

    // Assert
    expect(result.status).toBe(422);
    expect(result.fieldErrors).toEqual({
      email: "Not a valid email address.",
      password: "Password is too short.", // pragma: allowlist secret
    });
  });

  it("test_normalize_api_error_maps_register_400_validation_error_shape_without_problem_json_envelope", () => {
    // Arrange: RegistrationValidationError — 400, plain application/json,
    // {"errors":[{field,message,code}]}, no type/title/detail (OD-4).
    const input = {
      status: 400,
      contentType: "application/json",
      body: {
        errors: [{ field: "password", message: "Password must contain a digit.", code: "weak_password" }],
      },
    };

    // Act
    const result = normalizeApiError(input);

    // Assert
    expect(result.status).toBe(400);
    expect(result.fieldErrors).toEqual({ password: "Password must contain a digit." }); // pragma: allowlist secret
    expect(result.message).not.toMatch(/\[object Object\]/);
  });

  it("test_normalize_api_error_maps_register_409_duplicate_email_shape_without_problem_json_envelope", () => {
    // Arrange: DuplicateEmailError — 409, plain application/json,
    // {"detail": "..."}, no type/title/errors (OD-4).
    const input = {
      status: 409,
      contentType: "application/json",
      body: { detail: "Email is already registered." },
    };

    // Act
    const result = normalizeApiError(input);

    // Assert
    expect(result.status).toBe(409);
    expect(result.message).toBe("Email is already registered.");
    expect(result.fieldErrors).toBeUndefined();
  });

  it("test_normalize_api_error_never_renders_raw_json_or_stack_trace_for_an_unrecognized_shape", () => {
    // Arrange: a body with none of the known shapes present.
    const input = { status: 500, contentType: "text/plain", body: "Internal Server Error" };

    // Act
    const result = normalizeApiError(input);

    // Assert: falls through to a generic, human-readable message — never the raw body.
    expect(result.message).not.toContain("Internal Server Error");
    expect(result.status).toBe(500);
  });
});
