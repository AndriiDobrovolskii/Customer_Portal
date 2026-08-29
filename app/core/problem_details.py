from app.core.exceptions import DomainError, FieldError


class ProblemError(DomainError):
    """Base for domain errors rendered as RFC 7807 application/problem+json.

    Subclasses set the class attributes below; `headers` is only overridden
    by errors that need to add response headers (e.g. Retry-After). `errors`
    is only set by errors that name specific offending fields (e.g. a 422
    validation failure) and is rendered as an extra body member when present.
    """

    type_slug: str
    title: str
    status: int
    detail: str
    headers: dict[str, str] | None = None
    errors: list[FieldError] | None = None
