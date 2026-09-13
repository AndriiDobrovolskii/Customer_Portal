// FR-3 (Resolution OD-4)/FR-5 (Resolution OD-3): a single shared,
// unconditional `useQuery` for the role catalogue — no pagination (the API
// Contract table's GET /admin/roles has no cursor). Both
// AdminUserCreateScreen.tsx and AdminUserDetailScreen.tsx's role-replacement
// control read this exact query key, never a per-screen copy.
import { useQuery } from "@tanstack/react-query";
import { listRoles } from "../api/adminApi";

export const ADMIN_ROLES_QUERY_KEY = ["admin-roles"] as const;

export function useAdminRoles() {
  return useQuery({
    queryKey: ADMIN_ROLES_QUERY_KEY,
    queryFn: listRoles,
  });
}
