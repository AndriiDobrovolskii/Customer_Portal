// Unit test for useCloseTicket (TK-AC7/FR-7). onSuccess invalidates
// ticketDetailQueryKey(id) only — closing a ticket does not change the reply
// thread's already-fetched pages.
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useCloseTicket } from "./useCloseTicket";
import { ticketDetailQueryKey, ticketRepliesQueryKey } from "./useTicketDetail";

describe("useCloseTicket", () => {
  it("test_use_close_ticket_on_success_invalidates_ticket_detail_query_only", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/close", async () =>
        HttpResponse.json(
          { id: "t-1", ticket_number: "TCK-0001", status: "closed", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useCloseTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    await result.current.mutateAsync();

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(ticketDetailQueryKey("t-1"));
    expect(invalidatedKeys).not.toContainEqual(ticketRepliesQueryKey("t-1"));
  });

  it("test_use_close_ticket_calls_close_endpoint_and_resolves_with_status_closed", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/close", async () =>
        HttpResponse.json(
          { id: "t-1", ticket_number: "TCK-0001", status: "closed", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useCloseTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync();

    // Assert
    expect(data.status).toBe("closed");
  });
});
