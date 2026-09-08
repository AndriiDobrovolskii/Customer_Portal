// FR-4's landing call: wraps authApi.verifyEmail.
import { useMutation } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export function useVerifyEmail() {
  return useMutation({
    mutationFn: authApi.verifyEmail,
  });
}
