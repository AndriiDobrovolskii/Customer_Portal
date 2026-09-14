// The route table (Task T16, FE-AC10 both directions). Renders as `<Routes>`
// nested inside whatever Router is already in context (a real
// `BrowserRouter` in App.tsx, a `MemoryRouter` in tests) rather than owning
// its own `createBrowserRouter` instance, so it can be rendered directly
// inside `test/test-utils.tsx`'s `MemoryRouter`.
import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { GuestOnlyRoute } from "./GuestOnlyRoute";
import { AuthLayout } from "../layouts/AuthLayout";
import { AppShell } from "../layouts/AppShell";
import { RegisterScreen } from "../screens/RegisterScreen";
import { LoginScreen } from "../screens/LoginScreen";
import { MfaVerifyScreen } from "../screens/MfaVerifyScreen";
import { ForgotPasswordScreen } from "../screens/ForgotPasswordScreen";
import { ResetPasswordScreen } from "../screens/ResetPasswordScreen";
import { SessionsScreen } from "../screens/SessionsScreen";
import { TicketListScreen } from "../screens/TicketListScreen";
import { NewTicketScreen } from "../screens/NewTicketScreen";
import { TicketDetailScreen } from "../screens/TicketDetailScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { SecurityScreen } from "../screens/SecurityScreen";
import { DeactivateAccountScreen } from "../screens/DeactivateAccountScreen";
import { EmailVerificationScreen } from "../screens/EmailVerificationScreen";
import { ConfirmEmailChangeScreen } from "../screens/ConfirmEmailChangeScreen";
import { AdminUserListScreen } from "../screens/AdminUserListScreen";
import { AdminUserCreateScreen } from "../screens/AdminUserCreateScreen";
import { AdminUserDetailScreen } from "../screens/AdminUserDetailScreen";
import { AdminAuditLogScreen } from "../screens/AdminAuditLogScreen";
import { AgentTicketQueueScreen } from "../screens/AgentTicketQueueScreen";
import { AgentTicketDetailScreen } from "../screens/AgentTicketDetailScreen";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route
          path="/register"
          element={
            <GuestOnlyRoute>
              <RegisterScreen />
            </GuestOnlyRoute>
          }
        />
        <Route
          path="/login"
          element={
            <GuestOnlyRoute>
              <LoginScreen />
            </GuestOnlyRoute>
          }
        />
        <Route path="/mfa-verify" element={<MfaVerifyScreen />} />
        <Route
          path="/forgot-password"
          element={
            <GuestOnlyRoute>
              <ForgotPasswordScreen />
            </GuestOnlyRoute>
          }
        />
        <Route
          path="/reset-password"
          element={
            <GuestOnlyRoute>
              <ResetPasswordScreen />
            </GuestOnlyRoute>
          }
        />
      </Route>
      {/* US-5.2 Plan Change 10: FR-3/FR-4's routes sit outside BOTH guards —
          neither ProtectedRoute (would block a signed-out visitor) nor
          GuestOnlyRoute (would block a signed-in one) fits "works signed-in
          and signed-out" / "a visitor opens a link". No new guard component
          is introduced; "outside both" is achieved by simply not wrapping. */}
      <Route path="/verify-email" element={<EmailVerificationScreen />} />
      <Route path="/confirm-email-change" element={<ConfirmEmailChangeScreen />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        {/* US-5.3 FR-15/Change 11: "/" is retired as its own screen — a
            bookmarked or hand-typed "/" still lands an authenticated
            customer on their tickets. */}
        <Route path="/" element={<Navigate to="/tickets" replace />} />
        <Route path="/tickets" element={<TicketListScreen />} />
        <Route path="/tickets/new" element={<NewTicketScreen />} />
        <Route path="/tickets/:id" element={<TicketDetailScreen />} />
        <Route path="/sessions" element={<SessionsScreen />} />
        <Route path="/settings/profile" element={<ProfileScreen />} />
        <Route path="/settings/security" element={<SecurityScreen />} />
        <Route path="/settings/deactivate" element={<DeactivateAccountScreen />} />
        {/* US-5.4 FR-1 through FR-9: registered exactly like every other
            route in this ProtectedRoute/AppShell group — auth-only gating
            (Implementation Plan Risk 2/Architectural Change 4). Scope
            gating lives only at the presentation layer (AppShell.tsx's nav,
            each screen's own write-control disabling and server-403
            rendering), never here. */}
        <Route path="/admin/users" element={<AdminUserListScreen />} />
        <Route path="/admin/users/new" element={<AdminUserCreateScreen />} />
        <Route path="/admin/users/:id" element={<AdminUserDetailScreen />} />
        <Route path="/admin/audit-logs" element={<AdminAuditLogScreen />} />
        {/* US-5.5 FR-11/Resolution OD-4: the agent console shares this same
            ProtectedRoute/AppShell group — no separate entry point, same
            auth-only gating as every route above. Scope gating (tickets:read/
            tickets:write) lives only at the presentation layer. */}
        <Route path="/agent/tickets" element={<AgentTicketQueueScreen />} />
        <Route path="/agent/tickets/:id" element={<AgentTicketDetailScreen />} />
      </Route>
    </Routes>
  );
}
