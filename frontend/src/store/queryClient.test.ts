// Unit test for the shared TanStack Query client singleton (frontend-builder,
// IMPLEMENTATION re-pass for US-5.2). `queryClient.ts` is imported once by
// `App.tsx` to wire the app's real `<QueryClientProvider>`, but every test
// file builds its own isolated `QueryClient` via `test/test-utils.tsx`
// instead (deliberately, per that file's own header comment, so query cache
// state never leaks between tests) — so this module was never imported by
// the test suite and its module-level `new QueryClient(...)` construction
// never ran. This test imports the real singleton directly and asserts on
// its configured default options, closing that coverage gap without
// changing `test-utils.tsx`'s per-test isolation behavior.
import { describe, it, expect } from "vitest";
import { queryClient } from "./queryClient";

describe("queryClient", () => {
  it("test_query_client_is_a_configured_query_client_singleton", () => {
    // Assert: the module exports one constructed QueryClient instance with
    // the expected default retry behavior (one retry for queries, no retry
    // for mutations) rather than TanStack Query's own library defaults.
    const defaults = queryClient.getDefaultOptions();

    expect(defaults.queries?.retry).toBe(1);
    expect(defaults.mutations?.retry).toBe(0);
  });

  it("test_query_client_starts_with_an_empty_query_cache", () => {
    // Assert: the shared instance holds no stale query state at import time.
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});
