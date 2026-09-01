from dataclasses import dataclass

from app.core.exceptions import DomainError, FieldError
from app.core.problem_details import ProblemError


@dataclass(slots=True)
class RegistrationValidationError(DomainError):
    errors: list[FieldError]


class DuplicateEmailError(DomainError):
    """Raised when a registration email is already in use (case-insensitive)."""


class InvalidCredentialsError(ProblemError):
    """Raised for a wrong password or an unknown email — same response either way."""

    type_slug = "invalid-credentials"
    title = "Invalid Credentials"
    status = 401
    detail = "The email or password is incorrect."


class EmailNotVerifiedError(ProblemError):
    type_slug = "email-not-verified"
    title = "Email Not Verified"
    status = 403
    detail = "This account's email address has not been verified yet."


class AccountDeactivatedError(ProblemError):
    type_slug = "account-deactivated"
    title = "Account Deactivated"
    status = 403
    detail = (
        "This account has been deactivated. Log in again to reactivate it within the grace period."
    )


class TooManyAttemptsError(ProblemError):
    type_slug = "too-many-attempts"
    title = "Too Many Attempts"
    status = 429
    detail = "Too many failed login attempts. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}


class TokenInvalidError(ProblemError):
    """Raised for RT-AC2/RT-AC3/RT-AC5/RT-AC6 — reused uniformly so an
    unknown, expired, revoked-by-logout, reused, or raced-out refresh token
    all produce an identical response (FR-3's indistinguishability
    requirement, resolved OD-3 scoped to status/body only).
    """

    type_slug = "token-invalid"
    title = "Refresh Token Invalid"
    status = 401
    detail = "This session can no longer be refreshed. Sign in again."


class UnauthenticatedError(ProblemError):
    type_slug = "unauthenticated"
    title = "Unauthenticated"
    status = 401
    detail = "A valid access token is required."

    def __init__(self) -> None:
        super().__init__()
        self.headers = {"WWW-Authenticate": "Bearer"}
