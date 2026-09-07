// FE-AC1: wraps authApi.register in a TanStack Query mutation. No session
// state to update on success — the visitor is not authenticated yet.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export function useRegister() {
  return useMutation({
    mutationFn: authApi.register,
  });
}
