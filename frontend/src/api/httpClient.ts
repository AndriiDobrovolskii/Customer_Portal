// The one HTTP boundary this Story's endpoints go through (AGENTS.md §3's
// Frontend table: "`api/` ... the only fetch() layer"). Attaches the
// in-memory access token as a Bearer header (via the neutral session bridge,
// never importing `store/` directly), lets the browser handle the httpOnly
// refresh cookie automatically (`credentials: "include"`, never read or
// parsed here), and is the single interception point for FR-4's
// 401 -> refresh -> retry logic (via `refreshCoordinator.ts`) and FR-9's
// error normalization (via `errorNormalization.ts`).
import { coordinateRefresh } from "./refreshCoordinator";
import { normalizeApiError, type NormalizedApiError } from "./errorNormalization";
import { getSessionBridge } from "../session/sessionBridge";
import type { RefreshResponse } from "./types";

const API_BASE = "/api/v1";

export type HttpMethod = "GET" | "POST" | "DELETE" | "PUT" | "PATCH";

export interface HttpRequestInit {
  method: HttpMethod;
  body?: unknown;
  /** Whether this call carries the in-memory Bearer token. Default true. */
  auth?: boolean;
  idempotencyKey?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors?: Record<string, string>;
  readonly kind?: "network" | "server";
  readonly retryAfterSeconds?: number;

  constructor(normalized: NormalizedApiError, kind?: "network" | "server", retryAfterSeconds?: number) {
    super(normalized.message);
    this.name = "ApiError";
    this.status = normalized.status;
    this.fieldErrors = normalized.fieldErrors;
    this.kind = kind ?? (normalized.status >= 500 ? "server" : undefined);
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function networkError(): ApiError {
  return new ApiError(
    { status: 0, message: "Unable to reach the server. Please check your connection and try again." },
    "network",
  );
}

async function safeJsonParse(text: string): Promise<unknown> {
  if (!text) {
    return undefined;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type");
  const text = await response.text();
  const body = await safeJsonParse(text);

  if (response.ok) {
    return body as T;
  }

  const normalized = normalizeApiError({ status: response.status, contentType, body });

  let retryAfterSeconds: number | undefined;
  if (response.status === 429) {
    const retryAfter = response.headers.get("Retry-After");
    if (retryAfter !== null) {
      const parsed = parseInt(retryAfter, 10);
      if (!Number.isNaN(parsed)) {
        retryAfterSeconds = parsed;
      }
    }
  }

  throw new ApiError(normalized, undefined, retryAfterSeconds);
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw networkError();
  }
}

async function performRefreshRequest(): Promise<RefreshResponse> {
  const response = await rawFetch("/auth/refresh", {
    method: "POST",
    headers: { Accept: "application/json" },
    credentials: "include",
  });
  return parseResponse<RefreshResponse>(response);
}

function buildHeaders(hasBody: boolean, auth: boolean, idempotencyKey?: string): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }
  if (auth) {
    const token = getSessionBridge().getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  if (idempotencyKey !== undefined) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  return headers;
}

async function performRequest<T>(path: string, init: HttpRequestInit): Promise<T> {
  const auth = init.auth ?? true;
  const hasBody = init.body !== undefined;

  const doFetch = () =>
    rawFetch(path, {
      method: init.method,
      headers: buildHeaders(hasBody, auth, init.idempotencyKey),
      credentials: "include",
      body: hasBody ? JSON.stringify(init.body) : undefined,
    });

  let response = await doFetch();

  if (response.status === 401 && auth) {
    const bridge = getSessionBridge();
    try {
      const refreshed = await coordinateRefresh(performRefreshRequest);
      bridge.onTokenRefreshed(refreshed.access_token);
      response = await doFetch();
    } catch {
      bridge.onSessionExpired();
      throw new ApiError({ status: 401, message: "Your session has expired. Please log in again." });
    }
  }

  return parseResponse<T>(response);
}

export function httpGet<T>(path: string, options: { auth?: boolean } = {}): Promise<T> {
  return performRequest<T>(path, { method: "GET", auth: options.auth });
}

export function httpPost<T>(
  path: string,
  body?: unknown,
  options: { auth?: boolean; idempotencyKey?: string } = {},
): Promise<T> {
  return performRequest<T>(path, {
    method: "POST",
    body,
    auth: options.auth,
    idempotencyKey: options.idempotencyKey,
  });
}

// Additive: `body` is optional and new (US-5.2, FR-6's DELETE /auth/mfa
// carries a request body) — existing call sites (e.g. authApi.revokeSession)
// omit it and keep behaving exactly as before (Plan Risk 6).
export function httpDelete<T>(path: string, options: { auth?: boolean; body?: unknown } = {}): Promise<T> {
  return performRequest<T>(path, { method: "DELETE", auth: options.auth, body: options.body });
}

// US-5.2 Plan Change 1: a new, additive verb — `performRequest`/`parseResponse`
// above are untouched. FR-2 needs to tell a 200 (edit succeeded) apart from a
// 202 (email-change pending) apart from a 412 (conflict), and needs the
// `ETag` response header, none of which `Promise<T>`-only `httpGet`/`httpPost`/
// `httpDelete` can express. `httpPatch` stays transport-only: it threads
// `If-Match` only when `options.ifMatch` is supplied, and never decides *what*
// value to send — that policy belongs to `profileApi.ts`/`useProfileUpdate.ts`.
export interface HttpResult<T> {
  data: T;
  status: number;
  headers: Headers;
}

async function parseResponseWithMeta<T>(response: Response): Promise<HttpResult<T>> {
  const contentType = response.headers.get("content-type");
  const text = await response.text();
  const body = await safeJsonParse(text);

  if (response.ok) {
    return { data: body as T, status: response.status, headers: response.headers };
  }

  const normalized = normalizeApiError({ status: response.status, contentType, body });
  throw new ApiError(normalized);
}

export async function httpPatch<T>(
  path: string,
  body: unknown,
  options: { auth?: boolean; ifMatch?: string } = {},
): Promise<HttpResult<T>> {
  const auth = options.auth ?? true;

  const doFetch = () =>
    rawFetch(path, {
      method: "PATCH",
      headers: {
        ...buildHeaders(true, auth),
        ...(options.ifMatch !== undefined ? { "If-Match": options.ifMatch } : {}),
      },
      credentials: "include",
      body: JSON.stringify(body),
    });

  let response = await doFetch();

  if (response.status === 401 && auth) {
    const bridge = getSessionBridge();
    try {
      const refreshed = await coordinateRefresh(performRefreshRequest);
      bridge.onTokenRefreshed(refreshed.access_token);
      response = await doFetch();
    } catch {
      bridge.onSessionExpired();
      throw new ApiError({ status: 401, message: "Your session has expired. Please log in again." });
    }
  }

  return parseResponseWithMeta<T>(response);
}
