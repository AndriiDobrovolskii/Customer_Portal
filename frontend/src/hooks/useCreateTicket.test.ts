// Unit test for useCreateTicket (TK-AC3/FR-3, TK-AC4/FR-4, OD-6's binding
// resolution). Three dedicated key-lifecycle cases, per implementation_plan
// v2 Risk 5 / task_breakdown v2 T8: (1) identical key on a verbatim retry,
// (2) a distinct key on a fresh mount, (3) a distinct key on an
// edited-then-resubmitted payload.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders } from "../test/test-utils";
import { useCreateTicket } from "./useCreateTicket";

const PAYLOAD = { subject: "Cannot log in", body: "Details about the problem.", category: "account" };
const EDITED_PAYLOAD = { ...PAYLOAD, body: "Updated details about the problem." };

function captureIdempotencyKeyHandler(
  capturedKeys: string[],
  responder: () => Response | Promise<Response> = () =>
    HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 }),
) {
  return http.post("/api/v1/support/tickets", async ({ request }) => {
    capturedKeys.push(request.headers.get("idempotency-key") ?? "");
    return responder();
  });
}

describe("useCreateTicket key lifecycle (OD-6)", () => {
  it("test_use_create_ticket_mints_a_key_on_first_submission_and_sends_attachment_ids_empty", async () => {
    // Arrange
    const capturedKeys: string[] = [];
    let capturedBody: unknown;
    server.use(
      http.post("/api/v1/support/tickets", async ({ request }) => {
        capturedKeys.push(request.headers.get("idempotency-key") ?? "");
        capturedBody = await request.json();
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateTicket());

    // Act
    await result.current.mutateAsync(PAYLOAD);

    // Assert
    expect(capturedKeys[0]).toBeTruthy();
    expect(capturedKeys[0]).not.toBe("");
    expect(capturedBody).toMatchObject({ attachment_ids: [] });
  });

  it("test_use_create_ticket_reuses_the_identical_key_on_a_verbatim_retry_after_failure", async () => {
    // Arrange: first attempt 500s, second attempt (same composed ticket) succeeds.
    const capturedKeys: string[] = [];
    let attempt = 0;
    server.use(
      http.post("/api/v1/support/tickets", async ({ request }) => {
        capturedKeys.push(request.headers.get("idempotency-key") ?? "");
        attempt += 1;
        if (attempt === 1) {
          return new HttpResponse(null, { status: 503 });
        }
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateTicket());

    // Act
    await expect(result.current.mutateAsync(PAYLOAD)).rejects.toBeTruthy();
    await result.current.mutateAsync(PAYLOAD);

    // Assert
    expect(capturedKeys).toHaveLength(2);
    expect(capturedKeys[0]).toBe(capturedKeys[1]);
  });

  it("test_use_create_ticket_mints_a_new_key_on_an_edited_then_resubmitted_payload", async () => {
    // Arrange: OD-6's binding case — a changed subject/body/category before
    // resubmitting must rotate the key, never reuse it (the backend would
    // otherwise reject the reuse with a 422 IdempotencyKeyReuseError).
    const capturedKeys: string[] = [];
    let attempt = 0;
    server.use(
      http.post("/api/v1/support/tickets", async ({ request }) => {
        capturedKeys.push(request.headers.get("idempotency-key") ?? "");
        attempt += 1;
        if (attempt === 1) {
          return new HttpResponse(null, { status: 503 });
        }
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateTicket());

    // Act
    await expect(result.current.mutateAsync(PAYLOAD)).rejects.toBeTruthy();
    await result.current.mutateAsync(EDITED_PAYLOAD);

    // Assert
    expect(capturedKeys).toHaveLength(2);
    expect(capturedKeys[0]).not.toBe(capturedKeys[1]);
  });

  it("test_use_create_ticket_fresh_mount_mints_a_different_key_than_a_previous_composition", async () => {
    // Arrange: a genuinely new ticket composition (this screen unmounting and
    // remounting, e.g. navigating away and back) discards the previous key
    // entirely (FR-4: "not persisted across a full reload").
    const capturedKeys: string[] = [];
    server.use(captureIdempotencyKeyHandler(capturedKeys));
    const first = renderHookWithProviders(() => useCreateTicket());
    await first.result.current.mutateAsync(PAYLOAD);
    first.unmount();

    const second = renderHookWithProviders(() => useCreateTicket());

    // Act
    await second.result.current.mutateAsync(PAYLOAD);

    // Assert
    expect(capturedKeys).toHaveLength(2);
    expect(capturedKeys[0]).not.toBe(capturedKeys[1]);
  });
});

describe("useCreateTicket request shape", () => {
  it("test_use_create_ticket_never_sends_a_visibility_field", async () => {
    // Arrange
    let capturedBody: Record<string, unknown> = {};
    server.use(
      http.post("/api/v1/support/tickets", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const { result } = renderHookWithProviders(() => useCreateTicket());

    // Act
    await result.current.mutateAsync(PAYLOAD);

    // Assert
    expect(capturedBody).not.toHaveProperty("visibility");
    expect(capturedBody).toMatchObject({
      subject: PAYLOAD.subject,
      body: PAYLOAD.body,
      category: PAYLOAD.category,
    });
  });
});
