from app.core.exceptions import DomainError


class ProblemError(DomainError):
    """Base for domain errors rendered as RFC 7807 application/problem+json.

    Subclasses set the class attributes below; `headers` is only overridden
    by errors that need to add response headers (e.g. Retry-After).
    """

    type_slug: str
    title: str
    status: int
    detail: str
    headers: dict[str, str] | None = None
