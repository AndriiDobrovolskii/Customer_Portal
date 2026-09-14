// Unit test for useResolveTicket (FR-5/AG-AC5). A successful resolve writes
// the returned TicketStateRead (status "resolved") into
// ticketDetailQueryKey(id)'s cache, the same "mutation response is the new
// truth" pattern as useCloseTicket.ts, and a 409 on a closed ticket renders
// its problem+json detail.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useResolveTicket } from "./useResolveTicket";
import { ticketDetailQueryKey } from "./useTicketDetail";
import type { TicketDetailRead } from "../api/types";

function seedDetail(overrides: Partial<TicketDetailRead> = {}): TicketDetailRead {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    subject: "Cannot log in",
    category: "account",
    status: "open",
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    first_response_at: null,
    replies: { items: [], next_cursor: null },
    ...overrides,
  };
}

describe("useResolveTicket", () => {
  it("test_use_resolve_ticket_sends_the_resolution_note_and_resolves_with_status_resolved", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.post("/api/v1/support/tickets/t-1/resolve", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "resolved", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useResolveTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync({ resolution_note: "Fixed via password reset." });

    // Assert
    expect(receivedBody).toEqual({ resolution_note: "Fixed via password reset." });
    expect(data.status).toBe("resolved");
  });

  it("test_use_resolve_ticket_on_success_writes_ticket_state_read_into_the_detail_cache", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/resolve", async () =>
        HttpResponse.json(
          { id: "t-1", status: "resolved", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useResolveTicket("t-1"));
    queryClient.setQueryData(ticketDetailQueryKey("t-1"), seedDetail());

    // Act
    await result.current.mutateAsync({ resolution_note: "Fixed via password reset." });

    // Assert
    const cached = queryClient.getQueryData<TicketDetailRead>(ticketDetailQueryKey("t-1"));
    expect(cached?.status).toBe("resolved");
    expect(cached?.updated_at).toBe("2026-09-01T12:00:00Z");
    // The rest of the cached ticket is preserved, not blanked out.
    expect(cached?.subject).toBe("Cannot log in");
  });

  it("test_use_resolve_ticket_409_on_closed_ticket_propagates_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/resolve", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/ticket-closed",
            title: "Ticket closed",
            status: 409,
            detail: "This ticket is closed and cannot be resolved.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useResolveTicket("t-1"));

    // Act / Assert
    await expect(result.current.mutateAsync({ resolution_note: "Note." })).rejects.toMatchObject({
      status: 409,
      message: "This ticket is closed and cannot be resolved.",
    });
  });
});
