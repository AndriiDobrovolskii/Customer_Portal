// FR-2: wraps POST /support/tickets/{id}/assign — both "assign to me" and
// "assign to another agent" (Resolution OD-2's raw-UUID input) call this
// same endpoint with an AssignTicketRequest.
//
// Architectural Change 8: onSuccess unconditionally invalidates the queue's
// query-key PREFIX (every filter variation of useAgentTickets, via
// AGENT_TICKETS_QUERY_KEY_PREFIX) — one handler, regardless of whether the
// mutation was invoked from AgentTicketQueueScreen.tsx or
// AgentTicketDetailScreen.tsx (AG-AC2's "the queue is invalidated").
//
// Resolution OD-3 / Architectural Change 7: the detail screen's assignee
// value is navigation-state-handoff LOCAL COMPONENT STATE, not anything
// this hook (hooks/ layer) can reach directly or cache in TanStack Query —
// TicketDetailRead carries no assignee_id field to merge into (Plan Risk 3
// explicitly forbids spreading an AgentTicketStateRead over a full
// AgentTicketRead/TicketDetailRead-shaped cache entry). The mutation's
// resolved data (id/status/updated_at/assignee_id) is returned to the
// caller so a detail screen can pass its own per-call `onSuccess` to
// `mutate`/`mutateAsync` and write `assignee_id` into its local state —
// the standard TanStack Query "per-call onSuccess" mechanism, not a second
// hook-level side effect.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { assignTicket } from "../api/supportApi";
import { AGENT_TICKETS_QUERY_KEY_PREFIX } from "./useAgentTickets";
import type { AgentTicketStateRead, AssignTicketRequest } from "../api/types";

export function useAssignTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<AgentTicketStateRead, unknown, AssignTicketRequest>({
    mutationFn: (data) => assignTicket(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AGENT_TICKETS_QUERY_KEY_PREFIX });
    },
  });
}
