// Pure-function unit coverage for the new decoder (docs/tests/US-5.4-ac-test-matrix.md,
// "decodeTokenScopes" section) — no equivalent test existed before this Story.
import { describe, it, expect } from "vitest";
import { decodeTokenScopes } from "./decodeTokenScopes";

function base64UrlEncode(json: string): string {
  const base64 = btoa(json);
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function buildToken(payload: Record<string, unknown>): string {
  const header = base64UrlEncode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = base64UrlEncode(JSON.stringify(payload));
  return `${header}.${body}.unverified-signature`;
}

describe("decodeTokenScopes", () => {
  it("test_decode_token_scopes_returns_the_scopes_claim_from_a_well_formed_token", () => {
    // Arrange
    const token = buildToken({ sub: "u1", scopes: ["users:read", "users:write"] });

    // Act
    const scopes = decodeTokenScopes(token);

    // Assert
    expect(scopes).toEqual(["users:read", "users:write"]);
  });

  it("test_decode_token_scopes_returns_an_empty_array_when_the_scopes_claim_is_absent", () => {
    // Arrange
    const token = buildToken({ sub: "u1" });

    // Act
    const scopes = decodeTokenScopes(token);

    // Assert
    expect(scopes).toEqual([]);
  });

  it("test_decode_token_scopes_returns_an_empty_array_and_does_not_throw_on_a_malformed_payload", () => {
    // Arrange: a non-base64 / non-JWT-shaped payload segment.
    const malformedToken = "not-a-jwt";

    // Act / Assert
    expect(() => decodeTokenScopes(malformedToken)).not.toThrow();
    expect(decodeTokenScopes(malformedToken)).toEqual([]);
  });

  it("test_decode_token_scopes_returns_an_empty_array_for_a_null_or_undefined_token", () => {
    // Act / Assert
    expect(decodeTokenScopes(null)).toEqual([]);
    expect(decodeTokenScopes(undefined)).toEqual([]);
  });

  it("test_decode_token_scopes_returns_an_empty_array_when_the_scopes_claim_is_not_an_array_of_strings", () => {
    // Arrange: a scopes claim shaped as a bare string must never be iterated
    // character-by-character into a fake "scopes" array.
    const token = buildToken({ sub: "u1", scopes: "users:read" });

    // Act
    const scopes = decodeTokenScopes(token);

    // Assert
    expect(scopes).toEqual([]);
  });

  it("test_decode_token_scopes_returns_an_empty_array_when_the_payload_segment_is_not_valid_json", () => {
    // Arrange: valid base64url, but the decoded text is not JSON.
    const header = "eyJhbGciOiJIUzI1NiJ9";
    const body = btoa("not-json").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    const token = `${header}.${body}.sig`;

    // Act / Assert
    expect(() => decodeTokenScopes(token)).not.toThrow();
    expect(decodeTokenScopes(token)).toEqual([]);
  });
});
