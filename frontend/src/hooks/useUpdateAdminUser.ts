// FR-4: wraps adminApi.updateUser, reading the cached `ETag` from
// useAdminUser.ts's per-user-id key (adminUserEtagQueryKey) as the outgoing
// `If-Match` — directly mirrors useProfileUpdate.ts's `conflict` boolean
// state on a 412. Also exposes the parsed `immutable-field` problem's
// `detail` string when present (a 422/409-class response whose `detail` IS
// that problem's own message, per errorNormalization.ts's existing
// detail-first branch — no new normalization shape is added). `roles` is
// never part of `UpdateAdminUserRequest` (FR-5 keeps it a separate save
// path), so this hook cannot send it even by accident.
import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateUser } from "../api/adminApi";
import { ApiError } from "../api/httpClient";
import { adminUserEtagQueryKey, adminUserQueryKey } from "./useAdminUser";
import type { AdminUserRead, UpdateAdminUserRequest } from "../api/types";

export function useUpdateAdminUser(id: string) {
  const queryClient = useQueryClient();
  const [conflict, setConflict] = useState(false);
  const [immutableFieldDetail, setImmutableFieldDetail] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async (payload: UpdateAdminUserRequest): Promise<AdminUserRead> => {
      const cachedEtag = queryClient.getQueryData<string>(adminUserEtagQueryKey(id));
      const ifMatch = cachedEtag ?? "*";
      const { data, headers } = await updateUser(id, payload, ifMatch);

      const etag = headers.get("etag");
      if (etag) {
        queryClient.setQueryData(adminUserEtagQueryKey(id), etag);
      }
      queryClient.setQueryData(adminUserQueryKey(id), data);
      setConflict(false);
      setImmutableFieldDetail(null);

      return data;
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        if (error.status === 412) {
          setConflict(true);
        }
        if (error.status === 422 || error.status === 409) {
          setImmutableFieldDetail(error.message);
        }
      }
    },
  });

  const resetConflict = useCallback(() => setConflict(false), []);

  return { ...mutation, conflict, resetConflict, immutableFieldDetail };
}
