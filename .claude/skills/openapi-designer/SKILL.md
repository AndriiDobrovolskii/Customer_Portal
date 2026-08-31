---
name: openapi-designer
description: Produces the authoritative OpenAPI contract and API design notes for a story from its approved specification, before any router/schema code is written. Use when a story's spec has passed review and the endpoint shape needs to be decided ("design the API for US-xxx," "write the OpenAPI contract for this story"). Implementation follows this contract rather than inventing endpoints during coding; this skill does not write FastAPI route handlers or Pydantic schema classes itself.
---

# OpenAPI Designer

## Purpose

Design the API contract before implementation begins. The output is the authoritative source for what a router and its Pydantic schemas must look like — endpoints should not be invented during coding if a contract already exists (this project's own artifact-driven flow: Specification → OpenAPI Design → Implementation, per `docs/workflow/stage-map.yaml`).

## Operational Contract

```
Precondition: story-spec-reviewer's verdict is Pass or Pass with Issues (never Fail).
Input Artifacts: docs/specifications/<StoryId>-spec.md, docs/reviews/specifications/<StoryId>-spec-review.md, docs/product/business-rules.md, docs/product/business-glossary.md, docs/product/non-functional-requirements.md.
Output Artifacts: docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-spec.md` — functional requirements, acceptance criteria, validation rules.
2. `docs/reviews/specifications/<StoryId>-spec-review.md` — the design must not proceed against a **Fail** verdict; a **Pass with Issues** should have its open issues reflected as explicit gaps in the design output, not silently resolved.
3. `docs/product/business-rules.md`, `docs/product/business-glossary.md`, `docs/product/non-functional-requirements.md` — cross-cutting constraints (e.g. this project's response-model and status-code discipline from `AGENTS.md` §6.7).

## Design Responsibilities

For every endpoint the story requires, define:

- Path, HTTP method, and whether it sits under the existing `app/api/v1/` aggregation.
- Request schema — required/optional fields, types, `extra="forbid"` per this project's convention (`AGENTS.md` §4).
- Response schema per status code, and the exact `response_model`/`status_code` FastAPI will declare.
- Validation rules carried over from the spec (lengths, allowed values, uniqueness) — every validation rule in the spec must appear here; a contract that's silent on a stated rule is incomplete.
- Authentication requirement (token required? which scheme?) and authorization requirement (which role/permission scope, if any).

## Error Handling

Explicitly define the response shape for each status the endpoint can plausibly return: `400`, `401`, `403`, `404`, `409` — only include the ones the spec's error-handling section actually implies; don't pad the contract with statuses nothing in the spec calls for.

## Validation

Every constraint stated in the spec's Validation Rules section must be reflected here. If the OpenAPI design needs a constraint the spec never stated, that's a spec gap — log it rather than deciding it here.

## Outputs

Create:

- `docs/designs/api/<StoryId>-openapi.yaml` — the OpenAPI fragment (paths, schemas, responses) for this story's endpoints.
- `docs/designs/api/<StoryId>-api-design.md` — narrative: what each endpoint does, why it's shaped this way, and any open questions not resolved by the spec.

## Completion Criteria

Complete only when: the OpenAPI contract exists and is valid YAML, every acceptance criterion in the spec maps to at least one endpoint/response, authentication and authorization requirements are stated per endpoint (not just once for the whole story), and every validation rule from the spec is represented in a request schema.
