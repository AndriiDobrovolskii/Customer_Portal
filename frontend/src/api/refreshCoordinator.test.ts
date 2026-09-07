// Unit tests for the single-flight 401->refresh coordinator (Task T2).
// Collaborator-shape assumption (see docs/tests/US-5.1-test-strategy.md):
// `coordinateRefresh(refreshFn: () => Promise<RefreshResponse>): Promise<RefreshResponse>`
// is a module-level singleton — the first caller invokes `refreshFn`; every
// caller that arrives while that promise is unsettled awaits the SAME promise
// instead of invoking `refreshFn` again. This is Architectural Change 3 of
// docs/plans/US-5.1-implementation-plan.md, the FE-AC4 / OD-2 mitigation.
//
// Expected to fail at collection/import time until IMPLEMENTATION lands
// `frontend/src/api/refreshCoordinator.ts` — the intended TDD-red state,
// matching this project's US-4.3 test-writer precedent.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { coordinateRefresh, resetRefreshCoordinator } from "./refreshCoordinator";
import type { RefreshResponse } from "./types";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("refreshCoordinator", () => {
  beforeEach(() => {
    // Assumed test-only reset hook so each test starts with no in-flight promise.
    resetRefreshCoordinator();
  });

  it("test_refresh_coordinator_concurrent_callers_share_one_in_flight_refresh_promise", async () => {
    // Arrange
    const { promise: gate, resolve } = deferred<RefreshResponse>();
    const refreshFn = vi.fn(() => gate);
    const response: RefreshResponse = {
      access_token: "new-access-token",
      expires_in: 900,
    };

    // Act: three concurrent callers race against the same in-flight refresh.
    const callerA = coordinateRefresh(refreshFn);
    const callerB = coordinateRefresh(refreshFn);
    const callerC = coordinateRefresh(refreshFn);
    resolve(response);
    const [a, b, c] = await Promise.all([callerA, callerB, callerC]);

    // Assert
    expect(refreshFn).toHaveBeenCalledTimes(1);
    expect(a).toEqual(response);
    expect(b).toEqual(response);
    expect(c).toEqual(response);
  });

  it("test_refresh_coordinator_serial_calls_after_settle_each_trigger_a_new_refresh", async () => {
    // Arrange
    const refreshFn = vi
      .fn<() => Promise<RefreshResponse>>()
      .mockResolvedValueOnce({ access_token: "token-1", expires_in: 900 })
      .mockResolvedValueOnce({ access_token: "token-2", expires_in: 900 });

    // Act
    const first = await coordinateRefresh(refreshFn);
    const second = await coordinateRefresh(refreshFn);

    // Assert: once the first refresh has settled, a later 401 starts a new one.
    expect(refreshFn).toHaveBeenCalledTimes(2);
    expect(first.access_token).toBe("token-1");
    expect(second.access_token).toBe("token-2");
  });

  it("test_refresh_coordinator_rejects_all_waiters_when_the_shared_refresh_fails", async () => {
    // Arrange
    const failure = new Error("refresh failed");
    const { promise: gate, reject } = deferred<RefreshResponse>();
    const refreshFn = vi.fn(() => gate);

    // Act
    const callerA = coordinateRefresh(refreshFn);
    const callerB = coordinateRefresh(refreshFn);
    reject(failure);

    // Assert
    await expect(callerA).rejects.toThrow("refresh failed");
    await expect(callerB).rejects.toThrow("refresh failed");
    expect(refreshFn).toHaveBeenCalledTimes(1);
  });
});
