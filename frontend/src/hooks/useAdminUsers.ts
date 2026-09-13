// FR-1: wraps adminApi.listUsers in a cursor-paginated query, parameterized
// by q/status/role — the same useInfiniteQuery shape as useTickets.ts.
// Changing any filter changes the query key, which resets TanStack Query's
// pagination to a single page (AD-AC1's "filters re-request the list and
// reset the cursor").
import { useInfiniteQuery } from "@tanstack/react-query";
import { listUsers } from "../api/adminApi";
import type { AdminUserListResponse } from "../api/types";

export interface UseAdminUsersFilters {
  q?: string;
  status?: string;
  role?: string;
}

export function useAdminUsers({ q, status, role }: UseAdminUsersFilters = {}) {
  return useInfiniteQuery({
    queryKey: ["admin-users", q, status, role] as const,
    queryFn: ({ pageParam }) => listUsers({ q, status, role, cursor: pageParam ?? undefined }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage: AdminUserListResponse) => lastPage.next_cursor ?? undefined,
  });
}
