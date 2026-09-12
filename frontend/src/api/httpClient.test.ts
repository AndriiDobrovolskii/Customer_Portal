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
import { httpPatch, httpPost, httpGet } from "./httpClient";

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

// US-5.3 implementation_plan v2 Architectural Change 1 (OD-1 unaffected —
// this is the additive-only `idempotencyKey` option on `httpPost`, mirroring
// `httpPatch`'s existing `ifMatch` precedent). FR-3/FR-4.
describe("httpPost idempotencyKey option", () => {
  it("test_http_post_threads_idempotency_key_header_when_option_supplied", async () => {
    // Arrange
    let receivedHeader: string | null = null;
    server.use(
      http.post("/api/v1/test-resource", async ({ request }) => {
        receivedHeader = request.headers.get("idempotency-key");
        return HttpResponse.json({ id: "1" }, { status: 201 });
      }),
    );

    // Act
    await httpPost("/test-resource", { name: "x" }, { idempotencyKey: "key-123" });

    // Assert
    expect(receivedHeader).toBe("key-123");
  });

  it("test_http_post_omits_idempotency_key_header_when_option_not_supplied", async () => {
    // Arrange: every existing httpPost call site (authApi.ts, mfaApi.ts,
    // accountApi.ts) omits this option and must keep behaving exactly as
    // before — purely additive.
    let sawHeader = false;
    server.use(
      http.post("/api/v1/test-resource", async ({ request }) => {
        sawHeader = request.headers.get("idempotency-key") !== null;
        return HttpResponse.json({ id: "1" }, { status: 201 });
      }),
    );

    // Act
    await httpPost("/test-resource", { name: "x" });

    // Assert
    expect(sawHeader).toBe(false);
  });
});

// US-5.3 implementation_plan v2 Architectural Change 2 (OD-1's binding
// resolution): `ApiError.retryAfterSeconds` is a permanent, first-class field
// set by `parseResponse` on ANY `429` it parses — not a mechanism scoped to
// this story's two rate-limited endpoints. Proven here via `httpPost` (one of
// several verbs `performRequest`/`parseResponse` back) rather than a
// support-domain-specific helper, per the plan's explicit "any future 429
// reached through performRequest/parseResponse... automatically carries this
// field" requirement.
describe("ApiError.retryAfterSeconds (429 Retry-After threading, OD-1)", () => {
  it("test_parse_response_429_with_retry_after_header_populates_api_error_retry_after_seconds", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/test-resource", async () =>
        HttpResponse.json(
          { type: "https://errors.example/rate-limited", title: "Rate limited", status: 429 },
          { status: 429, headers: { "Retry-After": "30", "content-type": "application/problem+json" } },
        ),
      ),
    );

    // Act / Assert
    await expect(httpPost("/test-resource", { name: "x" })).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: 30,
    });
  });

  it("test_parse_response_429_without_a_retry_after_header_leaves_retry_after_seconds_undefined", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/test-resource", async () => HttpResponse.json({ status: 429 }, { status: 429 })),
    );

    // Act / Assert
    await expect(httpPost("/test-resource", { name: "x" })).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: undefined,
    });
  });

  it("test_parse_response_non_429_4xx_never_populates_retry_after_seconds_even_when_header_present", async () => {
    // Arrange: a `Retry-After` header on an unrelated 503/4xx must not be
    // misread as this story's rate-limit signal — the plan gates this
    // strictly to status === 429.
    server.use(
      http.post("/api/v1/test-resource", async () =>
        HttpResponse.json(
          { type: "https://errors.example/service-unavailable", title: "Unavailable", status: 503 },
          { status: 503, headers: { "Retry-After": "30" } },
        ),
      ),
    );

    // Act / Assert
    await expect(httpPost("/test-resource", { name: "x" })).rejects.toMatchObject({
      status: 503,
      retryAfterSeconds: undefined,
    });
  });

  it("test_parse_response_429_with_a_non_numeric_retry_after_header_leaves_retry_after_seconds_undefined", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/test-resource", async () =>
        HttpResponse.json(
          { status: 429 },
          { status: 429, headers: { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" } },
        ),
      ),
    );

    // Act / Assert
    await expect(httpPost("/test-resource", { name: "x" })).rejects.toMatchObject({
      status: 429,
      retryAfterSeconds: undefined,
    });
  });

  it("test_parse_response_429_threading_applies_to_httpget_not_only_httppost", async () => {
    // Arrange: the plan's explicit claim is that this is a shared-client
    // property of `parseResponse`, not a `httpPost`-only special case.
    server.use(
      http.get("/api/v1/test-resource", async () =>
        HttpResponse.json({ status: 429 }, { status: 429, headers: { "Retry-After": "15" } }),
      ),
    );

    // Act / Assert
    await expect(httpGet("/test-resource")).rejects.toMatchObject({ status: 429, retryAfterSeconds: 15 });
  });
});
