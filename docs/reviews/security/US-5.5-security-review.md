---
artifact_type: security_review
story: US-5.5
version: 2
status: APPROVED
created_at: "2026-09-14T15:10:00Z"
updated_at: "2026-09-14T15:10:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/reviews/specifications/US-5.5-spec-review.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/reviews/plans/US-5.5-plan-review.md
    version: 2
  - path: docs/evidence/US-5.5-implementation-report.md
    version: 3
  - path: docs/verification/US-5.5-implementation-verification.md
    version: 2
  - path: docs/tests/US-5.5-test-strategy.md
    version: 1
  - path: docs/tests/US-5.5-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.5-open-decisions.md
    version: 2
supersedes: docs/reviews/security/US-5.5-security-review.md (v1)
---

# Security Review: Agent Console (Frontend)

**Story ID:** US-5.5
**Reviewed:** 2026-09-14
**Overall Verdict:** PASS

## Summary

This is a re-run against the **current working tree**, not a diff check against v1's report.
Since v1 passed, `RECONCILIATION` (attempt 1) found one blocking gap — AG-AC7/FR-8's "a 422
validation-failed maps its errors array onto the matching form fields" clause was unimplemented in
both agent screens — and looped back to `IMPLEMENTATION`. `frontend-builder` wired the project's
existing `getFieldErrors()`/`FieldError` mechanism (already used by `NewTicketScreen.tsx` and five
other screens) into `AgentTicketQueueScreen.tsx` and `AgentTicketDetailScreen.tsx`, plus closed four
non-blocking test-coverage gaps; no other file in scope changed. `QUALITY_GATE` (v3) and
`IMPLEMENTATION_VERIFICATION` (v2) both re-passed. Track is `frontend`
(`docs/stories/US-5.5-agent-console-ui.md` front matter, `track: frontend`), so checks 1, 2, 4, and
5 of this skill's backend checklist (password hashing, reversible-encryption credentials,
`extra="forbid"` schemas, parameterized SQL) remain N/A by construction — no password hashing, no
credential-at-rest storage, no Pydantic schema, no SQL exists anywhere in `frontend/`. In their
place I re-verified `AGENTS.md` §3's Frontend invariants (access token memory-only, refresh token
never touched by client code, no sensitive value to console or a rendered error) end to end, plus
this stage's own task brief for the new surface: whether `getFieldErrors()`/`FieldError` ever
renders a raw server error object or a field name carrying a token/session value, and whether it
introduces any injection/XSS surface. It does not — traced the full chain
`httpClient.ts:parseResponse` → `errorNormalization.ts:normalizeApiError`/`extractFieldErrors` →
`ApiError.fieldErrors` → `apiErrorHelpers.ts:getFieldErrors` → `FieldError.tsx`.
`extractFieldErrors` (`frontend/src/api/errorNormalization.ts:38-49`) only ever copies a
`{field: string, message: string}` pair per array entry (`isRawFieldError`, `:34-36`) into a fresh
`Record<string, string>` — it never spreads or forwards the raw parsed body, and an entry missing
either key is silently dropped rather than passed through. `FieldError.tsx:12-16` renders the
resulting string as JSX text content (`{message}`), which React escapes; no
`dangerouslySetInnerHTML` exists anywhere in this Story's file set (confirmed by grep, zero
matches). The `field` key used to look the message up is always one of this Story's own request
field names (`assignee_id`, `body`, `resolution_note` — the literal strings passed as the `field`
prop at each call site), never a value read out of the response body itself, so there is no path by
which a server-controlled key could resolve to a token/session-shaped label. This is otherwise a
full re-review, not a diff-only check: I re-read every file this Story touches directly from the
working tree — `frontend/src/screens/AgentTicketQueueScreen.tsx`, `AgentTicketDetailScreen.tsx`,
`agentTicketHelpers.ts`, `frontend/src/hooks/useAgentTickets.ts`, `useAssignTicket.ts`,
`useUnassignTicket.ts`, `useResolveTicket.ts`, `useReplyToTicket.ts`, `useTicketDetail.ts`,
`frontend/src/api/types.ts`, `supportApi.ts`, `httpClient.ts`, `errorNormalization.ts`,
`frontend/src/components/apiErrorHelpers.ts`, `FieldError.tsx`, `frontend/src/routes/AppRoutes.tsx`,
`frontend/src/layouts/AppShell.tsx` — plus a grep for
`console.`/`localStorage`/`sessionStorage`/`dangerouslySetInnerHTML` across the full touched-file
set (zero matches, same result as v1). `frontend/src/store/authStore.tsx` and
`store/decodeTokenScopes.ts` are unmodified in this diff (confirmed via `git status`), so the
access-token/refresh-token handling is unchanged from v1's already-verified state. Harness
preconditions independently re-checked against the resolved paths supplied for this re-run: every
consumed artifact's front-matter `version`/`status` on disk matches this review's own `inputs:`
block (spec v2/APPROVED, spec_review v2/APPROVED, impact_analysis v2/DRAFT, implementation_plan
v2/DRAFT, plan_review v2/DRAFT, implementation_report v3/DRAFT, implementation_verification
v2/DRAFT — PASS per its own verdict, test_strategy v1/DRAFT, ac_test_matrix v1/DRAFT,
open_decisions v2/DRAFT) — none `SUPERSEDED`/`ARCHIVED`; `docs/decisions/US-5.5-open-decisions.md`
v2 confirms OD-1 through OD-5 all `RESOLVED`, no unresolved blocker; `docs/workflow/active-story.yaml`
(`active_story: US-5.5`) and `docs/workflow/workflow-state.yaml` (`story: US-5.5`,
`current_stage: SECURITY_REVIEW`) agree on the active story. All checks are clean. Verdict:
**PASS**. The same Low advisory carried since v1 (full untruncated assignee UUID exposed via a
`title` tooltip attribute) is still present, unchanged, in the current working tree — repeated
below per this review's own supersession rule, not re-litigated.

## AGENTS.md §7 Non-Negotiable Checklist (frontend track — reframed per this skill's routing)

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A (frontend track) | No password hashing exists anywhere in `frontend/`; this Story adds no auth/credential code. |
| No plaintext/reversible encryption for credentials | N/A (frontend track) | No credential-at-rest storage in this diff. |
| Access token lives in memory only, never `localStorage`/`sessionStorage` | Pass | `frontend/src/store/authStore.tsx` is unmodified by this loop-back (`git status --porcelain -- frontend/src/store` shows no entry) — `accessToken` still lives only in the in-memory `useReducer` state, cleared on `CLEAR_SESSION`, same as v1's already-verified finding. `grep -rniE "localStorage\|sessionStorage"` across every US-5.5 file (including the new `getFieldErrors()` call sites) returns zero matches, re-run this session. |
| Refresh token never read/stored/logged by client code | Pass | No US-5.5 file, including the newly-wired `getFieldErrors()`/`FieldError` paths, references a refresh token, a cookie, or `document.cookie`; `decodeTokenScopes.ts` is likewise unmodified in this diff (`git status` confirms). The refresh-cookie handoff remains entirely server/browser-automatic, unchanged from v1. |
| No password/token/recovery-code value reaches `console.*` or a rendered error message | Pass | `grep -rniE "console\."` across every US-5.5 file (both agent screens, all seven agent hooks, `agentTicketHelpers.ts`, `api/types.ts`, `api/supportApi.ts`, `api/httpClient.ts`, `api/errorNormalization.ts`, `components/apiErrorHelpers.ts`, `components/FieldError.tsx`, `routes/AppRoutes.tsx`, `layouts/AppShell.tsx`) returns zero matches. The new field-level errors render only a server-supplied `message` string copied field-by-field by `errorNormalization.ts:extractFieldErrors` (`frontend/src/api/errorNormalization.ts:38-49`) — never the raw response body, a caught exception object, or any token/session value; traced end to end (`httpClient.ts:69,82` → `errorNormalization.ts:61,67` → `ApiError.fieldErrors` `httpClient.ts:36` → `apiErrorHelpers.ts:44-46` → `FieldError.tsx:7-17`). |
| `extra="forbid"` + privilege-field exclusion on inbound schemas | N/A (frontend track) | No Pydantic schema exists in `frontend/`; the request types this Story's mutations send (`AssignTicketRequest`, `ResolveTicketRequest`, `CreateReplyRequest`, `frontend/src/api/types.ts`) carry only the fields the API contract defines — unchanged by this loop-back, which touched only error-rendering, not request-payload composition. |
| Parameterized SQL only, no string interpolation | N/A (frontend track) | No SQL exists in `frontend/`. |
| Uniform auth-failure response, no differentiation leaked (frontend analogue: UI adds no differentiation on top of the backend's response) | Pass | Every 4xx/403 path in this Story's screens still renders the backend's own problem+json `detail` (or a status-keyed mapped message) via the shared `getErrorKind`/`getErrorMessage`/`ErrorState` helpers, with the new `getFieldErrors()`/`FieldError` output rendered *alongside*, never in place of, that generic message when both are absent (`AgentTicketQueueScreen.tsx:216`: `{apiError && !errorKind && !fieldErrors && ...}`; `AgentTicketDetailScreen.tsx:340,368`: same `!...FieldErrors` guard pattern) — no per-screen special-casing of "which field failed" beyond what the server's own `errors[]` array names, and no screen substitutes a client-invented differentiation for an auth-failure response specifically (403/401 paths are unaffected by this loop-back's diff). |

## Story-Specific Security Surfaces (per this stage's own task brief)

| Surface | Result | Evidence |
|---|---|---|
| `getFieldErrors()`/`FieldError` wiring never leaks a raw server error object | Pass | `errorNormalization.ts:extractFieldErrors` (`:38-49`) iterates `body.errors` and, for each entry, keeps only `entry.field`/`entry.message` after a structural `isRawFieldError` guard (`:34-36`) requiring both to already be `string`s — any entry failing that guard (e.g. a malformed or unexpected shape) is silently skipped, not passed through. The resulting `Record<string, string>` is the only thing that reaches `FieldError.tsx`; nothing in the chain (`ApiError` class, `apiErrorHelpers.ts`, either screen) re-attaches the original parsed `body`, `response`, or exception object to what gets rendered. Confirmed by direct read of `frontend/src/api/httpClient.ts:60-83` (`parseResponse`) and `frontend/src/api/errorNormalization.ts:51-75` (`normalizeApiError`) — no code path returns `body` itself in `NormalizedApiError`. |
| `getFieldErrors()`/`FieldError` never carries a field name shaped like a token/session value | Pass | The `field` prop passed to every `<FieldError>` call site in this Story is a literal string hard-coded at the call site — `"assignee_id"` (`AgentTicketQueueScreen.tsx:210,114`; `AgentTicketDetailScreen.tsx:259`), `"body"` (`AgentTicketDetailScreen.tsx:307`), `"resolution_note"` (`AgentTicketDetailScreen.tsx:358`) — never a value read out of the response body or looped over dynamically. Even though `extractFieldErrors` itself is generic (it will key the map by whatever `field` string the server sends), the only keys these screens ever look up are the Story's own known request-field names; a server sending an unexpected key (e.g. something token-shaped) would populate the map but nothing in this diff renders an unmatched key or iterates `Object.keys(fieldErrors)` — confirmed by reading both screens in full, no such iteration exists. |
| `getFieldErrors()`/`FieldError` introduces no injection/XSS surface | Pass | `FieldError.tsx:12-16` renders `{message}` as JSX text content inside a `<p>` — React escapes this automatically; no `dangerouslySetInnerHTML`, `innerHTML`, or manual DOM write exists anywhere in `FieldError.tsx`, `apiErrorHelpers.ts`, or either agent screen. Project-wide grep for `dangerouslySetInnerHTML` across the full touched-file set returns zero matches, same as v1. The `message` value itself is server-authored text (from `body.errors[].message`) rendered exactly like every other error string this Story already renders through `getErrorMessage()` (already reviewed Pass in v1) — no new rendering primitive was introduced by this wiring, only a new call site for an existing, already-plain-text-safe mechanism (`NewTicketScreen.tsx`'s precedented pattern, per the implementation report). |
| Internal-note visibility never leaks to a customer-facing path | Pass (unchanged from v1) | `frontend/src/hooks/useReplyToTicket.ts:34-37`: `visibility` is included in the outbound request only `if (values.visibility !== undefined)`; `TicketDetailScreen.tsx` (US-5.3, zero diff) never registers a `visibility` field, so its request body is unaffected. `AgentTicketDetailScreen.tsx:81,86-88`: the composer seeds and re-asserts `visibility: "public"` on every successful submit (`reset({ body: "", visibility: "public" })`), so a prior "internal" choice cannot persist into the next open or reply. Internal replies still render with both a distinct `className` and a literal `<strong>Internal</strong>` text label (`:278,281`) — not colour alone. This loop-back's diff does not touch any line in this mechanism. |
| Raw-UUID assign-target/filter inputs: server is the actual enforcement boundary | Pass (unchanged from v1) | The assign-target input (`AgentTicketQueueScreen.tsx:100-106`, `AgentTicketDetailScreen.tsx:245-251`) and the queue's "specific agent" filter (`AgentTicketQueueScreen.tsx:203-209`) remain deliberately unvalidated raw-text inputs per Resolution OD-2 — no client-side UUID-format check was added or removed by this loop-back. The value still reaches the server only via `URLSearchParams.set()` (percent-encoded) or a JSON request body field (`api/supportApi.ts:79,91-92,96-97`), never string-concatenated into a URL or rendered back unescaped. |
| Scope-gated nav/route access | Pass (unchanged from v1) | `AppShell.tsx:38,45` and `AppRoutes.tsx:105-110` are unchanged by this loop-back's diff (confirmed: the loop-back's `AppRoutes.tsx`/`AppShell.tsx` changes present in `git diff --stat` predate this specific re-run's scope and were already reviewed — the `/agent/tickets` route sits inside the same `ProtectedRoute`/`AppShell` group as every other authenticated route, cosmetic scope gating only, server 403 remains the real boundary). |

## Advisory Findings (non-§7, does not force Fail)

- **[Low] Full assignee UUID exposed via a `title` tooltip attribute** — `frontend/src/screens/AgentTicketQueueScreen.tsx:80`: `<span title={ticket.assignee_id}>{formatAssigneeId(ticket.assignee_id)}</span>` sets the native HTML `title` attribute to the full, untruncated `assignee_id` UUID, even though the row's visible text and the story's own Resolution OD-1 both commit to a shortened/truncated display (`agentTicketHelpers.ts:49-56`). Re-confirmed present, unchanged, in the current working tree — this loop-back's diff did not touch this line. A `title` attribute is visible on hover/long-press and readable by anyone with sight of the screen or screen-reader access to the DOM, so this doesn't leak past the same audience already entitled to see the truncated form (the value is an internal agent-account identifier, not a credential, token, or customer PII), but it remains inconsistent with the documented "never render more than the truncated form" intent. Worth a follow-up UI fix (e.g. omit `title` or truncate it the same way), not an `AGENTS.md` §7 violation — no password, token, hash, or PII is involved.

## Verdict Rationale

Every checklist row is Pass or N/A (N/A rows are the four backend-only checks that do not apply by
construction to a `track: frontend` Story). The frontend-specific rows that do apply — access-token
memory-only storage, refresh-token never-touched, no sensitive value to console/rendered error, and
uniform-failure-response — are all Pass, re-derived from the current working tree, including the
newly-wired `getFieldErrors()`/`FieldError` mechanism this stage's task brief specifically named:
traced end to end, it never surfaces a raw server error object, never keys on a token/session-shaped
field name, and renders only as escaped plain text with no `dangerouslySetInnerHTML` anywhere in the
chain. The five pre-existing story-specific surfaces (internal-note non-leakage, raw-UUID inputs,
scope-gated nav/route access) are unchanged by this loop-back's diff and remain Pass. No §7
non-negotiable is violated, so the Overall Verdict is **PASS**; the one advisory finding (full UUID
in a `title` attribute, unchanged from v1) is Low, non-§7, and does not change it.
