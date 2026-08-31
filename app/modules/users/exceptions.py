from dataclasses import dataclass

from app.core.exceptions import DomainError, FieldError
from app.core.problem_details import ProblemError


@dataclass(slots=True)
class RegistrationValidationError(DomainError):
    errors: list[FieldError]


class DuplicateEmailError(DomainError):
    """Raised when a registration email is already in use (case-insensitive)."""


class InvalidCredentialsError(DomainError):
    """Raised for a wrong password or an unknown email — same response either way."""


class EmailNotVerifiedError(ProblemError):
    type_slug = "email-not-verified"
    title = "Email Not Verified"
    status = 403
    detail = "This account's email address has not been verified yet."


class UnauthenticatedError(ProblemError):
    type_slug = "unauthenticated"
    title = "Unauthenticated"
    status = 401
    detail = "A valid access token is required."

    def __init__(self) -> None:
        super().__init__()
        self.headers = {"WWW-Authenticate": "Bearer"}
