// Unit test for the useTickets hook (TK-AC1/FR-1, TK-AC2/FR-2). This is the
// first cursor-paginated list hook in this codebase (implementation_plan v2
// Change 5) — reference implementation for useTicketDetail.ts's reply-thread
// pagination. Built on TanStack Query's useInfiniteQuery, keyed
// ["tickets", status].
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useTickets } from "./useTickets";

function ticket(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    status: "open",
    requester_id: "u-1",
    subject: "Cannot log in",
    body: "I cannot log in to my account.",
    category: "account",
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    ...overrides,
  };
}

describe("useTickets", () => {
  it("test_use_tickets_first_page_has_next_page_true_when_next_cursor_is_present", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [ticket()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useTickets({}));

    // Act / Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pages[0].items).toHaveLength(1);
    expect(result.current.hasNextPage).toBe(true);
  });

  it("test_use_tickets_has_next_page_false_when_next_cursor_is_null", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [ticket()], next_cursor: null }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useTickets({}));

    // Act / Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(false);
  });

  it("test_use_tickets_fetch_next_page_appends_using_the_previous_pages_next_cursor", async () => {
    // Arrange
    const receivedCursors: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        receivedCursors.push(cursor);
        if (!cursor) {
          return HttpResponse.json(
            { items: [ticket({ id: "t-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json({ items: [ticket({ id: "t-2" })], next_cursor: null }, { status: 200 });
      }),
    );
    const { result } = renderHookWithProviders(() => useTickets({}));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Act
    result.current.fetchNextPage();

    // Assert
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    expect(receivedCursors).toEqual([null, "cursor-2"]);
    expect(result.current.hasNextPage).toBe(false);
  });

  it("test_use_tickets_status_filter_is_sent_as_the_status_query_parameter", async () => {
    // Arrange: a distinct `status` value is a distinct queryKey
    // (["tickets", status]) — TanStack Query starts that query fresh, with
    // no cursor, rather than the hook having to reset one by hand (FR-2).
    let receivedStatus: string | null = null;
    let receivedCursorOnFirstRequest: string | null = "unset";
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const url = new URL(request.url);
        receivedStatus = url.searchParams.get("status");
        receivedCursorOnFirstRequest = url.searchParams.get("cursor");
        return HttpResponse.json({ items: [ticket()], next_cursor: null }, { status: 200 });
      }),
    );
    const { result } = renderHookWithProviders(() => useTickets({ status: "resolved" }));

    // Act / Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(receivedStatus).toBe("resolved");
    expect(receivedCursorOnFirstRequest).toBeNull();
  });

  it("test_use_tickets_changing_the_status_filter_resets_pagination_to_a_single_unfiltered_page", async () => {
    // Arrange: TK-AC2's own text — "the cursor is reset" when the customer
    // changes the status filter. Mount unfiltered, page forward to a second
    // page, then flip `status` and confirm the hook is back to exactly one
    // page fetched with no cursor on the wire (a distinct `queryKey` per
    // `status` starts the query fresh rather than the hook hand-rolling a
    // cursor reset).
    const receivedRequests: { status: string | null; cursor: string | null }[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const url = new URL(request.url);
        const status = url.searchParams.get("status");
        const cursor = url.searchParams.get("cursor");
        receivedRequests.push({ status, cursor });
        if (!status && !cursor) {
          return HttpResponse.json(
            { items: [ticket({ id: "t-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        if (!status && cursor === "cursor-2") {
          return HttpResponse.json({ items: [ticket({ id: "t-2" })], next_cursor: null }, { status: 200 });
        }
        return HttpResponse.json(
          { items: [ticket({ id: "t-3", status: "resolved" })], next_cursor: null },
          {
            status: 200,
          },
        );
      }),
    );
    // A mutable ref object (rather than a reassigned `let`) so the hook
    // reads a fresh `status` on each render without ESLint's prefer-const
    // closure analysis flagging the binding itself as never reassigned —
    // the object identity never changes, only its `.current` property.
    const statusRef: { current: string | undefined } = { current: undefined };
    const { result, rerender } = renderHookWithProviders(() => useTickets({ status: statusRef.current }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));

    // Act
    statusRef.current = "resolved";
    rerender();

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pages).toHaveLength(1);
    const lastRequest = receivedRequests[receivedRequests.length - 1];
    expect(lastRequest).toEqual({ status: "resolved", cursor: null });
  });
});
