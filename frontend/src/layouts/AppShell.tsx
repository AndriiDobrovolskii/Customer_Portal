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
  const { mfaEnrollmentDeadline, scopes } = useAuthStore();

  // US-5.4 FR-9: admin nav entries are derived from `scopes` read directly
  // off the store (no hook call, no `api/` import) — cosmetic gating only,
  // independently per entry ("Users" on `users:read`, "Audit Log" on
  // `audit:read`); the server's own 403 remains the enforced boundary on
  // every admin screen regardless of what this renders.
  const canReadUsers = scopes.includes("users:read");
  const canReadAudit = scopes.includes("audit:read");
  // US-5.5 FR-11/Resolution OD-4: one shared authenticated app shell, a
  // `tickets:read`-gated nav entry alongside the existing `/tickets` entry —
  // no separate entry point, no role switcher for a user holding both a
  // customer identity and agent scopes.
  const canReadAgentQueue = scopes.includes("tickets:read");

  return (
    <div className="app-shell">
      <header>
        <nav>
          <Link to="/tickets">Tickets</Link>
          {canReadAgentQueue && <Link to="/agent/tickets">Agent Queue</Link>}
          {canReadUsers && <Link to="/admin/users">Users</Link>}
          {canReadAudit && <Link to="/admin/audit-logs">Audit Log</Link>}
        </nav>
        <LogoutControls />
      </header>
      <MfaEnrollmentBanner deadline={mfaEnrollmentDeadline} />
      <main>{children ?? <Outlet />}</main>
    </div>
  );
}
