// Unit test for the useRequestPasswordReset hook (Task T5, FE-AC7's request half).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useRequestPasswordReset } from "./useRequestPasswordReset";

describe("useRequestPasswordReset", () => {
  it("test_use_request_password_reset_returns_generic_message_regardless_of_account_existence", async () => {
    // Arrange: the backend's own anti-enumeration behavior — same 202 shape either way.
    server.use(
      http.post("/api/v1/auth/password-reset/request", async () =>
        HttpResponse.json(
          { message: "If an account exists for that email, a reset link has been sent." },
          { status: 202 },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useRequestPasswordReset());

    // Act
    const response = await result.current.mutateAsync({ email: "anyone@example.com" });

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(response.message).toMatch(/if an account exists/i);
  });
});
