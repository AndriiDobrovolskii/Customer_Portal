// Unit test for useUnassignTicket (FR-2/AG-AC2). Covers: DELETE .../assign
// unconditionally invalidates the queue query-key prefix regardless of call
// origin (Architectural Change 8, same one-onSuccess-handler shape as
// useAssignTicket.ts) and a 409 on a closed ticket renders its problem+json
// detail; same cache-merge constraint (Implementation Plan Risk 3) — the
// resolved data is never spread over a full AgentTicketRead shape.
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useUnassignTicket } from "./useUnassignTicket";
import { AGENT_TICKETS_QUERY_KEY_PREFIX } from "./useAgentTickets";

describe("useUnassignTicket", () => {
  it("test_use_unassign_ticket_calls_delete_assign_endpoint_and_resolves_with_null_assignee_id", async () => {
    // Arrange
    let deleteCalled = false;
    server.use(
      http.delete("/api/v1/support/tickets/t-1/assign", async () => {
        deleteCalled = true;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useUnassignTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync();

    // Assert
    expect(deleteCalled).toBe(true);
    expect(data.assignee_id).toBeNull();
  });

  it("test_use_unassign_ticket_on_success_unconditionally_invalidates_the_queue_query_key_prefix_queue_origin", async () => {
    // Arrange
    server.use(
      http.delete("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useUnassignTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    await result.current.mutateAsync();

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(AGENT_TICKETS_QUERY_KEY_PREFIX);
  });

  it("test_use_unassign_ticket_on_success_unconditionally_invalidates_the_queue_query_key_prefix_detail_origin", async () => {
    // Arrange: a detail-screen-originated unassign writes the response into
    // local state via a per-call onSuccess (Architectural Change 7) — same
    // single hook-level onSuccess handles invalidation regardless.
    server.use(
      http.delete("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useUnassignTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    let capturedForLocalState: unknown;
    await result.current.mutateAsync(undefined, {
      onSuccess: (data) => (capturedForLocalState = data),
    });

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(AGENT_TICKETS_QUERY_KEY_PREFIX);
    expect((capturedForLocalState as { assignee_id: string | null }).assignee_id).toBeNull();
  });

  it("test_use_unassign_ticket_resolved_data_carries_only_id_status_updated_at_assignee_id", async () => {
    // Arrange: Implementation Plan Risk 3.
    server.use(
      http.delete("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useUnassignTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync();

    // Assert
    expect(Object.keys(data).sort()).toEqual(["assignee_id", "id", "status", "updated_at"]);
  });

  it("test_use_unassign_ticket_409_closed_ticket_propagates_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.delete("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/ticket-closed",
            title: "Ticket closed",
            status: 409,
            detail: "This ticket is closed and cannot be unassigned.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useUnassignTicket("t-1"));

    // Act / Assert
    await expect(result.current.mutateAsync()).rejects.toMatchObject({
      status: 409,
      message: "This ticket is closed and cannot be unassigned.",
    });
  });
});
