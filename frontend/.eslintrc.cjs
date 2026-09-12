/* eslint-env node */
module.exports = {
  root: true,
  env: { browser: true, es2021: true, node: true },
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended", "plugin:react-hooks/recommended"],
  ignorePatterns: ["dist", "coverage", "node_modules", "*.cjs"],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  plugins: ["react-refresh"],
  rules: {
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "error",
  },
  overrides: [
    {
      // React Context provider files idiomatically export both the
      // `<XProvider>` component and its paired `useX()` accessor hook from
      // one module (this codebase's `store/` layer, per
      // AGENTS.md §3's Frontend session-handling rule) — Fast Refresh's
      // component-only-export heuristic is a false positive for that
      // deliberate, standard pattern, not a real code-quality finding.
      files: ["src/store/**/*.tsx"],
      rules: { "react-refresh/only-export-components": "off" },
    },
    {
      // Test-only helpers (e.g. `renderWithProviders`/`renderHookWithProviders`
      // alongside a probe component) are never part of the app's Fast Refresh
      // module graph, so the rule has nothing to protect here.
      files: ["src/test/**/*.tsx", "**/*.test.tsx", "**/*.test.ts"],
      rules: { "react-refresh/only-export-components": "off" },
    },
    {
      // Ambient `declare module "vitest"` augmentation: `Assertion<T>`'s `T`
      // must be re-declared (unused in the body) purely to match Vitest's own
      // generic arity so the two declarations merge — not a real unused-value
      // finding.
      files: ["src/test/vitest-axe.d.ts"],
      rules: { "@typescript-eslint/no-unused-vars": "off" },
    },
    {
      // TK-AC9 mandates `offeredActionsForStatus` as a named export alongside
      // the `TicketDetailScreen` component (implementation_plan v2 Change 6 /
      // test_strategy item 10 place it in this file by design, not a separate
      // module) — Fast Refresh's component-only-export heuristic is a false
      // positive for that deliberate export shape, not a real code-quality
      // finding. Human sign-off: 2026-09-12.
      files: ["src/screens/TicketDetailScreen.tsx"],
      rules: { "react-refresh/only-export-components": "off" },
    },
  ],
};
