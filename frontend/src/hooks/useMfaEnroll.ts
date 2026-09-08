// FR-5's first step: wraps mfaApi.enrollMfa. Requires current_password per
// OD-2's resolution (PS-AC5 itself names no such field).
import { useMutation } from "@tanstack/react-query";
import * as mfaApi from "../api/mfaApi";

export function useMfaEnroll() {
  return useMutation({
    mutationFn: mfaApi.enrollMfa,
  });
}
