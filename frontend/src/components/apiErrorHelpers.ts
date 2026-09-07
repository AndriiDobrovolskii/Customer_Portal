// Shared, structural (duck-typed) helpers every screen uses to read a
// TanStack Query mutation/query `error` (actually an `api/httpClient.ts`
// `ApiError` at runtime) WITHOUT importing the `ApiError` class itself —
// `screens/`/`components/` must not import `api/` directly (AGENTS.md §3's
// Frontend table). Structural checks avoid that import while still letting
// every screen render FE-AC9's message/fieldErrors and FE-AC11's
// network/server ErrorState consistently.
export interface PresentableApiError {
  status?: number;
  message?: string;
  fieldErrors?: Record<string, string>;
  kind?: "network" | "server";
}

function asPresentable(error: unknown): PresentableApiError | undefined {
  if (error && typeof error === "object") {
    return error as PresentableApiError;
  }
  return undefined;
}

export function getErrorKind(error: unknown): "network" | "server" | undefined {
  const kind = asPresentable(error)?.kind;
  return kind === "network" || kind === "server" ? kind : undefined;
}

export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  const message = asPresentable(error)?.message;
  return typeof message === "string" && message.length > 0 ? message : fallback;
}

export function getFieldErrors(error: unknown): Record<string, string> | undefined {
  return asPresentable(error)?.fieldErrors;
}
