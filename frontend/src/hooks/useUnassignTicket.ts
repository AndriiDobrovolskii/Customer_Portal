// FR-2: wraps DELETE /support/tickets/{id}/assign. Same invalidation/
// resolved-data shape as useAssignTicket.ts — kept as a separate hook (not
// a boolean flag on one hook) to match this codebase's existing
// one-hook-per-mutation convention (useCloseTicket.ts/useReopenTicket.ts
// are likewise separate). See useAssignTicket.ts's header comment for the
// full rationale on why no hook-level cache write of assignee_id exists.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { unassignTicket } from "../api/supportApi";
import { AGENT_TICKETS_QUERY_KEY_PREFIX } from "./useAgentTickets";
import type { AgentTicketStateRead } from "../api/types";

export function useUnassignTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<AgentTicketStateRead, unknown, void>({
    mutationFn: () => unassignTicket(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AGENT_TICKETS_QUERY_KEY_PREFIX });
    },
  });
}
