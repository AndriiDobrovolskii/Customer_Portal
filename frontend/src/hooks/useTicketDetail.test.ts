// Unit test for useTicketDetail (TK-AC5/FR-5). Exposes a `useQuery` on
// `ticketDetailQueryKey(id)` for the header fields plus a **sibling**
// `useInfiniteQuery` on `ticketRepliesQueryKey(id)` for the reply thread's
// own, independent cursor — implementation_plan v2 Change 5's explicit
// requirement that the two keys share no prefix, so invalidating one never
// resets the other's already-fetched pages.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useTicketDetail, ticketDetailQueryKey, ticketRepliesQueryKey } from "./useTicketDetail";

function detailBody(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    status: "open",
    requester_id: "u-1",
    subject: "Cannot log in",
    body: "I cannot log in.",
    category: "account",
    first_response_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    replies: { items: [], next_cursor: null },
    ...overrides,
  };
}

describe("useTicketDetail query keys", () => {
  it("test_ticket_detail_and_ticket_replies_query_keys_share_no_common_prefix", () => {
    // Arrange / Act
    const detailKey = ticketDetailQueryKey("t-1");
    const repliesKey = ticketRepliesQueryKey("t-1");

    // Assert: a nested key (e.g. ["ticket", "t-1", "replies"]) would make
    // invalidating ["ticket", "t-1"] also match the replies key as a
    // prefix — these must be two disjoint top-level keys.
    expect(detailKey[0]).not.toBe(repliesKey[0]);
  });
});

describe("useTicketDetail", () => {
  it("test_use_ticket_detail_ticket_query_renders_header_fields_from_the_first_page", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          detailBody({ replies: { items: [{ id: "r-1", author_kind: "customer" }], next_cursor: null } }),
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useTicketDetail("t-1"));

    // Act / Assert
    await waitFor(() => expect(result.current.ticketQuery.isSuccess).toBe(true));
    expect(result.current.ticketQuery.data?.ticket_number).toBe("TCK-0001");
    expect(result.current.ticketQuery.data?.status).toBe("open");
  });

  it("test_use_ticket_detail_replies_query_has_next_page_true_when_replies_next_cursor_is_present", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ replies: { items: [], next_cursor: "replies-cursor-2" } }), {
          status: 200,
        }),
      ),
    );
    const { result } = renderHookWithProviders(() => useTicketDetail("t-1"));

    // Act / Assert
    await waitFor(() => expect(result.current.repliesQuery.isSuccess).toBe(true));
    expect(result.current.repliesQuery.hasNextPage).toBe(true);
  });

  it("test_use_ticket_detail_replies_pagination_uses_its_own_cursor_independent_of_any_list_cursor", async () => {
    // Arrange: the thread's own cursor is distinct from the ticket list's
    // (US-5.3 Client State Notes: "two separate paginators").
    const receivedCursors: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets/t-1", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        receivedCursors.push(cursor);
        if (!cursor) {
          return HttpResponse.json(
            detailBody({ replies: { items: [{ id: "r-1" }], next_cursor: "replies-cursor-2" } }),
            { status: 200 },
          );
        }
        return HttpResponse.json(detailBody({ replies: { items: [{ id: "r-2" }], next_cursor: null } }), {
          status: 200,
        });
      }),
    );
    const { result } = renderHookWithProviders(() => useTicketDetail("t-1"));
    await waitFor(() => expect(result.current.repliesQuery.isSuccess).toBe(true));

    // Act
    await result.current.repliesQuery.fetchNextPage();

    // Assert
    await waitFor(() => expect(result.current.repliesQuery.data?.pages).toHaveLength(2));
    expect(receivedCursors.filter((c) => c === "replies-cursor-2")).toHaveLength(1);
  });
});
