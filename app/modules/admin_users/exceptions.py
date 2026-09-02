from app.core.exceptions import FieldError
from app.core.problem_details import ProblemError


class EmailAlreadyRegisteredError(ProblemError):
    """FR-6, BR-001: case-insensitive duplicate, enforced atomically at the
    data layer via the existing unique constraint on users.email.
    """

    type_slug = "email-already-registered"
    title = "Email Already Registered"
    status = 409
    detail = "This email address is already registered to another account."


class PreconditionRequiredError(ProblemError):
    """FR-10: If-Match header absent. Same slug/mechanism as
    app/modules/profile/exceptions.py's identical precedent.
    """

    type_slug = "precondition-required"
    title = "Precondition Required"
    status = 400
    detail = "An If-Match header is required to update this user."


class PreconditionFailedError(ProblemError):
    """FR-10: If-Match doesn't match the current ETag."""

    type_slug = "precondition-failed"
    title = "Precondition Failed"
    status = 412
    detail = "This user has changed since the supplied ETag was read."


class ImmutableFieldError(ProblemError):
    """FR-11: id/created_at/email_verified/roles in the request body."""

    type_slug = "immutable-field"
    title = "Immutable Field"
    status = 422
    detail = "One or more fields in the request are not editable through this endpoint."


class ValidationFailedError(ProblemError):
    type_slug = "validation-failed"
    title = "Validation Failed"
    status = 422
    detail = "One or more fields failed validation."

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors


class NotFoundError(ProblemError):
    """FR-12, FR-17b, FR-21, FR-23: unknown user id."""

    type_slug = "not-found"
    title = "User Not Found"
    status = 404
    detail = "No user was found with that identifier."


class AlreadyDeactivatedError(ProblemError):
    type_slug = "already-deactivated"
    title = "Already Deactivated"
    status = 409
    detail = "This user is already deactivated."


class CannotTargetSelfError(ProblemError):
    """FR-15: deliberately 409, not roles/exceptions.py's own 403
    CannotTargetSelfError for its own MU-AC15-unrelated check — same slug,
    different status, matching each story's own stated AC (each module
    owns its own exceptions per this project's established convention).
    """

    type_slug = "cannot-target-self"
    title = "Cannot Target Self"
    status = 409
    detail = "Use the self-service endpoint to deactivate your own account."


class InvalidStateTransitionError(ProblemError):
    type_slug = "invalid-state-transition"
    title = "Invalid State Transition"
    status = 409
    detail = "This user is not awaiting an invitation."


class TooManyAttemptsError(ProblemError):
    """FR-20: mirrors app/modules/email_verification/exceptions.py's
    identical TooManyAttemptsError pattern (dynamic Retry-After header).
    """

    type_slug = "too-many-requests"
    title = "Too Many Requests"
    status = 429
    detail = "Too many invitations resent for this account. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}
