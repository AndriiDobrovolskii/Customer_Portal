// Unit test for useAssignTicket (FR-2/AG-AC2). Covers: assign-to-me and
// assign-to-another-agent (Resolution OD-2's raw-UUID input) both call
// POST .../assign and unconditionally invalidate useAgentTickets.ts's
// query-key prefix — one onSuccess handler, regardless of whether the call
// "originates" from the queue screen or the detail screen (Architectural
// Change 8); the resolved AgentTicketStateRead carries exactly
// assignee_id/status/updated_at (never a spread over a full AgentTicketRead
// shape, Implementation Plan Risk 3) — available for a detail screen's own
// per-call onSuccess to write into its local navigation-state-handoff
// assignee value (Architectural Change 7; this hook itself holds no such
// state, per AGENTS.md §3's hooks/ layer never importing JSX/component
// state); a 409 (closed ticket) and 422 (assignee is not an agent) render
// their problem+json detail via the propagated error.
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useAssignTicket } from "./useAssignTicket";
import { AGENT_TICKETS_QUERY_KEY_PREFIX } from "./useAgentTickets";

describe("useAssignTicket", () => {
  it("test_use_assign_ticket_assign_to_me_calls_assign_endpoint_with_the_supplied_id", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-1" },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useAssignTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync({ assignee_id: "agent-1" });

    // Assert
    expect(receivedBody).toEqual({ assignee_id: "agent-1" });
    expect(data).toEqual({
      id: "t-1",
      status: "open",
      updated_at: "2026-09-01T12:00:00Z",
      assignee_id: "agent-1",
    });
  });

  it("test_use_assign_ticket_assign_to_another_agent_raw_uuid_calls_the_same_endpoint", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    const otherAgentId = "b2c3d4e5-f6a7-4890-b123-456789abcdef";
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: otherAgentId },
          { status: 200 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useAssignTicket("t-1"));

    // Act
    await result.current.mutateAsync({ assignee_id: otherAgentId });

    // Assert
    expect(receivedBody).toEqual({ assignee_id: otherAgentId });
  });

  it("test_use_assign_ticket_on_success_unconditionally_invalidates_the_queue_query_key_prefix_queue_origin", async () => {
    // Arrange: simulates a call "originating" from the queue screen — the
    // hook has exactly one onSuccess handler, so this and the next test
    // exercise the identical, origin-agnostic code path (Architectural
    // Change 8).
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-1" },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useAssignTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    await result.current.mutateAsync({ assignee_id: "agent-1" });

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(AGENT_TICKETS_QUERY_KEY_PREFIX);
  });

  it("test_use_assign_ticket_on_success_unconditionally_invalidates_the_queue_query_key_prefix_detail_origin", async () => {
    // Arrange: simulates a call originating from the detail screen — same
    // hook, same single onSuccess handler.
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-2" },
          { status: 200 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useAssignTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act: a per-call onSuccess is the mechanism a detail screen uses to
    // write the response into its own local assignee state (Architectural
    // Change 7) — asserted here as the resolved data being available to it.
    let capturedForLocalState: unknown;
    await result.current.mutateAsync(
      { assignee_id: "agent-2" },
      { onSuccess: (data) => (capturedForLocalState = data) },
    );

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(AGENT_TICKETS_QUERY_KEY_PREFIX);
    expect(capturedForLocalState).toEqual({
      id: "t-1",
      status: "open",
      updated_at: "2026-09-01T12:00:00Z",
      assignee_id: "agent-2",
    });
  });

  it("test_use_assign_ticket_resolved_data_carries_only_id_status_updated_at_assignee_id_never_a_full_queue_row", async () => {
    // Arrange: Implementation Plan Risk 3 — the assign response
    // (AgentTicketStateRead) must never be conflated with a full
    // AgentTicketRead (which also carries subject/category).
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-1" },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useAssignTicket("t-1"));

    // Act
    const data = await result.current.mutateAsync({ assignee_id: "agent-1" });

    // Assert
    expect(Object.keys(data).sort()).toEqual(["assignee_id", "id", "status", "updated_at"]);
    expect(data).not.toHaveProperty("subject");
    expect(data).not.toHaveProperty("category");
  });

  it("test_use_assign_ticket_409_closed_ticket_propagates_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/ticket-closed",
            title: "Ticket closed",
            status: 409,
            detail: "This ticket is closed and cannot be assigned.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useAssignTicket("t-1"));

    // Act / Assert
    await expect(result.current.mutateAsync({ assignee_id: "agent-1" })).rejects.toMatchObject({
      status: 409,
      message: "This ticket is closed and cannot be assigned.",
    });
  });

  it("test_use_assign_ticket_422_assignee_not_an_agent_propagates_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            detail: "The target user does not hold tickets:write.",
            errors: [{ field: "assignee_id", message: "The target user does not hold tickets:write." }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useAssignTicket("t-1"));

    // Act / Assert
    await expect(result.current.mutateAsync({ assignee_id: "not-an-agent" })).rejects.toMatchObject({
      status: 422,
    });
  });
});
