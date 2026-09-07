// Test-only render harness. Unlike mswServer.ts/mswHandlers.ts (Task T4,
// frontend-builder's own deliverable — they encode backend response shapes,
// builder territory), this file fixes the CONTRACT this pass's 26 test
// files depend on for asserting routing/session outcomes: without it,
// "renderWithProviders" and its `data-testid="route-location"` marker would
// be an assumption recorded only in prose (docs/tests/US-5.1-test-strategy.md)
// that `frontend-builder` is never told to read — every routing assertion in
// this suite would then fail on a missing test id the first time
// IMPLEMENTATION actually runs these tests. Written here instead, as an
// executable specification test-writer itself owns.
//
// Still expected to fail at module-resolution time until IMPLEMENTATION
// lands `frontend/src/store/authStore.tsx` (Task T3) and
// `frontend/src/store/queryClient.ts` (Task T3) — this file's own imports
// name symbols that do not exist yet, same TDD-red state as every other
// file this pass writes.
import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { render, renderHook, waitFor, type RenderHookOptions } from "@testing-library/react";
import { AuthProvider, type AuthStateSeed } from "../store/authStore";
import type { UserRead } from "../api/types";

export { waitFor };

export interface RenderWithProvidersOptions {
  /** Initial history entry, e.g. "/sessions" or "/reset-password?token=...". */
  route?: string;
  isAuthenticated?: boolean;
  user?: UserRead;
  mfaToken?: string;
  /** Surfaced by PlaceholderHomeScreen via the auth store, per LoginResponse/
   * MfaVerifyResponse's own `mfa_enrollment_deadline` field. */
  mfaEnrollmentDeadline?: string | null;
}

/**
 * Renders `location.pathname` into `data-testid="route-location"` and the
 * redirect-carried "return to this route after login" path (the string a
 * guard's `<Navigate state={{ from: location }} />` attaches) into
 * `data-testid="route-location-state"`. Rendered as a sibling of `ui` inside
 * the same `MemoryRouter`, so it reflects every navigation `ui` triggers
 * (including one fired by a bare guard component with no enclosing
 * `<Routes>` — `<Navigate>` only needs a Router context to act, not a
 * matched route tree).
 */
function RouteLocationProbe() {
  const location = useLocation();
  const fromState = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "";
  return (
    <>
      <div data-testid="route-location">{location.pathname}</div>
      <div data-testid="route-location-state">{fromState}</div>
    </>
  );
}

function buildAuthSeed(options: RenderWithProvidersOptions): AuthStateSeed {
  return {
    isAuthenticated: options.isAuthenticated ?? false,
    accessToken: options.isAuthenticated ? "seeded-access-token" : null,
    user: options.user ?? null,
    mfaToken: options.mfaToken ?? null,
    mfaEnrollmentDeadline: options.mfaEnrollmentDeadline ?? null,
  };
}

export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const seed = buildAuthSeed(options);

  const result = render(
    <MemoryRouter initialEntries={[options.route ?? "/"]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialState={seed}>
          {ui}
          <RouteLocationProbe />
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );

  return { ...result, queryClient };
}

export function renderHookWithProviders<TResult>(
  hook: () => TResult,
  options: RenderWithProvidersOptions & Omit<RenderHookOptions<unknown>, "wrapper"> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const seed = buildAuthSeed(options);

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[options.route ?? "/"]}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider initialState={seed}>{children}</AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  const result = renderHook(hook, { wrapper: Wrapper });
  return { ...result, queryClient };
}
