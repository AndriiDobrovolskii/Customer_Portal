// The route table (Task T16, FE-AC10 both directions). Renders as `<Routes>`
// nested inside whatever Router is already in context (a real
// `BrowserRouter` in App.tsx, a `MemoryRouter` in tests) rather than owning
// its own `createBrowserRouter` instance, so it can be rendered directly
// inside `test/test-utils.tsx`'s `MemoryRouter`.
import { Route, Routes } from "react-router-dom";
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
import { PlaceholderHomeScreen } from "../screens/PlaceholderHomeScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { SecurityScreen } from "../screens/SecurityScreen";
import { DeactivateAccountScreen } from "../screens/DeactivateAccountScreen";
import { EmailVerificationScreen } from "../screens/EmailVerificationScreen";
import { ConfirmEmailChangeScreen } from "../screens/ConfirmEmailChangeScreen";

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
        <Route path="/" element={<PlaceholderHomeScreen />} />
        <Route path="/sessions" element={<SessionsScreen />} />
        <Route path="/settings/profile" element={<ProfileScreen />} />
        <Route path="/settings/security" element={<SecurityScreen />} />
        <Route path="/settings/deactivate" element={<DeactivateAccountScreen />} />
      </Route>
    </Routes>
  );
}
