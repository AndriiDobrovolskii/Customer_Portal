import { useInfiniteQuery } from "@tanstack/react-query";
import { listTickets } from "../api/supportApi";
import type { TicketListResponse } from "../api/types";

export function useTickets({ status }: { status?: string } = {}) {
  return useInfiniteQuery({
    queryKey: ["tickets", status] as const,
    queryFn: ({ pageParam }) => listTickets({ status, cursor: pageParam ?? undefined }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage: TicketListResponse) => lastPage.next_cursor ?? undefined,
  });
}
