// Unit test for the useRevokeSession hook (Task T5, FE-AC6's revoke half).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useRevokeSession } from "./useRevokeSession";

describe("useRevokeSession", () => {
  it("test_use_revoke_session_calls_delete_endpoint_for_the_given_family_id", async () => {
    // Arrange
    let capturedFamilyId: string | undefined;
    server.use(
      http.delete("/api/v1/auth/sessions/:familyId", async ({ params }) => {
        capturedFamilyId = params.familyId as string;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { result } = renderHookWithProviders(() => useRevokeSession());

    // Act
    await result.current.mutateAsync("fam-2");

    // Assert
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(capturedFamilyId).toBe("fam-2");
  });

  it("test_use_revoke_session_current_session_surfaces_normalized_409_current_session_error", async () => {
    // Arrange: backend CurrentSessionError (OD-6's non-preventing default in force).
    server.use(
      http.delete("/api/v1/auth/sessions/:familyId", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/current-session",
            title: "Cannot revoke current session",
            status: 409,
            detail: "Ending your only active session through this endpoint has no described use case.",
          },
          { status: 409, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useRevokeSession());

    // Act / Assert
    await expect(result.current.mutateAsync("fam-1")).rejects.toMatchObject({ status: 409 });
  });
});
