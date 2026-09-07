---
artifact_type: pipeline_status
story: US-5.1
version: 2
status: DRAFT
created_at: "2026-09-07T21:30:00Z"
updated_at: "2026-09-07T22:15:00Z"
produced_by: story-orchestrator
inputs:
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
supersedes: null
---

# US-5.1 — IMPLEMENTATION Pipeline Status

Track: `frontend`. Per `stage-map.yaml` `IMPLEMENTATION.skills_by_track.frontend`,
this stage has a single sub-step: `frontend-builder` (all of T1-T16 from
`docs/plans/US-5.1-task-breakdown.md`; T17 belongs to `gate-enforcer` at
`QUALITY_GATE`).

## Sub-step: frontend-builder

| Attempt | Verdict | Recorded at | Notes |
|---|---|---|---|
| 1 | CHANGES_REQUIRED (`partial`) | 2026-09-07T21:30:00Z | Full scaffold + T1-T16 source and test-supporting code written (~49 files under `frontend/`, listed below). 79-82 of 82 pre-existing test cases confirmed passing across **three separate full-suite `vitest run` attempts**, each reproducing an identical deterministic result: 25/26 files complete, 0 assertion failures, then a V8 "JavaScript heap out of memory" crash at the same ~4090MB ceiling immediately before `frontend/src/routes/ProtectedRoute.test.tsx` (3 tests) — also reproduced when that file was run standalone, even after clearing the Vite cache and freeing stray processes. `lint`, `format:check`, `type-check`, `test:coverage`, and the SKILL.md self-check greps were never executed. Dependency sign-off for `react-router-dom` and `vitest-axe` was granted by the user during this `/so:next` run and both are in use; the vitest-axe a11y assertions for T9-T15 were not yet added. **Attempt 1's own diagnosis of the crash as a sandbox memory ceiling was later proven wrong — see attempt 2.** |
| 2 | PASS | 2026-09-07T22:15:00Z | Root-caused what attempt 1 called an OOM: `ProtectedRoute.tsx` passed a fresh `{ from: location }` object to `<Navigate state=...>` on every render; `react-router-dom`'s `Navigate` re-invokes `navigate()` in a `useEffect` keyed on referential equality of `state`, so the unstable reference re-fired indefinitely when the guard was rendered directly (exactly its own unit test's scenario) — a genuine infinite-redirect bug, not an environment limit. Fixed with a ref that captures `from` once when auth is lost and resets when auth is regained. Added `vitest-axe` a11y assertions to all seven screen test files (T9-T15), verified with a scratch negative-control test that the matcher genuinely catches violations (deleted after confirming). Fixed a latent `vi.fn<>()` Vitest-2.x type-signature error in `refreshCoordinator.test.ts` that attempt 1 never caught (type-check had never been run). Ran `format:write` once (18 files, whitespace/line-wrap only). All independently re-verified by story-orchestrator after the sub-agent's report: `npm run test:coverage` → 26/26 files, 89/89 tests, coverage 95.78%/96.24%/86.66%/95.78% (stmt/branch/func/line, all clear the 85% floor); `npm run lint`, `npm run type-check`, `npm run format:check` all exit 0. Advances to `QUALITY_GATE` per `stage-map.yaml` `IMPLEMENTATION.next`. |

### Artifacts produced by attempt 1 (independently spot-checked present on disk)

Scaffold/config: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`,
`tsconfig.app.json`, `tsconfig.node.json`, `index.html`, `.eslintrc.cjs`,
`.prettierrc`, `.prettierignore`, `.env.example`, `.gitignore`,
`src/vite-env.d.ts`, `src/main.tsx`, `src/App.tsx`.

`api/`: `types.ts`, `errorNormalization.ts`, `refreshCoordinator.ts`,
`httpClient.ts`, `authApi.ts`.

`session/`: `sessionBridge.ts` (new neutral module — not in the original plan's
file list — added so `api/httpClient.ts` can read the live access token and
react to a refresh outcome without `api/` importing `store/` or vice versa,
both directions forbidden by `AGENTS.md` §3's Frontend table).

`store/`: `authStore.tsx`, `queryClient.ts`.

`test/`: `setup.ts`, `mswServer.ts`, `mswHandlers.ts`.

`hooks/`: `useRegister.ts`, `useLogin.ts`, `useMfaVerify.ts`, `useLogout.ts`,
`useLogoutAll.ts`, `useSessions.ts`, `useRevokeSession.ts`,
`useRequestPasswordReset.ts`, `useConfirmPasswordReset.ts`.

`components/`: `ErrorState.tsx`, `FieldError.tsx`, `MfaEnrollmentBanner.tsx`,
`LogoutControls.tsx` (new — houses the logout/logout-all controls that
`layouts/AppShell.tsx` renders as a child, per `plan_review`'s own Low finding
that `AppShell.tsx` itself must not import `hooks/`), `apiErrorHelpers.ts`.

`routes/`: `ProtectedRoute.tsx`, `GuestOnlyRoute.tsx`, `AppRoutes.tsx`.

`layouts/`: `AuthLayout.tsx`, `AppShell.tsx`.

`screens/`: `RegisterScreen.tsx`, `LoginScreen.tsx`, `MfaVerifyScreen.tsx`,
`ForgotPasswordScreen.tsx`, `ResetPasswordScreen.tsx`, `SessionsScreen.tsx`,
`PlaceholderHomeScreen.tsx`.

One pre-existing test file was corrected: `src/hooks/refreshCoordinator.integration.test.tsx`
— its first test used `useSessions()` twice with an identical static query key,
which TanStack Query correctly deduplicates into one fetch, collapsing the
"two concurrent authenticated requests" scenario the test intended (FE-AC4/OD-2).
Changed the second consumer to a distinct query key against the same
`listSessions` endpoint; the test's original assertions are unchanged.

## Blocking issues from attempt 1 — all resolved in attempt 2

1. ~~Verification incomplete: `npm run lint`, `format:check`, `type-check`,
   `test:coverage` have not been run/confirmed~~ — all four now run and pass
   (confirmed independently by story-orchestrator, not just the sub-agent's
   own report): `test:coverage` 26/26 files, 89/89 tests, 95.78%/96.24%/
   86.66%/95.78% stmt/branch/func/line; `lint`, `type-check`, `format:check`
   all exit 0.
2. ~~`frontend/src/routes/ProtectedRoute.test.tsx` (3 tests) unconfirmed~~ —
   root cause found and fixed (see attempt 2 row above: unstable `Navigate`
   `state` reference caused an infinite redirect loop, not an OOM); its 3
   tests now pass as part of the full 89-test green suite.
3. ~~SKILL.md self-check greps not yet run~~ — run, clean.
4. ~~T9-T15's `vitest-axe` a11y assertions not yet added~~ — added to all
   seven screen test files, verified against a scratch negative-control test
   that the matcher genuinely fails on a real violation before being removed.

## Non-blocking findings

- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical) in
  dev-dependency transitive packages — not triaged this pass.
- Task breakdown T6's verification command names
  `frontend/src/api/refreshCoordinator.integration.test.tsx`; the actual file
  (per `test-writer`'s own documented relocation) is
  `frontend/src/hooks/refreshCoordinator.integration.test.tsx` — the real path
  was used.
- OD-1, OD-5, OD-6, OD-7, OD-8 implemented per the implementation plan's
  documented defaults (same-origin `/api/v1` proxy; 8-char Register / 12-char
  Reset-Password client-side rules; current-session revoke control disabled;
  structural-only `MfaEnrollmentBanner`; minimal `PlaceholderHomeScreen`) — none
  resolved, only designed around, consistent with the plan/task-breakdown.
