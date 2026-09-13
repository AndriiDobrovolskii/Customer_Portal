// AD-AC7's static/source-wide assertion (test_strategy's "Resolved here, not
// re-deferred" section) plus the `listAuditLogs` `from`-key-literal unit
// test named in docs/tests/US-5.4-ac-test-matrix.md.
//
// A per-screen render test can only prove the absence of a delete control in
// the screens it happens to render, not the whole codebase — this is the
// only mechanism that can prove "anywhere". Vite's `import.meta.glob` with
// `query: "?raw"` is a BUILD-TIME source-text map (resolved by Vite/Vitest's
// transform pipeline), not a runtime `node:fs` read, so it works
// synchronously under this project's `jsdom` Vitest environment.
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mswServer";
import * as adminApi from "./adminApi";

// Tolerates a generic type argument between `httpDelete` and its call
// parens (e.g. `httpDelete<void>(` — this codebase's actual idiom, used by
// every existing httpDelete call site in api/authApi.ts/mfaApi.ts), not
// only the bare `httpDelete(` form.
const DELETE_ADMIN_USER_PATTERN = /httpDelete\s*(<[^>]*>)?\s*\(\s*[`'"][^`'"]*\/admin\/users[^`'"]*[`'"]/;

const sourceFiles = import.meta.glob("/src/**/*.{ts,tsx}", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

describe("AD-AC7 — no control anywhere issues DELETE /admin/users/{id}", () => {
  it("test_no_frontend_source_file_calls_http_delete_against_the_admin_users_path", () => {
    // Arrange: exclude this test file's own source — its regex literal
    // above would otherwise match itself.
    const candidateFiles = Object.entries(sourceFiles).filter(
      ([path]) => !path.endsWith("/api/adminApi.test.ts"),
    );

    // Guard against a misconfigured glob (wrong root, `?raw` not resolving)
    // that would resolve to zero/near-zero files and pass vacuously,
    // proving nothing.
    expect(candidateFiles.length).toBeGreaterThan(20);

    const offendingFiles = candidateFiles
      .filter(([, contents]) => DELETE_ADMIN_USER_PATTERN.test(contents))
      .map(([path]) => path);

    // Act / Assert
    expect(offendingFiles).toEqual([]);
  });

  it("test_admin_api_ts_does_not_export_a_delete_user_function", () => {
    // Assert: narrower than the scan above, but catches the single most
    // likely reintroduction point directly by name.
    expect((adminApi as unknown as Record<string, unknown>).deleteUser).toBeUndefined();
  });
});

describe("listAuditLogs", () => {
  it("test_list_audit_logs_sends_the_start_of_window_parameter_key_literally_as_from_not_from_", async () => {
    // Arrange
    let receivedKeys: string[] = [];
    server.use(
      http.get("/api/v1/admin/audit-logs", async ({ request }) => {
        receivedKeys = Array.from(new URL(request.url).searchParams.keys());
        return HttpResponse.json({ items: [], next_cursor: null }, { status: 200 });
      }),
    );

    // Act
    await adminApi.listAuditLogs({ from: "2026-09-01T00:00:00Z", to: "2026-09-08T00:00:00Z" });

    // Assert
    expect(receivedKeys).toContain("from");
    expect(receivedKeys).not.toContain("from_");
  });
});
