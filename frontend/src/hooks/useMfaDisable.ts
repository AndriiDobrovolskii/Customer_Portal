// FR-6: wraps mfaApi.disableMfa. Requires current_password + code per OD-2's
// resolution. onSuccess calls authStore.setMfaEnabled(false) (Plan Change 6).
import { useMutation } from "@tanstack/react-query";
import * as mfaApi from "../api/mfaApi";
import { useAuthStore } from "../store/authStore";

export function useMfaDisable() {
  const { setMfaEnabled } = useAuthStore();

  return useMutation({
    mutationFn: mfaApi.disableMfa,
    onSuccess: () => setMfaEnabled(false),
  });
}
