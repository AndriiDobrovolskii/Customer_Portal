from app.core.problem_details import ProblemError


class InvalidPasswordError(ProblemError):
    type_slug = "invalid-credentials"
    title = "Invalid Credentials"
    status = 401
    detail = "The current password is incorrect."


class AlreadyDeactivatedError(ProblemError):
    type_slug = "already-deactivated"
    title = "Account Already Deactivated"
    status = 409
    detail = "This account is already deactivated."
