---
name: story-spec-writer
description: Converts a user story, ticket, or requirements file into a formal markdown specification document, saved under docs/specifications/. Use this whenever the user asks to "write a spec," "draft a specification," "turn this story/ticket into a spec," or wants requirements formalized from a file that contains Acceptance Criteria — even if they just paste a file path and say "spec this out." Every requirement in the output must trace back to a specific Acceptance Criterion from the source (via a traceability matrix and inline "Derived from: AC-n" citations), and the skill must never invent requirements, NFRs, or scope the source didn't state — gaps and ambiguities get logged as Open Questions instead. Trigger this for requests mentioning specs, specifications, requirements docs, PRDs-from-tickets, or acceptance-criteria traceability, not for writing user stories/ACs from scratch (that's the opposite direction).
---

# Story Spec Writer

## What this does

Reads a user story or requirements file that contains Acceptance Criteria (AC) and produces a formal markdown specification document. The spec organizes the same information the source already contains — it does not add scope, and every requirement it states is traceable back to the AC it came from.

The value here is discipline, not creativity: a developer or reviewer should be able to open the output spec, pick any requirement, and immediately see which Acceptance Criterion justifies it — and conversely, see at a glance if any AC was left uncovered.

## Operational Contract

```
Precondition: A source file containing Acceptance Criteria exists at a path the user provides; us-clarifier's verdict (if run) is "Ready for Specification" or the user explicitly accepts the open risk.
Input Artifacts: the user-provided source story/ticket/requirements file.
Output Artifacts: docs/specifications/<story-id>-<kebab-case-title>.md.
```

## Workflow

### 1. Get the source

The input is a file in the repo (a story, ticket export, or requirements doc). If the user gave a path, read it. If they only described the story verbally without pointing at a file, ask for the file path rather than guessing — this skill is specifically for formalizing an *existing* written source, not drafting one from a conversation.

If the file contains multiple stories/tickets, produce one spec document per story (see step 5 for naming), and confirm with the user first if it's ambiguous whether they want one doc or several.

### 2. Extract the Acceptance Criteria

Find the story's Acceptance Criteria (may be labeled "AC", "Acceptance Criteria", "Given/When/Then", "Definition of Done," a checklist, etc.).

- **If the source already labels ACs with IDs** (AC-1, AC1, GH-42-3, etc.), keep those IDs unchanged — they may already be referenced elsewhere (tests, tickets), so renumbering would break traceability rather than help it.
- **If the source has no IDs**, assign sequential IDs yourself in the order the criteria appear: AC-1, AC-2, .... Always pair an assigned ID with the exact original wording in the Traceability Matrix, so a reader can verify the ID against the source themselves.

If you can't find any Acceptance Criteria at all, stop and tell the user — don't write a spec with a fabricated or empty traceability matrix. A spec with no ACs to trace to defeats the purpose of this skill.

### 3. Draft the spec — formalize, never fabricate

Work through `assets/template.md` section by section. The governing rule: **every declarative sentence in the spec must be traceable to something the source actually said.** Concretely:

- Turn each Acceptance Criterion (or tightly related cluster of ACs) into one Functional Requirement, restated in clear, implementation-neutral spec language. Restating and clarifying wording is fine and expected; adding behavior, edge-case handling, or constraints the source never mentioned is not — even if it seems like an obvious gap. That gap belongs in Open Questions, not in an FR.
- Only include a Non-Functional Requirements or Out of Scope section if the source explicitly addresses those topics. It's normal and expected for a spec to omit these sections entirely.
- When something is missing, vague, or contradictory (e.g., an AC says "the user gets notified" without saying how), don't guess — write it up as an Open Question phrased so a reviewer can resolve it in one reply.
- Background/Summary should paraphrase the source's own framing, not introduce new motivation or context you inferred.

If you're ever unsure whether a detail came from the source or from your own inference, leave it out and flag it as an Open Question instead. Under-specifying and flagging is always the safer failure mode than inventing.

### 4. Build the Traceability Matrix

Every AC from the source must appear as a row, using its exact verbatim text (quoted, not paraphrased) and its ID from step 2. The "Covered by" column points to the FR(s) that implement it — or to the relevant Open Question if nothing in the spec addresses it yet (this can happen if an AC is too vague to formalize directly).

This matrix is the traceability contract: it should let a reviewer confirm two things at a glance — that nothing in the spec is unsupported, and that nothing in the source was dropped.

### 5. Save the output

Write the finished spec to `docs/specifications/` (relative to the project root), creating the directory if it doesn't exist. Name the file `<story-id-if-any>-<kebab-case-title>.md`, e.g. `story-142-guest-checkout.md`, or just `<kebab-case-title>.md` if the source has no story ID.

If a spec already exists at that path, treat the new run as the canonical update (overwrite it) — but mention to the user that you replaced an existing file, since specs are often iterated on as tickets evolve.

## Template

Use `assets/template.md` as the exact document structure — read it before drafting so section names and ordering stay consistent across every spec this skill produces.
