/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// OD-1 (CORS/cross-origin, US-5.1 Open Decision — still OPEN) default per
// docs/plans/US-5.1-implementation-plan.md Architectural Change 1: the
// frontend reaches the backend same-origin via this dev-server proxy, so the
// story's "no backend changes" premise holds and the httpOnly refresh cookie
// is treated as same-origin by the browser. If OD-1 later resolves toward an
// actual backend CORS change instead, this proxy block is what changes.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary", "html"],
      thresholds: {
        lines: 85,
        statements: 85,
        functions: 85,
        branches: 85,
      },
      exclude: ["src/main.tsx", "src/vite-env.d.ts", "src/test/**", "**/*.d.ts", "**/*.config.*"],
    },
  },
});
