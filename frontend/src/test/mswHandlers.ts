// Default MSW handlers (Task T4) — one per backend operation this Story's
// spec API Contract table names, shaped like the real responses (status
// code + body + content-type), PLUS two dedicated handlers demonstrating
// Register's own non-RFC7807 shapes (OD-4, docs/decisions/US-5.1-open-decisions.md):
// `RegistrationValidationError` (400, plain application/json, {"errors":[...]})
// and `DuplicateEmailError` (409, plain application/json, {"detail": "..."}).
// Every test file overrides the handler(s) relevant to its own scenario via
// `server.use(...)` — these are only the server's baseline, never asserted
// against directly.
import { http, HttpResponse } from "msw";

const API = "/api/v1";

export const handlers = [
  http.post(`${API}/auth/register`, async () =>
    HttpResponse.json({ id: "u1", email: "user@example.com" }, { status: 201 }),
  ),

  http.post(`${API}/auth/login`, async () =>
    HttpResponse.json(
      {
        access_token: "default-access-token",
        expires_in: 900,
        user: { id: "u1", email: "user@example.com" },
      },
      { status: 200 },
    ),
  ),

  http.post(`${API}/auth/mfa/verify`, async () =>
    HttpResponse.json(
      {
        access_token: "default-access-token",
        expires_in: 900,
        user: { id: "u1", email: "user@example.com" },
      },
      { status: 200 },
    ),
  ),

  http.post(`${API}/auth/refresh`, async () =>
    HttpResponse.json({ access_token: "refreshed-access-token", expires_in: 900 }, { status: 200 }),
  ),

  http.post(`${API}/auth/logout`, async () => new HttpResponse(null, { status: 204 })),

  http.post(`${API}/auth/logout-all`, async () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/auth/sessions`, async () => HttpResponse.json({ sessions: [] }, { status: 200 })),

  http.delete(`${API}/auth/sessions/:familyId`, async () => new HttpResponse(null, { status: 204 })),

  http.post(`${API}/auth/password-reset/request`, async () =>
    HttpResponse.json(
      { message: "If an account exists for that email, a reset link has been sent." },
      { status: 202 },
    ),
  ),

  http.post(`${API}/auth/password-reset/confirm`, async () => new HttpResponse(null, { status: 200 })),

  // US-5.2 baseline handlers — one per new endpoint (Task T1).
  http.patch(`${API}/profile`, async () =>
    HttpResponse.json(
      {
        id: "u1",
        email: "user@example.com",
        pending_email: null,
        display_name: "Default Name",
        locale: "en-US",
        timezone: "America/New_York",
        avatar_url: null,
        email_verified: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      { status: 200, headers: { ETag: "default-etag" } },
    ),
  ),

  http.post(`${API}/profile/confirm-email-change`, async () =>
    HttpResponse.json({ email: "user@example.com" }, { status: 200 }),
  ),

  http.post(`${API}/auth/verify-email`, async () =>
    HttpResponse.json({ email_verified: true }, { status: 200 }),
  ),

  http.post(`${API}/auth/verify-email/resend`, async () =>
    HttpResponse.json(
      { message: "If an account exists for that email, a verification link has been sent." },
      { status: 200 },
    ),
  ),

  http.post(`${API}/auth/mfa/enroll`, async () =>
    HttpResponse.json(
      {
        secret: "JBSWY3DPEHPK3PXP", // pragma: allowlist secret
        otpauth_uri: "otpauth://totp/CustomerPortal:user?secret=JBSWY3DPEHPK3PXP", // pragma: allowlist secret
      },
      { status: 200 },
    ),
  ),

  http.post(`${API}/auth/mfa/activate`, async () =>
    HttpResponse.json({ recovery_codes: ["AAAA-1111", "BBBB-2222"] }, { status: 200 }),
  ),

  http.delete(`${API}/auth/mfa`, async () => new HttpResponse(null, { status: 204 })),

  http.post(`${API}/account/deactivate`, async () =>
    HttpResponse.json({ status: "deactivated", deactivated_at: "2026-01-01T00:00:00Z" }, { status: 200 }),
  ),

  // US-5.3 Support Tickets baseline handlers
  http.get(`${API}/support/tickets`, async () =>
    HttpResponse.json({ items: [], next_cursor: null }, { status: 200 }),
  ),

  http.post(`${API}/support/tickets`, async () =>
    HttpResponse.json(
      {
        id: "t1",
        ticket_number: "TCK-1001",
        subject: "Default Subject",
        category: "General",
        status: "open",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      { status: 201 },
    ),
  ),

  http.get(`${API}/support/tickets/:id`, async () =>
    HttpResponse.json(
      {
        id: "t1",
        ticket_number: "TCK-1001",
        subject: "Default Subject",
        category: "General",
        status: "open",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        first_response_at: null,
        replies: { items: [], next_cursor: null },
      },
      { status: 200 },
    ),
  ),

  http.post(`${API}/support/tickets/:id/replies`, async () =>
    HttpResponse.json(
      {
        id: "r1",
        author_id: "u1",
        author_kind: "customer",
        body: "Default reply",
        created_at: "2026-01-01T00:00:00Z",
      },
      { status: 201 },
    ),
  ),

  http.post(`${API}/support/tickets/:id/close`, async () =>
    HttpResponse.json({ id: "t1", status: "closed", updated_at: "2026-01-01T00:00:00Z" }, { status: 200 }),
  ),

  http.post(`${API}/support/tickets/:id/reopen`, async () =>
    HttpResponse.json(
      { id: "t1", status: "waiting_on_support", updated_at: "2026-01-01T00:00:00Z" },
      { status: 200 },
    ),
  ),
];

/** OD-4: RegistrationValidationError — 400, plain application/json, no RFC 7807 envelope. */
export const registerValidationErrorHandler = http.post(`${API}/auth/register`, async () =>
  HttpResponse.json(
    { errors: [{ field: "password", message: "Password must contain a digit.", code: "weak_password" }] },
    { status: 400 },
  ),
);

/** OD-4: DuplicateEmailError — 409, plain application/json, no RFC 7807 envelope. */
export const registerDuplicateEmailHandler = http.post(`${API}/auth/register`, async () =>
  HttpResponse.json({ detail: "Email is already registered." }, { status: 409 }),
);
