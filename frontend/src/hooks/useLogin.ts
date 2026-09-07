// FE-AC2/FE-AC3's initial call: wraps authApi.login. On a LoginResponse
// success it calls authStore.setSession in onSuccess (never inside the
// calling screen); on an MfaRequiredResponse it calls authStore.setMfaToken
// instead, so ALL session-affecting store writes stay inside this hook's
// onSuccess (implementation-plan's hooks/ note) rather than in LoginScreen.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";
import { isMfaRequiredResponse } from "../api/types";
import { useAuthStore } from "../store/authStore";

export function useLogin() {
  const { setSession, setMfaToken } = useAuthStore();

  return useMutation({
    mutationFn: authApi.login,
    onSuccess: (response) => {
      if (isMfaRequiredResponse(response)) {
        setMfaToken(response.mfa_token);
      } else {
        setMfaToken(null);
        setSession({
          accessToken: response.access_token,
          user: response.user,
          mfaEnrollmentDeadline: response.mfa_enrollment_deadline ?? null,
        });
      }
    },
  });
}
