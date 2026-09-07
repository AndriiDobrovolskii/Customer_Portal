// Unit test for the useRegister hook (Task T5, FE-AC1).
// Collaborator-shape assumption: `useRegister()` wraps `authApi.register` in a
// TanStack Query `useMutation`, exposing `{ mutateAsync, isPending, isError,
// error }`. Test-infra assumption: `renderHookWithProviders` (test-utils.tsx,
// Task T4) wraps `renderHook` with `QueryClientProvider` + `AuthProvider`;
// `server`/`http`/`HttpResponse` (mswServer.ts/mswHandlers.ts, Task T4)
// provide the default `/auth/register` handler, overridden per test via
// `server.use(...)`.
//
// Expected to fail at collection/import time until IMPLEMENTATION lands
// `frontend/src/hooks/useRegister.ts` and the Task T4 test infrastructure.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import { renderHookWithProviders, waitFor } from "../test/test-utils";
import { useRegister } from "./useRegister";

describe("useRegister", () => {
  it("test_use_register_calls_register_endpoint_and_returns_created_user", async () => {
    // Arrange
    server.use(
      http.post("/api/v1/auth/register", async () =>
        HttpResponse.json({ id: "user-1", email: "new@example.com" }, { status: 201 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useRegister());

    // Act
    const created = await result.current.mutateAsync({
      email: "new@example.com",
      password: "Sup3r$ecret!", // pragma: allowlist secret
    });

    // Assert
    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(created).toEqual({ id: "user-1", email: "new@example.com" });
  });

  it("test_use_register_duplicate_email_surfaces_normalized_409_error", async () => {
    // Arrange: DuplicateEmailError shape (OD-4), not RFC 7807.
    server.use(
      http.post("/api/v1/auth/register", async () =>
        HttpResponse.json({ detail: "Email is already registered." }, { status: 409 }),
      ),
    );
    const { result } = renderHookWithProviders(() => useRegister());

    // Act / Assert
    await expect(
      result.current.mutateAsync({ email: "dup@example.com", password: "Sup3r$ecret!" }), // pragma: allowlist secret
    ).rejects.toMatchObject({ status: 409, message: "Email is already registered." });
  });
});
