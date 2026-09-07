// FE-AC7's request half: wraps authApi.requestPasswordReset.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: authApi.requestPasswordReset,
  });
}
