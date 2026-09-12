// FR-5: wraps GET /support/tickets/{id} in two sibling queries — a `useQuery`
// for the ticket header fields (["ticket", id]) and an independent
// `useInfiniteQuery` for the reply thread's own cursor (["ticket-replies",
// id]). implementation_plan v2 Change 5: the two keys are deliberately
// top-level and share no prefix, so invalidating one (e.g. after closing the
// ticket) never resets the other's already-fetched pages. Both query
// functions call the same `getTicketDetail` endpoint (the backend embeds the
// reply thread's first/next page inside the ticket detail response) — the
// replies query only ever reads its own `.replies` slice of that response.
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getTicketDetail } from "../api/supportApi";
import type { ReplyThreadPage } from "../api/types";

export function ticketDetailQueryKey(id: string) {
  return ["ticket", id] as const;
}

export function ticketRepliesQueryKey(id: string) {
  return ["ticket-replies", id] as const;
}

export function useTicketDetail(id: string) {
  const ticketQuery = useQuery({
    queryKey: ticketDetailQueryKey(id),
    queryFn: () => getTicketDetail(id),
    // Both queries here read the exact same underlying `GET
    // /support/tickets/{id}` resource under two disjoint cache keys.
    // TanStack Query v5's default "tracked properties" optimization only
    // re-renders a subscriber for a result field it saw read during that
    // subscriber's own last render pass; a caller that reads `.data` outside
    // of that render (e.g. a consumer awaiting a query/mutation and then
    // inspecting the result, as every hook-level test in this Story's suite
    // does via `renderHook`) can otherwise miss a legitimate update when a
    // sibling observer on the same overlapping resource is also active.
    // `"all"` opts out of that optimization for this pair, trading a
    // possible extra re-render for never silently dropping a real one.
    notifyOnChangeProps: "all",
  });

  const repliesQuery = useInfiniteQuery({
    queryKey: ticketRepliesQueryKey(id),
    queryFn: async ({ pageParam }): Promise<ReplyThreadPage> => {
      const detail = await getTicketDetail(id, { cursor: pageParam ?? undefined });
      return detail.replies;
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage: ReplyThreadPage) => lastPage.next_cursor ?? undefined,
    notifyOnChangeProps: "all",
  });

  return { ticketQuery, repliesQuery };
}
