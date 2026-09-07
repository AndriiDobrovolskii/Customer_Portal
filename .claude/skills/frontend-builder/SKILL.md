---
name: frontend-builder
description: Generates the React + Vite + TypeScript frontend for a `track: frontend` Story — project scaffold, the api-client layer, the auth/session store, route guards and layout, screens and forms, and their Vitest + React Testing Library + MSW tests — from an approved specification, implementation plan, and task breakdown. Use when a frontend Story's plan and tests are approved and the frontend/ code needs to be generated or extended ("build the frontend for US-xxx," "implement the React screens for this story," "scaffold the frontend"). Enforces the layer table from AGENTS.md §3's Frontend subsection (screens/components import hooks and store only, never api/ or fetch/axios directly; api/ imports no React/TanStack Query; store imports neither api/ nor hooks), the access-token-in-memory / refresh-token-never-touched-by-client-code session rule, and the exact npm script names (lint, format:check, type-check, test:coverage) gate-enforcer's frontend track invokes by name. Is the sole IMPLEMENTATION sub-step for a frontend-track Story (stage-map.yaml skills_by_track.frontend) — there is no split-by-layer equivalent of schema-builder/data-layer-builder/migration-manager/service-and-router-builder on this track yet. Does not design the screens/API contract (that's planner/openapi-designer where one exists) and does not decide task order (implementation-planner) — it builds what task_breakdown already named.
---

# Frontend Builder

## Purpose

Turn an approved implementation plan and task breakdown for a `track: frontend` Story into
working `frontend/` source: the project itself (if it doesn't exist yet), the layer that
talks to the backend, the layer that holds client session state, the routes that decide who
sees what, and the screens a user actually interacts with — plus the tests that prove each
of those works. This is the frontend counterpart to the four backend builder skills, but
unified into one, since this stack's layers don't have the backend's migration-ordering
constraints that justify splitting builders by layer there.

## Operational Contract

```
Precondition: implementation-planner's task_breakdown names this skill for one or more tasks; test-writer has produced (or is producing alongside) the matching test files.
Input Artifacts: docs/specifications/<StoryId>-spec.md; docs/plans/<StoryId>-implementation-plan.md; docs/plans/<StoryId>-task-breakdown.md; docs/impact-analysis/<StoryId>-impact-analysis.md; the existing frontend/ tree, if any.
Output Artifacts: frontend/ source files (scaffold, config, src/api, src/store, src/routes, src/components, src/screens) and their test files under the matching frontend/src/**/*.test.tsx paths.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — the Functional Requirements and validation rules a screen/hook must actually implement.
2. `docs/plans/<StoryId>-implementation-plan.md` and `docs/plans/<StoryId>-task-breakdown.md` — which files this run is responsible for; do not invent scope beyond what these name.
3. `docs/impact-analysis/<StoryId>-impact-analysis.md` — the affected-file survey this plan was built from.
4. `AGENTS.md` §2's Frontend subsection (stack, npm script names), §3's Frontend subsection (the layer table and session-handling rule), and §5/§6's Frontend subsections (test split, coverage floor, Definition of Done).
5. The existing `frontend/` tree, if this is not the first run — extend in place, matching its own established style, rather than re-scaffolding.

## Preconditions

`implementation-planner` has assigned one or more tasks to `frontend-builder` in
`task_breakdown`. If `frontend/` does not exist yet and no task covers scaffolding it, stop
and name the gap rather than inventing a scaffold nobody asked for.

## Workflow

### 1. Scaffold (first run only)

If `frontend/` does not exist: `npm create vite@latest frontend -- --template react-ts`,
then add TanStack Query, React Hook Form, Vitest, React Testing Library, MSW, ESLint,
Prettier as dev/runtime dependencies per `AGENTS.md` §2's Frontend table. Wire
`frontend/package.json` scripts to **exactly** `lint`, `format:check`, `type-check`,
`test:coverage` (`AGENTS.md` §2 — these names are load-bearing for `gate-enforcer`; do not
rename or add a fifth without updating both AGENTS.md and gate-enforcer's SKILL.md first).
Set the Vitest coverage threshold to the same 85% floor as the backend.

### 2. `api/` — the HTTP boundary

One function per backend operation this Story's spec names (e.g. `login`, `refreshToken`,
`getSessions`). Each function: takes typed arguments, returns a typed DTO matching the
backend's actual response shape (cite the spec's API Contract table, not a guess), and
translates a non-2xx response into a typed error the caller can branch on. This is the
**only** layer allowed to call `fetch`. Never import React, a hook, or the store here —
mirror the backend's "`cache.py` imports no service/router" discipline (§3).

### 3. `store/` — session state

The auth store holds the access token **in memory only** (never `localStorage`/
`sessionStorage`) and the current user, per `AGENTS.md` §3's session-handling rule. It
exposes actions (`setSession`, `clearSession`) and does not call `api/` itself — hooks call
`api/` and then update the store with the result. Never store the refresh token here or
anywhere client-reachable; the backend's `httpOnly` cookie is the only place it lives.

### 4. `hooks/` — TanStack Query wiring

One hook per screen-facing operation, wrapping the matching `api/` function in
`useQuery`/`useMutation`. A mutation that changes session state (login, MFA verify, logout)
updates the store in its `onSuccess`, never inside the component that calls it. A 401 from
any query/mutation triggers exactly one `POST /auth/refresh` retry before falling back to
clearing the session and redirecting — never a naive per-call retry loop (this Story's own
FE-AC4/OD-2 concurrency concern: if two hooks race a 401 simultaneously, both must resolve
against the same single in-flight refresh call, not fire two independently).

### 5. `routes/` — guards and layout

A route guard reads the store (never calls `api/` itself) to decide unauthenticated →
`/login` and authenticated-visiting-`/login` → the placeholder home, per the spec's own
Assumption #5. The auth layout (no sidebar/header) wraps pre-authentication screens,
distinct from the authenticated app shell's layout — the NFR the spec added specifically to
close its own DESIGN_REVIEW-equivalent gap.

### 6. `screens/` and their forms

One screen component per task_breakdown entry, composed from `hooks/` and shared
`components/` only — never `api/` directly. Forms use React Hook Form with client-side
validation matching the spec's stated rules (and *only* the rules the spec/Open Decisions
actually state — do not invent a shared password policy across screens where the story's
own OD-5 says the backend enforces two different ones per screen). Every screen has a
loading state and an explicit error state for its hook's in-flight/failed request — no
indefinite spinner, no unhandled rejection.

### 7. Tests, alongside each layer above

Per `AGENTS.md` §5's Frontend subsection: a Vitest unit test per hook/pure function, a
React Testing Library integration test per screen with MSW handlers shaped like the actual
backend responses (status code, body, and — for `/auth/register`'s two non-RFC7807 shapes,
per this Story's OD-4 — the actual non-conforming shape, not a normalized one). Never
`vi.mock()` the component/hook/store under test; mock the network via MSW.

### 8. Self-check before finishing

Grep new/changed `screens/`/`components/` files for a bare `fetch(` or `axios` import —
must be zero (everything goes through `hooks/`→`api/`). Grep `api/` files for `from "react"`
or a TanStack Query import — must be zero. Grep the whole diff for `localStorage` or
`sessionStorage` next to anything token-shaped — must be zero. Confirm
`frontend/package.json` still defines exactly `lint`/`format:check`/`type-check`/
`test:coverage`.

## Constraints

- Only files under `frontend/` may be created or modified by this skill.
- No screen/component imports `api/` or calls `fetch`/`axios` directly.
- No access or refresh token in `localStorage`/`sessionStorage`/a client-set cookie.
- No `any` in TypeScript; no `// eslint-disable` added to silence a real finding.
- `frontend/package.json`'s four gate scripts (`lint`, `format:check`, `type-check`,
  `test:coverage`) are never renamed or removed.

## Verification Checklist

- [ ] `screens/`/`components/` import only `hooks/`, `store/` (read-only), and shared UI —
      no `api/`, no `fetch`/`axios`.
- [ ] `api/` imports no React/TanStack Query; every function returns a typed DTO, never
      `any`.
- [ ] `store/` calls no `api/` function directly; access token never leaves memory.
- [ ] Every mutation that changes session state updates the store `onSuccess`, not inside
      the calling component.
- [ ] Concurrent 401s resolve against one shared in-flight refresh, not one per request.
- [ ] Every screen has an explicit loading and error state for its own request(s).
- [ ] A test exists for every hook/screen this run touched, using MSW for network
      boundaries, never mocking the unit under test.
- [ ] `frontend/package.json`'s `lint`/`format:check`/`type-check`/`test:coverage` scripts
      exist and are unrenamed.

## Outputs

- `frontend/` source and config files (scaffold on first run), plus their matching test
  files, per the task(s) `task_breakdown` assigned to this skill.

## Completion Criteria

Complete only when the checklist above is fully satisfied and every task_breakdown entry
assigned to `frontend-builder` has corresponding source and test files.

---

# Harness Contract

This skill is a sub-step of the `IMPLEMENTATION` stage
(`docs/workflow/stage-map.yaml`, `type: composite_skill`), selected via
`skills_by_track.frontend` for a Story whose `docs/stories/<StoryId>.md` front
matter sets `track: frontend` (`artifact-schema.md`). It produces `frontend/`
source — not a registry artifact. `story-orchestrator` records its progress in
`pipeline_status` (`docs/catalog/<StoryId>-pipeline-status.md`) and sets
`implementation_substep` in `workflow-state.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`IMPLEMENTATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `open_decisions`, `specification`, `specification_review`,
  `impact_analysis`, `implementation_plan`, `task_breakdown`, `plan_review`,
  `test_strategy`, `ac_test_matrix`. Any path shown elsewhere in this skill is
  illustrative; the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.
- Frontend conventions: `AGENTS.md` §2/§3/§5/§6 Frontend subsections.

## Inputs (registry keys)

- `story`
- `open_decisions`
- `specification`
- `specification_review`
- `impact_analysis`
- `implementation_plan`
- `task_breakdown`
- `plan_review`
- `test_strategy`
- `ac_test_matrix`

`api_design`/`openapi`/`database_design`/`entity_model` are not inputs — a
`track: frontend` Story records these `NOT_APPLICABLE` (no backend contract
change), so this skill works from the spec's own API Contract table (read-only
reference to the existing backend) instead.

## Preconditions (harness)

- Every consumed artifact is current: `status` is not `SUPERSEDED` or
  `ARCHIVED`, and the `version` this skill records in its own `inputs` is the
  version actually on disk. A stale input is `BLOCKED`, not a caveat.
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` input that this stage depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active.

## Result Envelope

Return exactly this. The orchestrator advances `IMPLEMENTATION` once this
sub-step (the only one on the frontend track) returns `PASS`.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: IMPLEMENTATION
  substep: frontend-builder
  story: <StoryId>
  artifacts: []          # source files, listed by path
  next_substep: null
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for `IMPLEMENTATION`:

| key | `loop_back_stage` |
|---|---|
| `partial` | `IMPLEMENTATION` |
| `blocked_by_plan` | `IMPLEMENTATION_PLANNING` |
| `blocked_by_architecture` | `ARCHITECTURE_PLANNING` |

## Prohibited (harness)

- Do not update workflow state (`workflow-state.yaml`, `active-story.yaml`,
  `history.jsonl`) - `story-orchestrator` owns those.
- Do not produce an artifact this skill does not own in
  `docs/workflow/artifact-paths.yaml`.
- Do not resolve Open Decisions.
- Do not emit a retired verdict (`Pass`, `Fail`, `Pass with Issues`,
  `APPROVED`, ...) - see `artifact-lifecycle.md` section 2.
- Do not use the retired sequential story ids (`US-0NN`) or retired stage
  identifiers (`DESIGN`, `PLANNING`, `TESTS`, `VERIFICATION`, `PR`).
- Do not create commits, branches, or Pull Requests.
- Do not edit `.pre-commit-config.yaml` or `AGENTS.md` — a frontend gate hook
  or convention change is a harness-level change, not this skill's to make.
