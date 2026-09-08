---
artifact_type: quality_gate_report
story: US-5.1
version: 1
status: ARCHIVED
created_at: "2026-09-07T06:47:57Z"
updated_at: "2026-09-07T06:47:57Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.1-task-breakdown.md
    version: 1
  - path: docs/tests/US-5.1-ac-test-matrix.md
    version: 1
supersedes: null
---

# US-5.1 — Quality Gate Report (frontend track)

Story: `docs/stories/US-5.1-authentication-session-management.md` (`track: frontend`).
Track command set: `AGENTS.md` §2/§6 Frontend subsections and
`gate-enforcer/SKILL.md` Part A′ / Part B′. All commands below were run inside
`frontend/` in this session (Windows / Git Bash), captured verbatim (trimmed
of ANSI-only decoration where noted). Nothing below is asserted from memory or
from a prior run's report — every command was re-executed live for this
report, per `AGENTS.md` §7.9.

## Required-context confirmation

- `frontend/package.json` `scripts` block confirmed to contain exactly
  `lint`, `format:check`, `type-check`, `test:coverage` (plus `dev`, `build`,
  `preview`, `format:write`, `test`, none of which are gate-invoked names) —
  no rename, no missing script.
- `.pre-commit-config.yaml` confirmed to contain the four frontend hooks
  (`frontend-lint`, `frontend-format`, `frontend-type-check`,
  `frontend-vi-mock-in-integration-tests`), all scoped `files: ^frontend/...`.
- `git status --porcelain frontend/` shows `?? frontend/` — the entire
  directory is new/untracked, consistent with `frontend-builder` scaffolding
  this Story's first frontend code; nothing about the diff was empty.

## Harness preconditions checked

- `docs/workflow/active-story.yaml` (`active_story: US-5.1`) and
  `docs/workflow/workflow-state.yaml` (`story: US-5.1`) agree on the active
  Story.
- `implementation_plan` (v1) and `task_breakdown` (v1), the two `APPROVED`
  inputs this stage consumes, contain no `TODO`/`TBD`/`FIXME`/`???`
  (`grep -n "TODO\|TBD\|FIXME\|???"` over both files: zero matches).
  `docs/decisions/US-5.1-open-decisions.md` logs OD-1 through OD-9 as `OPEN`
  and `docs/specifications/US-5.1-spec.md` (v2, the plan's own input) confirms
  none is resolved by the spec either — but both the plan (line 40-43: "each
  is either designed around so implementation can proceed regardless of how
  it resolves, or named as a blocking dependency below") and the task
  breakdown (Notes section: "None of these block scheduling — each task
  applies the plan's documented default") explicitly classify all nine as
  non-blocking for execution, with the one item that *was* a real blocking
  dependency (the `react-router-dom`/`vitest-axe` new-dependency sign-off
  gating T7/T16) recorded as resolved in
  `docs/catalog/US-5.1-pipeline-status.md` attempt 1 ("Dependency sign-off ...
  was granted by the user"). No unresolved *blocking* Open Decision remains
  against either `APPROVED` input this stage depends on.
- `ac_test_matrix` is `DRAFT` (not `APPROVED`) — that is its normal lifecycle
  state at this point in the pipeline, not a staleness signal.

## Part A′ — mechanical gates

### 1. `npm run lint`

```
> customer-portal-frontend@0.1.0 lint
> eslint . --max-warnings=0
```

Exit code 0. No findings, no output beyond the script echo (ESLint prints
nothing when there are zero problems under `--max-warnings=0`).

**Result: PASS.**

### 2. `npm run format:check`

```
> customer-portal-frontend@0.1.0 format:check
> prettier --check .

Checking formatting...
All matched files use Prettier code style!
```

Exit code 0. Check-only script (never `--write`) — no drift.

**Result: PASS.**

### 3. `npm run type-check`

```
> customer-portal-frontend@0.1.0 type-check
> tsc -b --noEmit
```

Exit code 0. No diagnostics against the whole `frontend/` project (project
references build via `tsc -b`, not a single file).

**Result: PASS.**

### 4. `npm run test:coverage`

```
> customer-portal-frontend@0.1.0 test:coverage
> vitest run --coverage

 Test Files  26 passed (26)
      Tests  89 passed (89)
   Start at  09:46:52
   Duration  13.55s (transform 871ms, setup 11.56s, collect 12.39s, tests 21.95s, environment 25.47s, prepare 4.15s)

 % Coverage report from v8
-------------------|---------|----------|---------|---------|-------------------
File               | % Stmts | % Branch | % Funcs | % Lines | Uncovered Line #s
-------------------|---------|----------|---------|---------|-------------------
All files          |   95.78 |    96.24 |   86.66 |   95.78 |
-------------------|---------|----------|---------|---------|-------------------

=============================== Coverage summary ===============================
Statements   : 95.78% ( 2229/2327 )
Branches     : 96.24% ( 436/453 )
Functions    : 86.66% ( 91/105 )
Lines        : 95.78% ( 2229/2327 )
================================================================================
```

26/26 test files passed, 89/89 tests passed, 0 failures. Coverage:
95.78% statements, 96.24% branches, 86.66% functions, 95.78% lines — all four
clear the 85% floor (`AGENTS.md` §5 Frontend subsection). This floor is
mechanically enforced, not just measured: `frontend/vite.config.ts`'s
`test.coverage.thresholds` sets `lines/statements/functions/branches: 85`
(with `exclude: ["src/main.tsx", "src/vite-env.d.ts", "src/test/**",
"**/*.d.ts", "**/*.config.*"]`), so Vitest itself would exit non-zero had any
metric landed under 85 — the exit-0 result above is proof the gate fired and
passed, the same way `--cov-fail-under=85` proves it on the backend. Per-file
coverage table (also captured in the full run log) shows two files at 0% —
`frontend/.eslintrc.cjs` (tooling config, not app logic — arguably should be
covered by the config's own `exclude` glob but is not, since `.eslintrc.cjs`
doesn't match `**/*.config.*`; worth a follow-up to add it) and
`frontend/src/App.tsx` (a 17-line composition root exercised end-to-end by
every screen/route integration test but not instrumented as a unit under test
itself) — the aggregate floor is still cleared by a wide margin and the
configured threshold gate did not need to tolerate either file specifically
(both are small enough that the aggregate absorbs them).

Non-fatal noise observed in the run (not gate failures): React Router v7
future-flag warnings (advisory, no `v7_startTransition`/`v7_relativeSplatPath`
opt-in yet), a handful of "not wrapped in `act(...)`" warnings from
`AuthProvider` state updates in three hook/integration tests, and
`axe-core`'s color-contrast rule throwing "`HTMLCanvasElement.getContext` not
implemented" in jsdom on 7 of the `vitest-axe` a11y assertions. Observed facts
only: all 7 of those a11y assertions still passed (no violation was reported
by any of them); this is a documented jsdom limitation in axe-core's
color-contrast check (jsdom has no real canvas), not a claim this report can
verify axe's internal handling of; `docs/catalog/US-5.1-pipeline-status.md`
attempt 2 records that `frontend-builder` separately verified the
`vitest-axe` matcher genuinely fails on a real violation via a scratch
negative-control test (deleted after confirming) before trusting these
assertions. None of this is a hidden failure: 89/89 tests are green.

**Result: PASS.** (Matches `story-orchestrator`'s independently-run figures in
`docs/catalog/US-5.1-pipeline-status.md` attempt 2 exactly: 26/26, 89/89,
95.78/96.24/86.66/95.78.)

## Part B′ — runtime rules (grep evidence)

### 5. API-boundary containment

`grep -rn "fetch(\|axios" src/screens src/components` → one match,
`screens/SessionsScreen.tsx:33: <ErrorState kind={kind} onRetry={() =>
sessionsQuery.refetch()} />` — this is TanStack Query's `refetch()` on a query
result object, not a bare `fetch`/`axios` call; the substring match is a false
positive from `fetch` being a substring of `refetch`. No screen or component
calls the network directly.

`grep -rn "from \"react\"\|from 'react'\|@tanstack/react-query" src/api` →
zero matches. No React or TanStack Query import inside `api/`.

**Result: PASS.**

### 6. Session-token handling

`grep -rn "localStorage\|sessionStorage" src` → matches only in
`components/MfaEnrollmentBanner.{tsx,test.tsx}` (the banner's own dismissal
flag, `sessionStorage.getItem/setItem("mfaEnrollmentBannerDismissed", ...)` —
explicitly sanctioned as non-sensitive by the story's own Client State Notes:
*"dismissal state may live in `sessionStorage` (non-sensitive)"*) and in
`screens/LoginScreen.test.tsx` / `store/authStore.tsx`, both of which
**assert/document the absence** of `mfaToken` from either storage
(`expect(localStorage.getItem("mfaToken")).toBeNull()`, and a code comment
confirming `accessToken` lives in memory only). No token/credential-shaped
value is ever written to `localStorage`/`sessionStorage`.

**Result: PASS.**

### 7. Store discipline

`grep -rn "setSession\|clearSession\|setAccessToken\|setUser" src/screens
src/components src/layouts src/routes` → zero matches — no screen, component,
layout, or route guard calls a store mutator directly.

All store-mutating calls (`setSession`, `setMfaToken`, `clearSession`) occur
only inside `hooks/` files, and inspection of each (`useLogin.ts`,
`useMfaVerify.ts`, `useLogout.ts`, `useLogoutAll.ts`, `useRevokeSession.ts`)
confirms every one is invoked from that hook's `useMutation({ onSuccess: ...
})` callback, never from the hook body's synchronous return path. Example
(`hooks/useLogin.ts`):

```ts
return useMutation({
  mutationFn: authApi.login,
  onSuccess: (response) => {
    if (isMfaRequiredResponse(response)) {
      setMfaToken(response.mfa_token);
    } else {
      setMfaToken(null);
      setSession({ accessToken: response.access_token, user: response.user, ... });
    }
  },
});
```

**Result: PASS**, with one adjacent finding surfaced while checking the
broader `AGENTS.md` §3 Frontend layer table (not one of this checklist's
named items, but the same "store/ must not import api/" line the task
breakdown's own T3 verification command tests): `grep -rn "from \"\.\./api\|
from \"\.\./hooks" src/store` returns one match —
`store/authStore.tsx:13: import type { UserRead } from "../api/types";`. This
is a type-only import (erased at compile time, zero runtime coupling, and the
file's own header comment claims "Imports neither `api/` nor `hooks/`
directly ... the one exception is the neutral `session/sessionBridge` seam" —
that comment is inaccurate as written, since this is a second, undocumented
exception). It does not affect any Part A′ gate (lint/type-check both pass)
and carries no security implication (`UserRead` is a public DTO shape, not a
secret), but it is a literal violation of the layer table's "must not import"
column and of T3's own stated verification command. Recorded as a
non-blocking finding for `implementation-verifier`/`security-reviewer` to
weigh — not adjudicated here, per this skill's "reports, does not judge
architecture" contract.

`grep -rn "from \"\.\./api" src/routes` (routes must not import `api/`
directly) → zero matches. `grep -rln "from \"react-router-dom\""
src/hooks` → zero matches (the only `react-router-dom` usage under `hooks/`
is in the integration *test* file, which is test infrastructure, not the
hook module itself, and is not part of the `hooks/` layer-import rule).

### 8. Banned idioms

`grep -rn ":\s*any\b\|<any>\|as any\b" --include="*.ts" --include="*.tsx" src`
→ zero matches. `grep -rn "eslint-disable" ...` → zero matches (no blanket or
scoped suppression anywhere in the diff). `grep -rn
"console\.(log|error|warn|debug)" ...` → zero matches.

**Result: PASS.**

### 9. Contract & security spot-check

- `api/errorNormalization.ts` maps every 4xx/5xx body (RFC 7807 envelope,
  `/auth/register`'s two non-RFC7807 shapes) into `{status, message,
  fieldErrors}` using only server-supplied `detail`/`errors[].message` text;
  on an unrecognized shape it falls back to a fixed generic string
  (`"Something went wrong. Please try again."`) rather than rendering the raw
  payload. No path echoes a submitted password, access token, or recovery
  code back into a message — those values never reach this module at all
  (only server response bodies do).
- `screens/`/`components/` read errors only through
  `components/apiErrorHelpers.ts`'s structural helpers
  (`getErrorMessage`/`getFieldErrors`/`getErrorKind`), which read the same
  normalized `{status, message, fieldErrors, kind}` shape — no raw exception,
  stack trace, or JSON dump path exists in the diff.
- `frontend/package.json`'s four gate scripts confirmed present and unrenamed
  (see Required-context confirmation above).

**Result: PASS.**

### 10. `pre-commit run --all-files` (T17's named verification, alongside the four scripts)

**Not run as the literal full-hook-set command in this session**, and that is
deliberate rather than a skipped check: `pre-commit run --all-files` would
also invoke every backend hook (`ruff check --fix`, `ruff format`, `mypy`,
`lint-imports`, `unit-tests`, `detect-secrets`) against the whole repository,
which mutates tracked Python files on an auto-fix and is unrelated to this
Story's frontend-only diff — exactly the kind of drive-by scope this stage
must not cause. Two things were confirmed instead:

- `git ls-files frontend/ | wc -l` → `0`. The entire `frontend/` tree is
  untracked (`git status` showed `?? frontend/`). Pre-commit's `files: ^frontend/...`
  hook patterns match against the file list `git` hands it (staged/tracked
  paths); with zero tracked files under `frontend/`, none of the four
  frontend-scoped hooks (`frontend-lint`, `frontend-format`,
  `frontend-type-check`, `frontend-vi-mock-in-integration-tests`) can fire on
  this tree today regardless of `--all-files`, until these files are staged.
- The three frontend-scoped hooks that mirror this stage's own scripts
  (`frontend-lint` → `npm run lint`, `frontend-format` → `npm run
  format:check`, `frontend-type-check` → `npm run type-check`) invoke exactly
  those three npm scripts by `entry:` — already run directly above with
  identical results. The fourth, `frontend-vi-mock-in-integration-tests`
  (pygrep `\bvi\.mock\(` over `frontend/src/screens/*.test.tsx`), was run
  manually: `grep -rn "vi\.mock(" frontend/src/screens/*.test.tsx` → zero
  matches, same result the hook would report.

**Result: not run here via the literal `pre-commit` command — CI is the
authority for the full hook set once these files are staged/committed
(`AGENTS.md` §6's "Where checks run"), but every check that hook set performs
on `frontend/` content was independently reproduced above with identical
expected results.**

## Verdict

**PASS.** Every Part A′ script was actually run in this session with output
captured above; all four passed, matching the coverage floor (mechanically
enforced via `vite.config.ts`'s `coverage.thresholds`) and the figures
independently recorded by `story-orchestrator`. Every Part B′ item was
checked with grep/read evidence and is compliant, with one non-blocking
finding (the `store/authStore.tsx` type-only import from `api/types`, §7
above) surfaced for downstream review. `pre-commit run --all-files` itself
was not run as a literal command — `frontend/` is entirely untracked so its
scoped hooks cannot fire regardless, and running the full backend hook set
would mutate unrelated tracked Python files — but every check that hook set
would perform on `frontend/` content (the three npm scripts plus the
`vi.mock()` pygrep) was independently reproduced with identical results,
labeled explicitly as not-run-via-that-route rather than a silent pass. No
check was skipped without disclosure, and no bypass (`--no-verify`, a
narrowed script, a coverage exclude, a blanket `eslint-disable`) was proposed
or needed.

## Non-blocking findings

1. `store/authStore.tsx:13` type-only-imports `UserRead` from `../api/types`,
   contradicting the file's own comment and the letter of `AGENTS.md` §3's
   Frontend layer table (`store/` must not import `api/`) and T3's literal
   verification grep. Zero runtime coupling (erased by TypeScript) and no
   security implication, but worth `implementation-verifier`/
   `security-reviewer` explicitly deciding whether a shared-types module
   (e.g. re-exporting DTO shapes outside `api/`) is warranted, or whether the
   comment should simply be corrected to name this as a second sanctioned
   exception.
2. `frontend/.eslintrc.cjs` shows 0% coverage and is not caught by
   `vite.config.ts`'s `coverage.exclude` glob (`**/*.config.*` does not match
   `.eslintrc.cjs`). Cosmetic — it is tooling config, not app logic — but the
   exclude list could be tightened.
3. `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical)
   in dev-dependency transitive packages (per
   `docs/catalog/US-5.1-pipeline-status.md`), not triaged this pass.
