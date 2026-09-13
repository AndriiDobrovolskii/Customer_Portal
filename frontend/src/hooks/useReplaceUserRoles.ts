// FR-5: wraps adminApi.replaceUserRoles (PUT, full replacement). On success,
// invalidates useAdminUser.ts's query key for the same user id — targeted
// invalidation over a hand-merged cache patch, per Implementation Plan
// Risk 3's preferred mitigation, the same "one hook invalidates another
// hook's query key" shape useReplyToTicket.ts already established against
// useTicketDetail.ts.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { replaceUserRoles } from "../api/adminApi";
import { adminUserQueryKey } from "./useAdminUser";
import type { ReplaceUserRolesRequest, ReplaceUserRolesResponse } from "../api/types";

export function useReplaceUserRoles(id: string) {
  const queryClient = useQueryClient();

  return useMutation<ReplaceUserRolesResponse, Error, ReplaceUserRolesRequest>({
    mutationFn: (payload) => replaceUserRoles(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: adminUserQueryKey(id) });
    },
  });
}
