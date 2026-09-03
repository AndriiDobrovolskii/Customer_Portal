---
name: data-layer-builder
description: Generates SQLAlchemy 2.0 models.py and repository.py for a module from an approved DB design (db-designer), and its Valkey cache.py gateway when the design calls for caching. Use when a story's database design is approved and the data-access code needs to be generated or extended ("generate the models for US-xxx," "write the repository for this entity," "build the data layer," "add a cache gateway for this module"). Enforces Mapped[]/mapped_column() only (never Column()), lazy="raise_on_sql" plus the correct eager-loading strategy on every relationship (joinedload for many-to-one, selectinload for collections, contains_eager for join-filtered queries), fixed repository verb conventions (get_by_*, get_with_*, list_*, exists_by_*, create, update, delete), repositories that flush() and never raise (return None/empty on failure), no session.query()/create_all(), and — for cache.py — Valkey-only async access with a documented key-prefix helper, a TTL on every write, and fail-open-except-denylist read semantics per AGENTS.md §3. Does not write schemas.py (schema-builder) or service.py/router.py (service-and-router-builder), and does not author the Alembic migration itself (migration-manager, which autogenerates off this skill's model diff) — produces only app/modules/<module>/models.py, repository.py, and cache.py.
---

# Data Layer Builder

## Purpose

Turn an approved DB design into the SQLAlchemy models and repository a service will depend on, and — when the design calls for it — the Valkey cache gateway sitting alongside it. Both are the same architectural tier in this codebase's import-linter contract (`repository | (cache)` is one position in the layers list), which is why one skill owns both: they're the two ways a service reaches persistent/fast state, and neither may leak into the router.

## Operational Contract

```
Precondition: db-designer has produced an approved DB design for the story. If the DB/API design signals cached reads for this module, cache.py is in scope for this run too.
Input Artifacts: docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; docs/designs/api/<StoryId>-api-design.md (for cache-need signals); app/db/base.py; existing app/modules/<module>/{models.py,repository.py,cache.py} if any.
Output Artifacts: app/modules/<module>/models.py, repository.py, and cache.py (only when the module needs caching).
```

## Required Context

Read, in order:

1. `docs/designs/database/<StoryId>-db-design.md` and `-entity-model.md` — column types/lengths/nullability/defaults, constraints, indexes, relationships and their required loading strategy. If only the `.gitignore` stub exists at this path, stop and tell the user `db-designer` needs to run first.
2. `docs/designs/api/<StoryId>-api-design.md` — check whether any endpoint is flagged as needing a cached read; if the design is silent on caching, do not add one speculatively.
3. `app/db/base.py` — the declarative `Base` every model inherits from.
4. The target module's existing `models.py`/`repository.py`/`cache.py`, if any — extend in place, matching existing style.
5. `AGENTS.md` §3 (Architectural Constraints — the full layer table, eager loading, dependency injection, transactions) and §4 (repository verb naming, v1→v2 migration table).

## Preconditions

DB design is approved. State explicitly whether this run extends an existing model (e.g. new columns on `users`) or creates a new module — do not silently assume one or the other.

## Workflow — Models

1. One class per entity, `Mapped[]`/`mapped_column()` for every column, matching the design's declared type/length/nullable/default **exactly** — never rely on an implicit ORM or PostgreSQL default when the design states one explicitly. Table name snake_case plural, class name PascalCase singular. Never `Column()`.
2. **Relationships.** This codebase currently has none declared anywhere (`grep -rn "relationship(" app/` is empty — every existing module does manual FK-based queries instead). Only add a `relationship()` when the DB design explicitly calls for one (i.e. an endpoint needs nested data returned together). When you do: declare it `lazy="raise_on_sql"` unconditionally, and add a comment naming the eager-loading strategy the repository must use and why — `joinedload()` for many-to-one, `selectinload()` for a collection, `contains_eager()` for a join-filtered query. Never `lazy="joined"` as a model default; never `session.refresh()` to patch a missing relation. If the design doesn't need nested data returned in one call, prefer the existing codebase's pattern of a plain FK column plus a separate repository query — don't add a relationship "for completeness."

## Workflow — Repository

3. Only implement methods the DB design/API design actually need — no speculative CRUD. Fixed verbs: `get_by_<key>`, `get_with_<relationship>` (only when eager-loading), `list_<plural>`, `exists_by_<key>`, `create`, `update`, `delete`. `select()`/`session.execute()` only — never `session.query()`. Never `joinedload()` a collection combined with `LIMIT`/`OFFSET` (use `selectinload()` or a two-query pattern instead).
4. Mutations (`create`/`update`/`delete`) call `session.add()`/`session.execute()` then `await self._session.flush()` only — catch the constraint violation you expect (typically `IntegrityError`) and `await self._session.rollback()` then return `None`/`False` rather than letting it propagate, mirroring `app/modules/users/repository.py::create` and `app/modules/profile/repository.py::apply_email_change`.
5. **`commit()` passthrough — established precedent, not a new decision.** Every repository in this codebase (`users`, `profile`, `email_verification`) exposes `async def commit(self) -> None: await self._session.commit()`, called by the service, never by the repository itself mid-method. New/extended repositories keep this exact shape (`AGENTS.md` §1's "never invent a second way to do something that already has one" outweighs the more literal — and already-superseded — §3 sentence "repositories may flush(), never commit()").
6. Repository methods never raise from expected failure paths — return `None`/`False`/empty instead. Only a truly unexpected exception propagates unhandled.

## Workflow — Cache Gateway (`cache.py`, only when the design calls for it)

No `cache.py` exists anywhere in this codebase yet (`grep -r valkey app/` is empty) — build this fresh from `AGENTS.md` §3 directly, using `references/patterns.md`'s skeleton as a starting shape, not from an in-repo exemplar.

7. `cache.py` imports only the Valkey client type and stdlib — never `service`, `router`, or `sqlalchemy`. It returns primitives or typed DTOs only, never an ORM model.
8. Cache keys come from a documented prefix-helper function (e.g. `def _user_key(user_id: uuid.UUID) -> str`) — never an ad-hoc f-string built at each call site.
9. **Every write sets a TTL.** No bare `set`/`hset` call without an accompanying expiry.
10. The cache is never authoritative: every read path degrades to the database on a miss or a Valkey outage — **except** a token-denylist use case, which fails closed (treats an unreachable cache as "denied," never as "allow through"). State explicitly in a comment which behavior a given method implements if it isn't obvious from its name.
11. Async Valkey client only — never a sync client, never `time.sleep`.
12. The gateway class takes the Valkey client via `__init__` — it is instantiated once at the `lifespan` level and injected, never constructed ad hoc inside a request path (that wiring is `service-and-router-builder`'s job in `dependencies.py`; this skill only defines the gateway class itself).

## Constraints

- Only `models.py`, `repository.py`, `cache.py` may be created or modified by this skill (per the import-linter "Module layers" contract's exhaustive file list: `router.py`, `dependencies.py`, `service.py`, `repository.py`, `cache.py`, `models.py`, `schemas.py`, `exceptions.py`, `__init__.py` are the only creatable module files).
- No `session.query()`, no `create_all()`, no `lazy="joined"` model default.
- No cache write without a TTL; no cache read treated as authoritative except the denylist case.
- No `typing.Any`, no `# type: ignore`.

## Verification Checklist

- [ ] Every column uses `Mapped[]`/`mapped_column()` with explicit type/length/nullable/default from the design.
- [ ] Every relationship (if any) declares `lazy="raise_on_sql"` and a comment naming its required eager-loading strategy.
- [ ] Every repository method name matches the fixed verb set.
- [ ] No `session.query()`, no `create_all()`, no collection `joinedload()` combined with `LIMIT`/`OFFSET`.
- [ ] Every mutation calls `flush()` only inside `create`/`update`/`delete`; `commit()` exists solely as the established passthrough, called only by the service.
- [ ] No repository method raises on an expected failure path.
- [ ] If `cache.py` was created: every write has a TTL, keys come from a prefix helper, reads degrade to the DB on miss/outage except the documented denylist case, only the Valkey client type + stdlib are imported.
- [ ] Only `models.py`/`repository.py`/`cache.py` were created or modified.

## Outputs

- `app/modules/<module>/models.py`, `repository.py`, and `cache.py` (only when needed).

## Completion Criteria

Complete only when the checklist above is fully satisfied, every query pattern the DB/API design implies has a corresponding repository method, and — if a cache gateway was in scope — every cache write it defines carries a TTL.

---

# Harness Contract

This skill is a sub-step of the `IMPLEMENTATION` stage
(`docs/workflow/stage-map.yaml`, `type: composite_skill`). It produces
models.py, repository.py, cache.py - source code, not a registry artifact. `story-orchestrator`
records its progress in `pipeline_status`
(`docs/catalog/<StoryId>-pipeline-status.md`) and sets
`implementation_substep` in `workflow-state.yaml`.

## Canonical sources

- Workflow / stage / loop-back keys: `docs/workflow/stage-map.yaml` (`IMPLEMENTATION`).
- Artifact paths: `docs/workflow/artifact-paths.yaml` - **authoritative**.
  Resolve `story`, `open_decisions`, `specification`, `specification_review`, `impact_analysis`, `implementation_plan`, `task_breakdown`, `plan_review`, `api_design`, `openapi`, `database_design`, `entity_model`, `test_strategy`, `ac_test_matrix`. Any path shown elsewhere in this skill is illustrative;
  the registry wins.
- Status vocabularies: `docs/workflow/artifact-lifecycle.md`.
- Front matter and the staleness contract: `docs/workflow/artifact-schema.md`.
- Workflow state: `docs/workflow/state-schema.md`.

## Inputs (registry keys)

- `story`
- `open_decisions`
- `specification`
- `specification_review`
- `impact_analysis`
- `implementation_plan`
- `task_breakdown`
- `plan_review`
- `api_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `openapi`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `database_design`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `entity_model`  (conditional - absent when its design stage recorded `NOT_APPLICABLE`)
- `test_strategy`
- `ac_test_matrix`

## Preconditions (harness)

- Every consumed artifact is current: `status` is not `SUPERSEDED` or
  `ARCHIVED`, and the `version` this skill records in its own `inputs` is the
  version actually on disk. A stale input is `BLOCKED`, not a caveat.
- No `TODO` / `TBD` / `FIXME` / unresolved blocking Open Decision in an
  `APPROVED` input that this stage depends on.
- `docs/workflow/active-story.yaml` and `docs/workflow/workflow-state.yaml`
  agree on which story is active.

## Result Envelope

Return exactly this. The orchestrator aggregates the sub-steps; only when all
four have returned `PASS` does the `IMPLEMENTATION` stage advance.

```yaml
result:
  verdict: PASS | CHANGES_REQUIRED | BLOCKED
  stage: IMPLEMENTATION
  substep: data-layer-builder
  story: <StoryId>
  artifacts: []          # source files, listed by path
  next_substep: <the next builder, or null>
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
