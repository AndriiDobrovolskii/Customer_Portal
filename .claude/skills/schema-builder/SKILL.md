---
name: schema-builder
description: Generates Pydantic v2 request/response schemas (*Base, *Create, *Update, *AdminUpdate, *Read) for a module's schemas.py from an approved OpenAPI contract (openapi-designer) and DB design (db-designer). Use when a story's API design and DB design are both approved and schema code needs to be generated or extended ("generate the schemas for US-xxx," "write the Pydantic models for this endpoint," "build the request/response schemas"). Enforces extra="forbid" on every inbound schema, exclusion of privilege/system fields from self-service inbound schemas, from_attributes=True with an explicit field list on every *Read, v2-only idioms (ConfigDict, @field_validator, model_validate — never class Config, @validator, from_orm), and the AGENTS.md §4.4.5 sanctioned exception for joint multi-field validation (loosely-typed fields, joint check deferred to the service layer). Does not write service.py/router.py (service-and-router-builder) or models.py/repository.py/cache.py (data-layer-builder) — consumes their upstream design artifacts and produces only app/modules/<module>/schemas.py.
---

# Schema Builder

## Purpose

Turn an approved OpenAPI contract and DB design into the Pydantic v2 schemas that are the *only* type a router is allowed to touch (`AGENTS.md` §3). Schemas are the first line of defense against mass assignment and malformed input — `extra="forbid"` and privilege-field exclusion are enforced here, not hoped for downstream.

## Operational Contract

```
Precondition: openapi-designer and db-designer have both produced approved artifacts for the story.
Input Artifacts: docs/specifications/<StoryId>-*-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; docs/designs/database/<StoryId>-db-design.md, docs/designs/database/<StoryId>-entity-model.md; existing app/modules/<module>/schemas.py if any.
Output Artifacts: app/modules/<module>/schemas.py (created or extended).
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-*-spec.md` — functional requirements and validation rules.
2. `docs/designs/api/<StoryId>-openapi.yaml` and `-api-design.md` — the exact request/response shapes to implement. If only the `.gitignore` stub exists at this path, stop and tell the user `openapi-designer` needs to run first.
3. `docs/designs/database/<StoryId>-db-design.md` and `-entity-model.md` — which columns exist, which are sensitive. If only the stub exists, stop and name `db-designer`.
4. The target module's existing `schemas.py`, if any — mirror its structure and import order rather than reformatting it.
5. `AGENTS.md` §4 — "Models vs schemas" split, the `extra="forbid"` requirement, the mass-assignment/field-exclusion rule, the §4.4.5 joint-validation exception, and the v1→v2 idiom migration table.

## Preconditions

Both upstream designs are approved (Pass or Pass with Issues from `story-spec-reviewer` carried through). If extending an existing module, read its current `schemas.py` in full before adding anything — never assume a shape from a sibling module without checking this one.

## Workflow

1. **Enumerate schema classes.** For each entity the OpenAPI contract exposes, determine which of `*Base` / `*Create` / `*Update` / `*AdminUpdate` / `*Read` it actually needs — driven strictly by which HTTP operations the contract defines. Don't emit a class no operation calls for.
2. **Build the privilege-field exclusion set.** Start from AGENTS.md §4's example list (`id`, `is_active`, `is_superuser`, `role`, `email_verified_at`, `created_at`, `hashed_password`) as a **floor, not the actual set** — cross-check the DB design for this module's own sensitive/system-derived columns (a module may have its own `status`, `email_verified`, `pending_email`, etc.) and add every one the OpenAPI contract doesn't list as client-writable. Prefer emitting a positive whitelist constant (e.g. `_EDITABLE_FIELD_NAMES`) alongside the exclusion, mirroring `app/modules/profile/service.py`'s `_IMMUTABLE_FIELD_NAMES`/`_EDITABLE_FIELD_NAMES` pair, so a newly added column can't silently become writable by omission.
3. **Inbound schemas** (`*Create`, `*Update`, `*AdminUpdate`, filters, query models, webhook payloads): `model_config = ConfigDict(extra="forbid")` on every one. `*AdminUpdate` sits behind an authz dependency enforced at the router/dependency level (not in the schema) and may expose fields `*Update` excludes — but never a hard-excluded field unless the OpenAPI contract explicitly grants it to an admin scope.
4. **Outbound schemas** (`*Read`): `ConfigDict(from_attributes=True)` plus an explicit field list matching exactly what the OpenAPI response schema promises — never a bare passthrough of the ORM model's columns.
5. **Validation split** (`AGENTS.md` §4.4.5): independent single-field rules use `@field_validator`. Joint multi-field rules (e.g. "email malformed *and* password weak" needing a combined response) keep those specific fields loosely typed (`str | None`, `SecretStr | None` — never bare) and leave the joint check to the service layer, which collects `FieldError`s into one domain exception. Do not implement a joint check inside a schema — it would short-circuit on the first field and silently hide the others.
6. **No mass assignment.** Never write `Model(**payload.model_dump())` anywhere this schema is consumed (that's the service's job to avoid, but the schema must make it possible: keep the field set narrow). PATCH-style updates are meant to be applied via `model_dump(exclude_unset=True)` over the editable whitelist — document that expectation for the downstream service in a short comment if the pattern isn't obvious from the class name.
7. **v2 idioms only.** `ConfigDict(...)`, `@field_validator`, `model_validate` — never `class Config`, `.dict()`/`.json()`, `@validator`, `from_orm`.
8. Write or extend `app/modules/<module>/schemas.py` only. Preserve existing class order, imports, and enums if the file already exists.
9. Self-check against the Verification Checklist before finishing.

## Constraints

- `schemas.py` is the only file this skill may create or modify (per the import-linter "Module layers" contract's exhaustive file list — `router.py`, `dependencies.py`, `service.py`, `repository.py`, `cache.py`, `models.py`, `schemas.py`, `exceptions.py`, `__init__.py` are the only creatable files in a module; a new helper module needs explicit user sign-off, not silent invention).
- No `typing.Any`, no `# type: ignore`.
- No field invented beyond what the OpenAPI contract and DB design actually state.

## Verification Checklist

- [ ] Every inbound schema (`*Create`/`*Update`/`*AdminUpdate`/filter/query model) sets `extra="forbid"`.
- [ ] No self-service inbound schema declares any field from the module's actual privilege/system-field set (checked against this module's real columns, not just AGENTS.md's example list).
- [ ] Every `*Read` sets `from_attributes=True` and lists fields explicitly.
- [ ] No v1 idiom present (`class Config`, `.dict()`/`.json()`, `@validator`, `from_orm`).
- [ ] Any joint multi-field validation is confined to loosely-typed fields with the actual check deferred to the service — never inside a short-circuiting `@field_validator`.
- [ ] Every field traces to the OpenAPI contract and/or DB design — nothing invented.
- [ ] Only `app/modules/<module>/schemas.py` was created or modified.

## Outputs

- `app/modules/<module>/schemas.py`.

## Completion Criteria

Complete only when the checklist above is fully satisfied and every request/response shape the OpenAPI contract defines for this story is representable by an emitted schema class.
