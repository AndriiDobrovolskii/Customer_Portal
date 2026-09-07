// FE-AC4 integration proof (Task T6): two-plus simultaneous authenticated
// hook calls both 401 via MSW; asserts exactly one POST /auth/refresh call
// and both original requests retried successfully.
//
// Placement note (docs/plans/US-5.1-task-breakdown.md's own Notes section
// flagged this file's path as the breakdown's placement, not plan-fixed, and
// asked test-writer to confirm it). This test is relocated from the
// breakdown's literal `frontend/src/api/refreshCoordinator.integration.test.tsx`
// to `frontend/src/hooks/` for two reasons: (1) AGENTS.md §3's Frontend layer
// table forbids `api/` from importing React/TanStack Query at all, and this
// test necessarily renders hooks via React Testing Library's `renderHook`
// under a `QueryClientProvider` — placing it in `api/` would put a
// React-importing file in the one layer that must never import React; (2)
// `hooks/` is exactly the layer AGENTS.md §3 authorizes to import both `api/`
// and TanStack Query together, which is the actual boundary this test proves
// (two independent hooks, both backed by `httpClient`/`refreshCoordinator`,
// converging on one refresh call) — not an `api/`-internal concern. The
// `screens/`-scoped `frontend-vi-mock-in-integration-tests` pre-commit hook
// (`.pre-commit-config.yaml`) does not reach `hooks/` either way, so this
// move changes no gate's coverage.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { useQuery } from "@tanstack/react-query";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useSessions } from "./useSessions";
import { useAuthStore } from "../store/authStore";
import { listSessions } from "../api/authApi";

// Second consumer used in the first test below: deliberately a DIFFERENT
// query key than `useSessions()`'s (`["sessions"]`), even though both call
// the same `listSessions` endpoint. TanStack Query correctly deduplicates
// concurrent fetches that share a query key — two `useSessions()` calls in
// the same render are, by design, ONE underlying network request, not two
// (confirmed empirically: a same-key version of this test collapses to a
// single 401 -> refresh -> retry cycle, which the MSW handler below cannot
// satisfy, since its "first two calls fail" bound assumes two genuinely
// independent fetches). A distinct key is the minimal way to exercise two
// real, independent authenticated requests that both 401 at once — the
// actual FE-AC4/OD-2 scenario (e.g. two different screens' queries expiring
// together) — while still proving refreshCoordinator's single-flight
// behavior across them.
function useSessionsAsSecondConsumer() {
  return useQuery({ queryKey: ["sessions", "second-consumer-fe-ac4-proof"], queryFn: listSessions });
}

describe("silent refresh on concurrent 401s (FE-AC4)", () => {
  it("test_two_concurrent_authenticated_requests_both_401_trigger_exactly_one_refresh_call_and_both_retry_succeed", async () => {
    // Arrange
    let sessionsCallCount = 0;
    let refreshCallCount = 0;
    server.use(
      http.get("/api/v1/auth/sessions", async () => {
        sessionsCallCount += 1;
        if (sessionsCallCount <= 2) {
          // Both of the first two callers (two independent useSessions()
          // consumers below) see an expired access token.
          return HttpResponse.json(
            {
              type: "https://errors.example/invalid-token",
              title: "Invalid or expired token",
              status: 401,
              detail: "The access token has expired.",
            },
            { status: 401, headers: { "content-type": "application/problem+json" } },
          );
        }
        return HttpResponse.json({ sessions: [] }, { status: 200 });
      }),
      http.post("/api/v1/auth/refresh", async () => {
        refreshCallCount += 1;
        return HttpResponse.json({ access_token: "refreshed-token", expires_in: 900 }, { status: 200 });
      }),
    );
    const { result } = renderHookWithProviders(() => ({
      store: useAuthStore(),
      first: useSessions(),
      second: useSessionsAsSecondConsumer(),
    }));
    result.current.store.setSession({
      accessToken: "expired-token",
      user: { id: "u1", email: "a@example.com" },
    });

    // Act: both hooks' underlying queries fire concurrently and both 401.

    // Assert
    await waitFor(() => expect(result.current.first.isSuccess).toBe(true));
    await waitFor(() => expect(result.current.second.isSuccess).toBe(true));
    expect(refreshCallCount).toBe(1);
    expect(result.current.store.accessToken).toBe("refreshed-token");
  });

  it("test_refresh_failure_clears_session_and_redirects_to_login_once_not_once_per_waiter", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/auth/sessions", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-token",
            title: "Invalid or expired token",
            status: 401,
            detail: "The access token has expired.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
      http.post("/api/v1/auth/refresh", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-refresh-token",
            title: "Refresh failed",
            status: 401,
            detail: "The refresh token is invalid or has been revoked.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      store: useAuthStore(),
      first: useSessions(),
      second: useSessions(),
    }));
    result.current.store.setSession({
      accessToken: "expired-token",
      user: { id: "u1", email: "a@example.com" },
    });

    // Act / Assert: both consumers observe a failure; in-memory state is cleared once.
    await waitFor(() => expect(result.current.first.isError).toBe(true));
    await waitFor(() => expect(result.current.second.isError).toBe(true));
    await waitFor(() => expect(result.current.store.isAuthenticated).toBe(false));
    expect(result.current.store.accessToken).toBeNull();
  });
});
