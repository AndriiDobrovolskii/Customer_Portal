// FR-6: wraps adminApi.deactivateUser. On success, updates useAdminUser.ts's
// cached AdminUserRead directly via setQueryData (not a full
// invalidate+refetch), per Implementation Plan Risk 3 and FR-6's "the
// returned status is reflected."
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deactivateUser } from "../api/adminApi";
import { adminUserQueryKey } from "./useAdminUser";
import type { AdminUserRead, DeactivateUserRequest } from "../api/types";

export function useDeactivateAdminUser(id: string) {
  const queryClient = useQueryClient();

  return useMutation<AdminUserRead, Error, DeactivateUserRequest>({
    mutationFn: (payload) => deactivateUser(id, payload),
    onSuccess: (data) => {
      queryClient.setQueryData(adminUserQueryKey(id), data);
    },
  });
}
