// Minimal authenticated shell (implementation-plan Files To Create):
// hosts the logout/logout-all control (FE-AC5) and the authenticated app's
// routed content. The logout control itself lives in `components/LogoutControls`
// (see that file's header comment) so this layout never imports `hooks/`
// directly.
//
// US-5.3 implementation_plan v2 Architectural Change 7: FR-15 adds the
// `/tickets` nav link (this file's first nav element), and
// `MfaEnrollmentBanner`'s render site relocates here from the now-deleted
// `PlaceholderHomeScreen.tsx` — this file already sits in AGENTS.md §3's
// Frontend `screens/`, `components/` row (store read-only, no `api/`
// import), so reading `mfaEnrollmentDeadline` off `useAuthStore()` directly
// is not a new layering exception.
import type { ReactNode } from "react";
import { Link, Outlet } from "react-router-dom";
import { LogoutControls } from "../components/LogoutControls";
import { MfaEnrollmentBanner } from "../components/MfaEnrollmentBanner";
import { useAuthStore } from "../store/authStore";

export interface AppShellProps {
  children?: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { mfaEnrollmentDeadline } = useAuthStore();

  return (
    <div className="app-shell">
      <header>
        <nav>
          <Link to="/tickets">Tickets</Link>
        </nav>
        <LogoutControls />
      </header>
      <MfaEnrollmentBanner deadline={mfaEnrollmentDeadline} />
      <main>{children ?? <Outlet />}</main>
    </div>
  );
}
