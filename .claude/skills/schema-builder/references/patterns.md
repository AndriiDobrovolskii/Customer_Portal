# Schema Patterns — Exemplars

Read these before drafting new schemas so new code matches this codebase's actual conventions, not a generic Pydantic v2 tutorial shape.

## `app/modules/users/schemas.py`

- `UserCreate` — inbound, `extra="forbid"`, fields loosely typed (`str | None`, `SecretStr | None`) because registration needs joint email+password validation in the service (AGENTS.md §4.4.5) rather than a schema validator that short-circuits on the first bad field.
- `UserRead` — outbound, `from_attributes=True`, explicit field list, uses `Field(serialization_alias=...)` for a camelCase wire name without renaming the Python attribute.
- `LoginRequest`/`LoginResponse` — a request/response pair that doesn't map 1:1 to a `*Create`/`*Read` entity shape; not every schema needs to fit the `*Base/*Create/*Update/*Read` mold if the OpenAPI operation itself isn't a CRUD verb.

## `app/modules/profile/schemas.py`

- `ProfileUpdate` — the canonical example of the §4.4.5 exception in this codebase: its docstring states outright *why* `current_password` isn't validated jointly with `email` inside the schema ("a schema-level model_validator can't attach the failure to the `current_password` field, only to the model as a whole"). Reuse this reasoning verbatim when a new schema needs the same exception — don't re-derive it from scratch each time.
- `_timezone_must_be_a_known_iana_name` — a single-field `@field_validator` example: independent, no cross-field dependency, safe to enforce directly in the schema.
- `ProfileRead` — every field explicit, including nullable ones (`pending_email: str | None`), never a bare `**model.__dict__` passthrough.

## Privilege-field whitelist precedent

`app/modules/profile/service.py` defines `_IMMUTABLE_FIELD_NAMES` and `_EDITABLE_FIELD_NAMES` (near the top of the file, alongside `_ETAG_FIELDS`) as the enforced source of truth for which columns a self-service update may touch — the story's stated immutable set (`id`, `created_at`, `role`, `email_verified`) plus `pending_email`, which is system-derived and never legitimately client-writable even though it isn't in AGENTS.md's example list. **This is the concrete proof that AGENTS.md §4's privilege-field list is a floor, not the ceiling** — every new module needs its own equivalent whitelist derived from its actual columns, not a copy of AGENTS.md's example set.

When a module's schemas.py doesn't already define such a whitelist constant, add one (e.g. `_EDITABLE_FIELD_NAMES` in the schema module, or delegate the decision to whichever file the service will read it from) so the exclusion logic is explicit and grep-able rather than implicit in which fields simply don't appear on the `*Update` class.
