// FR-7: wraps accountApi.deactivateAccount. onSuccess calls
// authStore.clearSession() (all in-memory auth state cleared), same pattern
// as useLogout.ts.
import { useMutation } from "@tanstack/react-query";
import * as accountApi from "../api/accountApi";
import { useAuthStore } from "../store/authStore";

export function useAccountDeactivate() {
  const { clearSession } = useAuthStore();

  return useMutation({
    mutationFn: accountApi.deactivateAccount,
    onSuccess: () => clearSession(),
  });
}
