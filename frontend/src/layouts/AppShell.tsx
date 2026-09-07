// Minimal authenticated shell (implementation-plan Files To Create):
// hosts the logout/logout-all control (FE-AC5) and the placeholder home's
// child content. The logout control itself lives in `components/LogoutControls`
// (see that file's header comment) so this layout never imports `hooks/`
// directly.
import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { LogoutControls } from "../components/LogoutControls";

export interface AppShellProps {
  children?: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <header>
        <LogoutControls />
      </header>
      <main>{children ?? <Outlet />}</main>
    </div>
  );
}
