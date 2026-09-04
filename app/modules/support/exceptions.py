from app.core.exceptions import FieldError
from app.core.problem_details import ProblemError


class ValidationFailedError(ProblemError):
    """FR-3: empty/oversized `subject`, oversized `body`, unrecognized
    `category` (OD-3, not enforced here — no enum exists to check against),
    or a missing `Idempotency-Key` header (OD-2). Same `errors: list[FieldError]`
    shape as `audit/exceptions.py`'s own `ValidationFailedError`.
    """

    type_slug = "validation-failed"
    title = "Validation Failed"
    status = 422
    detail = "One or more fields failed validation."

    def __init__(self, *, errors: list[FieldError]) -> None:
        super().__init__()
        self.errors = errors


class IdempotencyKeyReuseError(ProblemError):
    """FR-4: the same `Idempotency-Key` was reused with a different request
    body (stored `request_hash` mismatch).
    """

    type_slug = "idempotency-key-reuse"
    title = "Idempotency Key Reuse"
    status = 422
    detail = "This idempotency key was already used with a different request."


class AttachmentNotOwnedError(ProblemError):
    """FR-7/BR-016: an `attachment_id` uploaded by a different user, already
    bound to another ticket, or unknown — one slug for all three, since the
    response must never reveal which applied (IDOR prevention).
    """

    type_slug = "attachment-not-owned"
    title = "Attachment Not Owned"
    status = 422
    detail = "One or more attachments could not be attached to this ticket."


class TicketCreationRateLimitError(ProblemError):
    """FR-6: 5 tickets already created by this customer in the last hour."""

    type_slug = "too-many-requests"
    title = "Too Many Requests"
    status = 429
    detail = "Too many tickets created recently. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}


class AccountDeactivatedError(ProblemError):
    """FR-5: the caller's account is deactivated. Own `ProblemError`
    subclass per this module (never importing `users.exceptions`'
    identically-shaped one directly, per module ownership) — same
    `type_slug`/`status` as `users/exceptions.py`'s `AccountDeactivatedError`
    since it is the same condition observed from a different endpoint.
    """

    type_slug = "account-deactivated"
    title = "Account Deactivated"
    status = 403
    detail = "This account has been deactivated."


class AgentQueueNotAvailableError(ProblemError):
    """GET's staff-rejection branch (OD-4): caller holds `tickets:read`/
    `tickets:write` (support_agent/admin) — full agent queue behavior is
    Out of Scope for this story.
    """

    type_slug = "agent-queue-not-available"
    title = "Agent Queue Not Available"
    status = 403
    detail = "Agent queue views are not available through this endpoint yet."
