import { describe, it, expect, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useResendInvite } from "./useResendInvite";

describe("useResendInvite", () => {
  it("test_use_resend_invite_calls_the_resend_endpoint_and_never_surfaces_the_202_body", async () => {
    // Arrange
    let called = false;
    server.use(
      http.post("/api/v1/admin/users/user-a/resend-invite", async () => {
        called = true;
        return HttpResponse.json({ message: "Invite resent to target@example.com." }, { status: 202 });
      }),
    );
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const { result } = renderHookWithProviders(() => useResendInvite("user-a"));

    // Act
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert: the endpoint was called and the mutation resolved, but the
    // hook itself never writes the 202 body's message anywhere (the caller
    // — AdminUserDetailScreen.tsx — is separately asserted to show only a
    // generic confirmation, never this body).
    expect(called).toBe(true);
    expect(consoleLogSpy).not.toHaveBeenCalled();
    consoleLogSpy.mockRestore();
  });
});
