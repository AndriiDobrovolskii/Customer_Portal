// FE-AC5's "Log out" branch: wraps authApi.logout, clears the store on success.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";
import { useAuthStore } from "../store/authStore";

export function useLogout() {
  const { clearSession } = useAuthStore();

  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => clearSession(),
  });
}
