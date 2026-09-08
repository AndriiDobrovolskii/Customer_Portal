---
artifact_type: pr_summary
story: US-5.2
version: 1
status: DRAFT
created_at: "2026-09-08T15:10:00Z"
updated_at: "2026-09-08T15:10:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/stories/US-5.2-account-self-service-ui.md
    version: null
  - path: docs/specifications/US-5.2-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.2-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.2-implementation-plan.md
    version: 1
  - path: docs/evidence/US-5.2-implementation-report.md
    version: 1
  - path: docs/evidence/US-5.2-quality-gate-report.md
    version: 1
  - path: docs/verification/US-5.2-implementation-verification.md
    version: 1
  - path: docs/reviews/security/US-5.2-security-review.md
    version: 1
  - path: docs/reviews/reconciliation/US-5.2-reconciliation.md
    version: 1
  - path: docs/reconciliation/US-5.2-traceability.md
    version: 1
supersedes: null
---

# PR Draft: Account & Profile Self-Service — Frontend (US-5.2)

## Gate confirmation

All four required upstream gates confirmed **Pass** directly from their reports (not from a verbal summary):

| Gate | Verdict | Source |
|---|---|---|
| gate-enforcer | PASS | `docs/evidence/US-5.2-quality-gate-report.md` v1 (Verdict section: "**PASS.**"); also recorded in `docs/workflow/history.jsonl` (2026-09-08T17:45:00Z, `QUALITY_GATE → IMPLEMENTATION_VERIFICATION`) |
| implementation-verifier | PASS | `docs/verification/US-5.2-implementation-verification.md` v1, `status: APPROVED` |
| reconciliation-reviewer | PASS | `docs/reviews/reconciliation/US-5.2-reconciliation.md` v1, `status: APPROVED` |
| security-reviewer | PASS | `docs/reviews/security/US-5.2-security-review.md` v1, `status: APPROVED` |

`HUMAN_PR_APPROVAL` was already granted by the human (`sbruhov@gmail.com`, 2026-09-08), confirmed before drafting this content.

**Staleness check (mechanical, not taken from artifact front matter alone):** no file under `frontend/src` has an mtime newer than `docs/reviews/reconciliation/US-5.2-reconciliation.md` (2026-09-08 17:51:28 local) — `stale_reconciliation` does not apply.

## PR Title

```
feat: frontend account & profile self-service (US-5.2)
```

## Summary

Extends US-5.1's `frontend/` tree with the account-and-profile self-service surface: profile editing (write-only in the interim, pending a backend `GET /profile`), email change and confirmation, email verification landing and resend, MFA enrollment (enroll → activate → one-time recovery-code display) and disable, and account deactivation — plus the client-side validation, problem+json error rendering, and network/server-failure handling shared across all of these screens. No backend, API, or DB file is touched (`API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE`, confirmed by `design_review` v1 and `impact_analysis` v1).

Delivered screens/flows (FR-1..FR-10, all traced to PS-AC1..PS-AC7 / XC-AC1..XC-AC3):
- **Profile edit** (`ProfileScreen.tsx`, `/settings/profile`) — `PATCH /profile` with only changed fields; per OD-1's human-resolved default, `If-Match` is always sent (the cached ETag, or `"*"` when none is known yet — not omitted); a `200` refreshes the cached ETag, a `202` shows a "confirm the link sent to `<pending_email>`" state and clears the cached ETag, a `412` renders a "changed elsewhere, reload" conflict state.
- **Email confirmation** (`ConfirmEmailChangeScreen.tsx`, `/confirm-email-change`) — `POST /profile/confirm-email-change`, reachable signed-in or signed-out (sits outside both route guards).
- **Email verification** (`EmailVerificationScreen.tsx`, `/verify-email`) — `POST /auth/verify-email` with distinct success/expired/invalid outcomes, plus a resend control (`POST /auth/verify-email/resend`) that shows one generic confirmation regardless of whether the address exists.
- **MFA enrollment** (`SecurityScreen.tsx`, `/settings/security`) — per OD-2's human-resolved default, enroll requires `current_password`; `POST /auth/mfa/enroll` returns a `secret`/`otpauth_uri` rendered as a locally-generated QR (`QrCode.tsx`, `qrcode.react`, no network call); `POST /auth/mfa/activate` returns `recovery_codes` shown exactly once (`RecoveryCodesDisplay.tsx`, copy/download, no persistence) behind an explicit "I saved these" confirmation gate.
- **MFA disable** (`SecurityScreen.tsx`) — per OD-2's resolution, requires `current_password` + TOTP `code`; `DELETE /auth/mfa`; confirmation step names the session-revocation consequence explicitly. The enroll-vs-disable branch is driven by a new `authStore.mfaEnabled` signal derived from the existing login-response shape (Plan Change 6) — not a blind default — because the backend's `enroll_mfa` has no already-enabled guard and would silently overwrite a working TOTP secret otherwise.
- **Account deactivation** (`DeactivateAccountScreen.tsx`, `/settings/deactivate`) — per OD-4's resolution, `current_password` is unconditionally required; `POST /account/deactivate` on `200` clears all in-memory auth state and lands on `/login` with a confirmation message (an additive change to `LoginScreen.tsx` to render it).
- Shared: problem+json 4xx/`422` field-mapping (FR-8), client-side validation blocking submission with no API call (FR-9), retry-capable error state for network/5xx (FR-10).
- Infra: `httpClient.ts` gains an additive `httpPatch<T>` exposing `{data, status, headers}` (needed for `ETag`); `MfaEnrollmentBanner.tsx` (US-5.1) gains a link into the new enrollment flow.

**Story:** `docs/stories/US-5.2-account-self-service-ui.md`
**Spec:** `docs/specifications/US-5.2-spec.md` (v2, APPROVED)
**Implementation plan:** `docs/plans/US-5.2-implementation-plan.md` (v1, APPROVED)

### New dependency added (explicit `AGENTS.md` §7.8 sign-off, per Plan Change 9/Risk 2)

- `qrcode.react` — a thin, no-network SVG QR renderer, isolated to one adapter component (`components/QrCode.tsx`), for FR-5's "locally rendered QR, never an external service" requirement. Confirmed present in `frontend/package.json`; `QrCode.test.tsx` confirmed executing and passing in the 192/192 suite.

### Four Open Decisions resolved by the human at `HUMAN_SPEC_APPROVAL`, reflected directly in shipped code

- **OD-1** — `If-Match: *` sent whenever no ETag is known (spec v2 FR-2), superseding PS-AC2's literal "omitted otherwise" wording. Independently re-assessed by `security-reviewer`: behaviorally equivalent to omission under RFC 7232 §3.1 for an always-existing resource — no incremental exposure.
- **OD-2** — `current_password` required on MFA enroll; `current_password` + TOTP `code` required on MFA disable, plus an explicit session-revocation warning (spec v2 FR-5/FR-6).
- **OD-4** — `current_password` unconditionally required on deactivation; password-less accounts excluded from self-service deactivation (spec v2 FR-7, Out of Scope).

### Three Open Decisions remain OPEN by design, not resolved by this PR

`docs/decisions/US-5.2-open-decisions.md` v2 — OD-3 (no forced navigation for enrollment-scoped-token `403`s; banner-link-only, per the spec's own scope), OD-5 (no backend `GET /profile`/`GET /users/me` exists yet — PS-AC1/FR-1 is deferred, not built), OD-6 (locale list shipped as the current two-item placeholder, `en-US`/`en-GB`, via one shared `SUPPORTED_LOCALES` constant so a later expansion is a one-line change), OD-7 (timezone input uses the full `Intl.supportedValuesOf("timeZone")` set at runtime, not a curated subset — a pragmatic default, no new dependency). None blocks this PR; each is designed around with a documented, reversible default per `docs/plans/US-5.2-implementation-plan.md` Risks 1/4/5 and `docs/reconciliation/US-5.2-traceability.md`.

## Test Plan

`docs/reviews/reconciliation/US-5.2-reconciliation.md` (v1) confirms every one of the 10 spec ACs (PS-AC1–PS-AC7, XC-AC1–XC-AC3) has a `docs/tests/US-5.2-ac-test-matrix.md` row, every cited test function was confirmed to exist and execute, and test bodies were read directly (not just checked for proximity) for every deviation-bearing and highest-risk row:

- [x] PS-AC1 — Profile view: spec-sanctioned deferral (no backend read endpoint, OD-5); positively pinned by `test_profile_screen_starts_blank_write_only_interim_with_no_prefilled_values` (write-only interim behavior, not the deferred read).
- [x] PS-AC2 — Profile edit: only changed fields sent; first write in a session sends `If-Match: *`; a second write echoes the cached ETag; a `412` renders the "changed elsewhere, reload" conflict state instead of silently overwriting (12 test functions across `ProfileScreen.test.tsx`, `useProfileUpdate.test.ts`, `httpClient.test.ts`).
- [x] PS-AC3 — Email change: `202` shows the pending-confirmation state with the primary email unchanged; confirmation succeeds both signed-in and signed-out (9 test functions).
- [x] PS-AC4 — Email verification: success/expired/invalid render distinctly; resend shows one generic confirmation regardless of address existence (11 test functions).
- [x] PS-AC5 — MFA enrollment: QR rendered locally from `otpauth_uri` with the manual secret; recovery codes displayed exactly once (`toHaveLength(1)` asserted directly); cannot complete without explicit save-confirmation; secret/`otpauth_uri`/recovery codes never reach storage, console, or a third party (spied directly) (17 test functions).
- [x] PS-AC6 — MFA disable: `current_password` + `code` required; confirmation names the session-revocation consequence (asserted via "session"/"revok" text present); successful disable reflects MFA as disabled (7 test functions).
- [x] PS-AC7 — Deactivation: `current_password` unconditionally required (submission blocked, zero API calls, when empty); confirmation step names the consequence before final submit; success clears auth state and lands on `/login` with a confirmation message (5 test functions).
- [x] XC-AC1 — problem+json `detail`/mapped message rendering, `422` `errors[]` → field mapping, no raw JSON/stack trace (8 test functions).
- [x] XC-AC2 — Client-side validation blocks submission with a field-level error and zero API calls (`apiCalled === false` asserted directly), for every form (6 test functions).
- [x] XC-AC3 — Network error / 5xx → retry-capable error state (a `retry` button asserted present), never a blank screen or unhandled exception (8 test functions).
- [x] Route guards — the three new `ProtectedRoute`-wrapped settings routes redirect an unauthenticated visitor to `/login`; `/verify-email` and `/confirm-email-change` render for both an authenticated and unauthenticated visitor (7 test functions in `AppRoutes.test.tsx`, cited by name in `docs/verification/US-5.2-implementation-verification.md` §5).

**Mechanical gate** (`docs/evidence/US-5.2-quality-gate-report.md`, re-run live in-session per `AGENTS.md` §7.9): `npm run lint`, `npm run format:check`, `npm run type-check`, `npm run test:coverage` all green — **44/44 test files, 192/192 tests**, coverage **96.71% / 94.57% / 85.39% / 96.71%** (statements/branches/functions/lines), all four clear the 85% floor (functions the tightest margin, 85.39%).

**Security** (`docs/reviews/security/US-5.2-security-review.md`): all applicable AGENTS.md §7 checks Pass or N/A by construction (password-hashing/credential-at-rest/`extra="forbid"`/parameterized-SQL — no such layer exists in `frontend/`); access token confirmed memory-only; refresh token confirmed never read/stored/parsed by client code (including the new `httpPatch` 401→refresh→retry branch); MFA secret/`otpauth_uri`/recovery codes/`current_password` confirmed to never reach `localStorage`/`sessionStorage`/the console/a third party, with tests that spy on `Storage.prototype.setItem` and `console.*` directly. Two Low advisory findings (mutation-cache retention of sensitive values in-heap-only, not a leak; a pre-existing `sessionBridge.ts` seam gaining a second reader) — neither touches a §7 non-negotiable.

## Risk / Rollback

- This is an additive extension of the already-shipped `frontend/` tree with no backend/DB change — rollback is reverting the `frontend/` diff; nothing in the existing backend is at risk.
- **One Minor, non-blocking finding**, carried by `implementation-verifier`, `reconciliation-reviewer`, and `security-reviewer` alike: `frontend/src/screens/ProfileScreen.tsx:14` imports `SUPPORTED_LOCALES` and two types directly from `../api/types`, a letter-of-the-rule `AGENTS.md` §3 layer-table violation (screens must not import `api/` directly), contradicting the file's own header comment. `api/types.ts` has zero imports of its own and no import-time side effect — no live path into `httpClient`/`fetch`, no secret involved. Same class and verdict as US-5.1's own precedent (`authStore.tsx:13`). Mechanical fix recommended (not blocking): relocate `SUPPORTED_LOCALES` to a neutral module or re-export via `useProfileUpdate.ts`, and correct the header comment.
- **Observation, non-blocking:** `httpPatch` (`api/httpClient.ts:171-204`) re-implements its own 401→refresh→retry branch rather than routing through the existing `performRequest` helper that already has one. Both copies are correct and tested today; a future fix to one will not automatically reach the other.
- Three Open Decisions remain OPEN (OD-3, OD-6, OD-7) plus OD-5 (no backend profile-read endpoint) — see Summary. None blocks this PR; each is designed around with a reversible, documented default.
- `npm install` reported 8 vulnerabilities (5 moderate, 1 high, 2 critical) in dev-dependency transitive packages — not triaged this pass, same finding as US-5.1's own pipeline record; dev-only, not shipped to production.

## `.env.example`

- **No change required or made.** `git status --porcelain -- .env.example frontend/.env.example` shows no diff to either file. This story introduces no new backend or frontend setting — confirmed by `docs/evidence/US-5.2-quality-gate-report.md` and independently re-confirmed here. The one dependency added (`qrcode.react`) is a client-side rendering library, not a configuration value.

## Commit Hygiene

- The story's own diff is cleanly scoped: **58 files under `frontend/`** (22 modified + 36 untracked — new `api/`, `hooks/`, `screens/`, `components/` files; modified `authStore.tsx`, `AppRoutes.tsx`, `LoginScreen.tsx`, `MfaEnrollmentBanner.tsx`, `httpClient.ts`, `types.ts`, `authApi.ts`; test-infra edits to `test/mswHandlers.ts`/`test/test-utils.tsx`; `package.json`/`package-lock.json` for `qrcode.react`) — every path independently re-verified by `implementation-verifier` to map onto `task_breakdown` T1–T12's declared scope. No file outside `frontend/` is part of the code diff.
- This story's matching `docs/` pipeline artifacts are additive and story-scoped: `docs/stories/US-5.2-*`, `docs/specifications/US-5.2-*`, `docs/plans/US-5.2-*`, `docs/evidence/US-5.2-*`, `docs/verification/US-5.2-*`, `docs/reviews/*/US-5.2-*`, `docs/reconciliation/US-5.2-*`, `docs/decisions/US-5.2-*`, `docs/tests/US-5.2-*`, `docs/impact-analysis/US-5.2-*`, `docs/pr/US-5.2-pr-summary.md` (this file).
- **Flag — harness bookkeeping files outside this skill's scope, not part of the code diff:** `docs/catalog/stories.yaml`, `docs/workflow/active-story.yaml`, `docs/workflow/history.jsonl`, `docs/workflow/workflow-state.yaml` are modified in the working tree. These are `story-orchestrator`/`backlog-sync`-owned state files this delivery's own pipeline run produced — this skill does not write, stage, or evaluate them, and does not flag them as scope creep (they are the workflow's own record of this story's progress), but the human should be aware they will be part of the same commit/PR if staged together with the `frontend/` diff.
- No drive-by refactor of pre-existing backend code was found: `git status` shows no modification under `app/`.
- One additive-but-plan-named change to already-shipped US-5.1 code beyond a literal Files-To-Modify reading: `frontend/src/screens/LoginScreen.tsx` now renders `location.state.message` — required by FR-7/PS-AC7's "lands on `/login` with a confirmation message" and named explicitly in `task_breakdown` T10's own verification bullet, not an undocumented scope expansion. All 7 pre-existing `LoginScreen.test.tsx` assertions confirmed still passing.

## Pre-existing state

- **Currently on branch `main`.** No feature branch has been created for this story's work; if the human wants this reviewed as a PR rather than merged directly, a dedicated branch (e.g. `feat/us-5.2-account-self-service-ui`) should be created before pushing — this skill does not create branches or commits itself.
- `docs/workflow/active-story.yaml` (`active_story: US-5.2`) and `docs/workflow/workflow-state.yaml` agree on the active Story.

---

**This is drafted content only.** Staging, committing, pushing the branch, or opening the Pull Request all require an explicit, separate instruction from the user — none of that has been done as part of preparing this draft.
