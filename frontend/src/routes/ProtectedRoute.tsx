// FE-AC10's first half: unauthenticated -> /login, remembering the
// originally-requested route (via redirect state) for post-login return.
// Reads the store read-only (AGENTS.md §3's `routes/` row); never calls
// `api/` directly.
import { useRef, type ReactNode } from "react";
import { Navigate, useLocation, type Location } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export interface ProtectedRouteProps {
  children: ReactNode;
}

interface RedirectState {
  from: Location;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  // Captured the moment authentication is lost, then held stable (same
  // object reference) for as long as it stays lost — not captured once at
  // mount, and not recomputed every render. Both matter:
  // (1) Correctness: `ProtectedRoute` stays mounted across sibling
  //     protected routes (it wraps the whole authenticated layout in
  //     `AppRoutes`, e.g. both "/" and "/sessions"), so a session that
  //     expires *after* the user has navigated within that layout must
  //     still capture wherever they were at that moment, not wherever they
  //     were when this component first mounted.
  // (2) `<Navigate>` re-invokes `navigate()` in a `useEffect` keyed on
  //     referential equality of its `state` prop (react-router-dom's own
  //     Navigate implementation) — a brand-new `{ from: location }` object
  //     every render creates a new `state` reference every render, which
  //     re-fires that effect every render. In real usage this is masked:
  //     once the URL no longer matches this route, the matched `<Route>`
  //     unmounts it. Rendered directly with no enclosing `<Routes>` (as
  //     this file's own unit test does), it never unmounts, so an unstable
  //     `state` reference becomes a genuine infinite redirect loop. A plain
  //     ref mutated during render (reset once authenticated, set once on
  //     the first unauthenticated render after that) gives a value that's
  //     both correctly-timed and referentially stable — a `useMemo`/
  //     `useState` keyed on `location` alone can't do both at once.
  const redirectStateRef = useRef<RedirectState | null>(null);
  if (isAuthenticated) {
    redirectStateRef.current = null;
  } else if (redirectStateRef.current === null) {
    redirectStateRef.current = { from: location };
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={redirectStateRef.current} />;
  }

  return <>{children}</>;
}
