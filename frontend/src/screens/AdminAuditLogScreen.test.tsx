// AD-AC8/FR-8 (Resolutions OD-1/OD-2), XC-AC1 (this screen's 403 slice),
// XC-AC4 (this screen's slice), console hygiene NFR, loading state, a11y bar.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders, waitFor } from "../test/test-utils";
import { AdminAuditLogScreen } from "./AdminAuditLogScreen";

function entry(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    occurred_at: "2026-09-10T08:00:00Z",
    actor_id: "u-1",
    actor_role: "admin",
    event: "user_created",
    target_id: "u-2",
    outcome: "success",
    request_id: "req-abc",
    ip: "203.0.113.10",
    user_agent: "Mozilla/5.0",
    ...overrides,
  };
}

describe("AdminAuditLogScreen", () => {
  beforeEach(() => {
    vi.setSystemTime(new Date("2026-09-13T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("test_admin_audit_log_screen_renders_all_nine_columns_per_entry", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    const row = (await screen.findByText("2026-09-10T08:00:00Z")).closest("tr") as HTMLElement;
    expect(within(row).getByText("u-1")).toBeInTheDocument();
    expect(within(row).getByText("admin")).toBeInTheDocument();
    expect(within(row).getByText("user_created")).toBeInTheDocument();
    expect(within(row).getByText("u-2")).toBeInTheDocument();
    expect(within(row).getByText("success")).toBeInTheDocument();
    expect(within(row).getByText("req-abc")).toBeInTheDocument();
    expect(within(row).getByText("203.0.113.10")).toBeInTheDocument();
    expect(within(row).getByText("Mozilla/5.0")).toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_renders_an_explicit_placeholder_for_each_nullable_column", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json(
          {
            items: [
              entry({
                actor_id: null,
                actor_role: null,
                target_id: null,
                outcome: null,
                request_id: null,
                ip: null,
                user_agent: null,
              }),
            ],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    const row = (await screen.findByText("user_created")).closest("tr") as HTMLElement;
    const placeholderCells = within(row).getAllByText("—");
    expect(placeholderCells.length).toBe(7);
  });

  it("test_admin_audit_log_screen_from_and_to_inputs_are_visibly_prefilled_with_the_last_7_days_default_on_first_render_clock_frozen", async () => {
    // Arrange (Resolution OD-1, Implementation Plan Risk 5)
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    await screen.findByLabelText(/^from$/i);
    expect(screen.getByLabelText(/^from$/i)).toHaveValue("2026-09-06T12:00:00.000Z");
    expect(screen.getByLabelText(/^to$/i)).toHaveValue("2026-09-13T12:00:00.000Z");
  });

  it("test_admin_audit_log_screen_event_filter_is_a_free_text_input_with_an_illustrative_placeholder_never_a_select", async () => {
    // Arrange (Resolution OD-2)
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    const eventInput = screen.getByLabelText(/^event$/i);
    expect(eventInput.tagName).toBe("INPUT");
    expect(eventInput).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/e\.g\.|user_created|authz_denied/i),
    );
    expect(screen.queryByRole("combobox", { name: /event/i })).not.toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_actor_id_event_target_id_from_and_to_are_sent_as_query_parameters_with_the_literal_from_key", async () => {
    // Arrange
    let received: Record<string, string | null> = {};
    server.use(
      http.get("/api/v1/admin/audit-logs", async ({ request }) => {
        const url = new URL(request.url);
        received = {
          actor_id: url.searchParams.get("actor_id"),
          event: url.searchParams.get("event"),
          target_id: url.searchParams.get("target_id"),
          from: url.searchParams.get("from"),
          to: url.searchParams.get("to"),
        };
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });
    await screen.findByLabelText(/^from$/i);

    // Act
    await user.type(screen.getByLabelText(/actor id/i), "u-1");
    await user.type(screen.getByLabelText(/^event$/i), "user_created");
    await user.type(screen.getByLabelText(/target id/i), "u-2");

    // Assert
    await waitFor(() => expect(received.target_id).toBe("u-2"));
    expect(received.from).toBe("2026-09-06T12:00:00.000Z");
    expect(received.to).toBe("2026-09-13T12:00:00.000Z");
    expect(received.actor_id).toBe("u-1");
    expect(received.event).toBe("user_created");
  });

  it("test_admin_audit_log_screen_load_more_appends_using_a_stable_synthetic_row_key_across_pages", async () => {
    // Arrange (Implementation Plan Risk 7)
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    server.use(
      http.get("/api/v1/admin/audit-logs", async ({ request }) => {
        const cursor = new URL(request.url).searchParams.get("cursor");
        if (!cursor) {
          return HttpResponse.json(
            { items: [entry({ request_id: "req-1" })], next_cursor: "cursor-2" },
            { status: 200 },
          );
        }
        return HttpResponse.json(
          { items: [entry({ request_id: "req-2", event: "role_replaced" })], next_cursor: null },
          { status: 200 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });
    await screen.findByText("req-1");

    // Act
    await user.click(screen.getByRole("button", { name: /load more/i }));

    // Assert
    expect(await screen.findByText("req-2")).toBeInTheDocument();
    expect(screen.getByText("req-1")).toBeInTheDocument();
    const duplicateKeyWarning = consoleErrorSpy.mock.calls.some((call) =>
      call.some((arg) => typeof arg === "string" && /same key|duplicate key/i.test(arg)),
    );
    expect(duplicateKeyWarning).toBe(false);
    consoleErrorSpy.mockRestore();
  });

  it("test_admin_audit_log_screen_never_renders_a_total_count_or_page_number", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });
    await screen.findByText("user_created");

    // Assert
    expect(screen.queryByText(/total/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/page \d+/i)).not.toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_forced_403_renders_not_permitted_never_blank_or_spinner", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/forbidden",
            title: "Forbidden",
            status: 403,
            detail: "You do not have permission to view this page.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: [],
    });

    // Assert
    expect(await screen.findByRole("alert")).toHaveTextContent(/permission/i);
  });

  it("test_admin_audit_log_screen_network_error_shows_a_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/admin/audit-logs", () => HttpResponse.error()));

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_5xx_response_shows_a_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.get("/api/v1/admin/audit-logs", async () => new HttpResponse(null, { status: 500 })));

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_renders_a_distinct_loading_state_before_the_query_resolves", () => {
    // Arrange / Act: no override — the default baseline handler resolves
    // asynchronously, so the pending state is observable first.
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });

    // Assert
    expect(screen.getByText(/loading audit log/i)).toBeInTheDocument();
  });

  it("test_admin_audit_log_screen_console_spy_records_no_call_containing_ip_user_agent_or_request_id", async () => {
    // Arrange (spec NFR)
    const logSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json(
          {
            items: [entry({ ip: "198.51.100.7", user_agent: "TestAgent/1.0", request_id: "req-secret" })],
            next_cursor: null,
          },
          { status: 200 },
        ),
      ),
    );

    // Act
    renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });
    await screen.findByText("198.51.100.7");

    // Assert
    const sensitivePattern = /198\.51\.100\.7|TestAgent\/1\.0|req-secret/;
    for (const spy of [logSpy, warnSpy, errorSpy]) {
      const offending = spy.mock.calls.some((call) =>
        call.some((arg) => typeof arg === "string" && sensitivePattern.test(arg)),
      );
      expect(offending).toBe(false);
    }
    logSpy.mockRestore();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  it("test_admin_audit_log_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: "cursor-2" }, { status: 200 }),
      ),
    );
    const { container } = renderWithProviders(<AdminAuditLogScreen />, {
      route: "/admin/audit-logs",
      isAuthenticated: true,
      scopes: ["audit:read"],
    });
    await screen.findByText("user_created");

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
