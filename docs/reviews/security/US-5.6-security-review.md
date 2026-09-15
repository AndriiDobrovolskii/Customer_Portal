---
artifact_type: security_review
story: US-5.6
version: 1
status: APPROVED
created_at: "2026-09-15T15:00:00Z"
updated_at: "2026-09-15T16:00:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-5.6-global-navigation.md
    version: null
  - path: docs/specifications/US-5.6-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.6-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-5.6-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.6-implementation-plan.md
    version: 1
  - path: docs/reviews/plans/US-5.6-plan-review.md
    version: 1
  - path: docs/evidence/US-5.6-implementation-report.md
    version: 1
  - path: docs/verification/US-5.6-implementation-verification.md
    version: 1
  - path: docs/tests/US-5.6-test-strategy.md
    version: 1
  - path: docs/tests/US-5.6-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.6-open-decisions.md
    version: 2
supersedes: null
---

# Security Review: Global Navigation (Frontend)

**Story ID:** US-5.6
**Reviewed:** 2026-09-15
**Overall Verdict:** PASS

**Note on verdict vocabulary.** `assets/template.md`'s placeholder (`{{Pass | Fail}}`) uses the
retired enum. Per `AGENTS.md` §8 (canonical sources win on conflict) and
`docs/workflow/artifact-lifecycle.md` §2 ("`Pass`... MUST NOT appear in any skill or new
artifact"), and matching this skill's own Harness Contract, this report uses `PASS` /
`CHANGES_REQUIRED` / `BLOCKED` throughout.

## Summary

Track is `frontend` (`docs/stories/US-5.6-global-navigation.md` front matter). This Story is a
pure navigation-menu change confined to three files — `frontend/src/layouts/AppShell.tsx`
(+20/-5: `Link`→`NavLink` conversions on five pre-existing entries, one new plain `Link` "Home"
entry, four new ungated `NavLink` entries for the account self-service screens), plus test-only
additions to `AppShell.test.tsx` (+225) and `AppRoutes.test.tsx` (+31) — confirmed by
`git diff --stat -- frontend/` re-run this session, matching `implementation_verification` v1's
own file-set claim exactly. No backend code, no API endpoint, no password/auth/session logic, no
SQL, and no schema was touched. Per this skill's track-first routing, checks 1, 2, 4, and 5 of the
backend §7 checklist (Argon2id password storage, reversible-encryption credentials,
`extra="forbid"` inbound schemas, parameterized SQL) are **N/A by construction** — no password
hashing, no credential-at-rest storage, no Pydantic schema, and no SQL exists anywhere in
`frontend/`, and none of that surface is touched by this diff. In their place I independently
re-verified `AGENTS.md` §3's Frontend invariants (access token memory-only, refresh token never
touched by client code, no sensitive value to console/a committed file/a rendered error) against
the current working tree, plus this stage's own task-brief question: whether any of the four
newly-ungated nav entries exposes a route that should have been scope-gated but wasn't.

`git grep -nE "console\.|localStorage|sessionStorage|dangerouslySetInnerHTML|eyJ"` run across all
three changed files (`AppShell.tsx`, `AppShell.test.tsx`, `AppRoutes.test.tsx`, not just the
production file) returns exactly one hit: `AppShell.test.tsx:76`, `sessionStorage.clear()` inside a
`beforeEach`. Read in context (`AppShell.test.tsx:70-77`), this is pre-existing US-5.3 test-isolation
code (the block's own comment cites "US-5.2 attempt-2 report's defect #2") that clears the
`mfaEnrollmentBannerDismissed` UI-dismissal flag `MfaEnrollmentBanner` writes — not a token, not
app session state, and not code this Story added or modified. `AppShell.tsx` itself, and the new
US-5.6 test blocks within `AppShell.test.tsx`/`AppRoutes.test.tsx`, contain zero matches. No JWT- or
token-shaped literal (`eyJ...`) appears anywhere in the diff.

`useAuthStore()` (`frontend/src/store/authStore.tsx`) itself is unmodified by this diff (absent from
`git status --porcelain -- frontend/`) — `AppShell.tsx:25`'s `const { mfaEnrollmentDeadline, scopes }
= useAuthStore();` is a pre-existing, unchanged read-only destructure; this Story adds no new store
read, no store write, and no token handling of any kind.

**In-scope judgment question — does any new/converted nav entry expose a route that should have
been scope-gated but wasn't?** No. FR-2 of the approved spec (v2, `APPROVED`) states the ungated set
verbatim: "Tickets, Sessions, Profile, Security, Deactivate Account" are unscoped, and only "Agent
Queue, Users, and Audit Log" remain scope-gated "exactly as today." All four of this Story's new
entries (`Sessions`, `Profile`, `Security`, `Deactivate Account`) are account self-service screens
in that ungated list, and `AppRoutes.tsx:91-94` confirms their routes carry no scope check beyond
the shared `ProtectedRoute` (auth-only) — identical to the pre-existing, already-reviewed `/tickets`
entry. This is by design, not an oversight: these are the signed-in user's own account/session data,
inherently available to any authenticated user regardless of scope, matching the convention every
prior self-service screen in this codebase already follows. The `Home` entry targets `/tickets`,
sanctioned by FR-4's Boundary Condition (an empty ticket list for a staff-only account is expected,
not an authorization gap). The three entries that remain scope-gated (`Agent Queue`/`Users`/`Audit
Log`, `AppShell.tsx:55-57`) are rendered via conditional JSX (`{canReadX && <NavLink .../>}`), not
CSS-only hiding — an unscoped user's DOM contains no `/admin/users`/`/admin/audit-logs`/`/agent/
tickets` string at all — and this property is unchanged, still intact, by this diff. One
pre-existing, out-of-scope asymmetry is noted for completeness, not as a finding: `canReadAgentQueue
= scopes.includes("tickets:read")` (`AppShell.tsx:38`) means a plain ticket-holding customer with
`tickets:read` also sees the "Agent Queue" entry — this is US-5.5's line, unmodified by this diff,
already reviewed Pass at US-5.5's own security review, and remains cosmetic per `AGENTS.md` §3 and
this Story's own NFR ("no nav change alters server-side authorization"; the server 403 is the actual
boundary on `/agent/tickets`).

**Preconditions independently checked this session.** `implementation-verifier` passed
(`docs/verification/US-5.6-implementation-verification.md` v1, Overall Verdict **PASS**) —
precondition satisfied. Every registry input's front matter was read directly off disk this
session: `specification` v2/`APPROVED`, `specification_review` v1/`APPROVED`, `impact_analysis`
v1/`DRAFT`, `implementation_plan` v1/`APPROVED`, `plan_review` v1/`APPROVED`,
`implementation_report` v1/`DRAFT`, `implementation_verification` v1/`DRAFT` (Overall Verdict
PASS), `test_strategy` v1/`DRAFT`, `ac_test_matrix` v1/`DRAFT`, `open_decisions` v2/`DRAFT` — none
is `SUPERSEDED` or `ARCHIVED`; non-`APPROVED` statuses on otherwise-`DRAFT` artifacts are expected
per `artifact-lifecycle.md` §1 until a human gate bumps them, and every version matches this
report's own `inputs:` block. `api_design`/`openapi`/`database_design`/`entity_model` are
`NOT_APPLICABLE` per the resolved input paths supplied for this run — correct, no such artifacts
exist for a nav-only frontend Story. `docs/decisions/US-5.6-open-decisions.md` v2 confirms OD-1
through OD-4 all `RESOLVED` at `HUMAN_SPEC_APPROVAL` — no unresolved blocking Open Decision.
`docs/workflow/active-story.yaml` (`active_story: US-5.6`) agrees with the active story supplied.

## AGENTS.md §7 Non-Negotiable Checklist (frontend track — reframed per this skill's routing)

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A (frontend track, not touched) | No password hashing exists anywhere in `frontend/`; this Story adds no auth/credential code — its entire diff is nav markup (`Link`→`NavLink`, new `<NavLink>`/`<Link>` entries) plus tests. |
| No plaintext/reversible encryption for credentials | N/A (frontend track, not touched) | No credential-at-rest storage in this diff; no credential-shaped value appears anywhere in the three changed files (confirmed by the `console./localStorage/sessionStorage/dangerouslySetInnerHTML/eyJ` grep above). |
| Access token lives in memory only, never `localStorage`/`sessionStorage` (frontend substitute for checks 3/6) | PASS | `frontend/src/store/authStore.tsx` is unmodified by this diff (`git status --porcelain -- frontend/` shows no entry for it) — the access token still lives only in the store's in-memory state, unaffected. `AppShell.tsx:25`'s `useAuthStore()` read is a pre-existing, unchanged, read-only destructure of `{ mfaEnrollmentDeadline, scopes }` — no token field is read, stored, or forwarded. The one `sessionStorage` hit in the diff (`AppShell.test.tsx:76`, `sessionStorage.clear()`) is pre-existing US-5.3 test-isolation code for the MFA-banner dismissal flag, not a token and not new to this Story. |
| Refresh token never read/stored/logged by client code (frontend substitute) | PASS | No file in this diff references a refresh token, a cookie, or `document.cookie`; `decodeTokenScopes.ts` and `authStore.tsx` are both unmodified (confirmed via `git status`). The refresh-cookie handoff remains entirely server/browser-automatic, untouched by a nav-only change. |
| No token/hash/PII in logs; no `print()`; no sensitive value to console or a committed file (frontend substitute for check 3) | PASS | `git grep -nE "console\.\|localStorage\|sessionStorage\|dangerouslySetInnerHTML\|eyJ"` across all three changed files (`AppShell.tsx`, `AppShell.test.tsx`, `AppRoutes.test.tsx` — not the production file alone) returns exactly one hit, the pre-existing, non-token `sessionStorage.clear()` above; zero `console.*` calls anywhere in the diff. No JWT- or token-shaped literal appears in either test file's new fixtures — the new/converted nav assertions exercise only route paths and scope-array fixtures (`["users:read"]`-style string arrays), never a token value. |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A (frontend track, not touched) | No Pydantic schema exists in `frontend/`; this Story sends no request payload at all — it is presentation-only (nav links), no new mutation or form. |
| Parameterized SQL only, no string interpolation | N/A (frontend track, not touched) | No SQL exists in `frontend/`. |
| Uniform auth-failure response, no differentiation leaked (frontend substitute: UI adds no differentiation on top of the backend's response) | PASS | This diff touches no error-rendering, auth-failure, or 401/403-handling code path at all — `AppShell.tsx`'s only logic change is the scope-gated conditional render already reviewed above (`canReadUsers`/`canReadAudit`/`canReadAgentQueue`, unchanged expressions). No new differentiation between auth-failure cases is introduced or possible from a pure nav-markup diff. |

## Story-Specific Security Surfaces (per this stage's own task brief)

| Surface | Result | Evidence |
|---|---|---|
| No new nav entry exposes a route that should have been scope-gated but wasn't | PASS | Spec FR-2 (`docs/specifications/US-5.6-spec.md` v2, `APPROVED`) states verbatim that only "Agent Queue, Users, and Audit Log" remain scope-gated, while "Tickets, Sessions, Profile, Security, Deactivate Account" are the ungated set — all four new entries (`Sessions`, `Profile`, `Security`, `Deactivate Account`) are account self-service screens in that ungated list, matching every prior self-service screen's existing convention in this codebase. `AppRoutes.tsx:91-94` confirms their routes carry only the shared `ProtectedRoute` auth-only guard, no additional scope check — by design, not a gap. The three routes that do carry cosmetic scope gates (`AppShell.tsx:55-57`) are still conditionally rendered (not CSS-hidden), so an unscoped user's DOM contains no `/admin/users`/`/admin/audit-logs`/`/agent/tickets` string — unchanged by this diff. |
| Scope-gated nav/route access otherwise unchanged | PASS (pre-existing, out of scope) | `canReadAgentQueue = scopes.includes("tickets:read")` (`AppShell.tsx:38`) predates this Story (US-5.5) and is unmodified by this diff; a ticket-holding customer also seeing "Agent Queue" was already reviewed Pass at US-5.5's own security review and remains cosmetic — the server 403 on `/agent/tickets` is the real boundary, per `AGENTS.md` §3 and this Story's own NFR ("no nav change alters server-side authorization"). Noted for completeness, not a finding against this Story. |
| No injection/XSS surface introduced | PASS | Every new/converted nav label (`Home`, `Sessions`, `Profile`, `Security`, `Deactivate Account`, plus the five pre-existing labels) is a literal JSX text child — no interpolated or server-derived string is rendered. Zero `dangerouslySetInnerHTML` anywhere in the diff (confirmed by the grep above). |

## Advisory Findings (non-§7, does not force Fail)

None identified beyond the two Low, non-security findings `implementation-verifier` already carries
forward (OD-3 flat-list negative-assertion gap; pre-existing nav/route path-literal duplication) —
both are AC-compliance/maintainability observations, not security findings, and are not repeated
here per this stage's own scope.

## Verdict Rationale

Every §7 checklist row is PASS or explicitly N/A-by-construction (the four backend-only rows do not
apply to this `track: frontend`, nav-markup-only Story, and none of that surface is touched by the
diff). The frontend substitute rows that do apply — access-token memory-only, refresh-token
never-touched, no sensitive value to console/a committed file/a rendered error, and uniform
auth-failure response — are all PASS, independently re-derived from the current working tree
(`git diff --stat`, a fresh grep across all three changed files, and direct reads of `AppShell.tsx`
and the relevant `authStore.tsx`/`AppRoutes.tsx` state). The in-scope judgment question this stage
was specifically asked to answer — whether any of the four newly-ungated nav entries should have
carried a scope gate — is answered no, cross-checked against the approved spec's own FR-2 statement
and the registered routes in `AppRoutes.tsx`. No `AGENTS.md` §7 non-negotiable is violated, so the
Overall Verdict is **PASS**.
