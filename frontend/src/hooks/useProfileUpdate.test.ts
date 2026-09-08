// Unit test for the useProfileUpdate hook (Task T4, Plan Change 3). Owns
// both PATCH /profile payload shapes (field edit, email change) and
// disambiguates 200/202/412 by status, per FR-2/FR-3 and OD-1's resolution
// (docs/tests/US-5.2-test-strategy.md's collaborator-shape assumption for
// this hook's exact signature). Four branches, matching the plan's own
// Testing Strategy: known-ETag echo, no-ETag `If-Match: *`, a 202 clearing
// the cached ETag, a 412 setting the conflict flag.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useProfileUpdate } from "./useProfileUpdate";

const profileReadFixture = {
  id: "u1",
  email: "user@example.com",
  pending_email: null,
  display_name: "New Name",
  locale: "en-US",
  timezone: "America/New_York",
  avatar_url: null,
  email_verified: true,
  created_at: "2026-01-01T00:00:00Z",
};

describe("useProfileUpdate", () => {
  it("test_use_profile_update_first_write_in_session_sends_if_match_asterisk_and_caches_returned_etag", async () => {
    // Arrange
    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } });
      }),
    );
    const { result, queryClient } = renderHookWithProviders(() => useProfileUpdate());

    // Act
    const response = await result.current.mutateAsync({ display_name: "New Name" });

    // Assert
    expect(receivedIfMatch).toBe("*");
    expect(response).toEqual(profileReadFixture);
    expect(queryClient.getQueryData(["profile", "etag"])).toBe("etag-1");
  });

  it("test_use_profile_update_subsequent_write_in_same_session_echoes_previously_cached_etag_as_if_match", async () => {
    // Arrange: first write establishes the cached ETag.
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } }),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useProfileUpdate());
    await result.current.mutateAsync({ display_name: "First edit" });
    expect(queryClient.getQueryData(["profile", "etag"])).toBe("etag-1");

    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/profile", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-2" } });
      }),
    );

    // Act
    await result.current.mutateAsync({ display_name: "Second edit" });

    // Assert
    expect(receivedIfMatch).toBe("etag-1");
    expect(queryClient.getQueryData(["profile", "etag"])).toBe("etag-2");
  });

  it("test_use_profile_update_202_email_change_pending_removes_cached_etag_and_resolves_with_pending_email", async () => {
    // Arrange: seed a cached ETag from a prior write in the session.
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } }),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useProfileUpdate());
    await result.current.mutateAsync({ display_name: "First edit" });
    expect(queryClient.getQueryData(["profile", "etag"])).toBe("etag-1");

    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json({ ...profileReadFixture, pending_email: "new@example.com" }, { status: 202 }),
      ),
    );

    // Act
    const response = await result.current.mutateAsync({
      email: "new@example.com",
      current_password: "correct-password", // pragma: allowlist secret
    });

    // Assert
    expect(response.pending_email).toBe("new@example.com");
    expect(queryClient.getQueryData(["profile", "etag"])).toBeUndefined();
  });

  it("test_use_profile_update_412_response_sets_conflict_flag_without_updating_cached_etag", async () => {
    // Arrange: seed a cached ETag, then simulate it having gone stale.
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(profileReadFixture, { status: 200, headers: { ETag: "etag-1" } }),
      ),
    );
    const { result, queryClient } = renderHookWithProviders(() => useProfileUpdate());
    await result.current.mutateAsync({ display_name: "First edit" });

    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/precondition-failed",
            title: "Precondition failed",
            status: 412,
            detail: "The profile has changed elsewhere.",
          },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act
    await expect(result.current.mutateAsync({ display_name: "Stale edit" })).rejects.toMatchObject({
      status: 412,
    });

    // Assert
    await waitFor(() => expect(result.current.conflict).toBe(true));
    expect(queryClient.getQueryData(["profile", "etag"])).toBe("etag-1");
  });

  it("test_use_profile_update_reset_conflict_clears_the_conflict_flag", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/profile", async () =>
        HttpResponse.json(
          { type: "https://errors.example/precondition-failed", title: "x", status: 412, detail: "x" },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const { result } = renderHookWithProviders(() => useProfileUpdate());
    await expect(result.current.mutateAsync({ display_name: "x" })).rejects.toMatchObject({ status: 412 });
    await waitFor(() => expect(result.current.conflict).toBe(true));

    // Act
    result.current.resetConflict();

    // Assert
    await waitFor(() => expect(result.current.conflict).toBe(false));
  });
});
