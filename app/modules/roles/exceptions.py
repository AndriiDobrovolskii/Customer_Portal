from app.core.exceptions import FieldError
from app.core.problem_details import ProblemError


class InsufficientPermissionError(ProblemError):
    """Caller's access token lacks the scope a route requires.

    The `insufficient-permission` slug is named by US-3.1's MR-AC2 (not yet
    implemented), but this module is the first to actually raise it —
    reused here rather than inventing a synonym, per AGENTS.md SS1's "never
    invent a second way to do something that already has one."
    """

    type_slug = "insufficient-permission"
    title = "Insufficient Permission"
    status = 403
    detail = "Your access token does not carry the required permission."


class CannotTargetSelfError(ProblemError):
    type_slug = "cannot-target-self"
    title = "Cannot Target Self"
    status = 403
    detail = "An administrator cannot change their own role assignment."


class PrivilegeEscalationError(ProblemError):
    type_slug = "privilege-escalation"
    title = "Privilege Escalation"
    status = 403
    detail = "You cannot grant a role containing a permission you do not hold."


class LastAdminError(ProblemError):
    type_slug = "last-admin"
    title = "Last Administrator"
    status = 409
    detail = "This is the only remaining administrator; the system cannot be left without one."


class ValidationFailedError(ProblemError):
    type_slug = "validation-failed"
    title = "Validation Failed"
    status = 422
    detail = "One or more fields failed validation."

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors
