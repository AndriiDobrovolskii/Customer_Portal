// FR-4's resend control: wraps authApi.resendVerificationEmail. The
// anti-enumeration guarantee (same generic confirmation regardless of
// whether the address exists) is the server's own responsibility — this hook
// simply resolves whatever the server returns.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export function useResendVerificationEmail() {
  return useMutation({
    mutationFn: authApi.resendVerificationEmail,
  });
}
