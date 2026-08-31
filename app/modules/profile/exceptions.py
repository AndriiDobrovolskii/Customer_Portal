from app.core.exceptions import FieldError
from app.core.problem_details import ProblemError


class PreconditionRequiredError(ProblemError):
    type_slug = "precondition-required"
    title = "Precondition Required"
    status = 400
    detail = "An If-Match header is required to update the profile."


class PreconditionFailedError(ProblemError):
    type_slug = "precondition-failed"
    title = "Precondition Failed"
    status = 412
    detail = "The profile has changed since the supplied ETag was read."


class ImmutableFieldError(ProblemError):
    type_slug = "immutable-field"
    title = "Immutable Field"
    status = 422
    detail = "One or more fields in the request are not editable."


class ValidationFailedError(ProblemError):
    type_slug = "validation-failed"
    title = "Validation Failed"
    status = 422
    detail = "One or more fields failed validation."

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors


class ReauthenticationRequiredError(ProblemError):
    type_slug = "reauthentication-required"
    title = "Reauthentication Required"
    status = 401
    detail = "The current password is required to change the email address."


class DuplicateEmailError(ProblemError):
    type_slug = "email-already-registered"
    title = "Email Already Registered"
    status = 409
    detail = "This email address is already registered to another account."


class TokenExpiredError(ProblemError):
    type_slug = "token-expired"
    title = "Email Change Token Expired"
    status = 400
    detail = "The email change token has expired. Request a new email change."


class TokenInvalidError(ProblemError):
    type_slug = "token-invalid"
    title = "Email Change Token Invalid"
    status = 400
    detail = "The email change token is invalid."
