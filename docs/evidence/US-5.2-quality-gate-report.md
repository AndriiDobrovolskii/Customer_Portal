---
artifact_type: quality_gate_report
story: US-5.2
version: 1
status: DRAFT
created_at: "2026-09-08T17:00:00Z"
updated_at: "2026-09-08T17:00:00Z"
produced_by: gate-enforcer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/plans/US-5.2-task-breakdown.md
    version: 1
  - path: docs/tests/US-5.2-ac-test-matrix.md
    version: 1
supersedes: null
---

# US-5.2 — Quality Gate Report (frontend track)

Story: `docs/stories/US-5.2-account-self-service-ui.md` (`track: frontend`).
Track command set: `AGENTS.md` §2/§6 Frontend subsections and
`gate-enforcer/SKILL.md` Part A′ / Part B′. All commands below were run
inside `frontend/` in this session (Windows / Git Bash), captured verbatim.
Nothing below is asserted from `docs/catalog/US-5.2-pipeline-status.md` or
`docs/evidence/US-5.2-test-generation-report.md` from memory — every command
was re-executed live for this report, per `AGENTS.md` §7.9, and the results
happen to match those two upstream reports' own claimed numbers exactly.

## Required-context confirmation

- `frontend/package.json` `scripts` block confirmed to contain exactly
  `lint`, `format:check`, `type-check`, `test:coverage` (plus `dev`, `build`,
  `preview`, `test`, `format:write`, none of which are gate-invoked names) —
  no rename, no missing script.
- `.pre-commit-config.yaml` confirmed to contain the four frontend-scoped
  hooks (`frontend-lint`, `frontend-format`, `frontend-type-check`,
  `frontend-vi-mock-in-integration-tests`), all scoped `files: ^frontend/...`.
- `git status --porcelain -- frontend/` shows 21 modified + 32 untracked
  paths, all under `frontend/` — a real, non-empty diff.

## Harness preconditions checked

- `docs/workflow/active-story.yaml` (`active_story: US-5.2`) and
  `docs/workflow/workflow-state.yaml` (`story: US-5.2`) agree on the active
  Story.
- `implementation_plan` (v1, `APPROVED`) and `task_breakdown` (v1,
  `APPROVED`) — `grep -n "TODO\|TBD\|FIXME\|???"` over both: zero matches.
- `docs/decisions/US-5.2-open-decisions.md` (v2) logs OD-1 through OD-7;
  OD-3, OD-5, OD-6, OD-7 remain `OPEN` but each is implemented per the
  approved plan's documented default (banner-link-only for OD-3;
  `SUPPORTED_LOCALES` constant for OD-6; `Intl.supportedValuesOf("timeZone")`
  combobox for OD-7; OD-5 is the backend `GET /profile` gap the story's own
  Dependencies & Blockers #1 already scopes out of this delivery) — none is
  an unresolved *blocking* Open Decision against an `APPROVED` input this
  stage depends on.
- `ac_test_matrix` is `DRAFT` (not `APPROVED`) — its normal lifecycle state
  at this point in the pipeline, not a staleness signal, matching US-5.1's
  precedent.

## Part A′ — mechanical gates

### 1. `npm run lint`

```
> customer-portal-frontend@0.1.0 lint
> eslint . --max-warnings=0
```

Exit code 0. No findings, no output beyond the script echo.

**Result: PASS.**

### 2. `npm run format:check`

```
> customer-portal-frontend@0.1.0 format:check
> prettier --check .

Checking formatting...
All matched files use Prettier code style!
```

Exit code 0. Check-only script — no drift.

**Result: PASS.**

### 3. `npm run type-check`

```
> customer-portal-frontend@0.1.0 type-check
> tsc -b --noEmit
```

Exit code 0. No diagnostics against the whole `frontend/` project.

**Result: PASS.**

### 4. `npm run test:coverage`

```
> customer-portal-frontend@0.1.0 test:coverage
> vitest run --coverage

 Test Files  44 passed (44)
      Tests  192 passed (192)

=============================== Coverage summary ===============================
Statements   : 96.71% ( 4442/4593 )
Branches     : 94.57% ( 819/866 )
Functions    : 85.39% ( 152/178 )
Lines        : 96.71% ( 4442/4593 )
================================================================================
```

Re-run a second time with the exit code captured explicitly: `EXIT_CODE=0`.
44/44 test files passed, 192/192 tests passed, 0 failures. Coverage: 96.71%
statements, 94.57% branches, 85.39% functions, 96.71% lines — all four clear
the 85% floor (`AGENTS.md` §5 Frontend subsection). Functions is the tightest
margin (85.39% vs the 85% floor, 152/178) — per-file table confirms
`store/queryClient.ts` (previously the 0%-covered gap that failed attempt 1
of `test:coverage` at 84.91% functions) is now 100% across all four metrics
via the new `store/queryClient.test.ts`.

These figures match `docs/catalog/US-5.2-pipeline-status.md` attempt 2's own
independently-recorded numbers exactly (44 files / 192 tests;
85.39/96.71/94.57/96.71).

Non-fatal noise observed in the run (not gate failures): React Router v7
future-flag warnings (advisory), consistent with US-5.1's own precedent.

**Result: PASS.**

## Part B′ — runtime rules (grep evidence, independently re-run)

### 5. API-boundary containment

`grep -rn "fetch(\|axios" screens components --include="*.tsx" --include="*.ts"`
(excluding `.test.` files) → one match:
`screens/SessionsScreen.tsx:33: <ErrorState kind={kind} onRetry={() =>
sessionsQuery.refetch()} />` — TanStack Query's `refetch()` on a query result
object, not a bare `fetch`/`axios` call; the substring match is a false
positive from `fetch` being a substring of `refetch` (the same pre-existing
US-5.1 line, unmodified by this Story). No screen or component calls the
network directly.

`grep -rln "from \"react\"\|@tanstack/react-query" api` (excluding `.test.`
files) → zero matches. No React or TanStack Query import inside `api/`.

**Result: PASS.**

### 6. Session-token handling

`grep -rn "localStorage\|sessionStorage" api hooks screens components store`
(excluding `.test.` files) → matches only in
`components/MfaEnrollmentBanner.tsx` (pre-existing US-5.1 non-sensitive
dismissal flag, `sessionStorage.getItem/setItem("mfaEnrollmentBannerDismissed",
...)`, untouched in substance by this Story beyond an additive link) and one
explanatory comment in `store/authStore.tsx` documenting that `accessToken`
is memory-only. Also independently grepped every new US-5.2 source file
(`SecurityScreen.tsx`, `ProfileScreen.tsx`, `DeactivateAccountScreen.tsx`,
`EmailVerificationScreen.tsx`, `ConfirmEmailChangeScreen.tsx`,
`RecoveryCodesDisplay.tsx`, `QrCode.tsx`, all eight new `hooks/`, and
`accountApi.ts`/`mfaApi.ts`/`profileApi.ts`) for
`localStorage|sessionStorage|console\.(log|error|warn)` — zero matches. No
token/credential/secret/recovery-code-shaped value is ever written to either
storage API or logged.

**Result: PASS.**

### 7. Store discipline

`grep -rn "setSession(\|setMfaEnabled(" hooks screens components`
(excluding `.test.` files) → all four call sites are inside `hooks/`
(`useLogin.ts`, `useMfaVerify.ts`, `useMfaActivate.ts`, `useMfaDisable.ts`).
Read `useLogin.ts` directly to confirm placement:

```ts
return useMutation({
  mutationFn: authApi.login,
  onSuccess: (response) => {
    if (isMfaRequiredResponse(response)) {
      setMfaToken(response.mfa_token);
    } else {
      setMfaToken(null);
      setSession({ accessToken: ..., user: ..., mfaEnabled: false });
    }
  },
});
```

`useMfaActivate.ts`'s and `useMfaDisable.ts`'s `onSuccess: () =>
setMfaEnabled(true/false)` confirmed the same way. No screen or component
calls a store mutator directly.

**Result: PASS.**

### 8. Banned idioms

`grep -rnE ":\s*any\b|<any>|as any\b"` over every changed non-test `api/`,
`components/`, `hooks/`, `routes/`, `screens/`, `store/`, `test/` file →
zero matches. `grep -rn "eslint-disable"` over the same set → zero matches.
`grep -rn "console\.(log|error|warn)"` over the same set (non-test files)
→ zero matches.

**Result: PASS.**

### 9. Contract & security spot-check

- `components/apiErrorHelpers.ts` (read in full) exposes only
  `getErrorStatus`/`getErrorKind`/`getErrorMessage`/`getFieldErrors`, each
  reading a structural `{status, message, fieldErrors, kind}` shape off the
  caught `error: unknown` — this shape is populated upstream from the
  server's own response body (`api/httpClient.ts`'s `ApiError`), never from
  a raw JS `Error.message`/stack trace. No path in the new US-5.2 diff
  echoes a submitted `current_password`, TOTP `code`, `secret`,
  `otpauth_uri`, or `recovery_codes` value back into a rendered message —
  confirmed by the storage/console grep above finding zero hits in any
  screen/component/hook that handles those values, consistent with
  `docs/catalog/US-5.2-pipeline-status.md`'s own self-check and the passing
  `*_never_reach_storage_console_or_third_party`-style test assertions.
- `frontend/package.json`'s four gate scripts confirmed present and
  unrenamed (Required-context confirmation above).

**Result: PASS.**

### 10. `pre-commit run --all-files`

**Not run as the literal full-hook-set command in this session.** Unlike
US-5.1 (where the entire `frontend/` tree was untracked and its scoped hooks
therefore could not fire regardless of `--all-files`), `git ls-files
frontend/ | wc -l` here returns `82` — most of `frontend/` is now tracked
(carried over from US-5.1's prior delivery), so that earlier rationale does
not apply unchanged and is not repeated here. The reason this command was
not run as a literal invocation is instead: `--all-files` also invokes every
*backend* hook (`ruff check --fix`, `ruff format`, `mypy`, `lint-imports`,
`unit-tests`, `detect-secrets`) against the whole repository, on a diff that
touches only `frontend/` — out of this Story's scope, and `ruff --fix` would
mutate tracked Python files unrelated to this change. Instead, each hook
that actually applies to this diff (`files: ^frontend/...`) was run or
reproduced directly:

- The three frontend-scoped hooks that mirror this stage's own scripts
  (`frontend-lint` → `npm run lint`, `frontend-format` → `npm run
  format:check`, `frontend-type-check` → `npm run type-check`) invoke
  exactly those three npm scripts by `entry:` — already run directly above
  with identical results.
- The fourth, `frontend-vi-mock-in-integration-tests` (pygrep
  `\bvi\.mock\(` over `frontend/src/screens/*.test.tsx`), was run directly
  in this session: `grep -rn "vi\.mock(" src/screens/*.test.tsx` → one hit,
  `screens/DeactivateAccountScreen.test.tsx:11`, a comment line
  (`// \`vi.mock('react-router-dom')\` spy (Plan Testing Strategy).`)
  explaining *why* the file avoids that call — no actual `vi.mock(`
  invocation anywhere in `src/screens/*.test.tsx`. This independently
  confirms (rather than merely repeats) `docs/evidence/US-5.2-test-generation-report.md`'s
  own separate self-check claim of "one hit, a comment, no actual call."

**Result: not run here via the literal `pre-commit` command — CI is the
authority for the full hook set once these changes are committed
(`AGENTS.md` §6's "Where checks run"), but every hook scoped to
`frontend/` was either run directly (the three npm scripts) or reproduced
with an equivalent, independently-run command (the `vi.mock()` pygrep) with
matching results.**

## Verdict

**PASS.** Every Part A′ script was actually run in this session with output
captured above; all four passed, and the coverage numbers match the two
upstream reports' independently-recorded figures exactly (44/44 test files,
192/192 tests, 96.71%/94.57%/85.39%/96.71% stmt/branch/func/line — functions
clearing the 85% floor by a 0.39-point margin). Every Part B′ item was
checked with grep/read evidence and is fully compliant, with zero new
findings beyond what upstream reports already surfaced (see Non-blocking
findings below, carried forward). `pre-commit run --all-files` itself was
not run as a literal command for the reason given in check 10, but every
check it performs on `frontend/` content was independently reproduced with
identical results. No check was skipped without disclosure, and no bypass
(`--no-verify`, a narrowed script, a coverage exclude, a blanket
`eslint-disable`) was proposed or needed.

## Non-blocking findings

1. **Functions coverage clears the 85% floor by a narrow margin (85.39%,
   152/178).** Not a gate failure — genuinely passing — but worth noting for
   any future change to this codebase: a single additional untested
   function-heavy module could push this back under 85% the way
   `store/queryClient.ts` did in attempt 1 of `test:coverage`
   (`docs/catalog/US-5.2-pipeline-status.md`).
2. `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical)
   in dev-dependency transitive packages — not triaged this pass, same
   finding both US-5.1's and this Story's own pipeline-status record.
3. PS-AC1 ("profile view") has no test and cannot be built — no
   `GET /profile`/`GET /users/me` endpoint exists on the backend (story's own
   Dependencies & Blockers #1, OD-5). Approved spec's own deferral, carried
   forward here for `reconciliation-reviewer`'s AC-compliance pass, not
   re-adjudicated by this stage.
4. `ProfileScreen.tsx`'s "only the changed fields" diffing (FR-2) is proven
   only weakly by the current test suite, per
   `docs/evidence/US-5.2-test-generation-report.md`'s own caveat: because the
   form has no populated baseline (PS-AC1/FR-1 deferral), the test cannot
   fully exercise a scenario where a naive "send every field" implementation
   would leak an unchanged-but-populated value. It does catch sending
   empty-string values for untouched fields. Not re-adjudicated here.
