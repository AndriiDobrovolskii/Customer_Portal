---
name: story-spec-reviewer
description: Reviews a generated Story Specification artifact (e.g. docs/specifications/US-001-spec.md, typically produced by story-spec-writer) against its original User Story file (e.g. docs/backlog/US-001.md, containing business context and Acceptance Criteria) to check completeness and accuracy before implementation begins. Use this whenever the user asks to "review a spec," "check a spec against the story," "audit this specification," "verify AC coverage," or wants a QA pass on a spec before handing it to engineering — even if they just paste two file paths (a story and a spec) and ask "does this spec match?" Produces a structured Markdown review report saved under docs/reviews/, checking for: ambiguous or non-verifiable statements, contradictions with the original business requirements, missing Acceptance Criteria coverage, scope creep beyond the original story, and missing edge cases/boundary conditions/error handling. This is the downstream QA counterpart to story-spec-writer — it audits an existing spec, it does not draft or rewrite one. Trigger this for requests about spec review, spec audits, AC coverage checks, or spec-vs-story validation; not for writing a spec from scratch (that's story-spec-writer) and not for reviewing code or pull requests.
---

# Story Spec Reviewer

## Purpose & Role

This skill is the quality gate between "a spec exists" and "engineering starts building." It reads an original User Story (business context + Acceptance Criteria) side by side with a Story Specification artifact derived from it, and produces a structured, evidence-based review report.

The role is strictly auditor, not author. A developer or product owner should be able to read the report and know exactly what's wrong with the spec and where — without the reviewer having quietly patched the spec itself or invented requirements that were never in the original story. If `story-spec-writer` is the skill that formalizes a story into a spec, this skill is the one that checks the formalization was done faithfully.

## When To Use / When Not To Use

**Use this skill when:**
- A Story Specification artifact already exists and needs to be validated against its source story before implementation.
- The user wants to know whether a spec fully covers its Acceptance Criteria, whether it drifted from the original scope, or whether it's precise enough to build from.
- The user pastes or references two files — an original story/ticket and a generated spec — and asks for a comparison, audit, or sign-off.

**Do not use this skill when:**
- No spec exists yet — that's `story-spec-writer`'s job (writing a spec from a story), not this skill's.
- The user wants a code review or PR review — this skill only compares story vs. spec documents, not implementation code.
- The user wants the spec's *prose* improved (wording, formatting) rather than its *content* validated against the story — that's editing, not reviewing.
- The user asks you to just "fix" or "finish" the spec — flag that this skill reports findings, it doesn't rewrite the spec; the user or `story-spec-writer` should apply the fix.

## Inputs & Preconditions

Two files are required:

1. **Original User Story** — contains business context and Acceptance Criteria (e.g. `docs/backlog/US-001.md`). This is the source of truth for scope.
2. **Generated Story Specification** — the artifact being reviewed (e.g. `docs/specifications/US-001-spec.md`).

If the user gives only one file, or only describes one verbally, ask for the other rather than guessing — a review is meaningless without both sides of the comparison. If either file can't be found at the path given, say so and stop; don't review from memory or assumption.

Before starting the review, read both files in full. If the spec's Traceability Matrix references AC IDs that don't appear verbatim in the story (or vice versa), that mismatch is itself a finding — not a reason to silently reconcile them yourself.

## Step-by-Step Review Workflow

### 1. Extract the ground truth from the story

Read the original story and list every Acceptance Criterion with its ID (preserve the story's own IDs if it has them; if it doesn't, number them AC-1, AC-2, ... in order of appearance, exactly as `story-spec-writer` would). Also note any explicit business context, constraints, or out-of-scope statements — these matter for detecting contradictions and scope creep later, not just the AC list.

### 2. Read the spec as a reviewer, not a co-author

Read the full spec once straight through before judging anything, so you understand its overall shape. Then go back through it section by section for the five checks below. Resist the urge to fix issues as you spot them — note them as findings instead.

### 3. Check AC coverage

For every AC from step 1, find where (if anywhere) the spec addresses it. An AC is "covered" only if the spec's requirement actually implements what the AC says — a requirement that merely mentions related keywords without addressing the AC's actual behavior does not count as coverage. Mark each AC as Covered, Partially Covered, or Missing, and cite the specific spec section for Covered/Partially Covered ACs.

### 4. Check for ambiguity and non-verifiable statements

Flag any requirement in the spec that a developer or QA engineer couldn't act on without asking a follow-up question — vague verbs ("handle appropriately," "should be fast," "as needed"), undefined thresholds, or missing detail on *how* something should behave. The bar: could someone write a test against this statement as written? If not, it's a finding.

### 5. Check for contradictions with the original story

Compare each spec requirement against the story's business context and ACs for direct conflicts — e.g. the spec says a field is optional but the story's AC implies it's required, or the spec's stated behavior contradicts the story's stated user goal. Note the exact conflicting language from both sides so the finding is self-evident.

### 6. Check for scope creep

Flag anything in the spec — a requirement, an NFR, an edge case, a whole section — that isn't traceable to anything the original story said. This mirrors `story-spec-writer`'s own "never invent" discipline in reverse: that skill is supposed to avoid inventing scope, so this check is verifying it (or a human editor) didn't. A requirement that's a reasonable *elaboration* of an AC's wording is fine; a requirement that introduces new behavior, new fields, or new systems the story never mentioned is scope creep.

### 7. Check for missing edge cases, boundary conditions, and error handling

Look at what the ACs imply operationally and ask whether the spec addresses the boundaries: What happens at zero, at the maximum, on invalid input, on failure/timeout, on concurrent access, on permission denial? Only flag a gap where the story's own scope reasonably implies the case should be addressed — don't invent exotic scenarios the story gives no basis for; if you're not sure a scenario is in scope, phrase the finding as a question ("Does AC-3 apply when X is empty?") rather than asserting it as a defect.

### 8. Form the overall verdict

Based on the findings, assign one verdict:
- **Pass** — no missing AC coverage, no contradictions, and any ambiguity/edge-case/scope findings are minor.
- **Pass with Issues** — no missing AC coverage or contradictions, but there are ambiguities, scope creep, or edge-case gaps worth fixing before build.
- **Fail** — any AC is Missing or Partially Covered, or any contradiction exists. These block implementation until resolved.

### 9. Write and save the report

Build the report from `assets/template.md` (read it before drafting so structure stays consistent across reviews). Save it to `docs/reviews/<story-id>-spec-review.md` (e.g. `docs/reviews/US-001-spec-review.md`), creating the directory if needed. If a review already exists at that path, treat this run as the canonical update (overwrite it), and tell the user you replaced a prior review — reviews get re-run as specs are revised.

## Output Specification & Markdown Report Template

The output is always a saved Markdown file under `docs/reviews/` — never just a chat reply. Use `assets/template.md` verbatim as the structure: header metadata, overall verdict, an AC coverage table, and one subsection per check category (Ambiguities, Contradictions, Scope Creep, Missing Edge Cases), each listing findings with a severity, the exact quoted evidence from spec and/or story, and a plain description of the problem.

After saving, tell the user where the report was written and summarize the verdict and the highest-severity findings in chat — the file is the durable artifact, the chat summary is just a pointer to it.

## Constraints

- **Do not invent new requirements or ACs.** This skill's job is to compare what already exists in the story against what already exists in the spec — not to propose new scope, new requirements, or how a gap "should" be filled. If something's missing, say it's missing; don't write the missing content yourself.
- **Maintain strict traceability.** Every finding must cite the specific AC ID and/or exact quoted text (from story or spec) it's based on. A finding with no traceable evidence is not usable — cut it or find the citation.
- **Always write the durable artifact to `docs/reviews/`.** A review that only exists in the chat transcript can't be referenced later by other contributors or tools; the file is the deliverable.
- **Do not silently fix the spec.** This skill reports findings; it does not edit `docs/specifications/*`. If the user wants the spec fixed, that's a separate, explicit follow-up action (likely via `story-spec-writer`), not something to bundle into this review.
- **Don't soften a Fail verdict to be polite.** If ACs are missing or contradictions exist, the verdict must reflect that plainly — the report exists specifically to catch these before implementation cost is sunk.

## Validation Checklist

Before considering the review complete, confirm:

- [ ] Both source files (story and spec) were read in full.
- [ ] Every AC from the story appears in the coverage table exactly once, with a Covered / Partially Covered / Missing status.
- [ ] Every finding cites specific, quoted evidence from the story and/or spec — no unsupported assertions.
- [ ] No finding proposes new requirement text to add to the spec — gaps are described, not filled.
- [ ] The overall verdict (Pass / Pass with Issues / Fail) is consistent with the findings (any Missing/Partially Covered AC or contradiction forces Fail).
- [ ] The report was saved to `docs/reviews/<story-id>-spec-review.md`, not only shown in chat.
- [ ] The chat reply summarizes the verdict and points to the saved file path.
