# Service/Router Patterns — Exemplars

## Exception shapes: `app/modules/users/exceptions.py`, `app/modules/profile/exceptions.py`

Exactly two shapes exist in this codebase — pick one, never invent a third:

- **Bare `DomainError` subclass** (`InvalidCredentialsError`, `DuplicateEmailError` in `users`) — for errors a generic handler in `main.py` maps by type. `RegistrationValidationError` shows the variant that carries data: `@dataclass(slots=True)` with an `errors: list[FieldError]` field.
- **`ProblemError` subclass** (everything in `profile/exceptions.py`, plus `EmailNotVerifiedError`/`UnauthenticatedError` in `users`) — a self-describing RFC-7807-style error with `type_slug`/`title`/`status`/`detail` class attributes. Override `__init__` only when the instance needs extra state: `ValidationFailedError` takes `errors: list[FieldError]`; `UnauthenticatedError` sets a `WWW-Authenticate` response header.

## Service: `app/modules/users/service.py`

- `UserRepositoryProtocol` — a narrow `Protocol` declaring only the methods `UserService` actually calls, not the full `UserRepository` surface. Define a fresh one per service, don't import the concrete repository class as the type.
- `_validate_email`/`_validate_password` — the AGENTS.md §4.4.5 joint-validation pattern in practice: independent helper functions appending to a shared `errors: list[FieldError]`, called from the service method, raising `RegistrationValidationError(errors=errors)` once at the end so a single response reports every violation instead of stopping at the first.
- `register_user` — the canonical multi-step business operation: validate → hash password (note `hash_password` is `await`ed — CPU-bound Argon2 work goes through `anyio.to_thread.run_sync` under the hood per AGENTS.md §3, called like any other async function from the service) → `repository.create()` → check `None` for the uniqueness-conflict case → **one `commit()`** → then a `try`/`except Exception` + `logger.exception(...)` best-effort side effect (issuing + emailing the verification token) that must never undo the already-committed registration → return `UserRead.model_validate(user)`.
- `authenticate_user` — shows the "don't leak which check failed" security discipline from AGENTS.md §7 in code: the wrong-password check happens *before* the email-verification check, both raising exactly as much information as `InvalidCredentialsError`/`EmailNotVerifiedError` state and nothing more.
- `revoke_other_sessions` — the cross-module service→service pattern, with a docstring naming it as exactly that ("Cross-module collaborator for the profile module's ... Owns its own commit").

## Router: `app/modules/users/router.py`, `app/modules/profile/router.py`

- `register_user` (users) — `response_model`/`status_code` on the decorator, a thin body (one service call), and a `Location` header set from the returned `UserRead.id` — response shaping, not business logic.
- `update_profile` (profile) — shows a route needing a raw `dict[str, JsonValue]` body (for a PATCH-with-partial-fields flow) declared via `openapi_extra`, plus a status code chosen conditionally from what the service reports (`200` vs `202` depending on whether an email-change flow was triggered) — the router still does no business logic itself, it only maps the service's already-decided outcome to an HTTP status/header.

## Dependencies: `app/modules/users/dependencies.py`

- `get_user_service` composes `UserRepository(session)` plus two already-injected collaborators (a cross-module `EmailVerificationServiceDep` and an `EmailSender`) — the standard shape for a service factory that itself depends on another module's service.
- `get_current_user` + `CurrentUserDep` — the auth-dependency pattern every protected route in another module reuses via `from app.modules.users.dependencies import CurrentUserDep`, never redefining its own token-decoding logic.
