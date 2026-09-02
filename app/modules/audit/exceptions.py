from app.core.exceptions import FieldError
from app.core.problem_details import ProblemError


class RangeTooWideError(ProblemError):
    """AU-AC5/FR-5: the `from`/`to` window exceeds 90 days, or either bound
    is missing. The story's own Assumption #6 ("Maximum 90 days per query,
    **bounds required**") is why a single missing bound is treated the same
    as both missing, resolving OD-10's provisional gap — the AC text alone
    only names the two-bounds-omitted case, but "bounds required" reads as
    both bounds, not "at least one."
    """

    type_slug = "range-too-wide"
    title = "Range Too Wide"
    status = 422
    detail = "Audit queries cover at most 90 days. Use the export for wider ranges."


class ValidationFailedError(ProblemError):
    """`limit`/`cursor` bounds, per the `admin_users` precedent (OD-5)."""

    type_slug = "validation-failed"
    title = "Validation Failed"
    status = 422
    detail = "One or more fields failed validation."

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors
