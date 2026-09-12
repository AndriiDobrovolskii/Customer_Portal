---
artifact_type: security_review
story: US-5.3
version: 1
status: DRAFT
created_at: "2026-09-12T01:00:00Z"
updated_at: "2026-09-12T01:00:00Z"
produced_by: security-reviewer
inputs:
  - path: docs/stories/US-5.3-support-tickets-ui.md
    version: null
  - path: docs/specifications/US-5.3-spec.md
    version: 1
  - path: docs/reviews/specifications/US-5.3-spec-review.md
    version: 1
  - path: docs/impact-analysis/US-5.3-impact-analysis.md
    version: 1
  - path: docs/plans/US-5.3-implementation-plan.md
    version: 2
  - path: docs/reviews/plans/US-5.3-plan-review.md
    version: 2
  - path: docs/evidence/US-5.3-implementation-report.md
    version: 2
  - path: docs/verification/US-5.3-implementation-verification.md
    version: 1
  - path: docs/tests/US-5.3-test-strategy.md
    version: 1
  - path: docs/tests/US-5.3-ac-test-matrix.md
    version: 1
  - path: docs/decisions/US-5.3-open-decisions.md
    version: 1
supersedes: null
---

# Security Review: Support Tickets — Frontend (US-5.3)

**Story ID:** US-5.3
**Reviewed:** 2026-09-12
**Overall Verdict:** PASS

## Summary

`track: frontend`; `API_DESIGN`/`DB_DESIGN` both `NOT_APPLICABLE` — no backend, Pydantic, or
SQL surface exists in this Story's diff (re-confirmed via
`implementation-verification.md`'s working-tree enumeration: every touched/added path is
under `frontend/`). Per this skill's Track rule, checks 1, 2, 4, and 5 (password hashing,
reversible-encryption ban, `extra="forbid"`, parameterized SQL) are **N/A by construction**.
This story adds no auth/session-state change and no new dependency (OD-5), so the
frontend-specific invariants (memory-only access token, refresh token untouched by client
code) carry forward unchanged from US-5.1/US-5.2's own precedent, re-confirmed rather than
assumed. The story's actual new attack surface is customer-authored free text (ticket
`category`, reply `body`) rendered back to the same or another viewer, and a
client-generated `Idempotency-Key` — both checked below with cited evidence.

## AGENTS.md §7 Non-Negotiable Checklist (frontend track — see Summary for scope)

| Rule | Result | Evidence |
|---|---|---|
| Argon2id-only password storage, cost params from settings | N/A | `track: frontend`; no `models.py`/password-hashing code in this Story's diff. |
| No plaintext/reversible encryption for credentials | N/A | No server-side or client-side credential storage in scope — this story handles no password/credential field. |
| No tokens/hashes/PII in logs; no `print()` | Pass | `grep -rn "console\.\(log\|warn\|error\|debug\|info\)" frontend/src` → zero matches, whole tree (re-run independently). `print()` is Python-only, N/A to this TypeScript stack. |
| `extra="forbid"` + privilege-field exclusion | N/A | No Pydantic schema touched — `API_DESIGN`/`DB_DESIGN` `NOT_APPLICABLE` per the story's own Assumption #8. |
| Parameterized SQL only | N/A | No SQL, repository, or migration exists in this Story's diff. |
| Uniform auth-failure response, no differentiation leaked | N/A | This story adds no authentication endpoint or auth-failure path; the three new routes are gated by the pre-existing `ProtectedRoute` guard, unmodified. |

## Frontend-Specific Invariants (AGENTS.md §3 Frontend subsection, in place of checks 1/2/4/5)

| Invariant | Result | Evidence |
|---|---|---|
| Access token lives in memory only, never `localStorage`/`sessionStorage` | Pass | Unchanged by this story: `store/authStore.tsx` (not modified per `git status`) still holds `accessToken` only in reducer state. `grep -rn "localStorage\|sessionStorage" frontend/src` (excluding `.test.`) → only `authStore.tsx:2` (a comment, no live call) and `components/MfaEnrollmentBanner.tsx:14,22` (pre-existing, non-sensitive dismissal flag). Zero references in any US-5.3 file (`supportApi.ts`, the six ticket hooks, the three ticket screens). |
| Refresh token never read, stored, or parsed by client code | Pass | This story adds no new `httpClient.ts` refresh-retry branch (`httpClient.ts`'s existing `idempotencyKey`/`retryAfterSeconds` additions are additive to `httpPost`'s request/error path, not the refresh flow). `RefreshResponse` type is unchanged; no code path in the new `supportApi.ts`/hooks touches a refresh token. |
| No sensitive value reaches a rendered error | Pass | Re-confirmed independently in `implementation-verification.md`: the three new screens route every error through the existing `ErrorState`/`apiErrorHelpers` path; no ad hoc `err.message` rendering was introduced. This story handles no password/secret/recovery-code field, so there is no new sensitive-value class to check beyond what US-5.1/US-5.2 already covered. |

## New attack surface introduced by this story (not present in prior frontend-track reviews)

### 1. Customer-authored free text rendered back to a viewer (`category`, reply `body`)

- `frontend/src/screens/TicketDetailScreen.tsx:133` renders `{ticket.category}`;
  `:149` renders `{reply.body}` — both via plain JSX expression interpolation, not
  `dangerouslySetInnerHTML`. `grep -rn "dangerouslySetInnerHTML" frontend/src` (excluding
  `.test.`) → **zero matches** anywhere in the tree, including all three new screens. React
  escapes all text-node interpolation by default, so an HTML/script-bearing `category` or
  reply `body` value renders as literal text, never executes.
- This is independently proven by a real DOM-structure assertion, not just a string-contains
  check: `test_ticket_detail_screen_html_bearing_reply_body_renders_as_escaped_text_and_never_executes`
  (`frontend/src/screens/TicketDetailScreen.test.tsx:452`) posts an HTML-bearing reply body
  and asserts no injected element (e.g. `<img>`) appears in the rendered DOM.
- `NewTicketScreen.tsx`'s `category` field is a plain `<input maxLength={50}>` (OD-2, no
  enum) — client-side `maxLength` is a UX affordance only, not a security boundary; the
  value is sent to the backend verbatim and rendered back verbatim on the detail screen via
  the same escaped-interpolation path above. No new injection surface: this story neither
  introduces nor relies on any client-side sanitization step whose absence would matter.
  **Pass.**

### 2. Client-generated `Idempotency-Key` (`crypto.randomUUID()`, OD-6)

- `frontend/src/hooks/useCreateTicket.ts:36`: `keyRef.current = crypto.randomUUID()`. This is
  the Web Crypto API's CSPRNG-backed UUIDv4 generator (`Crypto.randomUUID()`), not
  `Math.random()` or any other predictable source — not guessable/replayable by an attacker
  who doesn't already control the client. The key's purpose is deduplication of a
  resubmission, not authentication or authorization, so its threat model doesn't require
  secrecy from the requesting client itself, only unpredictability from an outside party,
  which a CSPRNG UUID satisfies. **Pass, no finding.**

### 3. `429 Retry-After` handling (OD-1)

- `getRetryAfterSeconds`/`ApiError.retryAfterSeconds` (per `implementation-verification.md`
  §6.7) surfaces only a numeric seconds value already present in the backend's own
  standard HTTP `Retry-After` response header — this is not new information the frontend
  invents or extracts from anywhere more sensitive; the header is visible in browser
  DevTools' Network tab today regardless of whether the frontend parses it. No information
  disclosure beyond what the wire protocol already exposes. **Pass, no finding.**

## Verdict Rationale

All six §7 checklist rows are either N/A by construction (frontend-only story, no backend
surface, no auth-failure path touched) or Pass. The frontend-specific invariants carry
forward unchanged and re-confirmed. The three new-attack-surface items this story
specifically introduces (customer-authored free text rendered back, a client-generated
idempotency key, and 429 `Retry-After` surfacing) were each checked with cited file:line
evidence and a real test assertion where applicable (the HTML-bearing-reply DOM-structure
test) — none introduces a Critical, Major, or Low finding. **Overall Verdict: PASS.**
