// US-5.4 FR-9's "net-new infrastructure" (spec Background): a pure,
// dependency-light JWT-claims decoder — base64url-decodes the access
// token's payload segment and reads its `scopes` claim. Decode-only, NEVER
// verified client-side (Story Assumption #2/#3; spec NFR "client-side scope
// decoding is never treated as authorization"). Colocated under `store/`
// rather than `api/` because it performs no I/O; imports nothing from
// `api/`/`hooks/` (AGENTS.md §3's `store/` row).
//
// A hand-rolled two-line `atob`/base64url helper per Implementation Plan
// Risk 1 (closed) — no `jwt-decode`/`jose`-class dependency is added.
// Malformed input (a non-JWT string, invalid base64, a payload whose JSON
// doesn't parse, or a `scopes` claim that isn't an array of strings) must
// never throw and must degrade to no scopes — a scope-decoding failure must
// never crash the app or silently grant access.

function base64UrlDecode(segment: string): string {
  const normalized = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  return atob(padded);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

/**
 * Decodes (never verifies) the `scopes` claim from a JWT's payload segment.
 * Returns `[]` for any malformed token or claim shape, never throws.
 */
export function decodeTokenScopes(token: string | null | undefined): string[] {
  if (!token) {
    return [];
  }

  try {
    const parts = token.split(".");
    if (parts.length < 2) {
      return [];
    }
    const payloadJson = base64UrlDecode(parts[1]);
    const payload: unknown = JSON.parse(payloadJson);
    if (typeof payload !== "object" || payload === null) {
      return [];
    }
    const scopes = (payload as Record<string, unknown>).scopes;
    return isStringArray(scopes) ? scopes : [];
  } catch {
    return [];
  }
}
