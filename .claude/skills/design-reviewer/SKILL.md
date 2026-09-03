---
name: design-reviewer
description: >
  Independently reviews a story's API design (OpenAPI contract + API design
  notes from openapi-designer) and database design (DB design + entity model
  from db-designer) together in one pass, against the approved specification,
  AGENTS.md sections 3 and 4, and cross-model consistency. Owns the
  DESIGN_REVIEW stage, between DB_DESIGN and IMPACT_ANALYSIS. Use when both
  designs for a story are drafted and need a quality gate before impact
  analysis and planning ("review the designs for US-x.y", "are these designs
  ready to plan against"). Checks that every externally-observable acceptance
  criterion maps to an operation, that inbound schemas will be able to carry
  extra="forbid" without privilege fields, that the DB design states explicit
  column types/nullability/uniqueness/indexes and an eager-loading strategy per
  relationship, that no ORM model would cross the service to router boundary,
  and that DTO fields and column definitions agree where they represent the same
  data. Does not edit designs, write schemas.py/models.py, author migrations, or
  resolve Open Decisions - findings are reported and a loop-back target named.
---

# Design Reviewer

## Purpose

Own the **DESIGN_REVIEW** stage. Provide a quality gate on the API and database
designs before the story commits to impact analysis and planning.

Review both designs together in one pass. Do not split into separate API and DB
review stages.

This skill does not edit designs. It records findings and, on
`CHANGES_REQUIRED`, names the loop-back target.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml`
  (`DESIGN_REVIEW`; keys `changes_required_api`, `changes_required_database`,
  `changes_required_both`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` — authoritative; resolve
  every path from a registry key. Paths shown below are illustrative.
- Status vocabulary: `docs/workflow/artifact-lifecycle.md`.
- Front matter: `docs/workflow/artifact-schema.md`.

## Operational Contract

```
Precondition: SPEC_REVIEW returned PASS and HUMAN_SPEC_APPROVAL was recorded; API_DESIGN and DB_DESIGN have each either produced their artifacts or recorded NOT_APPLICABLE.
Input Artifacts: story; specification; specification_review; api_design; openapi; database_design; entity_model; open_decisions; AGENTS.md sections 3-4; docs/ARCHITECTURE.md; docs/product/business-rules.md; docs/product/non-functional-requirements.md.
Output Artifacts: docs/reviews/designs/<StoryId>-design-review.md.
```

## Inputs (registry keys)

- `story`
- `specification`, `specification_review`
- `api_design`, `openapi` (conditional — may be `NOT_APPLICABLE` upstream)
- `database_design`, `entity_model` (conditional — same)
- `open_decisions`
- Architecture references: `AGENTS.md` §3 (layering, ORM containment, eager
  loading, DI, transactions, async I/O) and §4 (naming, typing, models vs
  schemas, `extra="forbid"`, v2/2.0 idioms, errors, migrations);
  `docs/ARCHITECTURE.md`
- `docs/product/business-rules.md`, `docs/product/non-functional-requirements.md`

## Preconditions

- `specification_review` verdict is `PASS` and `HUMAN_SPEC_APPROVAL` was
  recorded. The orchestrator only routes here after that gate.
- For each design area not explicitly marked `NOT_APPLICABLE` by the approved
  specification, the corresponding artifacts exist and are `DRAFT` or
  `APPROVED` — never `SUPERSEDED`.
- Every input artifact's recorded `version` matches the current file
  (`artifact-schema.md` staleness contract). A stale input → `BLOCKED`.
- No blocking Open Decision affecting API or persistence design.

If a design area is `NOT_APPLICABLE`, confirm the specification actually says so
and review only the other area.

If **both** `API_DESIGN` and `DB_DESIGN` recorded `NOT_APPLICABLE`, there is no
design to review. Still produce a `design_review` artifact recording both areas
as out of scope (citing the specification), and return
`verdict: NOT_APPLICABLE` — the orchestrator advances to `IMPACT_ANALYSIS`.

## Review checklist

### API design (when applicable)

- every acceptance criterion with externally observable behavior maps to an
  operation and status code in the OpenAPI contract;
- paths, methods, media type, versioning (`/v1/...`), and the error model follow
  the existing contract — RFC 7807 problem details, consistent with
  `core/problem_details.py` and the modules already shipped;
- request and response schemas are DTOs. **No ORM model appears in the
  contract** (`AGENTS.md` §3, ORM containment);
- every inbound schema in the design can carry `extra="forbid"`, and **declares
  no privilege or system field** — no `id`, `is_active`, `is_superuser`, `role`,
  `email_verified_at`, `created_at`, `hashed_password` on a self-service
  `*Create`/`*Update` (§4, mass assignment). A privileged variant is a separate
  `*AdminUpdate` behind an authz dependency;
- every outbound `*Read` has an explicit field list, and no field exposes a
  credential, hash, token, session id, or internal-only value;
- validation constraints from the specification appear in the contract, and any
  field deferred to joint service-layer validation is called out with the
  `ARCHITECTURE.md` §4.4.5 exception cited rather than left implicit;
- error responses cover the documented failure cases (400/401/403/404/409/422 as
  applicable) and never leak whether an account exists — a uniform `401` on
  login-style failures;
- authentication and the required permission scope are stated **per operation**
  and match the scope system the `roles` module actually enforces;
- backward compatibility: any breaking change to an existing contract is named.

### Database design (when applicable)

- entities trace to business concepts in `business-glossary.md` /
  `business-rules.md`;
- expressed as SQLAlchemy 2.0 declarative — `Mapped[T]` / `mapped_column()`,
  never `Column()`; models singular, tables plural (§4 naming);
- explicit type, length, nullability, uniqueness, default, and index for every
  column. No reliance on a framework default;
- **every relationship declares `lazy="raise_on_sql"`** and the design names the
  eager-loading strategy the repository will use: `joinedload()` for
  many-to-one, `selectinload()` for collections, `contains_eager()` when
  filtering on the join. A relationship with no stated strategy is a Major
  finding — under `AsyncSession` a lazy load is a production 500, not slow code;
- no `joinedload()` on a collection combined with `LIMIT`/`OFFSET`;
- sensitive columns (password hash, tokens, PII) are identified with their
  storage rule — Argon2id for passwords, hashed-at-rest for tokens, never
  plaintext or reversible encryption;
- the migration story is stated: what Alembic will generate, and which parts the
  `Rewriter` in `migrations/env.py` cannot reach and therefore need an
  `sa.inspect(op.get_bind())` guard (raw `op.execute()`, backfills,
  `AlterColumnOp`, enum edits) — §4 Migrations;
- PostgreSQL hazards named where they apply: `CREATE INDEX CONCURRENTLY` in its
  own migration with `autocommit_block()` + `if_not_exists=True`;
  `ALTER TYPE ... ADD VALUE` split across transactions; idempotent batched
  backfills; expand → migrate → contract for destructive changes;
- no `create_all()`, and no schema change proposed outside a migration;
- relationships and cardinality are explicit.

### Cross-model consistency

- every resource in the API maps to a coherent persistence model;
- field names, types, and constraints agree between DTO schemas and columns
  where they represent the same data (a `str` field with no max length against a
  `String(255)` column is a finding);
- a constraint is enforced at both levels where it matters — e.g. email
  uniqueness in schema validation *and* as a DB unique constraint;
- the layering in `AGENTS.md` §3 survives the design: nothing requires a router
  to touch a repository or a service to import `fastapi`;
- pagination, filtering, and sorting in the contract are actually supportable by
  the indexes the DB design declares;
- **no business decision appears in a design that is absent from the
  specification or an approved Open Decision.** That is a finding, not something
  to accept.

## Findings

Classify each: `Critical` (blocks), `Major` (must fix before proceeding),
`Minor` (advisory). For every `Critical` / `Major` finding record the design area
(API / database / both), the evidence, and the required correction.

## Output

Create `design_review` at its registry path
(`docs/reviews/designs/{story_id}-design-review.md`) with front matter per
`artifact-schema.md` (`artifact_type: design_review`).

Sections: Summary; Reviewed Artifacts (paths + versions); API Design Review;
Database Design Review; Cross-Model Consistency; Security Review of Designs;
Findings (id, severity, area, evidence, required correction); Open Decisions;
Limitations; Verdict Rationale.

## Result Envelope

Return exactly this; `story-orchestrator` records the transition — this skill
does not touch `workflow-state.yaml`:

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED | NOT_APPLICABLE
  stage: DESIGN_REVIEW
  story: <StoryId>
  artifact_status: APPROVED        # of the design_review artifact itself
  artifacts:
    - docs/reviews/designs/<StoryId>-design-review.md
  next_stage: IMPACT_ANALYSIS
  loop_back_stage: null            # or API_DESIGN / DB_DESIGN
  blocking_issues: []
  non_blocking_findings: []
```

Loop-back selection (keys must match `stage-map.yaml` `DESIGN_REVIEW.loop_back`):

| Situation | `loop_back_stage` | key |
|---|---|---|
| API contract wrong or incomplete | `API_DESIGN` | `changes_required_api` |
| DB design wrong or incomplete | `DB_DESIGN` | `changes_required_database` |
| Both need changes | `API_DESIGN` | `changes_required_both` |

- `PASS` — no `Critical`/`Major` findings; both designs are sound and consistent.
- `CHANGES_REQUIRED` — `Critical` or `Major` findings; set `loop_back_stage`.
- `BLOCKED` — missing or stale mandatory input, or a blocking Open Decision.
- `NOT_APPLICABLE` — both design areas recorded `NOT_APPLICABLE` upstream; the
  artifact documents that and `next_stage` is `IMPACT_ANALYSIS`.

## Prohibited

- Do not edit designs, the OpenAPI file, the specification, `AGENTS.md`, or
  `docs/ARCHITECTURE.md`.
- Do not write `schemas.py`, `models.py`, `repository.py`, or a migration.
- Do not resolve Open Decisions.
- Do not update workflow state.
- Do not create commits or Pull Requests.
- Do not accept a design because it "looks reasonable" — every checklist row is
  either satisfied with evidence, marked N/A with a reason, or a finding.

## Verification Checklist

- [ ] Every acceptance criterion with observable behavior was traced to an
      operation, or recorded as having none.
- [ ] Every relationship in the DB design has a named eager-loading strategy.
- [ ] Every inbound schema was checked against the privilege-field list.
- [ ] Every input artifact's version was checked for staleness.
- [ ] The chosen `loop_back_stage` key exists in `stage-map.yaml`.

## Completion Criteria

Complete when the `design_review` artifact exists with a verdict, every finding
carries evidence and a required correction, and — on `CHANGES_REQUIRED` — a
loop-back key valid for this stage is named.
