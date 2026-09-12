// FR-6: wraps POST /support/tickets/{id}/replies. `onSuccess` invalidates
// BOTH ticketDetailQueryKey(id) (a customer reply on a "waiting_on_customer"
// ticket transitions it to "waiting_on_support" server-side, and ReplyRead
// carries no status field to report that) AND ticketRepliesQueryKey(id) (so
// the new reply appears in the thread) — the same "hook reaches into another
// hook's query key" shape as useRevokeSession.ts -> useSessions.ts.
import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { replyToTicket } from "../api/supportApi";
import { ticketDetailQueryKey, ticketRepliesQueryKey } from "./useTicketDetail";
import type { CreateReplyRequest, ReplyRead, ReplyThreadPage } from "../api/types";

export interface ReplyToTicketFormValues {
  body: string;
}

export function useReplyToTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<ReplyRead, unknown, ReplyToTicketFormValues>({
    mutationFn: (values) => {
      // FR-6: the composer offers no visibility control at all — never send
      // `visibility`, always send an empty `attachment_ids` (Assumption #3).
      const payload: CreateReplyRequest = { body: values.body, attachment_ids: [] };
      return replyToTicket(id, payload);
    },
    onSuccess: (reply) => {
      // The new reply is prepended to the FIRST (newest, no-cursor) page of
      // the already-fetched thread directly from the mutation's own
      // response — the freshest read of what was just posted — rather than
      // relying solely on a background refetch to bring it back
      // (`refetchType: "none"` below still marks the query stale for the
      // next natural refetch, without racing this synchronous cache write).
      // FR-5's own ordering ("Load older replies" fetches progressively
      // older pages via `replies.next_cursor`) means page 0 is the newest
      // page and a just-posted reply is newer than anything already
      // fetched, so it belongs at the front of page 0, not the end of the
      // last (oldest-loaded) page.
      queryClient.setQueryData<InfiniteData<ReplyThreadPage>>(ticketRepliesQueryKey(id), (current) => {
        if (!current || current.pages.length === 0) {
          return current;
        }
        const pages = [...current.pages];
        pages[0] = { ...pages[0], items: [reply, ...pages[0].items] };
        return { ...current, pages };
      });
      queryClient.invalidateQueries({ queryKey: ticketRepliesQueryKey(id), refetchType: "none" });
      // FR-6: a customer reply on a "waiting_on_customer" ticket transitions
      // it to "waiting_on_support" server-side, and ReplyRead carries no
      // status field to report that — this one DOES need a real refetch of
      // the ticket header to pick up the possible status change.
      queryClient.invalidateQueries({ queryKey: ticketDetailQueryKey(id) });
    },
  });
}
