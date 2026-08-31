---
name: service-and-router-builder
description: Generates service.py and router.py (and, where new, dependencies.py/exceptions.py) for a module implementing an approved OpenAPI contract (openapi-designer), consuming the models.py/repository.py/cache.py from data-layer-builder and the schemas.py from schema-builder. Use when a story's contract, DB design, models/repository, and schemas already exist and the business logic and HTTP layer need to be written or extended ("implement the service and router for US-xxx," "wire up this endpoint," "write the FastAPI route and service method"). Enforces the exact layer import table from AGENTS.md §3 (router imports schemas/service/dependencies only, never models/repository/sqlalchemy/AsyncSession/Valkey; service imports schemas/repository/cache-gateway/models/core.* only, never fastapi/starlette/HTTPException/raw clients), the service owning the transaction with one commit per business operation and cache writes after commit, DomainError/ProblemError subclasses raised from services and never HTTPException, ORM objects never crossing the service→router boundary (Schema.model_validate(orm_obj) returned while the session is open, with explicit -> *Read annotations everywhere), response_model and status_code declared on every route, and all collaborators injected via Depends (router) or __init__ (service) — never a raw client or module-level global. Does not design the API contract (openapi-designer) and does not write models/repository/cache/schemas (data-layer-builder, schema-builder) — it is the last code-generating step before migration-manager (which must already have run for any model change) and gate-enforcer.
---

# Service And Router Builder

## Purpose

Implement the business logic and HTTP surface for an approved OpenAPI contract, in that exact order of responsibility: the service owns transactions, exceptions, and cross-module calls; the router is a thin translation from HTTP to service calls and back. This is the layer where AGENTS.md §3's import table is easiest to violate by accident (an `AsyncSession` sneaking into a router, an `HTTPException` sneaking into a service) — this skill exists specifically to make that structurally hard to do.

## Operational Contract

```
Precondition: schema-builder and data-layer-builder have both produced their outputs for this module; migration-manager has already run for any model change this story makes.
Input Artifacts: docs/specifications/<StoryId>-*-spec.md; docs/designs/api/<StoryId>-openapi.yaml, docs/designs/api/<StoryId>-api-design.md; the module's models.py, repository.py, schemas.py, and cache.py (if data-layer-builder created one); app/core/exceptions.py; app/core/problem_details.py.
Output Artifacts: app/modules/<module>/service.py, router.py, and dependencies.py/exceptions.py where new.
```

## Required Context

Read, in order:

1. `docs/specifications/<StoryId>-*-spec.md` — the business rules and validation rules the service must enforce.
2. `docs/designs/api/<StoryId>-openapi.yaml` and `-api-design.md` — the exact endpoints, status codes, and response shapes to implement.
3. The module's `models.py`, `repository.py`, `schemas.py`, and `cache.py` if present — stop and name whichever of `schema-builder`/`data-layer-builder` is missing rather than guessing at a shape.
4. `app/core/exceptions.py` (`DomainError`, `FieldError`) and `app/core/problem_details.py` (`ProblemError`) — the two sanctioned exception shapes in this codebase.
5. `AGENTS.md` §3 in full (the layer import table, ORM containment, eager loading, dependency injection, transactions, async I/O) and §4's Error Handling / Exception Ownership bullets.
6. Sibling exemplars: `app/modules/users/{service,router,dependencies,exceptions}.py`, `app/modules/profile/{service,router,dependencies,exceptions}.py`.

## Preconditions

`schemas.py`, `models.py`, and `repository.py` already exist for this module. If any is missing, stop and name which skill (`schema-builder`/`data-layer-builder`) needs to run first rather than inventing a placeholder.

## Workflow

1. **Exceptions.** For each error response the OpenAPI contract implies, ensure a module-specific exception exists in `app/modules/<module>/exceptions.py` (a permitted new file). Exactly two shapes exist in this codebase — use one, never invent a third:
   - A bare `DomainError` subclass, mapped to a response by a generic handler in `main.py` (e.g. `InvalidCredentialsError`).
   - A `ProblemError` subclass with `type_slug`/`title`/`status`/`detail` for a specific, self-describing response (e.g. `EmailNotVerifiedError`, `DuplicateEmailError`). Override `__init__` only when the error needs to carry extra data (`ValidationFailedError.errors`, `UnauthenticatedError`'s `WWW-Authenticate` header) or accept constructor args (`RegistrationValidationError.errors`).
2. **Service class.** `<Module>Service.__init__` takes a narrowly-scoped `Protocol`-typed repository (define `<Module>RepositoryProtocol` with only the methods actually called — mirror `UserRepositoryProtocol`) and any other collaborators (cache gateway, cross-module service, email sender) via constructor injection only. Every public method has an explicit return type annotation and a business-intent name (`register_user`, `authenticate_user` — never a bare CRUD verb copied from the repository).
3. **Validation ownership.** Single-field checks already live in the schema (from `schema-builder`). Joint multi-field checks collect `FieldError`s into a list and raise a `DomainError` subclass carrying them (mirror `UserService.register_user`'s `_validate_email`/`_validate_password` + `RegistrationValidationError(errors=errors)` pattern) — never reimplement what Pydantic already validated.
4. **Transaction boundary.** Exactly one `await self._repository.commit()` per business operation, placed after every write for that operation has been flushed. A best-effort side effect that must not roll back an already-committed operation (e.g. sending a verification email) is wrapped in its own `try`/`except Exception` + `logger.exception(...)`, mirroring `UserService.register_user`'s token-issuance block exactly — never let a non-critical side effect's failure propagate and undo a committed write. If the module has a `cache.py`, any cache write happens strictly after that commit, never before or interleaved with it.
5. **ORM containment.** Build the return value via `Schema.model_validate(orm_obj)` while the session is still open, with an explicit `-> *Read` (or other domain-type) return annotation on every method that returns data. The ORM object itself must never appear in a return statement, a router-visible type, or cross into `router.py`.
6. **Cross-module calls.** When this service needs another module's behavior, depend on that module's *service* (Protocol-typed, injected via `__init__`), never its router — mirror `UserService.revoke_other_sessions`'s doc comment explicitly naming this as the sanctioned cross-module pattern.
7. **Router.** One function per OpenAPI operation: `@router.<verb>(path, response_model=<Schema>, status_code=status.HTTP_xxx)` — every route without exception. Signature takes only schemas, a `<Module>ServiceDep`, and auth deps (`CurrentUserDep`, etc.) — never `AsyncSession`, a repository, or anything from `sqlalchemy`. Router body is a thin call into the service plus response shaping only (e.g. a `Location` header per `users/router.py`, or a conditional status code per `profile/router.py`'s 200-vs-202 pattern) — no business logic in the router.
8. **Dependencies.** One `get_<module>_service` factory in `dependencies.py` composing the repository (and cache gateway/collaborators) from injected `AsyncSession`/other `Depends`, and one `<Module>ServiceDep = Annotated[<Module>Service, Depends(get_<module>_service)]` alias — mirror `app/modules/users/dependencies.py`'s shape exactly, including how it composes a cross-module service dependency (`EmailVerificationServiceDep`) as a parameter to its own factory.
9. **Self-check** before finishing: grep the new/changed `router.py` for `sqlalchemy`, `AsyncSession`, `models`, or `repository` imports — must be zero. Grep the new/changed `service.py` for `fastapi`, `starlette`, or `HTTPException` imports — must be zero.
10. Write the files; report which endpoints/service methods were added and which OpenAPI operations they satisfy.

## Constraints

- Only `service.py`, `router.py`, `dependencies.py`, `exceptions.py` may be created or modified by this skill (per the import-linter "Module layers" contract's exhaustive file list).
- Every route declares both `response_model` and `status_code` — no exceptions.
- No `HTTPException` raised from a service; no bare `except:`.
- Cross-module calls go through another module's service, never its router.
- No `typing.Any`, no `# type: ignore`.

## Verification Checklist

- [ ] `router.py` imports only schemas/service/dependencies (+ fastapi/starlette/stdlib) — no models, repository, sqlalchemy, `AsyncSession`, or cache client.
- [ ] `service.py` imports only schemas/repository/cache-gateway/models/`core.*` (+ stdlib) — no fastapi, starlette, `HTTPException`, or a manually constructed client.
- [ ] Every service method returning data has an explicit `-> *Read`/domain-type annotation; no ORM object in any return statement.
- [ ] Exactly one `repository.commit()` per business operation, after all its writes; any cache write comes strictly after that commit.
- [ ] Every route declares `response_model` and `status_code`.
- [ ] Every collaborator arrives via `Depends` (router) or `__init__` (service) — no module-level global, no manually constructed client.
- [ ] Cross-module calls target another module's service, never its router.
- [ ] Every raised exception is a `DomainError`/`ProblemError` subclass in this module's `exceptions.py` — never `HTTPException`, never a bare `Exception`.

## Outputs

- `app/modules/<module>/{service.py,router.py}`, and `dependencies.py`/`exceptions.py` where new.

## Completion Criteria

Complete only when the checklist above is fully satisfied, every OpenAPI operation for the story has a corresponding router function, and no `typing.Any` appears anywhere in the new code.
