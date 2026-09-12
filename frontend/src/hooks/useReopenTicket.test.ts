// Unit test for useReopenTicket (TK-AC8/FR-8, OD-3's binding resolution).
// onSuccess invalidates ticketDetailQueryKey(id) only — reopening does not
// change the reply thread. OD-3: the hook performs no client-computed
// reopen-eligibility check of any kind; the backend's 409 (outside the 7-day
// reopen window) is the sole source of truth, and must reach the caller
// unmodified (status + detail intact) so TicketDetailScreen.tsx can render it.
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useReopenTicket } from "./useReopenTicket";
import { ticketDetailQueryKey, ticketRepliesQueryKey } from "./useTicketDetail";

describe("useReopenTicket", () => {
  it("test_use_reopen_ticket_on_success_invalidates_ticket_detail_query_only", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/reopen", async () =>
        HttpResponse.json(
          {
            id: "t-1",
            ticket_number: "TCK-0001",
            status: "waiting_on_support",
            updated_at: "2026-09-01T12:00:00Z",
          },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useReopenTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    await result.current.mutateAsync();

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(ticketDetailQueryKey("t-1"));
    expect(invalidatedKeys).not.toContainEqual(ticketRepliesQueryKey("t-1"));
  });

  it("test_use_reopen_ticket_calls_reopen_endpoint_and_resolves_with_status_waiting_on_support", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/reopen", async () =>
        HttpResponse.json(
          {
            id: "t-1",
            ticket_number: "TCK-0001",
            status: "waiting_on_support",
            updated_at: "2026-09-01T12:00:00Z",
          },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useReopenTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync();

    // Assert
    expect(data.status).toBe("waiting_on_support");
  });

  it("test_use_reopen_ticket_409_outside_reopen_window_reaches_caller_unmodified_with_detail_intact", async () => {
    // Arrange: OD-3's binding resolution — no client-side eligibility window
    // exists in this hook, so a 409 must surface exactly as the backend sent
    // it (status + detail), not swallowed or reshaped.
    server.use(
      http.post("/api/v1/support/tickets/t-1/reopen", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/reopen-window-expired",
            title: "Reopen window expired",
            status: 409,
            detail: "This ticket can no longer be reopened; the 7-day window has passed.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useReopenTicket("t-1"));

    // Act / Assert
    await expect(result.current.mutateAsync()).rejects.toMatchObject({
      status: 409,
      message: "This ticket can no longer be reopened; the 7-day window has passed.",
    });
  });
});
