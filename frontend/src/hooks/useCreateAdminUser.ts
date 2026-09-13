// FR-3: wraps adminApi.createUser. On success the caller (screen) navigates
// to the new user's detail route using the response body's `id` — no
// password field anywhere in this hook's payload type
// (CreateAdminUserRequest excludes it structurally).
import { useMutation } from "@tanstack/react-query";
import { createUser } from "../api/adminApi";
import type { AdminUserRead, CreateAdminUserRequest } from "../api/types";

export function useCreateAdminUser() {
  return useMutation<AdminUserRead, Error, CreateAdminUserRequest>({
    mutationFn: (payload) => createUser(payload),
  });
}
