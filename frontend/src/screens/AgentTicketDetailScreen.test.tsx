// Integration test for AgentTicketDetailScreen (FR-3 through FR-10,
// AG-AC3 through AG-AC9, Resolutions OD-1/OD-3/OD-5, a11y bar).
import { useEffect } from "react";
import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { Route, Routes, useNavigate } from "react-router-dom";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { AgentTicketDetailScreen } from "./AgentTicketDetailScreen";
import { offeredAgentActionsForStatus, describeAssignee } from "./agentTicketHelpers";

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

interface RenderOptions {
  navigationState?: { assigneeId: string | null } | null;
  scopes?: string[];
  userId?: string;
}

// A minimal "queue row" stand-in mounted at /entry: on mount it navigates to
// /agent/tickets/t-1 exactly the way AgentTicketQueueScreen.tsx's row click
// does (Architectural Change 7 — `navigate(path, { state: { assigneeId } })`),
// so the detail screen's `useLocation().state` read is exercised through a
// real React Router navigation rather than a hand-built location object.
// test-utils.tsx's `route` option carries no `state` of its own — this
// launcher is a test-local workaround, not a change to that shared file.
function NavigationHandoffLauncher({ assigneeId }: { assigneeId: string | null }) {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/agent/tickets/t-1", { replace: true, state: { assigneeId } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

function renderDetail({
  navigationState = { assigneeId: null },
  scopes = ["tickets:read", "tickets:write"],
  userId = "agent-me",
}: RenderOptions = {}) {
  const hasHandoff = navigationState !== null;

  return renderWithProviders(
    <Routes>
      {hasHandoff && (
        <Route
          path="/entry"
          element={<NavigationHandoffLauncher assigneeId={navigationState.assigneeId} />}
        />
      )}
      <Route path="/agent/tickets/:id" element={<AgentTicketDetailScreen />} />
    </Routes>,
    {
      route: hasHandoff ? "/entry" : "/agent/tickets/t-1",
      isAuthenticated: true,
      scopes,
      user: { id: userId, email: "agent@example.com" },
    },
  );
}

describe("offeredAgentActionsForStatus (FR-6, AG-AC6)", () => {
  it.each([
    ["open", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["waiting_on_support", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["waiting_on_customer", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["resolved", { reply: true, assign: true, resolve: false, close: true, reopen: true }],
    ["closed", { reply: false, assign: false, resolve: false, close: false, reopen: false }],
  ] as const)(
    "test_offered_agent_actions_for_status_%s_returns_the_exact_offered_set",
    (status, expected) => {
      expect(offeredAgentActionsForStatus(status)).toEqual(expected);
    },
  );

  it("test_offered_agent_actions_for_status_an_unrecognized_status_offers_no_actions_fail_closed", () => {
    expect(offeredAgentActionsForStatus("pending_vendor_escalation")).toEqual({
      reply: false,
      assign: false,
      resolve: false,
      close: false,
      reopen: false,
    });
  });
});

describe("describeAssignee (Resolution OD-1, Architectural Change 8)", () => {
  it("test_describe_assignee_undefined_renders_the_em_dash_placeholder_with_an_aria_label", () => {
    expect(describeAssignee(undefined)).toEqual({ text: "—", ariaLabel: "Assignee unknown" });
  });

  it("test_describe_assignee_null_renders_the_literal_unassigned_text_with_no_aria_label", () => {
    expect(describeAssignee(null)).toEqual({ text: "Unassigned" });
  });

  it("test_describe_assignee_a_uuid_truncates_to_its_first_8_hex_characters", () => {
    expect(describeAssignee("a1b2c3d4-e5f6-4789-a012-3456789abcde")).toEqual({ text: "a1b2c3d4" });
  });
});

describe("AgentTicketDetailScreen", () => {
  it("test_agent_ticket_detail_screen_renders_header_fields_and_reply_thread", async () => {
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
                  visibility: "public",
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
    renderDetail({ navigationState: { assigneeId: "agent-1234-5678" } });

    // Assert
    expect(await screen.findByText("TCK-0001")).toBeInTheDocument();
    expect(screen.getByText(/account/i)).toBeInTheDocument();
    expect(screen.getByText(/any update\?/i)).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_renders_a_direct_url_entrys_assignee_as_unknown_stale", async () => {
    // Arrange: Resolution OD-3 — no navigation state (direct-URL entry).
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
    );

    // Act: a null navigationState means no launcher route runs — the
    // detail screen is rendered directly at its own URL, matching a real
    // direct-URL visit with no location.state at all.
    renderDetail({ navigationState: null });

    // Assert
    await screen.findByText("TCK-0001");
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByLabelText("Assignee unknown")).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_renders_internal_replies_with_a_distinct_style_and_a_literal_internal_label", async () => {
    // Arrange: NFR — distinct styling AND a text label, never colour alone.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          detailBody({
            replies: {
              items: [
                {
                  id: "r-1",
                  author_kind: "agent",
                  visibility: "internal",
                  body: "Escalating to billing.",
                  created_at: "2026-09-01T11:00:00Z",
                },
                {
                  id: "r-2",
                  author_kind: "customer",
                  visibility: "public",
                  body: "Thanks for the update.",
                  created_at: "2026-09-01T12:00:00Z",
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
    await screen.findByText("TCK-0001");

    // Assert: scoped to the reply's own label element — "Internal" also
    // appears as the composer's visibility radio option text.
    const internalLabel = screen.getByText("Internal", { selector: "strong.reply-visibility-label" });
    expect(internalLabel).toBeInTheDocument();
    const internalItem = internalLabel.closest("li");
    expect(internalItem).toHaveClass("reply--internal");
    expect(internalItem).toHaveAttribute("data-visibility", "internal");
    const publicItem = screen.getByText("Thanks for the update.").closest("li");
    expect(publicItem).toHaveClass("reply--public");
    expect(publicItem?.textContent).not.toContain("Internal");
  });

  it("test_agent_ticket_detail_screen_load_older_replies_fetches_using_its_own_cursor", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        if (!cursor) {
          return HttpResponse.json(
            detailBody({
              replies: {
                items: [
                  {
                    id: "r-1",
                    author_kind: "customer",
                    visibility: "public",
                    body: "First",
                    created_at: "2026-09-01T11:00:00Z",
                  },
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
                {
                  id: "r-2",
                  author_kind: "agent",
                  visibility: "public",
                  body: "Older reply",
                  created_at: "2026-09-01T09:00:00Z",
                },
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
  });

  it("test_agent_ticket_detail_screen_composer_defaults_to_public_and_sends_the_chosen_visibility", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "agent", visibility: "public", body: "On it." },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Assert: default is public.
    expect(screen.getByRole("radio", { name: /^public$/i })).toBeChecked();

    // Act
    await user.type(screen.getByLabelText(/^reply$/i), "On it.");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    expect(receivedBody).toMatchObject({ body: "On it.", visibility: "public" });
  });

  it("test_agent_ticket_detail_screen_submitting_an_internal_note_sends_visibility_internal_and_renders_it_internally", async () => {
    // Arrange: FR-4 — choosing "internal" is a deliberate, visible action.
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "r-1",
            ticket_id: "t-1",
            author_kind: "agent",
            visibility: "internal",
            body: "Internal note.",
          },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    expect(screen.getByText("open")).toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("radio", { name: /^internal$/i }));
    await user.type(screen.getByLabelText(/^reply$/i), "Internal note.");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    expect(receivedBody).toMatchObject({ body: "Internal note.", visibility: "internal" });
    expect(await screen.findByText("Internal note.")).toBeInTheDocument();
    // AG-AC4's explicit contrast case: an internal note produces no status
    // change (unlike the public-reply case asserted separately below) — the
    // ticket header still reads "open", never a server-side transition like
    // the public-reply path's "waiting_on_customer".
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_visibility_never_leaks_public_again_after_an_internal_submission", async () => {
    // Arrange: Implementation Plan Risk 2 — the concrete regression this
    // test exists to catch.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async () =>
        HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "agent", visibility: "internal", body: "Note." },
          { status: 201 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act: submit an internal note.
    await user.click(screen.getByRole("radio", { name: /^internal$/i }));
    await user.type(screen.getByLabelText(/^reply$/i), "Note.");
    await user.click(screen.getByRole("button", { name: /post reply/i }));
    await screen.findByText("Note.");

    // Assert: the composer shows "public" again, never remembering the
    // prior "internal" choice.
    expect(screen.getByRole("radio", { name: /^public$/i })).toBeChecked();
    expect(screen.getByRole("radio", { name: /^internal$/i })).not.toBeChecked();
  });

  it("test_agent_ticket_detail_screen_public_reply_invalidates_the_ticket_detail", async () => {
    // Arrange
    let detailFetchCount = 0;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => {
        detailFetchCount += 1;
        return HttpResponse.json(detailBody(), { status: 200 });
      }),
      http.post("/api/v1/support/tickets/t-1/replies", async () =>
        HttpResponse.json(
          { id: "r-1", ticket_id: "t-1", author_kind: "agent", visibility: "public", body: "On it." },
          { status: 201 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    const before = detailFetchCount;

    // Act
    await user.type(screen.getByLabelText(/^reply$/i), "On it.");
    await user.click(screen.getByRole("button", { name: /post reply/i }));
    await screen.findByText("On it.");

    // Assert
    expect(detailFetchCount).toBeGreaterThan(before);
  });

  it("test_agent_ticket_detail_screen_assign_to_me_calls_assign_endpoint_and_updates_the_local_assignee_display", async () => {
    // Arrange
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/assign", async ({ request }) => {
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-me" },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail({ navigationState: null });
    await screen.findByText("TCK-0001");
    expect(screen.getByText("—")).toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));

    // Assert
    expect(receivedBody).toEqual({ assignee_id: "agent-me" });
    expect(await screen.findByText("agent-me")).toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_unassign_calls_delete_assign_and_updates_the_local_assignee_display_to_unassigned", async () => {
    // Arrange
    let unassignCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.delete("/api/v1/support/tickets/t-1/assign", async () => {
        unassignCalled = true;
        return HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail({ navigationState: { assigneeId: "agent-1234-5678" } });
    await screen.findByText("TCK-0001");
    expect(screen.getByText("agent-12")).toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /^unassign$/i }));

    // Assert
    expect(unassignCalled).toBe(true);
    expect(await screen.findByText("Unassigned")).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_a_detail_originated_assign_also_invalidates_the_queue", async () => {
    // Arrange: Architectural Change 8 — useAssignTicket.ts's queue
    // invalidation is origin-agnostic; asserted here from the detail
    // screen specifically, the same way useAssignTicket.test.ts asserts it
    // from a bare hook render.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/assign", async () =>
        HttpResponse.json(
          { id: "t-1", status: "open", updated_at: "2026-09-01T12:00:00Z", assignee_id: "agent-me" },
          { status: 200 },
        ),
      ),
    );
    const { queryClient } = renderDetail({ navigationState: null });
    await screen.findByText("TCK-0001");
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    // Act
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /^assign to me$/i }));
    await screen.findByText("agent-me");

    // Assert
    const invalidatedKeys = invalidateSpy.mock.calls.map((call) => call[0]?.queryKey);
    expect(invalidatedKeys).toContainEqual(["agent-tickets"]);
  });

  it.each(["open", "waiting_on_support", "waiting_on_customer"])(
    "test_agent_ticket_detail_screen_resolve_from_%s_calls_resolve_endpoint_and_reflects_resolved",
    async (status) => {
      // Arrange
      let receivedBody: Record<string, unknown> = {};
      server.use(
        http.get("/api/v1/support/tickets/t-1", async () =>
          HttpResponse.json(detailBody({ status }), { status: 200 }),
        ),
        http.post("/api/v1/support/tickets/t-1/resolve", async ({ request }) => {
          receivedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            { id: "t-1", status: "resolved", updated_at: "2026-09-01T12:00:00Z" },
            { status: 200 },
          );
        }),
      );
      const user = userEvent.setup();
      renderDetail();
      await screen.findByText("TCK-0001");

      // Act
      await user.type(screen.getByLabelText(/resolution note/i), "Fixed via password reset.");
      await user.click(screen.getByRole("button", { name: /^resolve$/i }));

      // Assert
      expect(receivedBody).toEqual({ resolution_note: "Fixed via password reset." });
      expect(await screen.findByText(/resolved/i)).toBeInTheDocument();
    },
  );

  it("test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_an_empty_note", async () => {
    // Arrange
    let resolveCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/resolve", async () => {
        resolveCalled = true;
        return HttpResponse.json({ id: "t-1", status: "resolved", updated_at: "x" }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.click(screen.getByRole("button", { name: /^resolve$/i }));

    // Assert
    expect(await screen.findByText(/resolution note is required/i)).toBeInTheDocument();
    expect(resolveCalled).toBe(false);
  });

  it("test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_a_whitespace_only_note", async () => {
    // Arrange
    let resolveCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/resolve", async () => {
        resolveCalled = true;
        return HttpResponse.json({ id: "t-1", status: "resolved", updated_at: "x" }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/resolution note/i), "   ");
    await user.click(screen.getByRole("button", { name: /^resolve$/i }));

    // Assert
    expect(await screen.findByText(/resolution note is required/i)).toBeInTheDocument();
    expect(resolveCalled).toBe(false);
  });

  it("test_agent_ticket_detail_screen_resolve_blocks_submission_client_side_on_a_note_over_5000_characters", async () => {
    // Arrange: AG-AC5's upper bound — maxLength: 5000 is already implemented
    // on the resolution_note registration, but was previously untested; only
    // the empty and whitespace-only lower-bound cases were covered above.
    // fireEvent.change (not userEvent.type) sets the 5001-character value in
    // one step — typing it character-by-character would be needlessly slow.
    let resolveCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/resolve", async () => {
        resolveCalled = true;
        return HttpResponse.json({ id: "t-1", status: "resolved", updated_at: "x" }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    const overLimitNote = "a".repeat(5001);

    // Act
    fireEvent.change(screen.getByLabelText(/resolution note/i), { target: { value: overLimitNote } });
    await user.click(screen.getByRole("button", { name: /^resolve$/i }));

    // Assert
    expect(await screen.findByText(/resolution note must be 5000 characters or fewer/i)).toBeInTheDocument();
    expect(resolveCalled).toBe(false);
  });

  it("test_agent_ticket_detail_screen_422_validation_failed_maps_the_errors_array_onto_the_matching_form_fields", async () => {
    // Arrange: AG-AC7/FR-8 — a 422's errors[] array must map onto its
    // matching form field via the project's shared getFieldErrors()/
    // FieldError mechanism (NewTicketScreen.tsx's established pattern), not
    // just render the top-level detail string generically. `detail` and the
    // field message are deliberately different strings so a passing
    // assertion proves the field-scoped renderer fired (and the generic
    // top-level paragraph was suppressed in its favor).
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            detail: "Validation failed.",
            errors: [{ field: "body", message: "Reply body contains a disallowed pattern." }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/^reply$/i), "Bad body.");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    const fieldError = await screen.findByText("Reply body contains a disallowed pattern.");
    expect(fieldError).toHaveAttribute("data-field", "body");
    expect(screen.queryByText("Validation failed.")).not.toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_resolve_409_on_closed_ticket_renders_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
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
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/resolution note/i), "Fixed.");
    await user.click(screen.getByRole("button", { name: /^resolve$/i }));

    // Assert
    expect(await screen.findByText("This ticket is closed and cannot be resolved.")).toBeInTheDocument();
  });

  it.each([
    ["open", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["waiting_on_support", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["waiting_on_customer", { reply: true, assign: true, resolve: true, close: true, reopen: false }],
    ["resolved", { reply: true, assign: true, resolve: false, close: true, reopen: true }],
    ["closed", { reply: false, assign: false, resolve: false, close: false, reopen: false }],
  ] as const)(
    "test_agent_ticket_detail_screen_status_%s_wires_offered_actions_to_what_is_actually_rendered",
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
      expect(screen.queryByLabelText(/^reply$/i) !== null).toBe(expected.reply);
      expect(screen.queryByRole("button", { name: /^assign to me$/i }) !== null).toBe(expected.assign);
      expect(screen.queryByRole("button", { name: /^resolve$/i }) !== null).toBe(expected.resolve);
      expect(screen.queryByRole("button", { name: /close ticket/i }) !== null).toBe(expected.close);
      expect(screen.queryByRole("button", { name: /^reopen$/i }) !== null).toBe(expected.reopen);
    },
  );

  it("test_agent_ticket_detail_screen_disables_every_write_control_when_tickets_write_is_absent", async () => {
    // Arrange: FR-6/AG-AC6 read-only view.
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
    );

    // Act
    renderDetail({ scopes: ["tickets:read"] });
    await screen.findByText("TCK-0001");

    // Assert
    expect(screen.getByRole("button", { name: /^assign to me$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /post reply/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^resolve$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /close ticket/i })).toBeDisabled();
  });

  it("test_agent_ticket_detail_screen_close_single_button_no_reason_field_no_confirmation", async () => {
    // Arrange: Resolution OD-5.
    let closeCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/close", async () => {
        closeCalled = true;
        return HttpResponse.json(
          { id: "t-1", status: "closed", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    expect(screen.queryByLabelText(/reason/i)).not.toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /close ticket/i }));

    // Assert
    expect(closeCalled).toBe(true);
    expect(await screen.findByText(/closed/i)).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_reopen_single_button_no_reason_field_no_confirmation", async () => {
    // Arrange
    let reopenCalled = false;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(detailBody({ status: "resolved" }), { status: 200 }),
      ),
      http.post("/api/v1/support/tickets/t-1/reopen", async () => {
        reopenCalled = true;
        return HttpResponse.json(
          { id: "t-1", status: "waiting_on_support", updated_at: "2026-09-01T12:00:00Z" },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");
    expect(screen.queryByLabelText(/reason/i)).not.toBeInTheDocument();

    // Act
    await user.click(screen.getByRole("button", { name: /^reopen$/i }));

    // Assert
    expect(reopenCalled).toBe(true);
    expect(await screen.findByText(/waiting_on_support|waiting on support/i)).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_4xx_problem_json_renders_mapped_detail_with_no_raw_json", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "You do not have permission to view this ticket.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByText("You do not have permission to view this ticket.")).toBeInTheDocument();
    expect(screen.queryByText(/"type":|"title":/)).not.toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_reply_429_shows_retry_time_disables_submit_and_fires_exactly_once", async () => {
    // Arrange
    let replyRequestCount = 0;
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () => HttpResponse.json(detailBody(), { status: 200 })),
      http.post("/api/v1/support/tickets/t-1/replies", async () => {
        replyRequestCount += 1;
        return HttpResponse.json(
          { type: "https://errors.example/rate-limited", title: "Rate limited", status: 429 },
          { status: 429, headers: { "Retry-After": "15", "content-type": "application/problem+json" } },
        );
      }),
    );
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("TCK-0001");

    // Act
    await user.type(screen.getByLabelText(/^reply$/i), "Trying again");
    await user.click(screen.getByRole("button", { name: /post reply/i }));

    // Assert
    expect(await screen.findByText(/try again in|retry in/i)).toBeInTheDocument();
    expect(await screen.findByText(/15/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /post reply/i })).toBeDisabled();
    expect(replyRequestCount).toBe(1);
  });

  it("test_agent_ticket_detail_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets/t-1", () => HttpResponse.error()));

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_5xx_response_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/support/tickets/t-1", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderDetail();

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes", async () => {
    // Arrange: no dangerouslySetInnerHTML anywhere in this Story.
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
                  visibility: "public",
                  body: '<img src="x" onerror="window.__pwned2 = true">',
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
    expect((window as unknown as { __pwned2?: boolean }).__pwned2).toBeUndefined();
    expect(screen.getByText(/<img/i)).toBeInTheDocument();
  });

  it("test_agent_ticket_detail_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/support/tickets/t-1", async () =>
        HttpResponse.json(
          detailBody({
            replies: {
              items: [
                {
                  id: "r-1",
                  author_kind: "agent",
                  visibility: "internal",
                  body: "Internal note.",
                  created_at: "2026-09-01T11:00:00Z",
                },
              ],
              next_cursor: "replies-cursor-2",
            },
          }),
          { status: 200 },
        ),
      ),
    );
    const { container } = renderDetail({ navigationState: { assigneeId: "agent-1234" } });
    await screen.findByText("TCK-0001");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
