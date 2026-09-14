// Unit test for useAgentTickets (FR-1/AG-AC1). Covers: a status/category/
// assignee_id filter change produces a new query key and resets the cursor;
// the me/none presets and a raw-UUID "specific agent" value are sent as the
// literal assignee_id string with no client-side substitution or UUID
// validation; a malformed assignee_id renders the server's 422 problem+json
// detail inline (via the mutation's own error) rather than being blocked
// client-side (Implementation Plan Risk 4); "Load more" appends on a
// non-null next_cursor.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useAgentTickets, agentTicketsQueryKey, AGENT_TICKETS_QUERY_KEY_PREFIX } from "./useAgentTickets";

function agentTicket(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    subject: "Cannot log in",
    category: "account",
    status: "open",
    assignee_id: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    ...overrides,
  };
}

describe("agentTicketsQueryKey", () => {
  it("test_agent_tickets_query_key_prefix_matches_a_full_key_with_filters", () => {
    // Arrange / Act
    const fullKey = agentTicketsQueryKey({ status: "open", category: "account", assigneeId: "me" });

    // Assert: TanStack Query's prefix-invalidation relies on the shorter
    // key being a real array-prefix of the longer one.
    for (let i = 0; i < AGENT_TICKETS_QUERY_KEY_PREFIX.length; i += 1) {
      expect(fullKey[i]).toBe(AGENT_TICKETS_QUERY_KEY_PREFIX[i]);
    }
  });
});

describe("useAgentTickets", () => {
  it("test_use_agent_tickets_first_page_has_next_page_true_when_next_cursor_is_present", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAgentTickets());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(result.current.hasNextPage).toBe(true);
  });

  it("test_use_agent_tickets_load_more_appends_the_second_page", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        if (!cursor) {
          return HttpResponse.json(
            { items: [agentTicket({ id: "t-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json({ items: [agentTicket({ id: "t-2" })], next_cursor: null }, { status: 200 });
      }),
    );
    const { result } = renderHookWithProviders(() => useAgentTickets());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Act
    result.current.fetchNextPage();

    // Assert
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    const ids = result.current.data?.pages.flatMap((page) => page.items.map((item) => item.id));
    expect(ids).toEqual(["t-1", "t-2"]);
  });

  it("test_use_agent_tickets_status_category_filters_are_sent_as_query_parameters", async () => {
    // Arrange
    let received: { status: string | null; category: string | null } | null = null;
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const url = new URL(request.url);
        received = { status: url.searchParams.get("status"), category: url.searchParams.get("category") };
        return HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 });
      }),
    );

    // Act
    const { result } = renderHookWithProviders(() =>
      useAgentTickets({ status: "open", category: "account" }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(received).toEqual({ status: "open", category: "account" });
  });

  it.each(["me", "none"])(
    "test_use_agent_tickets_%s_preset_is_sent_verbatim_as_the_assignee_id_query_parameter",
    async (preset) => {
      // Arrange
      let receivedAssigneeId: string | null = null;
      server.use(
        http.get("/api/v1/support/tickets", async ({ request }) => {
          receivedAssigneeId = new URL(request.url).searchParams.get("assignee_id");
          return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
        }),
      );

      // Act
      const { result } = renderHookWithProviders(() => useAgentTickets({ assigneeId: preset }));
      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // Assert: no client-side substitution — the literal string is sent as-is.
      expect(receivedAssigneeId).toBe(preset);
    },
  );

  it("test_use_agent_tickets_a_raw_uuid_specific_agent_value_is_sent_verbatim_with_no_client_side_validation", async () => {
    // Arrange
    let receivedAssigneeId: string | null = null;
    const rawUuid = "a1b2c3d4-e5f6-4789-a012-3456789abcde";
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        receivedAssigneeId = new URL(request.url).searchParams.get("assignee_id");
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAgentTickets({ assigneeId: rawUuid }));
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert
    expect(receivedAssigneeId).toBe(rawUuid);
  });

  it("test_use_agent_tickets_a_malformed_assignee_id_propagates_the_servers_422_problem_json_detail", async () => {
    // Arrange: Implementation Plan Risk 4 — no client-side UUID shape
    // validation; the 422 from list_agent_queue is left to propagate as-is.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            detail: 'assignee_id must be a UUID, "me", or "none".',
            errors: [{ field: "assignee_id", message: 'assignee_id must be a UUID, "me", or "none".' }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAgentTickets({ assigneeId: "not-a-uuid" }));
    await waitFor(() => expect(result.current.isError).toBe(true));

    // Assert
    expect((result.current.error as { status?: number }).status).toBe(422);
    expect((result.current.error as { message?: string }).message).toContain("assignee_id");
  });

  it("test_use_agent_tickets_changing_a_filter_resets_pagination_to_a_single_page", async () => {
    // Arrange: a filter change is a query-key change in TanStack Query, so
    // a previously-fetched second page must not survive into the new
    // filter's result set (AG-AC1's "filters... reset the cursor").
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const url = new URL(request.url);
        const status = url.searchParams.get("status");
        const cursor = url.searchParams.get("cursor");
        if (!status && !cursor) {
          return HttpResponse.json(
            { items: [agentTicket({ id: "t-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        if (!status && cursor === "cursor-2") {
          return HttpResponse.json(
            { items: [agentTicket({ id: "t-2" })], next_cursor: null },
            { status: 200 },
          );
        }
        return HttpResponse.json(
          { items: [agentTicket({ id: "t-3", status })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const statusRef: { current: string | undefined } = { current: undefined };
    const { result, rerender } = renderHookWithProviders(() =>
      useAgentTickets({ status: statusRef.current }),
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    result.current.fetchNextPage();
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));

    // Act
    statusRef.current = "waiting_on_support";
    rerender();

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pages).toHaveLength(1);
  });
});
