// FR-4 / OD-2 (docs/specifications/US-5.1-spec.md, docs/decisions/US-5.1-open-decisions.md):
// single-flight `/auth/refresh` coordinator. Architectural Change 3 of
// docs/plans/US-5.1-implementation-plan.md — a module-level singleton
// promise so concurrent 401s across independent TanStack Query calls resolve
// against ONE in-flight refresh, never one refresh attempt per failing
// request (BR-008: a superseded, already-rotated refresh cookie looks like
// token-reuse/theft to the backend). Pure module, no React/fetch/store —
// `httpClient.ts` supplies the actual refresh call as `refreshFn`.
import type { RefreshResponse } from "./types";

let inFlightRefresh: Promise<RefreshResponse> | null = null;

export function coordinateRefresh(refreshFn: () => Promise<RefreshResponse>): Promise<RefreshResponse> {
  if (!inFlightRefresh) {
    inFlightRefresh = refreshFn().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

/** Test-only reset hook — clears the singleton so each test starts clean. */
export function resetRefreshCoordinator(): void {
  inFlightRefresh = null;
}
