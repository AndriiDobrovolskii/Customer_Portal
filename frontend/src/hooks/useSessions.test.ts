// Unit test for the useSessions hook (Task T5, FE-AC6's list half).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useSessions } from "./useSessions";

describe("useSessions", () => {
  it("test_use_sessions_returns_session_list_on_success", async () => {
    // Arrange
    server.use(
      http.get("/api/v1/auth/sessions", async () =>
        HttpResponse.json(
          {
            sessions: [
              {
                family_id: "fam-1",
                device_label: "Chrome on Windows",
                location: "Kyiv, UA",
                last_used_at: "2026-09-06T10:00:00Z",
                is_current: true,
              },
              {
                family_id: "fam-2",
                device_label: "Safari on iPhone",
                location: null,
                last_used_at: "2026-09-05T08:00:00Z",
                is_current: false,
              },
            ],
          },
          { status: 200 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useSessions());

    // Act / Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.sessions).toHaveLength(2);
    expect(result.current.data?.sessions[0].is_current).toBe(true);
  });
});
