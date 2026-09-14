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

// US-5.5 Architectural Change 2: `visibility` is an additive, OPTIONAL field
// on the mutation's own input — not a change to `useReplyToTicket(id)`'s
// single-argument call signature. TicketDetailScreen.tsx's (US-5.3, customer)
// `useForm<ReplyToTicketFormValues>()` never registers a `visibility` field,
// so `values.visibility` stays `undefined` there and the payload omits the
// key exactly as before this Story — this hook's customer-path behavior is
// unchanged. The new agent composer (US-5.5, AgentTicketDetailScreen.tsx)
// supplies an explicit `"public"`/`"internal"` value instead.
export interface ReplyToTicketFormValues {
  body: string;
  visibility?: "public" | "internal";
}

export function useReplyToTicket(id: string) {
  const queryClient = useQueryClient();

  return useMutation<ReplyRead, unknown, ReplyToTicketFormValues>({
    mutationFn: (values) => {
      // The customer path (visibility undefined) sends no `visibility` key
      // at all, always an empty `attachment_ids` (Assumption #3). The agent
      // path supplies an explicit value, included only when defined so the
      // customer request body stays byte-for-byte identical to before.
      const payload: CreateReplyRequest = { body: values.body, attachment_ids: [] };
      if (values.visibility !== undefined) {
        payload.visibility = values.visibility;
      }
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
