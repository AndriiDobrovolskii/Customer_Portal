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


class TicketNotFoundError(ProblemError):
    """FR-4 (US-4.2): unknown ticket id, a different customer's ticket, or an
    authenticated caller who is neither the ticket's requester nor an agent —
    always 404, never 403, so the response never confirms the ticket id exists.
    """

    type_slug = "not-found"
    title = "Ticket Not Found"
    status = 404
    detail = "No ticket was found with that identifier."


class InsufficientPermissionError(ProblemError):
    """FR-5 (US-4.2): a customer submitted `visibility: "internal"`. Own
    subclass per module (implementation-plan Architectural Change #6) —
    same `type_slug`/`status` as `app/modules/roles/exceptions.py`'s class of
    the same name, since it is the same condition observed from a different
    endpoint, but never imported from there directly (module ownership,
    matching `AccountDeactivatedError`'s existing precedent).
    """

    type_slug = "insufficient-permission"
    title = "Insufficient Permission"
    status = 403
    detail = "Your access token does not carry the required permission."


class TicketClosedError(ProblemError):
    """FR-6 (US-4.2): the ticket's status is `"closed"`. New slug, first use
    in this codebase — a `"resolved"` ticket is accepted, not rejected here
    (Resolution OD-5/OD-8).
    """

    type_slug = "ticket-closed"
    title = "Ticket Closed"
    status = 409
    detail = "This ticket is closed. Create a new ticket if you still need help."


class TicketReplyRateLimitError(ProblemError):
    """NFR (US-4.2): 30 replies already posted by this caller in the last
    hour — a distinct Valkey counter from `TicketCreationRateLimitError`'s
    (Risk 6).
    """

    type_slug = "too-many-requests"
    title = "Too Many Requests"
    status = 429
    detail = "Too many replies posted recently. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}
