// FR-8: wraps adminApi.listAuditLogs in a cursor-paginated query,
// parameterized by actor_id/event/target_id/from/to — same useInfiniteQuery
// shape as useAdminUsers.ts/useTickets.ts. Resolution OD-1: on initial
// mount, before any filter is chosen, computes the default window
// (`now - 7 days` / `now`, ISO 8601 UTC) exactly once and RETURNS both
// values to the caller (`AdminAuditLogScreen.tsx` needs them to pre-fill
// the date-picker inputs *visibly*, per that resolution — never applied
// silently with no value handed back).
import { useRef } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { listAuditLogs } from "../api/adminApi";
import type { AuditLogListResponse } from "../api/types";

export interface UseAuditLogsFilters {
  actor_id?: string;
  event?: string;
  target_id?: string;
  from?: string;
  to?: string;
}

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function computeDefaultWindow(): { defaultFrom: string; defaultTo: string } {
  const to = new Date();
  const from = new Date(to.getTime() - SEVEN_DAYS_MS);
  return { defaultFrom: from.toISOString(), defaultTo: to.toISOString() };
}

export function useAuditLogs(filters: UseAuditLogsFilters = {}) {
  // A ref (not useState/useMemo) so the default window is computed exactly
  // once per mount and never recomputed on a later render, regardless of
  // what re-renders this hook's caller.
  const defaultsRef = useRef<{ defaultFrom: string; defaultTo: string } | null>(null);
  if (defaultsRef.current === null) {
    defaultsRef.current = computeDefaultWindow();
  }
  const { defaultFrom, defaultTo } = defaultsRef.current;

  const from = filters.from ?? defaultFrom;
  const to = filters.to ?? defaultTo;

  const query = useInfiniteQuery({
    queryKey: ["admin-audit-logs", filters.actor_id, filters.event, filters.target_id, from, to] as const,
    queryFn: ({ pageParam }) =>
      listAuditLogs({
        actor_id: filters.actor_id,
        event: filters.event,
        target_id: filters.target_id,
        from,
        to,
        cursor: pageParam ?? undefined,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage: AuditLogListResponse) => lastPage.next_cursor ?? undefined,
  });

  return { query, defaultFrom, defaultTo };
}
