# Archive Flow

Consolidate knowledge from a finished delivery and clean up workflow state.
Explicit, infrequent, human-invoked only. Never inferred.

## Preconditions

Archive only when ALL of these hold:

- exactly one active Story;
- `workflow-state.yaml.current_stage == COMPLETED` — a human recorded the PR
  merge or delivery completion via `/so:approve` at the `COMPLETED` gate;
- the `reconciliation`, `traceability`, and `pr_summary` artifacts exist, are
  current, and are `APPROVED`;
- no Critical or Major findings remain open;
- no blocking Open Decisions remain;
- the artifact inventory is complete — every mandatory `stage-map.yaml` output
  produced and current, with conditional artifacts either present or recorded
  `NOT_APPLICABLE`;
- no unclassified Story files remain in the working tree.

Do not archive merely because an implementation exists, or because the PR
merged. `COMPLETED` must have been recorded at its gate.

## Steps

1. Confirm `current_stage == COMPLETED` and that a human invoked this command.
2. Build the artifact inventory for the Story from `artifact-paths.yaml` — path,
   type, version, status.
3. Create the **delivery summary** at the `delivery_summary` registry path
   (`docs/evidence/{story_id}-delivery-summary.md`), owned by this skill: Story
   id; final catalog state; source Issue and PR reference, or `null`; final
   branch; activation / completion / archive timestamps taken at runtime; the
   full artifact inventory; the final acceptance-criteria result; the final
   verification, security, and reconciliation verdicts; known limitations;
   deferred work; a history reference. No secrets, no full sensitive logs.
4. Set the Story's catalog `state` to `ARCHIVED` in `docs/catalog/stories.yaml`,
   atomically. Set each Story artifact's front-matter `status` to `ARCHIVED`
   where appropriate. **Do not move any file.** Paths and `supersedes` links are
   preserved.
5. Update `docs/knowledge/project-state.md` (registry key `project_state`) with
   the capabilities this Story delivered.
6. **Propose — do not apply —** updates to `docs/product/business-rules.md` and
   `docs/ARCHITECTURE.md` implied by the delivery. Present them as a diff or
   bullet list for human review. `AGENTS.md` is never edited by a skill
   (`AGENTS.md` §7.8).
7. Apply the knowledge-doc updates from step 6 **only after explicit human
   approval in this session**. If not approved, leave them as proposals recorded
   in the delivery summary.
8. GitHub sync, if a source is configured and permitted: show the proposed Issue
   state change, request explicit approval, perform only the approved
   read/label/close operation, and record the result. Never merge a Pull
   Request.
9. Clear active state: `active-story.yaml.active_story: null`,
   `status: ARCHIVED`; `workflow-state.yaml.current_stage: ARCHIVED`,
   `status: ARCHIVED`, `archived_at` at runtime. Preserve state history.
10. Append one `history.jsonl` event — `to_stage: ARCHIVED`,
    `skill: story-orchestrator`, `verdict: "ARCHIVED"`.

Do not delete workflow history or Story artifacts.

## Archive Result

Return: the archived Story; final catalog state; PR reference; source Issue
status; the delivery summary path; which knowledge updates were proposed versus
applied; confirmation that the active Story was cleared; and remaining deferred
work. Recommend `/so:start <NextStoryId>` only when the next Story id is
explicit or unambiguous from the catalog.
