// Integration test for NewTicketScreen (TK-AC3/FR-3, TK-AC4/FR-4, TK-AC10/FR-10,
// TK-AC12/FR-12, TK-AC13/FR-13, TK-AC14's 403 deactivated-account clause,
// TK-AC11's 422 field-mapping case, OD-2, a11y bar).
//
// Field-label collaborator-shape assumptions (docs/tests/US-5.3-test-strategy.md
// item 7): "Subject" / "Body" / "Category" fields, a "Create ticket" submit
// button. OD-2: category is a plain text <input maxLength={50}>, not a
// <select> — asserted directly by tag name.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { server } from "../test/mswServer";
import { renderWithProviders } from "../test/test-utils";
import { NewTicketScreen } from "./NewTicketScreen";

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/subject/i), "Cannot log in");
  await user.type(screen.getByLabelText(/body/i), "I cannot log in to my account.");
  await user.type(screen.getByLabelText(/category/i), "account");
}

describe("NewTicketScreen", () => {
  it("test_new_ticket_screen_valid_submission_sends_idempotency_key_and_attachment_ids_empty_and_lands_on_detail_on_201", async () => {
    // Arrange
    let receivedHeader: string | null = null;
    let receivedBody: Record<string, unknown> = {};
    server.use(
      http.post("/api/v1/support/tickets", async ({ request }) => {
        receivedHeader = request.headers.get("idempotency-key");
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(receivedHeader).toBeTruthy();
    expect(receivedBody).toMatchObject({ attachment_ids: [] });
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets/t-1");
  });

  it("test_new_ticket_screen_category_field_is_a_plain_text_input_not_a_select", () => {
    // Arrange / Act
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Assert
    expect(screen.getByLabelText(/category/i).tagName).toBe("INPUT");
  });

  it("test_new_ticket_screen_blocks_submission_on_empty_required_fields_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/support/tickets", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(apiCalled).toBe(false);
  });

  it("test_new_ticket_screen_blocks_submission_on_over_length_subject_body_category_without_calling_api", async () => {
    // Arrange
    let apiCalled = false;
    server.use(
      http.post("/api/v1/support/tickets", async () => {
        apiCalled = true;
        return HttpResponse.json({ id: "t-1", ticket_number: "TCK-0001" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act: subject 151, body 5001, category 51 chars — one over each max.
    // These lengths are set via fireEvent.change rather than user.type():
    // user.type() dispatches one keystroke event per character, and a
    // 5001-character string does not complete even at a 60s timeout — a
    // known @testing-library/user-event characteristic for very long
    // strings, unrelated to the component under test.
    fireEvent.change(screen.getByLabelText(/subject/i), { target: { value: "s".repeat(151) } });
    fireEvent.change(screen.getByLabelText(/body/i), { target: { value: "b".repeat(5001) } });
    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: "c".repeat(51) } });
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
    expect(apiCalled).toBe(false);
  });

  it("test_new_ticket_screen_verbatim_retry_after_5xx_sends_the_identical_idempotency_key", async () => {
    // Arrange: TK-AC4, proven end-to-end through the screen (not only the
    // hook) — a 5xx on first submit, then a verbatim retry.
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
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));
    await screen.findByRole("button", { name: /retry/i });

    // Act
    await user.click(screen.getByRole("button", { name: /retry/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets/t-1");
    expect(capturedKeys).toHaveLength(2);
    expect(capturedKeys[0]).toBe(capturedKeys[1]);
  });

  it("test_new_ticket_screen_editing_a_field_after_a_failure_and_resubmitting_sends_a_different_key", async () => {
    // Arrange: OD-6's binding case — an edited-then-resubmitted payload must
    // rotate the key, never reuse it (avoiding the backend's 422
    // IdempotencyKeyReuseError).
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
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));
    await screen.findByRole("button", { name: /retry/i });

    // Act: edit the body before resubmitting.
    await user.type(screen.getByLabelText(/body/i), " Updated.");
    await user.click(screen.getByRole("button", { name: /retry/i }));

    // Assert
    expect(await screen.findByTestId("route-location")).toHaveTextContent("/tickets/t-1");
    expect(capturedKeys).toHaveLength(2);
    expect(capturedKeys[0]).not.toBe(capturedKeys[1]);
  });

  it("test_new_ticket_screen_422_validation_error_maps_errors_array_onto_matching_fields", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/validation-failed",
            title: "Validation failed",
            status: 422,
            errors: [{ field: "subject", message: "Subject is too long.", code: "too_long" }],
          },
          { status: 422, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findByText("Subject is too long.")).toBeInTheDocument();
  });

  it("test_new_ticket_screen_429_response_shows_retry_time_disables_submit_and_fires_exactly_once", async () => {
    // Arrange
    let requestCount = 0;
    server.use(
      http.post("/api/v1/support/tickets", async () => {
        requestCount += 1;
        return HttpResponse.json(
          { type: "https://errors.example/rate-limited", title: "Rate limited", status: 429 },
          { status: 429, headers: { "Retry-After": "30", "content-type": "application/problem+json" } },
        );
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findByText(/try again in|retry in/i)).toBeInTheDocument();
    expect(await screen.findByText(/30/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create ticket/i })).toBeDisabled();
    expect(requestCount).toBe(1);
  });

  it("test_new_ticket_screen_403_deactivated_account_renders_problem_json_detail", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/support/tickets", async () =>
        HttpResponse.json(
          {
            type: "https://errors.example/account-deactivated",
            title: "Account deactivated",
            status: 403,
            detail: "Your account has been deactivated.",
          },
          { status: 403, headers: { "content-type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findByText("Your account has been deactivated.")).toBeInTheDocument();
  });

  it("test_new_ticket_screen_network_error_shows_retry_capable_error_state", async () => {
    // Arrange
    server.use(http.post("/api/v1/support/tickets", () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<NewTicketScreen />, { route: "/tickets/new", isAuthenticated: true });

    // Act
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /create ticket/i }));

    // Assert
    expect(await screen.findByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("test_new_ticket_screen_has_no_detectable_accessibility_violations", async () => {
    // Arrange
    const { container } = renderWithProviders(<NewTicketScreen />, {
      route: "/tickets/new",
      isAuthenticated: true,
    });

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });
});
