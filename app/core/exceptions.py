from dataclasses import dataclass


class DomainError(Exception):
    """Base class for all domain-layer errors raised by services."""


@dataclass(frozen=True, slots=True)
class FieldError:
    field: str
    message: str
    code: str
