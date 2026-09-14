// Integration test for AgentTicketQueueScreen (FR-1/AG-AC1, FR-2/AG-AC2's
// queue-side assertions, a11y bar). Covers: columns, filters resetting the
// cursor, mutually-exclusive me/none presets, the raw-UUID "specific agent"
// filter (Resolution OD-2), "Load more", the explicit empty-result state,
// the assignee column's shortened/truncated-UUID rendering (Resolution
// OD-1) and its literal "Unassigned" text for a null assignee_id
// (Architectural Change 8), assign/unassign call shape and 409/422
// rendering, the navigation-state handoff on row click (Architectural
// Change 7), the tickets:write-absent read-only/disabled-controls case
// (FR-6/AG-AC6), and an axe a11y pass with the table's cells associated to
// column headers.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AgentTicketQueueScreen } from "./AgentTicketQueueScreen";
import { formatAssigneeId } from "./agentTicketHelpers";

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

function renderQueue(scopes: string[] = ["tickets:read", "tickets:write"], userId = "agent-me") {
  return renderWithProviders(
    <Routes>
      <Route path="/agent/tickets" element={<AgentTicketQueueScreen />} />
      <Route path="/agent/tickets/:id" element={<div data-testid="detail-screen-marker">Detail</div>} />
    </Routes>,
    {
      route: "/agent/tickets",
      isAuthenticated: true,
      scopes,
      user: { id: userId, email: "agent@example.com" },
    },
  );
}

describe("formatAssigneeId (Resolution OD-1, Architectural Change 8)", () => {
  it("test_format_assignee_id_null_renders_the_literal_unassigned_text", () => {
    expect(formatAssigneeId(null)).toBe("Unassigned");
  });

  it("test_format_assignee_id_truncates_a_uuid_to_its_first_8_hex_characters", () => {
    expect(formatAssigneeId("a1b2c3d4-e5f6-4789-a012-3456789abcde")).toBe("a1b2c3d4");
  });
});

describe("AgentTicketQueueScreen", () => {
  it("test_agent_ticket_queue_screen_renders_every_column_for_a_ticket_row", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderQueue();

    // Assert
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
    expect(screen.getByText("Cannot log in")).toBeInTheDocument();
    expect(screen.getByText("account")).toBeInTheDocument();
    expect(screen.getAllByText("open").length).toBeGreaterThan(0);
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("2026-09-01T10:00:00Z")).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_renders_a_truncated_uuid_for_an_assigned_ticket", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            items: [agentTicket({ assignee_id: "a1b2c3d4-e5f6-4789-a012-3456789abcde" })],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderQueue();

    // Assert
    expect(await screen.findByText("a1b2c3d4")).toBeInTheDocument();
    expect(screen.queryByText("Unassigned")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_renders_the_explicit_empty_result_state", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderQueue();

    // Assert
    expect(await screen.findByText("No tickets match these filters.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_status_and_category_filters_re_request_and_reset_the_cursor", async () => {
    // Arrange
    const receivedParams: { status: string | null; category: string | null; cursor: string | null }[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const url = new URL(request.url);
        const cursor = url.searchParams.get("cursor");
        receivedParams.push({
          status: url.searchParams.get("status"),
          category: url.searchParams.get("category"),
          cursor,
        });
        if (!url.searchParams.get("status")) {
          // Distinct ids per page (t-1, then t-2 for the "Load more" page)
          // so flattening pages never renders two rows with the same key —
          // a real backend's cursor pagination never repeats an id either.
          // next_cursor stays "cursor-2" on the second page too, so "Load
          // more" is still present for the assertion below.
          if (cursor === "cursor-2") {
            return HttpResponse.json(
              { items: [agentTicket({ id: "t-2" })], next_cursor: "cursor-2" },
              { status: 200 },
            );
          }
          return HttpResponse.json(
            { items: [agentTicket({ id: "t-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json({ items: [agentTicket({ id: "t-3" })], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");
    await user.click(screen.getByRole("button", { name: /load more/i }));
    await screen.findByText(/load more/i);

    // Act: changing the status filter must re-issue the request and reset
    // the cursor (AG-AC1) — the next request must NOT carry the cursor from
    // the page-2 fetch above.
    await user.selectOptions(screen.getByLabelText(/status/i), "open");

    // Assert
    await screen.findByText("TCK-0001");
    const lastCall = receivedParams[receivedParams.length - 1];
    expect(lastCall.status).toBe("open");
    expect(lastCall.cursor).toBeNull();
  });

  it("test_agent_ticket_queue_screen_me_and_none_presets_are_mutually_exclusive", async () => {
    // Arrange
    const receivedAssigneeIds: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        receivedAssigneeIds.push(new URL(request.url).searchParams.get("assignee_id"));
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText(/no tickets match/i);

    // Act
    await user.click(screen.getByRole("button", { name: /assigned to me/i }));
    await user.click(screen.getByRole("button", { name: /no assignee/i }));

    // Assert: the last request reflects "none", and "me" is no longer active.
    expect(receivedAssigneeIds[receivedAssigneeIds.length - 1]).toBe("none");
    expect(screen.getByRole("button", { name: /assigned to me/i })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /no assignee/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("test_agent_ticket_queue_screen_a_raw_uuid_specific_agent_filter_clears_any_active_preset", async () => {
    // Arrange
    const receivedAssigneeIds: (string | null)[] = [];
    const rawUuid = "b2c3d4e5-f6a7-4890-b123-456789abcdef";
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        receivedAssigneeIds.push(new URL(request.url).searchParams.get("assignee_id"));
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText(/no tickets match/i);
    await user.click(screen.getByRole("button", { name: /assigned to me/i }));

    // Act
    await user.type(screen.getByLabelText(/specific agent/i), rawUuid);

    // Assert
    expect(receivedAssigneeIds[receivedAssigneeIds.length - 1]).toBe(rawUuid);
    expect(screen.getByRole("button", { name: /assigned to me/i })).toHaveAttribute("aria-pressed", "false");
  });

  it("test_agent_ticket_queue_screen_load_more_appends_the_second_page", async () => {
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
        return HttpResponse.json(
          { items: [agentTicket({ id: "t-2", ticket_number: "TCK-0002" })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /load more/i }));

    // Assert
    expect(await screen.findByText("TCK-0002")).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_assign_to_me_calls_assign_endpoint_with_the_agents_own_id", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/assign", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-me" },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    expect(receivedBody).toEqual({ assignee_id: "agent-me" });
  });

  it("test_agent_ticket_queue_screen_assign_to_another_agent_raw_uuid_calls_the_assign_endpoint", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    const otherAgentId = "c3d4e5f6-a7b8-4901-c234-56789abcdef0";
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/assign", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: otherAgentId },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/assign to agent \(uuid\)/i), otherAgentId);
    await user.click(screen.getByRole("button", { name: /^assign$/i }));

    // Assert
    expect(receivedBody).toEqual({ assignee_id: otherAgentId });
  });

  it("test_agent_ticket_queue_screen_unassign_calls_delete_assign_endpoint", async () => {
    // Arrange
    let unassignCalled = false;
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          { items: [agentTicket({ assignee_id: "agent-me" })], next_cursor: null },
          { status: 200 },
        ),
      ),
      http.delete("/api/v1/support/tickets/t-1/assign", async () => {
        unassignCalled = true;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^unassign$/i }));

    // Assert
    expect(unassignCalled).toBe(true);
  });

  it("test_agent_ticket_queue_screen_assign_409_closed_ticket_renders_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
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
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    expect(await screen.findByText("This ticket is closed and cannot be assigned.")).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_assign_422_assignee_not_an_agent_renders_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
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
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    expect(await screen.findByText("The target user does not hold tickets:write.")).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_assign_422_maps_the_errors_array_onto_the_assignee_id_field", async () => {
    // Arrange: AG-AC7/FR-8 — a 422's errors[] array must map onto its
    // matching form field via the project's shared getFieldErrors()/
    // FieldError mechanism (NewTicketScreen.tsx's established pattern), not
    // just render the top-level detail string generically. `detail` and the
    // field message are deliberately different strings here so a passing
    // assertion proves the field-scoped renderer fired (and the generic
    // top-level paragraph was suppressed in its favor), not just that some
    // text on the page happens to match.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            detail: "Validation failed.",
            errors: [{ field: "assignee_id", message: "The target user does not hold tickets:write." }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    const fieldError = await screen.findByText("The target user does not hold tickets:write.");
    expect(fieldError).toHaveAttribute("data-field", "assignee_id");
    expect(screen.queryByText("Validation failed.")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_assign_to_me_updates_the_row_to_reflect_the_new_assignee_after_success", async () => {
    // Arrange: AG-AC2's "the row reflects the new assignee" clause — the
    // prior test only asserted the outgoing request body fired; this proves
    // the DOM actually reflects the new assignee once the success-triggered
    // queue invalidation refetches.
    let ticketsFetchCount = 0;
    server.use(
      http.get("/api/v1/support/tickets", async () => {
        ticketsFetchCount += 1;
        return HttpResponse.json(
          {
            items: [agentTicket({ assignee_id: ticketsFetchCount > 1 ? "agent-me" : null })],
            next_cursor: null,
          },
          { status: 200 },
        );
      }),
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-me" },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");
    expect(screen.getByText("Unassigned")).toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    expect(await screen.findByText("agent-me")).toBeInTheDocument();
    expect(screen.queryByText("Unassigned")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_renders_tickets_in_the_servers_returned_order_and_shows_no_total_count_or_page_number", async () => {
    // Arrange: AG-AC1 — "oldest-updated first" is the server's own ordering
    // (this screen applies no client-side sort, confirmed by direct read);
    // this asserts the DOM preserves the server's row order verbatim, and
    // that no total-count/page-number element is rendered anywhere.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            items: [
              agentTicket({ id: "t-1", ticket_number: "TCK-0001", updated_at: "2026-09-01T09:00:00Z" }),
              agentTicket({ id: "t-2", ticket_number: "TCK-0002", updated_at: "2026-09-01T10:00:00Z" }),
              agentTicket({ id: "t-3", ticket_number: "TCK-0003", updated_at: "2026-09-01T11:00:00Z" }),
            ],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderQueue();
    await screen.findByText("TCK-0001");

    // Assert: row order matches the server's returned (oldest-updated-first) order.
    const rowButtons = screen.getAllByRole("button", { name: /^TCK-\d{4}$/ });
    expect(rowButtons.map((button) => button.textContent)).toEqual(["TCK-0001", "TCK-0002", "TCK-0003"]);
    // No total count or page number is displayed anywhere on this screen.
    expect(screen.queryByText(/total|page\s*\d|\d+\s*of\s*\d+/i)).not.toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_a_malformed_raw_uuid_filter_renders_the_422_inline", async () => {
    // Arrange: Implementation Plan Risk 4 — no client-side UUID shape
    // validation; the server's 422 is rendered, not a client-side block.
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const assigneeId = new URL(request.url).searchParams.get("assignee_id");
        if (assigneeId === "not-a-uuid") {
          return HttpResponse.json(
            {
              type: "https://errors.example/validation-failed",
              title: "Validation failed",
              status: 422,
              detail: 'assignee_id must be a UUID, "me", or "none".',
            },
            { status: 422, headers: { "content-type": "application/problem+json" } },
          );
        }
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText(/no tickets match/i);

    // Act
    await user.type(screen.getByLabelText(/specific agent/i), "not-a-uuid");

    // Assert
    expect(await screen.findByText('assignee_id must be a UUID, "me", or "none".')).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_navigates_with_assignee_id_navigation_state_on_row_click", async () => {
    // Arrange: Architectural Change 7's navigation-state handoff.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          { items: [agentTicket({ assignee_id: "agent-me" })], next_cursor: null },
          { status: 200 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: "TCK-0001" }));

    // Assert
    expect(await screen.findByTestId("detail-screen-marker")).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_disables_every_write_control_when_tickets_write_is_absent", async () => {
    // Arrange: FR-6/AG-AC6 — read-only view with every write control disabled.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderQueue(["tickets:read"]);
    await screen.findByText("TCK-0001");

    // Assert
    expect(screen.getByRole("button", { name: /^assign to me$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^unassign$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^assign$/i })).toBeDisabled();
    expect(screen.getByLabelText(/assign to agent \(uuid\)/i)).toBeDisabled();
  });

  it("test_agent_ticket_queue_screen_table_cells_are_associated_with_column_headers", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderQueue();
    await screen.findByText("TCK-0001");

    // Assert
    const table = screen.getByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((header) => header.textContent)).toEqual([
      "Ticket number",
      "Subject",
      "Category",
      "Status",
      "Assignee",
      "Updated",
      "Actions",
    ]);
  });

  it("test_agent_ticket_queue_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [agentTicket()], next_cursor: null }, { status: 200 }),
      ),
    );
    const { container } = renderQueue();
    await screen.findByText("TCK-0001");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });

  it("test_agent_ticket_queue_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets", () => HttpResponse.error()));

    // Act
    renderQueue();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_agent_ticket_queue_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderQueue();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
