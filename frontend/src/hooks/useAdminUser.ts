// FR-2: wraps GET /admin/users/{id}, capturing the response's `ETag` header
// into a per-user-id TanStack Query cache key — generalizing
// useProfileUpdate.ts's single fixed ETAG_QUERY_KEY constant to many users,
// one admin session (implementation_plan v2 Risk 4). `useUpdateAdminUser.ts`
// reads the outgoing `If-Match` from `adminUserEtagQueryKey(id)`, never a
// fixed key, so a key collision (user A's ETag echoed for user B) is a
// namable, testable property rather than an incidental correctness bug.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getUser } from "../api/adminApi";
import type { AdminUserRead } from "../api/types";

export function adminUserQueryKey(id: string) {
  return ["admin-user", id] as const;
}

export function adminUserEtagQueryKey(id: string) {
  return ["admin-user", id, "etag"] as const;
}

export function useAdminUser(id: string) {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: adminUserQueryKey(id),
    queryFn: async (): Promise<AdminUserRead> => {
      const { data, etag } = await getUser(id);
      if (etag) {
        queryClient.setQueryData(adminUserEtagQueryKey(id), etag);
      } else {
        queryClient.removeQueries({ queryKey: adminUserEtagQueryKey(id) });
      }
      return data;
    },
  });
}
