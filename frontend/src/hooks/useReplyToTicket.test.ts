// Unit test for useReplyToTicket (TK-AC6/FR-6). onSuccess must invalidate
// BOTH ticketDetailQueryKey(id) (a customer reply on "waiting_on_customer"
// silently transitions the ticket to "waiting_on_support" server-side, and
// ReplyRead carries no status field to report it) AND ticketRepliesQueryKey(id)
// (so the new reply appears in the thread).
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useReplyToTicket } from "./useReplyToTicket";
import { ticketDetailQueryKey, ticketRepliesQueryKey } from "./useTicketDetail";

describe("useReplyToTicket", () => {
  it("test_use_reply_to_ticket_on_success_invalidates_both_ticket_detail_and_ticket_replies_queries", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets/t-1/replies", async () =>
        HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "customer", visibility: "public", body: "Thanks" },
          { status: 201 },
        ),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useReplyToTicket("t-1"));
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    await result.current.mutateAsync({ body: "Thanks" });

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(ticketDetailQueryKey("t-1"));
    expect(invalidatedKeys).toContainEqual(ticketRepliesQueryKey("t-1"));
  });

  it("test_use_reply_to_ticket_sends_no_visibility_field_and_attachment_ids_empty", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> = {};
    server.use(
      http.post("/api/v1/support/tickets/t-1/replies", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "customer", visibility: "public", body: "Thanks" },
          { status: 201 },
        );
      }),
    );
    const { result } = renderHookWithProviders(() => useReplyToTicket("t-1"));

    // Act
    await result.current.mutateAsync({ body: "Thanks" });

    // Assert
    expect(capturedBody).not.toHaveProperty("visibility");
    expect(capturedBody).toMatchObject({ body: "Thanks", attachment_ids: [] });
  });

  // US-5.5 Architectural Change 2: a supplied visibility (the agent
  // composer's path) is included in the request body; the customer path
  // above (no visibility supplied) is unaffected and keeps omitting the key
  // entirely.
  it.each(["public", "internal"] as const)(
    "test_use_reply_to_ticket_a_supplied_visibility_%s_is_included_in_the_request_body",
    async (visibility) => {
      // Arrange
      let capturedBody: Record<string, unknown> = {};
      server.use(
        http.post("/api/v1/support/tickets/t-1/replies", async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            { id: "r-1", ticket_id: "t-1", author_kind: "agent", visibility, body: "Noted" },
            { status: 201 },
          );
        }),
      );
      const { result } = renderHookWithProviders(() => useReplyToTicket("t-1"));

      // Act
      await result.current.mutateAsync({ body: "Noted", visibility });

      // Assert
      expect(capturedBody).toEqual({ body: "Noted", visibility, attachment_ids: [] });
    },
  );
});
