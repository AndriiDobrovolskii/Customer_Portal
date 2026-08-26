from dataclasses import dataclass


class DomainError(Exception):
    """Base class for all domain-layer errors raised by services."""


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str
    code: str


@dataclass(slots=True)
class RegistrationValidationError(DomainError):
    errors: list[FieldError]


class DuplicateEmailError(DomainError):
    """Raised when a registration email is already in use (case-insensitive)."""
