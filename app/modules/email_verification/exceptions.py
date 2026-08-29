from app.core.problem_details import ProblemError


class TokenExpiredError(ProblemError):
    type_slug = "token-expired"
    title = "Verification Token Expired"
    status = 400
    detail = "The verification token has expired. Request a new one."


class TokenInvalidError(ProblemError):
    type_slug = "token-invalid"
    title = "Verification Token Invalid"
    status = 400
    detail = "The verification token is invalid."


class InvalidRequestError(ProblemError):
    type_slug = "invalid-request"
    title = "Invalid Request"
    status = 400
    detail = "The request body is missing or malformed."


class TooManyAttemptsError(ProblemError):
    type_slug = "too-many-attempts"
    title = "Too Many Attempts"
    status = 429
    detail = "A verification email was already sent recently. Please wait before retrying."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}
