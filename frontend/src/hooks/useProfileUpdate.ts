// US-5.2 Plan Change 3: owns both PATCH /profile payload shapes (field edit,
// email change) and disambiguates 200/202/412 by response status, not shape.
// The ETag is held in TanStack Query's cache as a dedicated, non-fetching
// query key (Plan Change 2) rather than a new store/ slice. Per OD-1's
// resolution, this hook — not profileApi.ts or the screen — decides the
// outgoing If-Match: the cached ETag when known, the literal string "*"
// otherwise, on every write including the session's first.
import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as profileApi from "../api/profileApi";
import { ApiError } from "../api/httpClient";
import type { EmailChangeRequest, ProfileRead, ProfileUpdateRequest } from "../api/types";

const ETAG_QUERY_KEY = ["profile", "etag"] as const;

export function useProfileUpdate() {
  const queryClient = useQueryClient();
  const [conflict, setConflict] = useState(false);

  const mutation = useMutation({
    mutationFn: async (payload: ProfileUpdateRequest | EmailChangeRequest): Promise<ProfileRead> => {
      const cachedEtag = queryClient.getQueryData<string>(ETAG_QUERY_KEY);
      const ifMatch = cachedEtag ?? "*";
      const { data, status, headers } = await profileApi.patchProfile(payload, ifMatch);

      if (status === 202) {
        // FR-3: a 202 sets no ETag — invalidate rather than reuse a stale one.
        queryClient.removeQueries({ queryKey: ETAG_QUERY_KEY });
      } else {
        const etag = headers.get("etag");
        if (etag) {
          queryClient.setQueryData(ETAG_QUERY_KEY, etag);
        }
        setConflict(false);
      }

      return data;
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 412) {
        setConflict(true);
      }
    },
  });

  const resetConflict = useCallback(() => setConflict(false), []);

  return { ...mutation, conflict, resetConflict };
}
