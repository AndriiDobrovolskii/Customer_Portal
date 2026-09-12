// FR-8, OD-3's binding resolution: wraps POST /support/tickets/{id}/reopen.
// `onSuccess` invalidates ticketDetailQueryKey(id) only (reopening does not
// change the reply thread). This hook performs NO client-computed
// reopen-eligibility check of any kind — the backend's 409 (outside the
// 7-day reopen window) is the sole source of truth, and is left to propagate
// to the caller exactly as thrown (status + detail intact), never swallowed
// or reshaped, so TicketDetailScreen.tsx can render it via the existing
// problem+json rendering path.
// The reopen response (`TicketStateRead`) is written into the detail query's
// cache directly (same "mutation response is the new truth" precedent as
// useRevokeSession.ts / useCloseTicket.ts) so the screen reflects
// "waiting_on_support" immediately rather than waiting on a background
// refetch of `GET /support/tickets/{id}` (`refetchType: "none"` still marks
// the query stale for the next natural refetch without racing this
// synchronous cache write).
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reopenTicket } from "../api/supportApi";
import { ticketDetailQueryKey } from "./useTicketDetail";
import type { TicketDetailRead, TicketStateRead } from "../api/types";

export function useReopenTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<TicketStateRead, unknown, void>({
    mutationFn: () => reopenTicket(id, {}),
    onSuccess: (data) => {
      queryClient.setQueryData<TicketDetailRead>(ticketDetailQueryKey(id), (current) =>
        current ? { ...current, status: data.status, updated_at: data.updated_at } : current,
      );
      queryClient.invalidateQueries({ queryKey: ticketDetailQueryKey(id), refetchType: "none" });
    },
  });
}
