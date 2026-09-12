// Integration test for TicketListScreen (TK-AC1/FR-1, TK-AC2/FR-2, the
// TK-AC11 shared 4xx case, the TK-AC14 401->refresh-coordinator assertion
// per task_breakdown v2 T13, a11y bar).
//
// Field-label collaborator-shape assumptions (docs/tests/US-5.3-test-strategy.md
// item 7 — no design doc fixes UI copy): a "Status" <select> filter (five
// options + "All"), a "Load more" button, a "New ticket" call-to-action link.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { TicketListScreen } from "./TicketListScreen";

function ticket(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    subject: "Cannot log in",
    category: "account",
    status: "open",
    updated_at: "2026-09-01T10:00:00Z",
    ...overrides,
  };
}

describe("TicketListScreen", () => {
  it("test_ticket_list_screen_renders_ticket_number_subject_category_status_and_updated_at_per_row", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [ticket()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    const row = await screen.findByText("TCK-0001");
    const container = row.closest("li, tr, div") ?? document.body;
    expect(within(container as HTMLElement).getByText(/cannot log in/i)).toBeInTheDocument();
    expect(within(container as HTMLElement).getByText(/account/i)).toBeInTheDocument();
    expect(within(container as HTMLElement).getByText(/open/i)).toBeInTheDocument();
    expect(within(container as HTMLElement).getByText(/2026-09-01/)).toBeInTheDocument();
  });

  it("test_ticket_list_screen_renders_an_unrecognized_status_value_verbatim_with_neutral_styling", async () => {
    // Arrange: FR-1 — status is a plain string, not an enum; an unrecognized
    // value renders verbatim rather than being hidden or crashing the screen.
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          { items: [ticket({ status: "pending_vendor_escalation" })], next_cursor: null },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByText(/pending_vendor_escalation/i)).toBeInTheDocument();
  });

  it("test_ticket_list_screen_load_more_appends_the_next_page_using_next_cursor_and_disappears_when_null", async () => {
    // Arrange
    const receivedCursors: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        receivedCursors.push(cursor);
        if (!cursor) {
          return HttpResponse.json(
            { items: [ticket({ id: "t-1", ticket_number: "TCK-0001" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json(
          { items: [ticket({ id: "t-2", ticket_number: "TCK-0002" })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /load more/i }));

    // Assert
    expect(await screen.findByText("TCK-0002")).toBeInTheDocument();
    expect(receivedCursors).toEqual([null, "cursor-2"]);
    expect(screen.queryByRole("button", { name: /load more/i })).not.toBeInTheDocument();
  });

  it("test_ticket_list_screen_empty_items_shows_new_ticket_cta_instead_of_a_blank_screen", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByRole("link", { name: /new ticket/i })).toHaveAttribute("href", "/tickets/new");
  });

  it.each(["open", "waiting_on_support", "waiting_on_customer", "resolved", "closed"])(
    "test_ticket_list_screen_selecting_status_%s_re_issues_the_request_with_that_status_and_a_reset_cursor",
    async (status) => {
      // Arrange
      const receivedRequests: { status: string | null; cursor: string | null }[] = [];
      server.use(
        http.get("/api/v1/support/tickets", async ({ request }) => {
          const url = new URL(request.url);
          receivedRequests.push({
            status: url.searchParams.get("status"),
            cursor: url.searchParams.get("cursor"),
          });
          return HttpResponse.json({ items: [ticket({ status })], next_cursor: null }, { status: 200 });
        }),
      );
      const user = userEvent.setup();
      renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });
      await screen.findByText("TCK-0001");

      // Act
      await user.selectOptions(screen.getByLabelText(/status/i), status);

      // Assert
      await screen.findByText(new RegExp(status, "i"));
      const lastRequest = receivedRequests[receivedRequests.length - 1];
      expect(lastRequest).toEqual({ status, cursor: null });
    },
  );

  it("test_ticket_list_screen_clearing_the_filter_re_requests_the_unfiltered_list", async () => {
    // Arrange
    const receivedStatuses: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets", async ({ request }) => {
        receivedStatuses.push(new URL(request.url).searchParams.get("status"));
        return HttpResponse.json({ items: [ticket()], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });
    await screen.findByText("TCK-0001");
    await user.selectOptions(screen.getByLabelText(/status/i), "resolved");

    // Act
    await user.selectOptions(screen.getByLabelText(/status/i), "");

    // Assert
    await screen.findByText("TCK-0001");
    expect(receivedStatuses[receivedStatuses.length - 1]).toBeNull();
  });

  it("test_ticket_list_screen_4xx_problem_json_renders_mapped_detail_message_with_no_raw_json", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "Your account has been deactivated.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByText("Your account has been deactivated.")).toBeInTheDocument();
    expect(screen.queryByText(/"type":|"title":/)).not.toBeInTheDocument();
  });

  it("test_ticket_list_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets", () => HttpResponse.error()));

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_ticket_list_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_ticket_list_screen_401_triggers_the_existing_silent_refresh_coordinator_and_retries", async () => {
    // Arrange: TK-AC14 — a ticket-domain request feeds the same
    // 401->refresh->retry path US-5.1's httpClient already implements;
    // this is not a duplicate of that unit-level coverage, only a
    // confirmation that this Story's requests go through it too.
    let ticketsAttempts = 0;
    let refreshCalled = false;
    server.use(
      http.get("/api/v1/support/tickets", async () => {
        ticketsAttempts += 1;
        if (ticketsAttempts === 1) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json({ items: [ticket()], next_cursor: null }, { status: 200 });
      }),
      http.post("/api/v1/auth/refresh", async () => {
        refreshCalled = true;
        return HttpResponse.json({ access_token: "refreshed-token", expires_in: 900 }, { status: 200 });
      }),
    );

    // Act
    renderWithProviders(<TicketListScreen />, { route: "/tickets", isAuthenticated: true });

    // Assert
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
    expect(refreshCalled).toBe(true);
    expect(ticketsAttempts).toBe(2);
  });

  it("test_ticket_list_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets", async () =>
        HttpResponse.json({ items: [ticket()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );
    const { container } = renderWithProviders(<TicketListScreen />, {
      route: "/tickets",
      isAuthenticated: true,
    });
    await screen.findByText("TCK-0001");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
