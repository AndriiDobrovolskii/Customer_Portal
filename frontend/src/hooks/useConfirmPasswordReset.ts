// FE-AC7's confirm half: wraps authApi.confirmPasswordReset.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: authApi.confirmPasswordReset,
  });
}
