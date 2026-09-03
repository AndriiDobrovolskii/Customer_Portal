---
name: security-reviewer
description: Audits implemented code against this project's non-negotiable security invariants stated in AGENTS.md's closing security paragraph (§7): Argon2id-only password storage (never plaintext or reversible encryption), no logging of tokens/hashes/PII, extra="forbid" plus privilege-field exclusion on every inbound schema, parameterized SQL only (no string interpolation), and uniform 401 on auth failure without leaking which check failed. Use after implementation-verifier passes and before pr-preparer runs ("security review for US-xxx," "check this against AGENTS.md security rules"). Scoped specifically to this codebase's stated invariants — for a broader, non-project-specific security sweep, the built-in security-review command or agent-skills:security-and-hardening skill may run alongside this one, but this skill's findings against AGENTS.md's stated rules take precedence since those are binding project rules, not general best practice. Any violation of a §7 "non-negotiable" rule is an automatic Fail, never Pass with Issues.
---

# Security Reviewer

## Purpose

Audit implemented code against the specific, binding security invariants AGENTS.md §7 states for this codebase — not a general-purpose security sweep. These rules are non-negotiable by AGENTS.md's own wording, so any violation forces a Fail; there is no "Pass with Issues" for a §7 violation.

## Operational Contract

```
Precondition: implementation-verifier has passed for the story.
Input Artifacts: the story's implemented models.py, schemas.py, service.py, router.py; AGENTS.md §7's closing security paragraph; AGENTS.md §4's extra="forbid"+privilege-field rule; AGENTS.md §3's Async I/O forbidden list; AGENTS.md §4's no-logging rule.
Output Artifacts: docs/reviews/security/<StoryId>-security-review.md.
```

## Required Context

Read, in order:

1. The story's implemented code across all layers.
2. `AGENTS.md` §7's closing paragraph (the six non-negotiable rules, quoted in the checklist below).
3. `AGENTS.md` §4's `extra="forbid"` + privilege-field-exclusion rule, and its "Config & secrets" no-logging rule.
4. `AGENTS.md` §3's Async I/O forbidden list (relevant if the story touches auth/session/crypto code paths that could introduce blocking calls around sensitive operations).

## Preconditions

`implementation-verifier` has passed. If it hasn't, stop and say so — a technical-compliance failure should be resolved before a security audit is meaningful.

## Workflow

Check each item below with cited file:line evidence — no blanket assertion:

1. **Password storage.** Confirm passwords are hashed with Argon2id only (`argon2-cffi`), never stored plaintext or with reversible encryption, and that cost parameters (time/memory/parallelism) come from settings (`get_settings()`), not hardcoded.
2. **No plaintext/reversible encryption for credentials.** Confirm no credential-like field anywhere uses a fast hash (MD5/SHA without a proper KDF) or symmetric/reversible encryption in place of Argon2id.
3. **No sensitive data in logs.** Grep every `log.*`/`logger.*` call the story touches for tokens, password hashes, JWTs, refresh tokens, session ids, or auth request bodies. `print()` itself is separately forbidden by `AGENTS.md` §4 — flag any occurrence regardless of content.
4. **`extra="forbid"` + privilege-field exclusion.** Confirm every inbound schema (`*Create`, `*Update`, filters, webhook payloads) sets `extra="forbid"` and excludes this module's actual privilege/system fields (not just AGENTS.md's example list — cross-check against the real model columns, mirroring `schema-builder`'s whitelist approach).
5. **Parameterized SQL only.** Confirm every SQL statement (repository queries, hand-written migration `op.execute()` calls) uses SQLAlchemy constructs with bound parameters — no f-string/`.format()`/`%`-interpolated SQL anywhere, including inside a migration's raw `op.execute()`.
6. **Uniform auth-failure response.** Confirm every authentication failure path (wrong password, unknown email, expired/malformed/revoked token) returns the same status/response shape without differentiating which specific check failed — cite the code path that guarantees this (e.g. checking password before the verification-status gate, as `UserService.authenticate_user` does).
7. Assign a verdict: **Pass** (all six checks clean) / **Fail** (any one violated — non-§7 hardening suggestions, if any, are noted as advisory and do not by themselves force a Fail). There is no "Pass with Issues" outcome for this skill.
8. Write the report to `docs/reviews/security/<StoryId>-security-review.md` using `assets/template.md`.

## Constraints

- Scoped to AGENTS.md §7's stated invariants specifically — not a substitute for a general-purpose security sweep (the `security-review` command or `agent-skills:security-and-hardening` may run in addition, but this skill's findings against AGENTS.md's binding rules take precedence for this codebase).
- Any §7 non-negotiable violation is an automatic Fail — never softened to "Pass with Issues."
- Every finding cites file:line evidence.

## Verification Checklist

- [ ] Password storage is Argon2id-only, cost params from settings.
- [ ] No plaintext or reversible encryption anywhere a credential is stored.
- [ ] No token/hash/PII appears in any log call; no `print()` anywhere.
- [ ] Every inbound schema sets `extra="forbid"` and excludes this module's actual privilege fields.
- [ ] All SQL uses bound parameters — no string interpolation, including in migrations.
- [ ] Every auth-failure path returns a uniform response with no differentiation leaked.
- [ ] Verdict is Pass or Fail only — no §7 violation was softened to "Pass with Issues."

## Outputs

- `docs/reviews/security/<StoryId>-security-review.md`.

## Completion Criteria

Complete only when all six checks have cited evidence and the verdict follows strictly from them — any single violation forces Fail regardless of how minor it otherwise seems.

---

# Harness Contract

This skill owns the `SECURITY_REVIEW` stage of `docs/workflow/stage-map.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`SECURITY_REVIEW`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `specification`, `specification_review`, `impact_analysis`, `implementation_plan`, `plan_review`, `implementation_report`, `implementation_verification`, `api_design`, `openapi`, `database_design`, `entity_model`, `test_strategy`, `ac_test_matrix`, `open_decisions`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `specification`
- `specification_review`
- `impact_analysis`
- `implementation_plan`
- `plan_review`
- `implementation_report`
- `implementation_verification`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `test_strategy`
- `ac_test_matrix`
- `open_decisions`

## Preconditions (harness)

- Every consumed artifact is current: `status` is not `SUPERSEDED` or
  `ARCHIVED`, and the `version` this skill records in its own `inputs` is the
  version actually on disk. A stale input is `BLOCKED`, not a caveat.
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` input that this stage depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active.

## Result Envelope

Return exactly this. `story-orchestrator` records the transition; this skill
never writes `docs/workflow/workflow-state.yaml`.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: SECURITY_REVIEW
  story: <StoryId>
  artifact_status: DRAFT
  artifacts:
    - docs/reviews/security/<StoryId>-security-review.md
  next_stage: RECONCILIATION
  loop_back_stage: null
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back keys valid for this stage (from `stage-map.yaml`; naming any other key
is rejected and holds the stage as `BLOCKED`):

| key | `loop_back_stage` |
|---|---|
| `changes_required` | `IMPLEMENTATION` |
| `invalid_security_design` | `API_DESIGN` |

- `PASS` - no Critical or Major security findings. Low findings may be carried
  forward in `non_blocking_findings`, and must then be repeated by the next
  stage that consumes this review.
- `CHANGES_REQUIRED` - use `invalid_security_design` when the flaw is in the
  contract rather than the code.
- `BLOCKED` - a mandatory input is missing or stale.

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
