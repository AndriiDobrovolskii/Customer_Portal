// FE-AC10's converse half: an authenticated user visiting /login or
// /register is redirected to the placeholder authenticated home instead.
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export interface GuestOnlyRouteProps {
  children: ReactNode;
}

export function GuestOnlyRoute({ children }: GuestOnlyRouteProps) {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    // US-5.3 FR-15: the authenticated home route moved from "/" to "/tickets".
    return <Navigate to="/tickets" replace />;
  }

  return <>{children}</>;
}
