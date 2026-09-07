// Vitest global setup (vite.config.ts test.setupFiles). Registers jest-dom's
// matchers (toBeInTheDocument, toHaveFocus, toBeDisabled, ...) and
// vitest-axe's toHaveNoViolations, and owns the one `server.listen`/
// `resetHandlers`/`close` lifecycle every test file's `server.use(...)`
// overrides against (docs/tests/US-5.1-test-strategy.md: "beforeAll/
// afterEach/afterAll wiring already done in a global Vitest setup file —
// assumed, not itself under test here").
import "@testing-library/jest-dom/vitest";
// vitest-axe's own type entry points (matchers.d.ts, extend-expect.d.ts) both
// predate this project's Vitest 2.x + `moduleResolution: "Bundler"` setup:
// the root matchers.d.ts re-exports everything as `export type *` (so the
// named runtime value can't be imported directly without a type error), and
// extend-expect.d.ts augments an old `Vi` namespace Vitest 2.x no longer
// reads. Importing the runtime value from its real `dist/` module (a proper,
// non-type-only export) and declaring our own `declare module "vitest"`
// augmentation (./vitest-axe.d.ts) work around both, per AGENTS.md §3's
// "no `any`" rule — this keeps `toHaveNoViolations` fully typed rather than
// casting past the mismatch.
import { afterAll, afterEach, beforeAll, expect } from "vitest";
import { toHaveNoViolations } from "vitest-axe/dist/matchers.js";
import { server } from "./mswServer";

expect.extend({ toHaveNoViolations });

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
