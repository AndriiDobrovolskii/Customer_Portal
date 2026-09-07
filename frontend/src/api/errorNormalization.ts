// FR-9 / OD-4 (docs/specifications/US-5.1-spec.md, docs/decisions/US-5.1-open-decisions.md):
// maps every 4xx/5xx response shape this Story's endpoints can return into one
// internal NormalizedApiError every screen's error rendering consumes,
// including `/auth/register`'s two non-RFC7807 shapes
// (RegistrationValidationError's `{"errors":[...]}, and DuplicateEmailError's
// `{"detail": "..."}`, both plain `application/json`, confirmed in
// app/main.py). Pure function, no React/TanStack Query/fetch — `api/` layer
// only (AGENTS.md §3's Frontend table).

export interface NormalizedApiError {
  status: number;
  message: string;
  fieldErrors?: Record<string, string>;
}

export interface NormalizeApiErrorInput {
  status: number;
  contentType: string | null;
  body: unknown;
}

const GENERIC_MESSAGE = "Something went wrong. Please try again.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

interface RawFieldError {
  field: string;
  message: string;
  code?: string;
}

function isRawFieldError(value: unknown): value is RawFieldError {
  return isRecord(value) && typeof value.field === "string" && typeof value.message === "string";
}

function extractFieldErrors(body: Record<string, unknown>): Record<string, string> | undefined {
  if (!Array.isArray(body.errors)) {
    return undefined;
  }
  const fieldErrors: Record<string, string> = {};
  for (const entry of body.errors) {
    if (isRawFieldError(entry)) {
      fieldErrors[entry.field] = entry.message;
    }
  }
  return Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined;
}

export function normalizeApiError(input: NormalizeApiErrorInput): NormalizedApiError {
  const { status, body } = input;

  if (isRecord(body)) {
    const fieldErrors = extractFieldErrors(body);
    const detail = typeof body.detail === "string" ? body.detail : undefined;

    if (detail) {
      // RFC 7807 envelope (type/title/status/detail[/errors]) and
      // DuplicateEmailError's bare {"detail": "..."} both land here.
      return { status, message: detail, fieldErrors };
    }

    if (fieldErrors) {
      // RegistrationValidationError's bare {"errors": [...]}, no detail.
      const firstMessage = Object.values(fieldErrors)[0] ?? GENERIC_MESSAGE;
      return { status, message: firstMessage, fieldErrors };
    }
  }

  // Unrecognized shape (network failure surfaced as text, an unmapped
  // status, or a body with none of the known fields) — never render the raw
  // payload, always fall through to a generic, human-readable message.
  return { status, message: GENERIC_MESSAGE };
}
