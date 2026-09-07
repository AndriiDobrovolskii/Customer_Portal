// Ambient type augmentation for vitest-axe's `toHaveNoViolations` matcher.
// vitest-axe ships its own `extend-expect.d.ts`, but it augments an old `Vi`
// namespace from pre-2.x Vitest typings; this project's installed Vitest
// (2.x) expects `declare module "vitest"` augmentation instead (see
// @testing-library/jest-dom/types/vitest.d.ts for the same pattern this
// project already relies on for jest-dom's matchers). Picked up automatically
// by tsconfig.app.json's `"include": ["src"]` — no explicit import needed.
// Members are declared directly (rather than `extends AxeMatchers {}`) so
// this augmentation is never an empty-bodied interface under
// `@typescript-eslint/no-empty-object-type`; `Assertion`'s own `T` parameter
// is unused in the body (see .eslintrc.cjs override) because it exists only
// to match Vitest's declaration so the two merge — vitest-axe's matcher does
// not depend on the asserted value's type.
import "vitest";
import type { NoViolationsMatcherResult } from "vitest-axe/dist/matchers.js";

declare module "vitest" {
  interface Assertion<T = unknown> {
    toHaveNoViolations(): NoViolationsMatcherResult;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): NoViolationsMatcherResult;
  }
}
