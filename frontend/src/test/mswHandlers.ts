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
