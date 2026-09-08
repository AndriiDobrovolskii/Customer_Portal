// FR-3's confirmation half: wraps profileApi.confirmEmailChange. Callable
// signed-in or signed-out — does not assume an authenticated hook context.
import { useMutation } from "@tanstack/react-query";
import * as profileApi from "../api/profileApi";

export function useConfirmEmailChange() {
  return useMutation({
    mutationFn: profileApi.confirmEmailChange,
  });
}
