import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useAuditLogs } from "./useAuditLogs";

function entry(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    occurred_at: "2026-09-01T00:00:00Z",
    actor_id: "u-1",
    actor_role: "admin",
    event: "user_created",
    target_id: "u-2",
    outcome: "success",
    request_id: "req-1",
    ip: "127.0.0.1",
    user_agent: "vitest",
    ...overrides,
  };
}

describe("useAuditLogs", () => {
  beforeEach(() => {
    vi.setSystemTime(new Date("2026-09-13T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("test_use_audit_logs_default_window_is_the_last_7_days_in_iso_8601_utc_with_the_clock_frozen", async () => {
    // Arrange (Resolution OD-1, Implementation Plan Risk 5)
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAuditLogs());
    await waitFor(() => expect(result.current.query.isSuccess).toBe(true));

    // Assert
    expect(result.current.defaultTo).toBe("2026-09-13T12:00:00.000Z");
    expect(result.current.defaultFrom).toBe("2026-09-06T12:00:00.000Z");
  });

  it("test_use_audit_logs_computes_the_default_window_exactly_once_per_mount", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: null }, { status: 200 }),
      ),
    );
    const { result, rerender } = renderHookWithProviders(() => useAuditLogs());
    await waitFor(() => expect(result.current.query.isSuccess).toBe(true));
    const firstDefaultFrom = result.current.defaultFrom;
    const firstDefaultTo = result.current.defaultTo;

    // Act: advance the clock, then re-render the same hook instance.
    vi.setSystemTime(new Date("2026-09-14T00:00:00Z"));
    rerender();

    // Assert: unchanged — computed once per mount, not per render.
    expect(result.current.defaultFrom).toBe(firstDefaultFrom);
    expect(result.current.defaultTo).toBe(firstDefaultTo);
  });

  it("test_use_audit_logs_actor_id_event_target_id_from_and_to_are_sent_as_query_parameters_with_the_literal_from_key", async () => {
    // Arrange
    let receivedKeys: Record<string, string | null> = {};
    server.use(
      http.get("/api/v1/admin/audit-logs", async ({ request }) => {
        const url = new URL(request.url);
        receivedKeys = {
          actor_id: url.searchParams.get("actor_id"),
          event: url.searchParams.get("event"),
          target_id: url.searchParams.get("target_id"),
          from: url.searchParams.get("from"),
          to: url.searchParams.get("to"),
        };
        return HttpResponse.json({ items: [entry()], next_cursor: null }, { status: 200 });
      }),
    );

    // Act
    const { result } = renderHookWithProviders(() =>
      useAuditLogs({
        actor_id: "u-1",
        event: "user_created",
        target_id: "u-2",
        from: "2026-09-01T00:00:00.000Z",
        to: "2026-09-08T00:00:00.000Z",
      }),
    );
    await waitFor(() => expect(result.current.query.isSuccess).toBe(true));

    // Assert
    expect(receivedKeys).toEqual({
      actor_id: "u-1",
      event: "user_created",
      target_id: "u-2",
      from: "2026-09-01T00:00:00.000Z",
      to: "2026-09-08T00:00:00.000Z",
    });
  });

  it("test_use_audit_logs_has_next_page_false_when_next_cursor_is_null", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/admin/audit-logs", async () =>
        HttpResponse.json({ items: [entry()], next_cursor: null }, { status: 200 }),
      ),
    );

    // Act
    const { result } = renderHookWithProviders(() => useAuditLogs());
    await waitFor(() => expect(result.current.query.isSuccess).toBe(true));

    // Assert
    expect(result.current.query.hasNextPage).toBe(false);
  });
});
