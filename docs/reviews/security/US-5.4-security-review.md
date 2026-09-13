---
artifact_type: security_review
story: US-5.4
version: 1
status: DRAFT
created_at: "2026-09-13T22:00:00Z"
updated_at: "2026-09-13T22:00:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-5.4-admin-console-ui.md
    version: null
  - path: docs/specifications/US-5.4-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.4-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.4-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.4-implementation-plan.md
    version: 2
  - path: docs/reviews/plans/US-5.4-plan-review.md
    version: 2
  - path: docs/evidence/US-5.4-implementation-report.md
    version: 2
  - path: docs/verification/US-5.4-implementation-verification.md
    version: 1
  - path: docs/tests/US-5.4-test-strategy.md
    version: 1
  - path: docs/tests/US-5.4-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.4-open-decisions.md
    version: 2
supersedes: null
---

# Security Review: Admin Console (Frontend)

**Story ID:** US-5.4
**Reviewed:** 2026-09-13
**Overall Verdict:** PASS

## Summary

`track: frontend` (`docs/stories/US-5.4-admin-console-ui.md` front matter), so per this skill's own routing instruction, checks 1/2/4/5 of the AGENTS.md §7 checklist (Argon2id password storage, no reversible credential encryption, `extra="forbid"`+privilege-field exclusion, parameterized SQL) are **N/A by construction** — this diff adds no password hashing, no credential-at-rest storage, no Pydantic schema, and no SQL; there is no backend/API/DB surface in this Story (`api_design`/`openapi`/`database_design`/`entity_model` all recorded `NOT_APPLICABLE`). In their place I independently re-verified the frontend-specific invariants AGENTS.md §3's Frontend subsection states — access-token-in-memory-only, refresh-token-never-touched-client-side, no sensitive value reaching a log call or a rendered error — directly against the current repository state (not taken on the prior implementation-verification report's word), plus the narrower auth-failure-uniformity check (the frontend adds no differentiation on top of the server's 403). All items are clean. Overall Verdict: **PASS**, with one Low advisory finding carried forward.

Harness preconditions independently checked before writing this report: `docs/workflow/active-story.yaml` (`active_story: US-5.4`) and `docs/workflow/workflow-state.yaml` (`story: US-5.4`, `current_stage: SECURITY_REVIEW`) agree on the active story. Every input's front-matter `version:` was read directly off disk and matches the version recorded in this report's own `inputs` (spec v2/APPROVED, spec-review v2/APPROVED, impact-analysis v2/DRAFT, implementation-plan v2/DRAFT, plan-review v2/DRAFT, implementation-report v2/DRAFT, implementation-verification v1/DRAFT, test-strategy v1/DRAFT, ac-test-matrix v1/DRAFT, open-decisions v2/DRAFT) — none is `SUPERSEDED` or `ARCHIVED`; the non-`APPROVED` statuses are expected per `artifact-lifecycle.md` §1 ("an artifact stays `DRAFT` even after its owning review stage returns `PASS`" until a human gate bumps it), not staleness. `docs/decisions/US-5.4-open-decisions.md` v2 was read directly: all four Open Decisions (OD-1–OD-4) are marked `RESOLVED`. `grep -n "TODO\|TBD\|FIXME\|???"` over the two `APPROVED` inputs (`US-5.4-spec.md` v2, `US-5.4-spec-review.md` v2) returns zero matches.

## AGENTS.md §7 Non-Negotiable Checklist

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | `track: frontend`; no password hashing exists anywhere in `frontend/`. `git status --porcelain` (re-run directly, not the conversation's earlier snapshot) confirms every code file this Story touches is under `frontend/` (`api/`, `hooks/`, `screens/`, `store/`, `layouts/`, `routes/`, `test/`) — the only non-`frontend/` changes in the tree are the workflow/catalog/docs artifacts this and prior stages produced (`docs/catalog/stories.yaml`, `docs/workflow/*`, `docs/specifications/`, `docs/plans/`, etc.), none of which contain executable code. |
| No plaintext/reversible encryption for credentials | N/A | No credential-at-rest storage in this stack; the access token lives only in the in-memory reducer state in `frontend/src/store/authStore.tsx` (see below), never written to any storage medium. |
| No tokens/hashes/PII in logs; no `print()` | Pass | Widened check (bare `console\.`, not just the `log\|error\|warn\|info\|debug` method whitelist, so `table`/`trace`/`dir`/`group`/bracket-access variants are also covered): `grep -rn "console\." frontend/src` returns exactly one hit, `frontend/src/screens/AdminAuditLogScreen.tsx:12` — a comment ("... console. Composed from hooks/, store/ ...") documenting the rule, not an invocation. Zero actual `console.*` calls exist anywhere in `frontend/src`. `print()` has no JS/TS equivalent invoked anywhere in the diff. Independently re-run against the current tree, not taken from the prior verification report. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A | No Pydantic schema exists in this stack — the frontend has no request-schema layer of that kind. The frontend analogue (request payload shape) is checked below under Advisory Findings for completeness, not as a §7 item. |
| Parameterized SQL only, no string interpolation | N/A | No SQL, no ORM, no `models.py`/`repository.py` in this diff — purely a frontend consuming an already-delivered backend contract. |
| Uniform auth-failure response, no differentiation leaked | Pass | Narrowed to: does the frontend itself add differentiation on top of the backend's already-uniform response? Two layers checked. (1) The 403-handling layer: `frontend/src/screens/AdminUserListScreen.tsx:42`, `frontend/src/screens/AdminUserDetailScreen.tsx:173`, and `frontend/src/screens/AdminAuditLogScreen.tsx:60` each branch on a single `errorStatus === 403` check and render one generic "not permitted" state — no branch inspects the problem+json `detail`/`type` to render a different message per failure reason. (2) The 401/session layer, this Story's own modified file: `frontend/src/api/httpClient.ts:141`, `:226`, and `:271` are the three post-refresh-attempt `catch` blocks (in `performRequest`, `httpPatch`, and `httpGetWithMeta` respectively) — each throws the identical `new ApiError({ status: 401, message: "Your session has expired. Please log in again." })` regardless of whether the refresh failed because the token was expired, malformed, or revoked; the bare `catch` never inspects the refresh failure's cause before choosing the message. `frontend/src/api/errorNormalization.ts:51-74` (`normalizeApiError`) passes the backend's own `detail` straight through into `message` for any other 4xx and falls back to one generic string (`GENERIC_MESSAGE`, line 22) for any unrecognized shape — it never fabricates or varies wording based on which specific check failed server-side. |

## Frontend-Specific Invariants (AGENTS.md §3 Frontend subsection, in place of N/A backend checks)

| Item | Result | Evidence |
|---|---|---|
| Access token in memory only, never `localStorage`/`sessionStorage` | Pass | `frontend/src/store/authStore.tsx`: `accessToken` lives only in `useReducer` state (lines 16-95); no `localStorage`/`sessionStorage` call anywhere in the file (only a header comment at line 2 documents the rule). Repo-wide `grep -rn "localStorage\|sessionStorage" frontend/src` returns matches only in unrelated pre-existing US-5.1/US-5.2 files (`MfaEnrollmentBanner.tsx`, `LoginScreen.test.tsx`, `AppShell.test.tsx`) for a non-sensitive UI-dismissal flag — none in any US-5.4 file (`adminApi.ts`, the nine `hooks/use{Admin,AuditLogs}*` files, the four `Admin*Screen.tsx` files, `decodeTokenScopes.ts`). |
| Refresh token never read, stored, or parsed by client code | Pass | `frontend/src/api/httpClient.ts:93-100` (`performRefreshRequest`) calls `POST /auth/refresh` with `credentials: "include"` and reads only the JSON response body (`RefreshResponse`, which carries `access_token`); the `httpOnly`/`secure`/`samesite=strict` cookie itself is never accessed via `document.cookie` or any header read. Repo-wide `grep -rn "refresh_token\|refreshToken" frontend/src` returns **zero matches** — no code path reads, stores, or names a refresh-token value client-side. |
| No password/token/recovery-code value reaches `console.*` or a rendered error | Pass | Zero `console.*` calls repo-wide (see §7 row above). `frontend/src/screens/*` never reference `accessToken`/`Authorization`/`Bearer` (`grep -rn "accessToken\|Authorization\|Bearer" frontend/src/screens` returns zero matches) — the Bearer header is built only inside `httpClient.ts:107-112` via the session bridge, never surfaced to a screen or error string. `frontend/src/api/errorNormalization.ts` only ever surfaces the backend's own `detail`/`errors[].message` strings or a hardcoded generic fallback (line 74) — it never echoes a request body, a header, or the token itself into `message`. |
| Client-decoded scopes never treated as authorization | Pass | `frontend/src/store/decodeTokenScopes.ts` is decode-only (no signature verification), documented as advisory in its own header comment and in the story's Assumption #3/spec NFR; every admin screen (`AdminUserListScreen.tsx:42`, `AdminUserDetailScreen.tsx:173`, `AdminAuditLogScreen.tsx:60`) still renders the server's 403 as the authoritative gate — scope-derived nav hiding is cosmetic only, never a substitute for the 403 branch. |
| No delete affordance for `DELETE /admin/users/{id}` (AD-AC7, adjacent hardening concern) | Pass | `frontend/src/api/adminApi.ts` declares no `deleteUser` function (confirmed by direct read of the full file — the only HTTP verbs used are `httpGet`/`httpGetWithMeta`/`httpPost`/`httpPatch`/`httpPut`). `grep -rn "deleteUser\|httpDelete" frontend/src` shows `httpDelete` used only by pre-existing, out-of-scope `authApi.revokeSession` (`/auth/sessions/{id}`) and `mfaApi` (`/auth/mfa`) — neither targets `/admin/users`. `frontend/src/api/adminApi.test.ts` independently backstops this with a source-wide static regex scan (`import.meta.glob` over `/src/**/*.{ts,tsx}`) asserting no file contains `httpDelete(...)` against an `/admin/users` path, guarded against a vacuous pass (`candidateFiles.length > 20`). |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] Request payload shape not schema-enforced at the type layer** — `frontend/src/api/types.ts:264-268` (`CreateAdminUserRequest`) and `:272-278` (`UpdateAdminUserRequest`, confirmed by direct read) are plain TypeScript interfaces (compile-time only), not a runtime-validated schema with an `extra="forbid"`-equivalent guard; a stray extra property could in principle be added to a request body without any test flagging it unless a specific assertion catches it. Not a §7 violation (no Pydantic schema exists in this stack by design), but worth noting since it's the closest frontend analogue. Confirmed by direct read that this risk is substantially covered for the fields the story cares about: `frontend/src/hooks/useCreateAdminUser.test.ts:40` asserts `Object.keys(receivedBody).toEqual(["email", "display_name", "roles"])` (exact key set, no password field), and `docs/verification/US-5.4-implementation-verification.md`'s AD-AC5 row cites `test_admin_user_detail_screen_patch_never_includes_a_roles_field` (`AdminUserDetailScreen.test.tsx:166`) for the PATCH side.

## Verdict Rationale

All six §7 rows are either Pass or N/A-by-construction per the skill's own frontend-track routing instruction, and every N/A is backed by an independent structural check (no ORM/SQL/schema/password-hashing code exists anywhere in the diff) rather than asserted blindly. The two frontend-substitute checks that actually apply on this track (no sensitive log/console output, no differentiation added to the uniform 403) were independently re-derived from the current repository state via direct grep and file reads, not taken from the prior implementation-verification report, and both are clean. No Critical or Major finding exists. Overall Verdict: **Pass**.
