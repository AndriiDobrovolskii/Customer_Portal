// FE-AC6's list half: wraps authApi.listSessions in a TanStack Query query.
import { useQuery } from "@tanstack/react-query";
import * as authApi from "../api/authApi";

export const SESSIONS_QUERY_KEY = ["sessions"] as const;

export function useSessions() {
  return useQuery({
    queryKey: SESSIONS_QUERY_KEY,
    queryFn: authApi.listSessions,
  });
}
