// FR-5's second step: wraps mfaApi.activateMfa. recovery_codes flow to the
// caller for display only — never persisted here. onSuccess calls the new
// authStore.setMfaEnabled(true) action (Plan Change 6) so SecurityScreen's
// enroll-vs-disable branch reflects the just-completed enrollment.
import { useMutation } from "@tanstack/react-query";
import * as mfaApi from "../api/mfaApi";
import { useAuthStore } from "../store/authStore";

export function useMfaActivate() {
  const { setMfaEnabled } = useAuthStore();

  return useMutation({
    mutationFn: mfaApi.activateMfa,
    onSuccess: () => setMfaEnabled(true),
  });
}
