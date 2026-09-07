// Neutral wiring seam between `store/` (the single source of truth for
// session state) and `api/` (which must attach the current access token to
// every authenticated request and react to a silent-refresh outcome).
//
// AGENTS.md §3's Frontend layer table forbids `api/` importing `store` AND
// forbids `store/` importing `api/` (both directions) — but FR-4's
// single-flight refresh coordinator (docs/plans/US-5.1-implementation-plan.md
// Architectural Change 3) genuinely needs `httpClient.ts` to read the live
// token and to clear/update the store's session on a refresh outcome. Rather
// than have either layer import the other directly (a real layering
// violation of the kind AGENTS.md §3 calls out — "a screen calling fetch
// directly, or an api/ function importing a React hook"), this module lives
// outside both `api/` and `store/`, holds no React, no fetch, and no
// business logic of its own — only a small mutable callback registry, the
// same pattern as a dependency-injection seam. `store/authStore.tsx`'s
// `AuthProvider` is the only place that calls `configureSessionBridge`;
// `api/httpClient.ts` is the only place that calls `getSessionBridge`.
// Flagged here (and in the Result Envelope's non_blocking_findings) as a
// deliberate categorization call, the same class of decision plan_review
// already made for `AppShell.tsx`'s logout control.
export interface SessionBridge {
  getAccessToken: () => string | null;
  onTokenRefreshed: (accessToken: string) => void;
  onSessionExpired: () => void;
}

const noopBridge: SessionBridge = {
  getAccessToken: () => null,
  onTokenRefreshed: () => {},
  onSessionExpired: () => {},
};

let activeBridge: SessionBridge = noopBridge;

export function configureSessionBridge(bridge: SessionBridge): void {
  activeBridge = bridge;
}

export function resetSessionBridge(): void {
  activeBridge = noopBridge;
}

export function getSessionBridge(): SessionBridge {
  return activeBridge;
}
