// Spec NFR: "A distinct auth layout — with no main sidebar or header — is
// used for this Story's pre-authentication screens." Closes the v1
// spec-review Major finding (docs/reviews/specifications/US-5.1-spec-review.md).
import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

export interface AuthLayoutProps {
  children?: ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return <main className="auth-layout">{children ?? <Outlet />}</main>;
}
