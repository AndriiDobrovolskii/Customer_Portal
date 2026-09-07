// FE-AC5's "Log out everywhere" branch: wraps authApi.logoutAll, same
// client-side effect as useLogout on success.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";
import { useAuthStore } from "../store/authStore";

export function useLogoutAll() {
  const { clearSession } = useAuthStore();

  return useMutation({
    mutationFn: authApi.logoutAll,
    onSuccess: () => clearSession(),
  });
}
