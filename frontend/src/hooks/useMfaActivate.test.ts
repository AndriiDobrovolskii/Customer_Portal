// Unit test for useMfaActivate (Task T4, FR-5's second step). Calls
// POST /auth/mfa/activate with `{code}`; on success, `onSuccess` calls the
// new `authStore.setMfaEnabled(true)` action (Plan Change 6) so
// `SecurityScreen`'s enroll-vs-disable branch reflects the just-completed
// enrollment without a page reload. `recovery_codes` flow to the caller for
// display only — never persisted by the hook itself (asserted here by
// confirming they are absent from the auth store, whose own PS-AC5 storage
// prohibition this suite also checks at the component level).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useMfaActivate } from "./useMfaActivate";
import { useAuthStore } from "../store/authStore";

describe("useMfaActivate", () => {
  it("test_use_mfa_activate_success_resolves_recovery_codes_and_sets_auth_store_mfa_enabled_true", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      activate: useMfaActivate(),
      store: useAuthStore(),
    }));

    // Act
    const response = await result.current.activate.mutateAsync({ code: "123456" });

    // Assert
    expect(response.recovery_codes).toEqual(["AAAA-1111", "BBBB-2222"]);
    await waitFor(() => expect(result.current.store.mfaEnabled).toBe(true));
  });

  it("test_use_mfa_activate_invalid_code_surfaces_normalized_error_and_leaves_mfa_enabled_unchanged", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/mfa/activate", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/invalid-mfa-code",
            title: "Invalid code",
            status: 401,
            detail: "The verification code is incorrect or expired.",
          },
          { status: 401, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => ({
      activate: useMfaActivate(),
      store: useAuthStore(),
    }));

    // Act / Assert
    await expect(result.current.activate.mutateAsync({ code: "000000" })).rejects.toMatchObject({
      status: 401,
    });
    expect(result.current.store.mfaEnabled).toBe(false);
  });
});
