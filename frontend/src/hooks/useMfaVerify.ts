// FE-AC3's second step: wraps authApi.verifyMfa. Always completes login on
// success (MfaVerifyResponse is a full LoginResponse), same store update as
// useLogin's non-MFA branch.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";
import { useAuthStore } from "../store/authStore";

export function useMfaVerify() {
  const { setSession } = useAuthStore();

  return useMutation({
    mutationFn: authApi.verifyMfa,
    onSuccess: (response) => {
      setSession({
        accessToken: response.access_token,
        user: response.user,
        mfaEnrollmentDeadline: response.mfa_enrollment_deadline ?? null,
      });
    },
  });
}
