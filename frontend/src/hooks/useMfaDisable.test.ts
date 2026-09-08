// Unit test for useMfaDisable (Task T4, FR-6). Calls DELETE /auth/mfa with
// a body (`{current_password, code}`, per OD-2's resolution) — this requires
// `httpClient.ts`'s `httpDelete` to accept a `body` option, an additive
// extension beyond Plan Architectural Change 1's literal "httpPatch only"
// wording, recorded as a collaborator-shape assumption in
// docs/tests/US-5.2-test-strategy.md. On success, `onSuccess` calls the new
// `authStore.setMfaEnabled(false)` action (Plan Change 6).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useMfaDisable } from "./useMfaDisable";
import { useAuthStore } from "../store/authStore";

describe("useMfaDisable", () => {
  it("test_use_mfa_disable_success_sends_current_password_and_code_and_sets_auth_store_mfa_enabled_false", async () => {
    // Arrange
    let receivedBody: unknown;
    server.use(
      http.delete("/api/v1/auth/mfa", async ({ request }) => {
        receivedBody = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { result } = renderHookWithProviders(() => ({ disable: useMfaDisable(), store: useAuthStore() }), {
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Act
    await result.current.disable.mutateAsync({
      current_password: "correct-password", // pragma: allowlist secret
      code: "123456",
    });

    // Assert
    expect(receivedBody).toEqual({
      current_password: "correct-password", // pragma: allowlist secret
      code: "123456",
    });
    await waitFor(() => expect(result.current.store.mfaEnabled).toBe(false));
  });

  it("test_use_mfa_disable_incorrect_password_or_code_surfaces_normalized_error_and_leaves_mfa_enabled_unchanged", async () => {
    // Arrange
    server.use(
      http.delete("/api/v1/auth/mfa", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-credentials",
            title: "Invalid credentials",
            status: 401,
            detail: "Your current password or code is incorrect.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({ disable: useMfaDisable(), store: useAuthStore() }), {
      isAuthenticated: true,
      mfaEnabled: true,
    });

    // Act / Assert
    await expect(
      result.current.disable.mutateAsync({
        current_password: "wrong", // pragma: allowlist secret
        code: "000000",
      }),
    ).rejects.toMatchObject({ status: 401 });
    expect(result.current.store.mfaEnabled).toBe(true);
  });
});
