// FR-5: wraps POST /support/tickets/{id}/resolve. onSuccess writes the
// returned TicketStateRead into ticketDetailQueryKey(id)'s cache — the same
// "mutation response is the new truth" pattern useCloseTicket.ts/
// useReopenTicket.ts already use (`refetchType: "none"` still marks the
// query stale for the next natural refetch, without racing this synchronous
// cache write). Resolving does not change the reply thread's already-
// fetched pages, so ticketRepliesQueryKey(id) is left alone.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resolveTicket } from "../api/supportApi";
import { ticketDetailQueryKey } from "./useTicketDetail";
import type { ResolveTicketRequest, TicketDetailRead, TicketStateRead } from "../api/types";

export function useResolveTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<TicketStateRead, unknown, ResolveTicketRequest>({
    mutationFn: (data) => resolveTicket(id, data),
    onSuccess: (data) => {
      queryClient.setQueryData<TicketDetailRead>(ticketDetailQueryKey(id), (current) =>
        current ? { ...current, status: data.status, updated_at: data.updated_at } : current,
      );
      queryClient.invalidateQueries({ queryKey: ticketDetailQueryKey(id), refetchType: "none" });
    },
  });
}
