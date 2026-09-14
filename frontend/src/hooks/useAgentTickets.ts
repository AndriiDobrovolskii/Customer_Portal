// FR-1: wraps supportApi.listAgentTickets in a cursor-paginated query,
// parameterized by status/category/assigneeId — the same useInfiniteQuery
// shape as useAdminUsers.ts. A filter change changes the query key, which
// resets TanStack Query's page state, satisfying FR-1's "each re-issue[s]
// the request and reset[s] the cursor."
//
// Resolution OD-2 / Implementation Plan Architectural Change 3: assigneeId
// is sent to supportApi.listAgentTickets verbatim — the literal "me", the
// literal "none", or a raw UUID string exactly as typed/clicked. The
// SERVICE (list_agent_queue) resolves "me"/"none" server-side; a value that
// parses as neither a UUID nor those two literals is rejected with a 422
// this hook does not attempt to pre-validate (Implementation Plan Risk 4).
//
// AGENT_TICKETS_QUERY_KEY_PREFIX is exported as a separate, shorter key so
// useAssignTicket.ts/useUnassignTicket.ts can invalidate every filter
// variation of the queue at once (TanStack Query's invalidateQueries
// matches by key prefix) — origin-agnostic, unconditional invalidation
// regardless of which filters are currently active (Architectural Change 8).
import { useInfiniteQuery } from "@tanstack/react-query";
import { listAgentTickets } from "../api/supportApi";
import type { AgentTicketListResponse } from "../api/types";

export interface UseAgentTicketsFilters {
  status?: string;
  category?: string;
  assigneeId?: string;
}

export const AGENT_TICKETS_QUERY_KEY_PREFIX = ["agent-tickets"] as const;

export function agentTicketsQueryKey({ status, category, assigneeId }: UseAgentTicketsFilters = {}) {
  return [...AGENT_TICKETS_QUERY_KEY_PREFIX, status, category, assigneeId] as const;
}

export function useAgentTickets({ status, category, assigneeId }: UseAgentTicketsFilters = {}) {
  return useInfiniteQuery({
    queryKey: agentTicketsQueryKey({ status, category, assigneeId }),
    queryFn: ({ pageParam }) =>
      listAgentTickets({
        status,
        category,
        assignee_id: assigneeId,
        cursor: pageParam ?? undefined,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage: AgentTicketListResponse) => lastPage.next_cursor ?? undefined,
  });
}
