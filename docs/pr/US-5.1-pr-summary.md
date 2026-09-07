---
artifact_type: pr_summary
story: US-5.1
version: 1
status: APPROVED
created_at: "2026-09-07T23:59:00Z"
updated_at: "2026-09-07T23:59:30Z"
produced_by: pr-preparer
inputs:
  - path: docs/stories/US-5.1-authentication-session-management.md
    version: null
  - path: docs/specifications/US-5.1-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.1-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.1-implementation-plan.md
    version: 1
  - path: docs/evidence/US-5.1-implementation-report.md
    version: 1
  - path: docs/evidence/US-5.1-quality-gate-report.md
    version: 1
  - path: docs/verification/US-5.1-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.1-security-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-5.1-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-5.1-traceability.md
    version: 1
supersedes: null
---

# PR Draft: Authentication & Session Management — Frontend (US-5.1)

## Gate confirmation

All four required upstream gates confirmed **Pass** directly from their reports (not from a verbal summary or a prior stage's prose):

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | PASS | `docs/evidence/US-5.1-quality-gate-report.md` v1 (read directly — front matter `status: DRAFT`, verdict section states "**PASS.**"; not taken from `workflow-state.yaml` prose) |
| implementation-verifier | PASS | `docs/verification/US-5.1-implementation-verification.md` v1 |
| security-reviewer | PASS | `docs/reviews/security/US-5.1-security-review.md` v1 (artifact's own prose says "Pass"; `docs/workflow/artifact-lifecycle.md` §2's retired-values table maps `Pass` → `PASS`, normalized here) |
| reconciliation-reviewer | PASS | `docs/reviews/reconciliation/US-5.1-reconciliation.md` v1 |

`HUMAN_PR_APPROVAL` was already granted by the user (`sbruhov@gmail.com`, no comment — `docs/workflow/workflow-state.yaml`), confirmed before drafting this content.

## PR Title

```
feat: frontend authentication & session management (US-5.1)
```

## Summary

Stands up the Customer Portal's **first `frontend/` project** (React + Vite + TypeScript + TanStack Query + React Hook Form + `react-router-dom`) and implements the complete client-side authentication and session-management surface against the already-shipped backend `/auth/*` contract — no backend, API, or DB file is touched (`API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE`, confirmed by `design_review` v1 and `impact_analysis` v1).

Delivered screens/flows (FR-1..FR-11, all traced to FE-AC1..FE-AC11):
- **Register** (`POST /auth/register`) → lands on Login with a success message.
- **Login**, both branches: plain success (access token held in memory, redirect to placeholder home) and the **MFA-challenge branch** (`MfaRequiredResponse` → MFA-verify screen, `mfa_token` held only in transient state → `POST /auth/mfa/verify` completes login).
- **Silent 401 → refresh**: a single-flight `refreshCoordinator.ts` singleton guarantees exactly one `POST /auth/refresh` call regardless of how many concurrent requests 401 at once; all waiters retry on success, or are cleared and redirected to `/login` once (not once per waiter) on failure.
- **Logout** and **logout everywhere** (`POST /auth/logout`, `POST /auth/logout-all`).
- **Active Sessions**: list with device label/location/last-used/current marker; revoke a non-current session (`DELETE /auth/sessions/{family_id}`); the current session's own revoke control is disabled (OD-6's documented default).
- **Password reset**, request + confirm, with the backend's anti-enumeration-uniform message rendered verbatim.
- Client-side validation (React Hook Form native rules, no schema-resolver dependency) that blocks submission without calling the API, while explicitly **not** simulating the two server-only Reset-Password checks (breach / differs-from-current).
- RFC 7807 error normalization (`errorNormalization.ts`) that also absorbs Register's two non-uniform (`OD-4`) response shapes into one internal shape, and a generic retry-capable `ErrorState` for network/5xx failures.
- Route guards both directions (`ProtectedRoute`, `GuestOnlyRoute`) with post-login return-to-originally-requested-route.
- A distinct pre-auth `AuthLayout` (no sidebar/header), per the spec's NFR added specifically to close SPEC_REVIEW v1's Major finding.
- Automated accessibility coverage (`vitest-axe`, dependency sign-off explicitly granted by the user) plus manual keyboard-navigation tests on all seven screens.

**Story:** `docs/stories/US-5.1-authentication-session-management.md`
**Spec:** `docs/specifications/US-5.1-spec.md` (v2, APPROVED)
**Implementation plan:** `docs/plans/US-5.1-implementation-plan.md` (v1, APPROVED)

### New dependencies added (explicit `AGENTS.md` §7.8 sign-off granted by the user during `/so:next`)

- `react-router-dom` (v6) — no router existed in `AGENTS.md` §2's Frontend stack table or `frontend-builder`'s scaffold list; required by FR-10's route guards.
- `vitest-axe` — the story's own Enforcement Matrix names an automated a11y check as a mandatory `[gate]` row; no such tool was previously in the stack.

### Notable implementation-time correction

- **`ProtectedRoute.tsx` (attempt 1 → 2):** attempt 1 initially misdiagnosed a real bug (an unstable object identity passed to `<Navigate state=...>` causing an infinite redirect loop) as a sandbox out-of-memory condition. Root-caused and fixed in attempt 2 with a `ref` that captures the redirect target once. No AC-visible behavior changed — confirmed by `reconciliation-reviewer` against FE-AC10's literal text (`docs/reviews/reconciliation/US-5.1-reconciliation.md`, Drift Register).

### Nine Open Decisions remain OPEN by design, not resolved by this PR

`docs/decisions/US-5.1-open-decisions.md` — every OD (OD-1 CORS/cross-origin, OD-2 concurrent-401 single-flight, OD-3 proactive refresh, OD-4 Register's non-uniform error shapes, OD-5 per-screen validation rules, OD-6 current-session revoke affordance, OD-7 MFA-banner copy, OD-8 placeholder home content, OD-9 design-system choice) was **designed around** with an explicit, documented default rather than guessed at or silently resolved — each is traced to the specific file/behavior it constrains in `docs/plans/US-5.1-implementation-plan.md` Risks 2–6 and `docs/reconciliation/US-5.1-traceability.md`. None blocks this PR; a human answering any of them later is an additive follow-up, not a rework, per the plan's own framing.

## Test Plan

`docs/reconciliation/US-5.1-traceability.md` (v1) confirms every FE-AC1–FE-AC11 has exactly one `docs/tests/US-5.1-ac-test-matrix.md` row, every cited test function exists verbatim (all 89 `it()` names cross-checked by exhaustive grep — zero missing, zero mismatched), and 24 of 26 test files were read in full to confirm assertions match each AC's literal stated behavior, not just proximity:

- [x] FE-AC1 — Register: valid submission → `POST /auth/register` → `201` → lands on `/login` with success message
- [x] FE-AC2 — Login without MFA: `LoginResponse` → access token held in memory (asserted directly on the store, not just the redirect) → redirect to placeholder home; refresh cookie never read/stored by client code (verified by source-reading — no UI-level test is possible for this whole-codebase negative invariant, per `reconciliation` Finding F2)
- [x] FE-AC3 — Login with MFA: `MfaRequiredResponse` → MFA-verify screen (`mfa_token` transient-only) → valid TOTP **or** recovery code → completes login identically to FE-AC2, proven end-to-end against the real route tree
- [x] FE-AC4 — Silent refresh: two concurrent 401s trigger **exactly one** `/auth/refresh` call, both requests retry successfully; on refresh failure, in-memory state is cleared (redirect-on-failure proven by composition of two independently-tested facts — `implementation-verification` §5 and `reconciliation` Finding F1, not a gap)
- [x] FE-AC5 — Logout / logout-all: correct endpoint called, session cleared, lands on `/login` (both branches, both halves each directly asserted)
- [x] FE-AC6 — Sessions: device label/location/last-used/current marker rendered; non-current revoke removes its row without disturbing the current row; current-session revoke control disabled (OD-6 default)
- [x] FE-AC7 — Password reset: request shows the generic anti-enumeration message regardless of account existence; confirm with a valid token + compliant password lands on `/login` with a success message
- [x] FE-AC8 — Client-side validation blocks submission (empty/malformed fields) with **zero** API calls, proven via an MSW-handler-set flag, not just an error message appearing; explicit tests confirm the two server-only Reset-Password checks are **not** simulated client-side
- [x] FE-AC9 — RFC 7807 `detail`/`type` mapping, `422` `errors[]` → field mapping, both of Register's non-uniform shapes (OD-4) normalize correctly, unrecognized shapes fall through to a fixed generic string (never a raw JSON dump)
- [x] FE-AC10 — Route guards both directions plus "remembers the originally-requested route," proven through the real route tree (no `vi.mock('react-router-dom')`)
- [x] FE-AC11 — Network error and 5xx response per screen → generic retry-capable `ErrorState`, retry button invokes its callback, never a blank screen
- [x] a11y bar — automated `vitest-axe` check (no detectable violations) on all seven screens, plus manual full-keyboard-navigation test

**Mechanical gate** (`docs/evidence/US-5.1-quality-gate-report.md`, re-verified independently by `story-orchestrator` after the sub-agent's own report): `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage` all green — **26/26 test files, 89/89 tests**, coverage **95.78% / 96.24% / 86.66% / 95.78%** (statements/branches/functions/lines), all clear the 85% floor.

**Security** (`docs/reviews/security/US-5.1-security-review.md`): all applicable AGENTS.md §7/§3-Frontend checks Pass (password-hashing/credential-at-rest/`extra="forbid"`/parameterized-SQL are N/A by construction — no such layer exists in `frontend/`); zero `console.*` calls anywhere in `frontend/src`; access token confirmed memory-only; refresh cookie confirmed never read/parsed by client code; no password/token/recovery-code value reaches a rendered error. Zero findings, blocking or non-blocking — this skill's verdict is Pass/Fail only.

## Risk / Rollback

- This is a purely additive, brand-new `frontend/` tree with no backend/DB change — rollback is simply not merging/removing the `frontend/` directory; nothing in the existing backend is at risk.
- One Minor, non-blocking finding carried by both `implementation-verifier` and `reconciliation-reviewer`: `frontend/src/store/authStore.tsx:13` type-only-imports `UserRead` from `../api/types`, a letter-of-the-rule violation of `AGENTS.md` §3's Frontend layer table (`store/` must not import `api/`). It is `import type` (erased at compile time, zero runtime coupling), carries no security exposure (`UserRead` is `{id, email}`), and does not change either verdict. Recommended follow-up (not blocking this PR): relocate the shared DTO to a neutral module (the same pattern already used for `session/sessionBridge.ts`), or amend `authStore.tsx`'s header comment to name this as a second sanctioned exception.
- Nine Open Decisions (see Summary) remain OPEN. If OD-1 (CORS/cross-origin) is later answered toward an actual backend CORS/`allow_credentials` change rather than the same-origin dev-proxy default this PR ships, `app/main.py`'s CORS middleware becomes newly affected and both `design_review`'s `NOT_APPLICABLE` verdict and this Story's "zero backend file changes" premise would need to be revisited — flagged and carried forward through every stage from `impact_analysis` onward, not a surprise.
- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical) in dev-dependency transitive packages, not triaged in this pass (`docs/catalog/US-5.1-pipeline-status.md` v2, Non-blocking findings) — worth a follow-up `npm audit` pass, does not block this PR (dev-only dependencies, not shipped to production).

## `.env.example`

- **`frontend/.env.example` (new file, confirmed present and correctly scoped):** documents `VITE_API_BASE_URL` as commented-out/not-currently-needed, with an explanatory comment that the dev server proxies `/api` to the backend (OD-1's same-origin default) so no target URL needs injecting today. Correctly kept separate from the repo-root `.env.example`.
- **Repo-root `.env.example`:** confirmed unchanged — no backend setting was added or modified by this story (`git diff` shows zero touch to `app/core/config.py` or the root file); consistent with `API_DESIGN`/`DB_DESIGN` both being `NOT_APPLICABLE`.

## Commit Hygiene

- The story's own deliverable is cleanly scoped: the entire `frontend/` tree (new, ~53 files: scaffold/config, `api/`, `store/`, `session/`, `routes/`, `layouts/`, `screens/`, `components/`, `hooks/`, `test/`) plus its matching `docs/` workflow artifacts (`docs/stories/US-5.1-*`, `docs/specifications/US-5.1-*`, `docs/plans/US-5.1-*`, `docs/evidence/US-5.1-*`, `docs/verification/US-5.1-*`, `docs/reviews/*/US-5.1-*`, `docs/reconciliation/US-5.1-*`, `docs/decisions/US-5.1-*`, `docs/tests/US-5.1-*`, `docs/catalog/US-5.1-pipeline-status.md`, `docs/impact-analysis/US-5.1-*`) and `docs/intent/EPIC-5-story-5.1-auth.md`.
- **Flag — scope beyond this story's own code, needs a human decision before staging:** the working tree also carries a substantial set of **modified, currently-tracked** files that are not `frontend/` code or US-5.1 docs: `.claude/skills/gate-enforcer/SKILL.md`, `.claude/skills/implementation-planner/SKILL.md`, `.claude/skills/implementation-verifier/SKILL.md`, `.claude/skills/plan-reviewer/SKILL.md`, `.claude/skills/planner/SKILL.md`, `.claude/skills/security-reviewer/SKILL.md`, `.claude/skills/story-orchestrator/SKILL.md` and its `references/continue-flow.md`, `.claude/skills/test-writer/SKILL.md`, `.pre-commit-config.yaml`, `AGENTS.md`, `docs/catalog/stories.yaml`, and the harness state files `docs/workflow/active-story.yaml`, `docs/workflow/artifact-lifecycle.md`, `docs/workflow/artifact-schema.md`, `docs/workflow/history.jsonl`, `docs/workflow/stage-map.yaml`, `docs/workflow/workflow-state.yaml`, plus a new untracked `.claude/skills/frontend-builder/` directory. These appear to be the harness's own infrastructure updates needed to *support* a frontend-track story at all (adding the `frontend-builder` skill, `AGENTS.md`'s Frontend subsections, the frontend-scoped pre-commit hooks, and the workflow-state schema/history entries this delivery itself produced) rather than an unrelated drive-by refactor — but that is this skill's inference, not a confirmed fact, and per `AGENTS.md` §7.8/§7.9 several of these (`AGENTS.md` itself, `.pre-commit-config.yaml`) are protected files. **Recommend the user confirm these are intended to ship in the same PR as US-5.1's frontend code** (a harness-capability PR bundled with its first real consumer) rather than split into a separate PR — this skill does not stage, split, or commit anything itself.
- Also present, untracked, and not obviously part of US-5.1: none found beyond the above — no stray log/cache files were seen in `git status --porcelain`.
- No drive-by refactor of pre-existing backend code was found anywhere in the diff (confirmed: `git status` shows no modification under `app/`).

## Pre-existing uncommitted state

This story's entire implementation (code, tests, and every upstream workflow artifact) exists only in the working tree on branch `fix/hook-log-path-cwd-independent` — no commit has been made yet for US-5.1, and the branch name does not reflect this story's scope (worth renaming or re-basing onto a dedicated branch before opening the PR, at the user's discretion).

`docs/workflow/active-story.yaml` (`active_story: US-5.1`) and `docs/workflow/workflow-state.yaml` (`story: US-5.1`) agree on the active Story — confirmed by reading both directly, per this stage's harness Preconditions.

**`stale_reconciliation` does not apply, checked mechanically, not asserted from the artifact's own (unreliable) timestamp:** the newest file under `frontend/src` (`routes/ProtectedRoute.tsx`) has an mtime of 2026-09-07 06:38:45 UTC; `docs/reviews/reconciliation/US-5.1-reconciliation.md` has an mtime of 2026-09-07 07:16:39 UTC — reconciliation was written after the last source-file change, so it reviewed exactly this working-tree state.

---

**This is drafted content only.** Staging, committing, pushing the branch, or opening the Pull Request all require an explicit, separate instruction from the user — none of that has been done as part of preparing this draft.
