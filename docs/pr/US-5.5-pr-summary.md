---
artifact_type: pr_summary
story: US-5.5
version: 1
status: DRAFT
created_at: "2026-09-14T17:15:00Z"
updated_at: "2026-09-14T17:15:00Z"
produced_by: pr-preparer
inputs:
  - path: docs/stories/US-5.5-agent-console-ui.md
    version: null
  - path: docs/specifications/US-5.5-spec.md
    version: 2
  - path: docs/impact-analysis/US-5.5-impact-analysis.md
    version: 2
  - path: docs/plans/US-5.5-implementation-plan.md
    version: 2
  - path: docs/evidence/US-5.5-implementation-report.md
    version: 3
  - path: docs/verification/US-5.5-implementation-verification.md
    version: 2
  - path: docs/reviews/security/US-5.5-security-review.md
    version: 2
  - path: docs/reviews/reconciliation/US-5.5-reconciliation.md
    version: 2
  - path: docs/reconciliation/US-5.5-traceability.md
    version: 2
  - path: docs/evidence/US-5.5-quality-gate-report.md
    version: 3
supersedes: null
---

# PR Summary: US-5.5 — Agent Console (Frontend)

## Gate Confirmation

All four required upstream gates were read directly from their own artifacts (not taken on a
verbal "it's all good") and each records verdict **PASS**, against the current, non-stale
input versions:

| Gate | Artifact | Version | Verdict |
|---|---|---|---|
| `gate-enforcer` (QUALITY_GATE, attempt 3) | `docs/evidence/US-5.5-quality-gate-report.md` | v3 | PASS |
| `implementation-verifier` | `docs/verification/US-5.5-implementation-verification.md` | v2 | PASS |
| `security-reviewer` | `docs/reviews/security/US-5.5-security-review.md` | v2 | PASS |
| `reconciliation-reviewer` | `docs/reviews/reconciliation/US-5.5-reconciliation.md` | v2 | PASS |

`docs/workflow/workflow-state.yaml` (`story: US-5.5`, `current_stage: PR_PREPARATION`,
`previous_stage: HUMAN_PR_APPROVAL`, `last_result.verdict: PASS` for `RECONCILIATION`) and
`docs/workflow/active-story.yaml` (`active_story: US-5.5`) agree on the active story.
`HUMAN_PR_APPROVAL` was recorded approved by `sbruhov@gmail.com` at `2026-09-14T17:00:00Z`
(`docs/workflow/history.jsonl`) against exactly these four artifacts at these versions. Every
front-matter `version`/`status` was re-read directly off disk in this session, not carried
from the resolved-path list handed to this stage: `specification` v2/APPROVED, `impact_analysis`
v2/DRAFT, `implementation_plan` v2/DRAFT, `implementation_report` v3/DRAFT, `implementation_verification`
v2/APPROVED, `security_review` v2/APPROVED, `reconciliation` v2/APPROVED, `traceability` v2/APPROVED
— none is `SUPERSEDED` or `ARCHIVED`. This is a re-run story (`RECONCILIATION` attempt 1 found a
blocking gap and looped back to `IMPLEMENTATION`); all four gates read here are the re-run's
results against the current working tree, not the earlier passing run that predates the fix.
`docs/decisions/US-5.5-open-decisions.md` v2 confirms OD-1 through OD-5 all `RESOLVED`; no
unresolved blocking Open Decision remains in any `APPROVED` input this stage depends on.

## PR Title

```
feat: add agent console UI (US-5.5)
```

## Summary

Adds the frontend agent console for the Customer Portal — a pure `frontend/`-only consumer of
the already-shipped US-4.4 agent-side backend contract (agent queue branch, assign/unassign).
No backend, API, or database change is included (`API_DESIGN`/`DB_DESIGN` both recorded
`NOT_APPLICABLE`, per the story's own Assumption #7).

Delivers:
- **Agent ticket queue** (`/agent/tickets`) rendering every non-closed ticket's `ticket_number`,
  `subject`, `category`, `status`, assignee (shortened/truncated UUID), and `updated_at`,
  oldest-updated first — with `status`/`category`/`assignee_id` filters that re-request and
  reset the cursor, mutually-exclusive `me`/`none` one-click assignee presets, an independent
  raw-UUID "specific agent" filter, and cursor-based "Load more" with no total count or page
  number anywhere (FR-1).
- **Assign / unassign** — "Assign to me" and assign-to-another-agent (raw-UUID input) both call
  `POST /support/tickets/{id}/assign`; unassign calls `DELETE .../assign`; both invalidate the
  queue on success and a `409`/`422` renders its problem+json detail (FR-2).
- **Agent ticket detail** (`/agent/tickets/:id`) rendering the header and full thread, including
  internal-visibility replies shown with a distinct style and an explicit "Internal" text
  label — never colour alone — plus cursor-paged "Load older replies" (FR-3).
- **Reply composer with explicit visibility** — defaults to `"public"` on every open (never
  sticky across a prior internal choice), sends `visibility` explicitly, and invalidates the
  ticket detail on a public reply (FR-4).
- **Resolve** with a mandatory 1–5000 character `resolution_note`, client-side blocked on an
  empty/whitespace-only/over-limit note, `409` on a closed ticket rendering its detail (FR-5).
- **Status- and scope-driven affordances** — only the actions valid for a ticket's current
  status are offered per FR-6's table; an agent holding `tickets:read` but not `tickets:write`
  sees every write control disabled, matching `AdminUserDetailScreen.tsx`'s established pattern
  (FR-6).
- **Close / reopen** as single action buttons, no `reason` field, no confirmation step,
  mirroring the customer-facing US-5.3 pattern (FR-7).
- **Uniform problem+json rendering** (FR-8) — a 4xx renders its `detail` (or a mapped message),
  and a `422`'s `errors[]` array is mapped onto the matching form field via the project's
  existing `getFieldErrors()`/`FieldError` mechanism, already used by seven other screens.
- **429 rate-limit handling** (FR-9) and a **retry-capable network/5xx error state** on every
  endpoint this Story calls (FR-10).
- **Shared app-shell navigation** — a `tickets:read`-gated `/agent/*` nav entry alongside the
  existing `/tickets` entry in one authenticated shell, no separate entry point, no role
  switcher (FR-11).

Linked story: `docs/stories/US-5.5-agent-console-ui.md`
Linked spec: `docs/specifications/US-5.5-spec.md` (v2, APPROVED)
Linked plan: `docs/plans/US-5.5-implementation-plan.md` (v2)

No new dependency, no new configuration/setting, and no existing exported function signature
changed shape — every `api/`/`hooks/` change is additive (see `.env.example` Check below).

## Test Plan

Built from `docs/reconciliation/US-5.5-traceability.md` (v2) and
`docs/evidence/US-5.5-quality-gate-report.md` (v3). All 9 spec Acceptance Criteria
(AG-AC1–AG-AC9) have a matrix row, a test function confirmed to exist verbatim in the working
tree, and assertions confirmed by `reconciliation-reviewer` — reading the actual test files, not
their names — to match the AC's stated behavior.

- [x] AG-AC1 `[gate]` — queue renders every non-closed ticket's six fields, oldest-updated
      first, no total count/page number displayed; filters re-request and reset the cursor;
      `me`/`none` presets mutually exclusive; "Load more" appends. (`AgentTicketQueueScreen.test.tsx`,
      `useAgentTickets.test.ts`)
- [x] AG-AC2 `[gate]` — assign-to-me/assign-to-another-agent/unassign call the correct
      endpoints; the row reflects the new assignee after a successful assign; `409`/`422`
      render problem+json detail. (`AgentTicketQueueScreen.test.tsx`, `useAssignTicket.test.ts`,
      `useUnassignTicket.test.ts`)
- [x] AG-AC3 — detail screen renders header + full thread; internal replies get a distinct
      style and literal "Internal" label; "Load older replies" pages by its own cursor.
      (`AgentTicketDetailScreen.test.tsx`)
- [x] AG-AC4 — composer defaults to public; public reply invalidates the detail; internal note
      sends `visibility: "internal"`, renders internally, and produces no status change (converse
      case explicitly asserted). (`AgentTicketDetailScreen.test.tsx`, `useReplyToTicket.test.ts`)
- [x] AG-AC5 — resolve on an eligible status calls `POST /{id}/resolve` and reflects
      `"resolved"`; empty/whitespace-only/>5000-character notes block submission client-side;
      `409` on a closed ticket renders its detail. (`AgentTicketDetailScreen.test.tsx`,
      `useResolveTicket.test.ts`)
- [x] AG-AC6 `[gate]` — offered-action set matches FR-6's five-status table exactly; a
      `tickets:read`-only (no `tickets:write`) view disables every write control on both
      screens. (`agentTicketHelpers.ts` unit cases, both screen test files)
- [x] AG-AC7 `[gate]` — every 4xx renders its detail (or a mapped message) with no raw JSON; a
      `422`'s `errors[]` maps onto the matching form field via `getFieldErrors()`/`FieldError`
      (reused, unmodified). Both clauses independently tested on both screens; the
      detail-suppressed-when-a-field-error-renders behavior matches the established,
      non-drifting convention already used on seven prior screens (see
      `docs/reviews/reconciliation/US-5.5-reconciliation.md` v2's AG-AC7 Special Determination).
- [x] AG-AC8 — a `429` on reply shows the retry-after message, disables submit, fires the
      request exactly once (no auto-retry loop). (`AgentTicketDetailScreen.test.tsx`)
- [x] AG-AC9 — a network error or `5xx` from any endpoint in this Story shows a retry-capable
      error state, never a blank screen or unhandled exception, on both screens.
- [x] a11y bar (`axe`) — `AgentTicketQueueScreen`, `AgentTicketDetailScreen` pass against a
      fully-rendered, populated screen; queue table cells are associated with column headers.
- [x] Plain-text rendering — an HTML-bearing reply body renders as escaped text; no
      `dangerouslySetInnerHTML` anywhere in this Story's files.
- [x] Full Definition-of-Done mechanical gate (`docs/evidence/US-5.5-quality-gate-report.md`,
      v3): `npm run lint` PASS (0 warnings), `npm run format:check` PASS, `npm run type-check`
      PASS, `npm run test:coverage` PASS — **74/74 test files, 493/493 tests**, coverage
      Statements 97.64%, Branches 94.51%, Functions 86.47%, Lines 97.64% (all four clear the
      85% floor).
- [x] Frontend runtime-rule substitutes independently re-verified twice (once by
      `gate-enforcer`, once by `implementation-verifier`, both against the current working
      tree): no `fetch`/`axios` in screens, no React/TanStack import in `api/`, no
      `localStorage`/`sessionStorage` write, read-only `useAuthStore()` in screens, zero banned
      idioms (`console.*`, `any`, `eslint-disable`).

Coverage type split: unit (Vitest, MSW-backed, no `fetch` mocking) for the four new hooks
(`useAgentTickets`, `useAssignTicket`, `useUnassignTicket`, `useResolveTicket`); integration
(React Testing Library + MSW, full screen/hook/store tree) for both new screens, `AppShell`, and
`AppRoutes`.

**Non-blocking, does not gate this PR** (carried through `IMPLEMENTATION_VERIFICATION` and
`RECONCILIATION`, none escalated): the queue screen's own `GET /support/tickets` call has no
dedicated forced-403 test of its own (the underlying rendering mechanism is proven on the
sibling detail screen and for 409/422 on this same screen); FR-11's "both nav entries render
together" has no single combined test (FR-11 traces to no AC); no stylesheet anywhere in
`frontend/` backs the internal-note "distinct styling" class names (pre-existing, project-wide,
true since US-5.3); a `title` tooltip on the queue's assignee cell exposes the full,
untruncated UUID (Low security advisory, inconsistent with the documented truncated-display
intent but not a credential/token/PII leak).

## Risk / Rollback

Per `docs/plans/US-5.5-implementation-plan.md`'s Risks section:

- **No backend/API/DB surface is touched** — every change is additive within `frontend/src/`
  (new files) or an additive change to an existing file; no existing exported function
  signature changed shape (`useReplyToTicket.ts` gained an optional `visibility` field only).
  Rollback is a plain revert of the frontend commit(s); no migration to reverse, no data to
  backfill.
- **No new dependency was added** — `package.json`/`package-lock.json` show no diff.
- **`ReplyRead.visibility` becoming a required field is additive, not breaking** — the two
  existing test files that build untyped reply fixtures (`TicketDetailScreen.test.tsx`,
  `useTicketDetail.test.ts`) were updated to include an explicit `"public"` value, closing the
  only latent type/runtime inconsistency this widening could have introduced (Risk 1, closed).
- **The "internal visibility must never leak into the next reply" NFR is enforced by an
  explicit `reset({ body: "", visibility: "public" })` on every successful submit**, not just
  assumed from the form's default value — directly asserted by
  `AgentTicketDetailScreen.test.tsx` (Risk 2, closed).
- **The assign/unassign response shape (`AgentTicketStateRead`) is never conflated with the
  full queue-row shape (`AgentTicketRead`)** — `useAssignTicket.ts`/`useUnassignTicket.ts` merge
  only `assignee_id`/`status`/`updated_at` into existing cache entries, confirmed by direct read
  (Risk 3, closed).
- **Client-decoded scopes remain cosmetic only, never an authorization boundary** — every
  privileged control renders the server's `403`/`409`/`422` as the actual gate; no client-side
  UUID-format validation blocks the deliberately-unvalidated raw-UUID assign/filter inputs
  (Risk 4 / Resolution OD-2), independently confirmed by `security-reviewer`.
- One Low, non-blocking security advisory is carried (not a gap): the queue's assignee cell
  exposes the full UUID via a `title` tooltip attribute, inconsistent with the documented
  truncated-display intent — not a credential, token, or customer PII, and the same audience
  already sees the truncated form. Worth a follow-up UI fix; does not block this PR.

## `.env.example` Check

**Confirmed current — no change required.** This Story adds no new configuration, setting, or
dependency: `git status --porcelain -- .env.example frontend/.env.example` returns empty,
consistent with the story's own Assumption #7 (no backend/API/DB change) and independently
confirmed by both `implementation-verifier` (§6.7 row, "N/A — no new setting") and
`security-reviewer`.

## Commit Hygiene Check (AGENTS.md §7.8)

**US-5.5's own file set is clean; one cross-story scope concern is flagged, not silently
absorbed into this draft.**

- Every new/modified `frontend/` file under this Story matches `task_breakdown` v2's T1–T14
  file list exactly, independently re-confirmed against `git status --porcelain -- frontend/`
  this session (12 modified tracked files, 13 new untracked files — 25 total, matching
  `implementation_report` v3's own claim). No existing exported function signature's shape was
  altered; every touched file is additive. `frontend/tsconfig.app.tsbuildinfo` is a `tsc -b`
  build artifact, not implementation code, already called out by name in
  `docs/evidence/US-5.5-implementation-report.md`.
- Every `docs/{specifications,plans,evidence,verification,reviews,reconciliation,decisions,
  tests,impact-analysis,catalog}/US-5.5-*` artifact in the working tree is this delivery's own
  workflow/documentation output, owned by its producing skill per
  `docs/workflow/artifact-paths.yaml` — not unrelated scope.
- **Flagged, not resolved here:** `git status --porcelain` shows this working tree also carries
  **uncommitted US-5.4 archive-mode changes** — `docs/ARCHITECTURE.md`, `docs/catalog/stories.yaml`,
  every `docs/{decisions,evidence,impact-analysis,plans,pr,reconciliation,reviews,
  specifications,tests,verification}/US-5.4-*` artifact, `docs/knowledge/project-state.md`,
  `docs/pr/US-5.4-pr-record.md`, and `docs/evidence/US-5.4-delivery-summary.md` — all still
  pending commit on the current branch, `feat/us-5.4-admin-console-ui`. No `US-5.5` branch has
  been created yet; `docs/workflow/workflow-state.yaml`'s own `note` field already records this
  as reported, not auto-resolved, at Story activation. This is a **pre-existing branch/commit
  state, not something this Story's implementation introduced** — but it means a plain `git
  push` from this branch today would carry US-5.4's archive-mode documentation changes into
  whatever US-5.5 commit(s)/PR follow, mixing two stories' history. Recommend committing (or
  branching off) the US-5.4 archive changes separately, and cutting a dedicated branch for
  US-5.5's own file set, before `pr-creator` pushes anything — this stage does not run `git`
  itself and takes no action on it.
- No file outside `frontend/` and this Story's own `docs/` artifact set is touched by US-5.5's
  implementation. No refactor of any file this Story did not need to change was found within
  the US-5.5 file set itself.

---

**This is drafted content only.** Pushing the branch or opening the Pull Request requires an
explicit, separate human instruction to run `git push` / invoke `pr-creator` (`gh pr create` or
the `github` MCP server) — this skill does not push, open, or merge anything itself. Given the
commit-hygiene flag above, that instruction should also settle how the US-5.4 archive changes
and the US-5.5 implementation are separated before anything is pushed.
