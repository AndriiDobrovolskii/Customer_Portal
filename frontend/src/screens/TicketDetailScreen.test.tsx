// Integration test for TicketDetailScreen (TK-AC5 through TK-AC9, TK-AC11,
// TK-AC12, TK-AC13, OD-3, OD-4, a11y bar), plus a unit-level describe block
// for the pure `offeredActionsForStatus` function this screen owns (FR-9).
//
// implementation_plan v2 Risk 2: test-utils.tsx has no precedent for a screen
// reading a URL param. This file wraps `ui` in its own local
// <Routes><Route path="/tickets/:id" element={ui} /></Routes> rather than
// changing test-utils.tsx's signature.
//
// Field-label collaborator-shape assumptions (docs/tests/US-5.3-test-strategy.md
// item 7): "Load older replies", a reply composer with a "Reply" field and a
// "Post reply" submit, "Close ticket" / "Reopen" action buttons, "First
// response" as OD-4's label for first_response_at.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { Route, Routes } from "react-router-dom";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { TicketDetailScreen, offeredActionsForStatus } from "./TicketDetailScreen";

function renderDetail(id = "t-1") {
  return renderWithProviders(
    <Routes>
      <Route path="/tickets/:id" element={<TicketDetailScreen />} />
    </Routes>,
    { route: `/tickets/${id}`, isAuthenticated: true },
  );
}

function detailBody(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "t-1",
    ticket_number: "TCK-0001",
    status: "open",
    requester_id: "u-1",
    subject: "Cannot log in",
    body: "I cannot log in to my account.",
    category: "account",
    first_response_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
    replies: { items: [], next_cursor: null },
    ...overrides,
  };
}

describe("offeredActionsForStatus (FR-9, TK-AC9)", () => {
  it.each([
    ["open", { reply: true, close: true, reopen: false }],
    ["waiting_on_support", { reply: true, close: true, reopen: false }],
    ["waiting_on_customer", { reply: true, close: true, reopen: false }],
    ["resolved", { reply: true, close: true, reopen: true }],
    ["closed", { reply: false, close: false, reopen: false }],
  ] as const)("test_offered_actions_for_status_%s_returns_the_exact_offered_set", (status, expected) => {
    expect(offeredActionsForStatus(status)).toEqual(expected);
  });

  it("test_offered_actions_for_status_an_unrecognized_status_offers_no_actions_fail_closed", () => {
    expect(offeredActionsForStatus("pending_vendor_escalation")).toEqual({
      reply: false,
      close: false,
      reopen: false,
    });
  });

  it("test_offered_actions_for_status_never_has_a_resolve_key_for_any_input", () => {
    for (const status of ["open", "waiting_on_support", "waiting_on_customer", "resolved", "closed", "x"]) {
      expect(offeredActionsForStatus(status)).not.toHaveProperty("resolve");
    }
  });

  it("test_offered_actions_for_status_resolved_always_includes_reopen_true_regardless_of_any_date_input", () => {
    // OD-3: no client-side eligibility computation exists — the offered set
    // for "resolved" never varies with a date.
    expect(offeredActionsForStatus("resolved").reopen).toBe(true);
  });
});

describe("TicketDetailScreen", () => {
  it("test_ticket_detail_screen_renders_header_fields_and_reply_thread", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          detailBody({
            replies: {
              items: [
                {
                  id: "r-1",
                  author_kind: "customer",
                  body: "Any update?",
                  created_at: "2026-09-01T11:00:00Z",
                },
              ],
              next_cursor: null,
            },
          }),
          { status: 200 },
        ),
      ),
    );

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
    expect(screen.getByText(/open/i)).toBeInTheDocument();
    expect(screen.getByText(/account/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-09-01/)).toBeInTheDocument();
    expect(screen.getByText(/any update\?/i)).toBeInTheDocument();
    expect(screen.getByText(/customer/i)).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_renders_first_response_at_with_a_plain_label_and_no_sla_styling_when_present", async () => {
    // Arrange: OD-4's binding resolution — plain text, no SLA-breach
    // context/styling.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ first_response_at: "2026-09-01T12:00:00Z" }), { status: 200 }),
      ),
    );

    // Act
    renderDetail();

    // Assert
    const label = await screen.findByText(/first response/i);
    expect(label).toBeInTheDocument();
    expect(screen.getByText(/2026-09-01t12:00:00z|2026-09-01/i)).toBeInTheDocument();
    expect(screen.queryByText(/sla|breach|overdue|deadline/i)).not.toBeInTheDocument();
  });

  it("test_ticket_detail_screen_omits_first_response_label_when_absent", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ first_response_at: null }), { status: 200 }),
      ),
    );

    // Act
    renderDetail();
    await screen.findByText("TCK-0001");

    // Assert
    expect(screen.queryByText(/first response/i)).not.toBeInTheDocument();
  });

  it("test_ticket_detail_screen_load_older_replies_fetches_using_its_own_cursor_independent_of_the_list", async () => {
    // Arrange
    const receivedCursors: (string | null)[] = [];
    server.use(
      http.get("/api/v1/support/tickets/t-1", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        receivedCursors.push(cursor);
        if (!cursor) {
          return HttpResponse.json(
            detailBody({
              replies: {
                items: [
                  { id: "r-1", author_kind: "customer", body: "First", created_at: "2026-09-01T11:00:00Z" },
                ],
                next_cursor: "replies-cursor-2",
              },
            }),
            { status: 200 },
          );
        }
        return HttpResponse.json(
          detailBody({
            replies: {
              items: [
                { id: "r-2", author_kind: "agent", body: "Older reply", created_at: "2026-09-01T09:00:00Z" },
              ],
              next_cursor: null,
            },
          }),
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText(/first/i);

    // Act
    await user.click(screen.getByRole("button", { name: /load older replies/i }));

    // Assert
    expect(await screen.findByText(/older reply/i)).toBeInTheDocument();
    expect(receivedCursors).toContain("replies-cursor-2");
  });

  it("test_ticket_detail_screen_reply_submission_sends_no_visibility_and_attachment_ids_empty_appends_and_clears", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    let detailFetchCount = 0;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => {
        detailFetchCount += 1;
        return HttpResponse.json(detailBody(), { status: 200 });
      }),
      http.post("/api/v1/support/tickets/t-1/replies", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "customer", visibility: "public", body: "Thanks!" },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    const fetchesBeforeReply = detailFetchCount;

    // Act
    await user.type(screen.getByLabelText(/reply/i), "Thanks!");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    expect(await screen.findByText("Thanks!")).toBeInTheDocument();
    expect(receivedBody).not.toHaveProperty("visibility");
    expect(receivedBody).toMatchObject({ body: "Thanks!", attachment_ids: [] });
    expect(screen.getByLabelText(/reply/i)).toHaveValue("");
    expect(detailFetchCount).toBeGreaterThan(fetchesBeforeReply);
  });

  it.each(["open", "waiting_on_support", "waiting_on_customer", "resolved"])(
    "test_ticket_detail_screen_close_ticket_from_%s_calls_close_endpoint_and_reflects_closed",
    async (status) => {
      // Arrange
      let closeCalled = false;
      server.use(
        http.get("/api/v1/support/tickets/t-1", async () =>
          HttpResponse.json(detailBody({ status }), { status: 200 }),
        ),
        http.post("/api/v1/support/tickets/t-1/close", async () => {
          closeCalled = true;
          return HttpResponse.json(
            { id: "t-1", ticket_number: "TCK-0001", status: "closed", updated_at: "2026-09-01T12:00:00Z" },
            { status: 200 },
          );
        }),
      );
      const user = userEvent.setup();
      renderDetail();
      await screen.findByText("TCK-0001");

      // Act
      await user.click(screen.getByRole("button", { name: /close ticket/i }));

      // Assert
      expect(closeCalled).toBe(true);
      expect(await screen.findByText(/closed/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/reply/i)).not.toBeInTheDocument();
    },
  );

  it("test_ticket_detail_screen_reopen_from_resolved_is_clickable_calls_endpoint_and_reflects_waiting_on_support", async () => {
    // Arrange: OD-3 — never proactively disabled.
    let reopenCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ status: "resolved" }), { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/reopen", async () => {
        reopenCalled = true;
        return HttpResponse.json(
          {
            id: "t-1",
            ticket_number: "TCK-0001",
            status: "waiting_on_support",
            updated_at: "2026-09-01T12:00:00Z",
          },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    const reopenButton = screen.getByRole("button", { name: /reopen/i });
    expect(reopenButton).toBeEnabled();

    // Act
    await user.click(reopenButton);

    // Assert
    expect(reopenCalled).toBe(true);
    expect(await screen.findByText(/waiting_on_support|waiting on support/i)).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_reopen_409_outside_window_renders_detail_and_button_stays_clickable", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ status: "resolved" }), { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/reopen", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/reopen-window-expired",
            title: "Reopen window expired",
            status: 409,
            detail: "This ticket can no longer be reopened.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /reopen/i }));

    // Assert
    expect(await screen.findByText("This ticket can no longer be reopened.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reopen/i })).toBeEnabled();
  });

  it.each([
    ["open", { reply: true, close: true, reopen: false }],
    ["waiting_on_support", { reply: true, close: true, reopen: false }],
    ["waiting_on_customer", { reply: true, close: true, reopen: false }],
    ["resolved", { reply: true, close: true, reopen: true }],
    ["closed", { reply: false, close: false, reopen: false }],
  ] as const)(
    "test_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered",
    async (status, expected) => {
      // Arrange
      server.use(
        http.get("/api/v1/support/tickets/t-1", async () =>
          HttpResponse.json(detailBody({ status }), { status: 200 }),
        ),
      );

      // Act
      renderDetail();
      await screen.findByText("TCK-0001");

      // Assert
      expect(screen.queryByLabelText(/reply/i) !== null).toBe(expected.reply);
      expect(screen.queryByRole("button", { name: /close ticket/i }) !== null).toBe(expected.close);
      expect(screen.queryByRole("button", { name: /^reopen$/i }) !== null).toBe(expected.reopen);
      expect(screen.queryByRole("button", { name: /^resolve$/i })).not.toBeInTheDocument();
    },
  );

  it("test_ticket_detail_screen_404_renders_a_dedicated_not_found_state", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/not-found",
            title: "Not found",
            status: 404,
            detail: "No such ticket.",
          },
          { status: 404, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByText(/not found|could not be found/i)).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "You cannot view this ticket.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByText("You cannot view this ticket.")).toBeInTheDocument();
    expect(screen.queryByText(/"type":|"title":/)).not.toBeInTheDocument();
  });

  it("test_ticket_detail_screen_reply_429_shows_retry_time_disables_submit_and_fires_exactly_once", async () => {
    // Arrange
    let replyRequestCount = 0;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async () => {
        replyRequestCount += 1;
        return HttpResponse.json(
          { type: "https://errors.example/rate-limited", title: "Rate limited", status: 429 },
          { status: 429, headers: { "Retry-After": "20", "content-type": "application/problem+json" } },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/reply/i), "Trying again");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    expect(await screen.findByText(/try again in|retry in/i)).toBeInTheDocument();
    expect(await screen.findByText(/20/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /post reply/i })).toBeDisabled();
    expect(replyRequestCount).toBe(1);
  });

  it("test_ticket_detail_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets/t-1", () => HttpResponse.error()));

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets/t-1", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes", async () => {
    // Arrange: no dangerouslySetInnerHTML anywhere in this Story — asserted
    // via the DOM (no injected <img> element), not a string-contains check.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          {
            ...detailBody(),
            replies: {
              items: [
                {
                  id: "r-1",
                  author_kind: "customer",
                  body: '<img src="x" onerror="window.__pwned = true">',
                  created_at: "2026-09-01T11:00:00Z",
                },
              ],
              next_cursor: null,
            },
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderDetail();

    // Assert
    await screen.findByText("TCK-0001");
    expect(document.querySelector("img")).not.toBeInTheDocument();
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
    expect(screen.getByText(/<img/i)).toBeInTheDocument();
  });

  it("test_ticket_detail_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          detailBody({
            replies: {
              items: [
                { id: "r-1", author_kind: "customer", body: "Hello", created_at: "2026-09-01T11:00:00Z" },
              ],
              next_cursor: "replies-cursor-2",
            },
          }),
          { status: 200 },
        ),
      ),
    );
    const { container } = renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
