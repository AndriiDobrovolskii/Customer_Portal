// Unit test for apiErrorHelpers.ts (Task T3). No dedicated test file existed
// for this module before US-5.2 (its three existing functions,
// `getErrorKind`/`getErrorMessage`/`getFieldErrors`, were exercised only
// indirectly through screen-level integration tests) — this pass adds direct
// coverage for all four, including the new `getErrorStatus` (Plan Change 4),
// which FR-2's 412-conflict detection needs without `ProfileScreen.tsx`
// importing `api/httpClient.ts`'s `ApiError` class directly (AGENTS.md §3
// Frontend table).
import { describe, it, expect } from "vitest";
import { getErrorKind, getErrorMessage, getFieldErrors, getErrorStatus } from "./apiErrorHelpers";

describe("apiErrorHelpers", () => {
  describe("getErrorStatus", () => {
    it("test_get_error_status_returns_the_numeric_status_from_a_structural_error", () => {
      expect(getErrorStatus({ status: 412, message: "conflict" })).toBe(412);
    });

    it("test_get_error_status_returns_undefined_for_a_non_object_error", () => {
      expect(getErrorStatus("not an error object")).toBeUndefined();
      expect(getErrorStatus(undefined)).toBeUndefined();
      expect(getErrorStatus(null)).toBeUndefined();
    });

    it("test_get_error_status_returns_undefined_when_status_field_is_absent", () => {
      expect(getErrorStatus({ message: "no status here" })).toBeUndefined();
    });
  });

  describe("getErrorKind", () => {
    it("test_get_error_kind_returns_network_or_server_when_present", () => {
      expect(getErrorKind({ kind: "network" })).toBe("network");
      expect(getErrorKind({ kind: "server" })).toBe("server");
    });

    it("test_get_error_kind_returns_undefined_for_an_unrecognized_kind_value", () => {
      expect(getErrorKind({ kind: "not-a-real-kind" })).toBeUndefined();
      expect(getErrorKind(undefined)).toBeUndefined();
    });
  });

  describe("getErrorMessage", () => {
    it("test_get_error_message_returns_the_message_field_when_present", () => {
      expect(getErrorMessage({ message: "Something specific broke." })).toBe("Something specific broke.");
    });

    it("test_get_error_message_falls_back_to_the_default_generic_message_when_absent", () => {
      expect(getErrorMessage(undefined)).toBe("Something went wrong. Please try again.");
      expect(getErrorMessage({})).toBe("Something went wrong. Please try again.");
    });

    it("test_get_error_message_falls_back_to_a_caller_supplied_message_when_provided", () => {
      expect(getErrorMessage(undefined, "Custom fallback.")).toBe("Custom fallback.");
    });
  });

  describe("getFieldErrors", () => {
    it("test_get_field_errors_returns_the_field_errors_record_when_present", () => {
      expect(getFieldErrors({ fieldErrors: { email: "Invalid email." } })).toEqual({
        email: "Invalid email.",
      });
    });

    it("test_get_field_errors_returns_undefined_when_absent", () => {
      expect(getFieldErrors({ message: "no field errors" })).toBeUndefined();
      expect(getFieldErrors(undefined)).toBeUndefined();
    });
  });
});
