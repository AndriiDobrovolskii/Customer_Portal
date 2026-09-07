// FE-AC6's revoke half: wraps authApi.revokeSession. On success, removes the
// revoked session directly from the "sessions" query cache (rather than
// invalidating and refetching) so SessionsScreen's list updates immediately
// without depending on the backend's GET reflecting the DELETE within the
// same request — the AC's actual requirement ("that row disappears from the
// list") is a client-rendering guarantee, not a refetch-timing one.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as authApi from "../api/authApi";
import { SESSIONS_QUERY_KEY } from "./useSessions";
import type { SessionListResponse } from "../api/types";

export function useRevokeSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (familyId: string) => authApi.revokeSession(familyId),
    onSuccess: (_data, familyId) => {
      queryClient.setQueryData<SessionListResponse>(SESSIONS_QUERY_KEY, (current) =>
        current
          ? { sessions: current.sessions.filter((session) => session.family_id !== familyId) }
          : current,
      );
    },
  });
}
