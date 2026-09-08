// Unit test for httpClient.ts's new httpPatch<T> export (Task T1, Plan
// Architectural Change 1). FR-2 needs a verb that resolves `{data, status,
// headers}` (not bare `T`) so a 200 (edit succeeded) can be told apart from
// a 202 (email-change pending) apart from a 412 (conflict), and needs the
// `ETag` response header exposed. `performRequest`'s existing 401->refresh
// and error-normalization internals are reused unchanged by `httpPatch` per
// Plan Risk 6 — not re-proven here; `httpGet`/`httpPost`/`httpDelete`'s
// existing behavior is already covered indirectly by every other hook test
// in this suite and is unmodified by this Story (diff-read is the actual
// proof per Task T1's verification command).
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { httpPatch } from "./httpClient";

describe("httpPatch", () => {
  it("test_http_patch_resolves_with_data_status_and_headers_on_200", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/test-resource", async () =>
        HttpResponse.json({ id: "1", name: "updated" }, { status: 200, headers: { ETag: "etag-abc" } }),
      ),
    );

    // Act
    const result = await httpPatch<{ id: string; name: string }>("/test-resource", { name: "updated" });

    // Assert
    expect(result.status).toBe(200);
    expect(result.data).toEqual({ id: "1", name: "updated" });
    expect(result.headers.get("etag")).toBe("etag-abc");
  });

  it("test_http_patch_threads_if_match_header_when_option_supplied", async () => {
    // Arrange
    let receivedIfMatch: string | null = null;
    server.use(
      http.patch("/api/v1/test-resource", async ({ request }) => {
        receivedIfMatch = request.headers.get("if-match");
        return HttpResponse.json({ id: "1" }, { status: 200 });
      }),
    );

    // Act
    await httpPatch("/test-resource", { name: "x" }, { ifMatch: "cached-etag-1" });

    // Assert
    expect(receivedIfMatch).toBe("cached-etag-1");
  });

  it("test_http_patch_omits_if_match_header_when_option_not_supplied", async () => {
    // Arrange: httpPatch is a transport-only layer (Change 1) — the "always
    // send If-Match, using `*` when no ETag is known" policy is
    // profileApi/useProfileUpdate's, not httpClient's.
    let sawIfMatch = false;
    server.use(
      http.patch("/api/v1/test-resource", async ({ request }) => {
        sawIfMatch = request.headers.get("if-match") !== null;
        return HttpResponse.json({ id: "1" }, { status: 200 });
      }),
    );

    // Act
    await httpPatch("/test-resource", { name: "x" });

    // Assert
    expect(sawIfMatch).toBe(false);
  });

  it("test_http_patch_resolves_with_202_status_and_no_etag_header_for_email_change_pending", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/test-resource", async () =>
        HttpResponse.json({ id: "1", pending_email: "new@example.com" }, { status: 202 }),
      ),
    );

    // Act
    const result = await httpPatch<{ id: string; pending_email: string }>("/test-resource", {
      email: "new@example.com",
    });

    // Assert
    expect(result.status).toBe(202);
    expect(result.data.pending_email).toBe("new@example.com");
    expect(result.headers.get("etag")).toBeNull();
  });

  it("test_http_patch_412_response_rejects_with_api_error_status_412", async () => {
    // Arrange
    server.use(
      http.patch("/api/v1/test-resource", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/precondition-failed",
            title: "Precondition failed",
            status: 412,
            detail: "The resource has changed since you last loaded it.",
          },
          { status: 412, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act / Assert
    await expect(httpPatch("/test-resource", { name: "x" }, { ifMatch: "stale-etag" })).rejects.toMatchObject(
      { status: 412 },
    );
  });
});
