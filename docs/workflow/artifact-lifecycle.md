# Status Vocabularies

This file is the **single authoritative source** for status values used across
the harness. There are **three separate enums**. They describe different things
and MUST NOT be mixed or conflated.

| Enum | Question it answers | Where it is stored |
|---|---|---|
| Artifact lifecycle status | "Is this document current?" | `status:` in each artifact's front matter (`artifact-schema.md`) |
| Review verdict | "What did this automated stage decide?" | `result.verdict` in the stage Result Envelope |
| Workflow status | "What state is the delivery workflow in?" | `status:` / `pending_human_gate.status` in `workflow-state.yaml` |

---

## 1. Artifact lifecycle status

Applies to every story-level artifact (front-matter `status:` field).

| Value | Meaning |
|---|---|
| `DRAFT` | Produced by its owner skill; not yet reviewed or approved. |
| `IN_REVIEW` | A downstream review stage is currently evaluating it. |
| `APPROVED` | Passed its review gate (and human gate where one exists). Safe to consume downstream. |
| `SUPERSEDED` | A newer version exists. The newer artifact's `supersedes:` points here. Never used as a current input. |
| `ARCHIVED` | Belongs to a delivery that has completed archive mode. Retained for history only. |

Rules:

- A revised artifact increments `version:` and sets `supersedes:` to the prior
  path/version. The prior revision becomes `SUPERSEDED`.
- Reviewers MUST check that every input artifact they consumed is the current
  (non-`SUPERSEDED`, non-`ARCHIVED`) version and that its `version:` matches what
  downstream artifacts recorded consuming.
- Stale input (a review or evidence artifact generated from a now-`SUPERSEDED`
  upstream) blocks progression until the dependent stage is re-run.

---

## 2. Review verdict

The only values an automated stage skill may emit in `result.verdict`.

| Value | Meaning | Orchestrator action |
|---|---|---|
| `PASS` | Stage goal met. Zero blocking findings. May carry `non_blocking_findings`. | Advance to `stage-map.yaml` `next`. |
| `CHANGES_REQUIRED` | Correctable problem. The skill sets `loop_back_stage` to a key defined under this stage's `loop_back` map. | Route to `loop_back_stage`. |
| `BLOCKED` | Stage cannot be evaluated: missing/stale mandatory input, unresolved blocking Open Decision, environment failure, artifact conflict. | Hold at current stage; surface `blocking_issues`; may require human decision. |
| `NOT_APPLICABLE` | Only for a stage marked `optional: true` whose `optional_when` condition is met and recorded. | Advance to `next`. |

### Retired result values

These were used by this project's skills before the Result Envelope existed.
They MUST NOT appear in any skill or new artifact. Historical artifacts written
before the harness migration are read-only history and are not rewritten to use
these mappings — but nothing new may emit them.

| Retired | Canonical |
|---|---|
| `Pass` | `PASS` |
| `Pass with Issues` | `PASS` with `non_blocking_findings` populated |
| `Fail` | `CHANGES_REQUIRED` (correctable) or `BLOCKED` (not evaluable) |
| `APPROVED` (as a verdict) | `PASS` |
| `APPROVED_WITH_COMMENTS` | `PASS` with `non_blocking_findings` |
| `REJECTED` | `CHANGES_REQUIRED` or `BLOCKED` |
| `Ready for Specification` | `PASS` |
| `Not Ready` | `BLOCKED` |
| `READY_FOR_PLANNING` | `PASS` |
| `PARTIALLY_IMPLEMENTED` | `CHANGES_REQUIRED` (`loop_back_stage: IMPLEMENTATION`, key `partial`) |
| `FAILED` | `CHANGES_REQUIRED` or `BLOCKED` |
| `READY_FOR_PR` (as a verdict) | `PASS` at `PR_PREPARATION` |
| `PROCEED_TO_*` | derive the next stage from `stage-map.yaml`; do not name it in the skill |
| `RETURN_TO_*` | use `loop_back_stage` with a key from `stage-map.yaml` |

Note: `READY_FOR_PR`, `COMPLETED`, and `ARCHIVED` are also **workflow stages**
(`stage-map.yaml`). They are not verdicts. The verdict at `PR_PREPARATION` is
`PASS`; the orchestrator then advances the *stage* to `READY_FOR_PR`.

---

## 3. Workflow status

Stored in `workflow-state.yaml` (`status:` and inside `pending_human_gate`).

| Value | Meaning |
|---|---|
| `NOT_STARTED` | Story activated; no stage has run. |
| `IN_PROGRESS` | An automated stage is the current stage and is runnable. |
| `WAITING_FOR_HUMAN` | Current stage is a `human_gate`; `pending_human_gate.status = PENDING`. |
| `BLOCKED` | Last stage returned `BLOCKED`, or a workflow invariant failed. |
| `COMPLETED` | Reached stage `COMPLETED` (human confirmed PR merged / delivery done). |
| `ARCHIVED` | Reached stage `ARCHIVED` via archive mode. |

`pending_human_gate.status` sub-enum: `PENDING`, `APPROVED`, `REJECTED`.

---

## Relationship to AGENTS.md

`AGENTS.md` §1 requires reporting a conflict rather than silently relaxing a
rule. Applied here: a skill that cannot honestly emit `PASS` emits
`CHANGES_REQUIRED` or `BLOCKED` — it never emits `PASS` with the problem
described only in prose. A `PASS` from a review skill is **not** human approval;
human approval is recorded only at a `human_gate` stage via `/so:approve`.
