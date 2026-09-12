// FR-7: wraps POST /support/tickets/{id}/close. `onSuccess` invalidates
// ticketDetailQueryKey(id) only — closing a ticket does not change the reply
// thread's already-fetched pages, so ticketRepliesQueryKey(id) is left alone.
//
// The close response (`TicketStateRead`) is the freshest, most authoritative
// read of the ticket's new status — it is written into the detail query's
// cache directly (same "mutation response is the new truth" precedent as
// useRevokeSession.ts) so the screen reflects "closed" immediately rather
// than waiting on a background refetch of `GET /support/tickets/{id}`
// (`refetchType: "none"` still marks the query stale for the next natural
// refetch — e.g. a remount or window refocus — without racing this
// synchronous cache write).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { closeTicket } from "../api/supportApi";
import { ticketDetailQueryKey } from "./useTicketDetail";
import type { TicketDetailRead, TicketStateRead } from "../api/types";

export function useCloseTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<TicketStateRead, unknown, void>({
    // This Story's UI never collects a `reason` (no FR/AC asks for one) —
    // `{}` is a legal CloseTicketRequest body (`reason` is optional).
    mutationFn: () => closeTicket(id, {}),
    onSuccess: (data) => {
      queryClient.setQueryData<TicketDetailRead>(ticketDetailQueryKey(id), (current) =>
        current ? { ...current, status: data.status, updated_at: data.updated_at } : current,
      );
      queryClient.invalidateQueries({ queryKey: ticketDetailQueryKey(id), refetchType: "none" });
    },
  });
}
