// FR-6: wraps adminApi.resendInvite. Success renders a generic confirmation
// only — the endpoint's `202` body per the story's API Contract table is
// never displayed by any caller.
import { useMutation } from "@tanstack/react-query";
import { resendInvite } from "../api/adminApi";
import type { ResendInviteResponse } from "../api/types";

export function useResendInvite(id: string) {
  return useMutation<ResendInviteResponse, Error, void>({
    mutationFn: () => resendInvite(id),
  });
}
