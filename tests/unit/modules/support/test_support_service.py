import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.support.cache import IdempotencyEnvelope
from app.modules.support.exceptions import (
    AccountDeactivatedError,
    AttachmentNotOwnedError,
    IdempotencyKeyReuseError,
    InsufficientPermissionError,
    InvalidStateTransitionError,
    TicketClosedError,
    TicketCreationRateLimitError,
    TicketNotFoundError,
    TicketReplyRateLimitError,
)
from app.modules.support.models import Attachment, Ticket, TicketReply
from app.modules.support.repository import ReplyListPage, TicketListPage
from app.modules.support.service import (
    _ALLOWED_EVENTS_BY_STATUS,
    TicketReplyService,
    TicketService,
    _hash_request,
)

pytestmark = pytest.mark.unit

_FIXED_NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
_RATE_LIMIT = 5
_SUBJECT = "Cannot log in"
_BODY = "My login keeps failing."
_CATEGORY = "billing"


def _make_ticket(*, requester_id: uuid.UUID, category: str = _CATEGORY) -> Ticket:
    # Real ORM model, not a lookalike dataclass — `TicketRepositoryProtocol`'s
    # return types are covariant with `app.modules.support.models.Ticket`
    # under mypy --strict, matching this project's existing fake-repository
    # convention (e.g. `admin_users`' `_make_user` building a real `User`).
    # Server-computed columns (`ticket_number`/`status`/timestamps) are set
    # directly here rather than left to a DB `server_default`.
    ticket = Ticket(requester_id=requester_id, subject=_SUBJECT, body=_BODY, category=category)
    ticket.id = uuid.uuid4()
    ticket.ticket_number = "CP-2026-0000001"
    ticket.status = "open"
    ticket.created_at = _FIXED_NOW
    ticket.updated_at = _FIXED_NOW
    # US-4.3: not yet mapped columns as of this test-writing pass (added by
    # data-layer-builder, T2) - initialized explicitly so a test reading one
    # of these before IMPLEMENTATION lands fails on an assertion, not an
    # AttributeError from an unmapped, never-set attribute.
    ticket.resolved_at = None
    ticket.resolution_note = None
    ticket.closed_at = None
    ticket.closed_by = None
    return ticket


def _make_attachment(
    *,
    attachment_id: uuid.UUID | None = None,
    uploaded_by: uuid.UUID,
    ticket_id: uuid.UUID | None = None,
    ticket_reply_id: uuid.UUID | None = None,
) -> Attachment:
    attachment = Attachment(uploaded_by=uploaded_by, ticket_id=ticket_id)
    attachment.id = attachment_id or uuid.uuid4()
    attachment.created_at = _FIXED_NOW
    attachment.ticket_reply_id = ticket_reply_id
    return attachment


def _make_reply(
    *,
    reply_id: uuid.UUID | None = None,
    ticket_id: uuid.UUID,
    author_id: uuid.UUID,
    author_kind: str,
    visibility: str = "public",
    body: str = "We're looking into it.",
) -> TicketReply:
    reply = TicketReply(
        ticket_id=ticket_id,
        author_id=author_id,
        author_kind=author_kind,
        body=body,
        visibility=visibility,
    )
    reply.id = reply_id or uuid.uuid4()
    reply.created_at = _FIXED_NOW
    return reply


class FakeTicketRepository:
    def __init__(self, *, existing: dict[uuid.UUID, Ticket] | None = None) -> None:
        self.existing = existing or {}
        self.created: list[dict[str, Any]] = []
        self.commit_count = 0
        self.list_calls: list[dict[str, Any]] = []
        self.list_page: TicketListPage | None = TicketListPage(items=[], next_cursor=None)
        self.update_calls: list[dict[str, Any]] = []
        self.transition_calls: list[dict[str, Any]] = []
        self.transition_returns_none = False

    async def create(
        self, *, requester_id: uuid.UUID, subject: str, body: str, category: str
    ) -> Ticket:
        self.created.append(
            {"requester_id": requester_id, "subject": subject, "body": body, "category": category}
        )
        ticket = _make_ticket(requester_id=requester_id, category=category)
        self.existing[ticket.id] = ticket
        return ticket

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None:
        return self.existing.get(ticket_id)

    async def list_for_requester(
        self, *, requester_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TicketListPage | None:
        self.list_calls.append({"requester_id": requester_id, "cursor": cursor, "limit": limit})
        return self.list_page

    async def update(
        self,
        ticket_id: uuid.UUID,
        *,
        status: str | None = None,
        first_response_at: datetime | None = None,
    ) -> Ticket | None:
        # US-4.2-implementation-plan.md Architectural Change #3: both fields
        # optional, `None` means "leave unchanged" — never used to clear a
        # value, since no FR in this story ever clears either one.
        self.update_calls.append(
            {"ticket_id": ticket_id, "status": status, "first_response_at": first_response_at}
        )
        ticket = self.existing.get(ticket_id)
        if ticket is None:
            return None
        if status is not None:
            ticket.status = status
        if first_response_at is not None:
            ticket.first_response_at = first_response_at
        return ticket

    async def transition_status(
        self,
        ticket_id: uuid.UUID,
        *,
        expected_statuses: list[str],
        new_status: str,
        resolved_at: datetime | None = None,
        clear_resolved_at: bool = False,
        resolution_note: str | None = None,
        closed_at: datetime | None = None,
        closed_by: uuid.UUID | None = None,
        require_resolved_within_window: bool = False,
    ) -> Ticket | None:
        # US-4.3 implementation-plan.md Decision 2: a conditional UPDATE
        # scoped to `expected_statuses`, returning None on zero rows
        # affected - a wrong-state loss (FR-6/FR-9) and, per
        # `transition_returns_none`, a simulated race-loss or elapsed-window
        # loss (the fake cannot itself evaluate real interval arithmetic;
        # the caller sets this flag to stand in for "the DB's own WHERE
        # clause matched zero rows").
        self.transition_calls.append(
            {
                "ticket_id": ticket_id,
                "expected_statuses": list(expected_statuses),
                "new_status": new_status,
                "resolved_at": resolved_at,
                "clear_resolved_at": clear_resolved_at,
                "resolution_note": resolution_note,
                "closed_at": closed_at,
                "closed_by": closed_by,
                "require_resolved_within_window": require_resolved_within_window,
            }
        )
        if self.transition_returns_none:
            return None
        ticket = self.existing.get(ticket_id)
        if ticket is None or ticket.status not in expected_statuses:
            return None
        ticket.status = new_status
        if resolved_at is not None:
            ticket.resolved_at = resolved_at
        if clear_resolved_at:
            ticket.resolved_at = None
        if resolution_note is not None:
            ticket.resolution_note = resolution_note
        if closed_at is not None:
            ticket.closed_at = closed_at
        if closed_by is not None:
            ticket.closed_by = closed_by
        return ticket

    async def commit(self) -> None:
        self.commit_count += 1


class FakeAttachmentRepository:
    def __init__(self, *, attachments: dict[uuid.UUID, Attachment] | None = None) -> None:
        self.attachments = attachments or {}
        self.bind_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.bind_reply_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
        self.bind_returns_none = False
        self.commit_count = 0

    async def get_by_id(self, attachment_id: uuid.UUID) -> Attachment | None:
        return self.attachments.get(attachment_id)

    async def bind_to_ticket(
        self, *, attachment_id: uuid.UUID, ticket_id: uuid.UUID
    ) -> Attachment | None:
        self.bind_calls.append((attachment_id, ticket_id))
        if self.bind_returns_none:
            return None
        attachment = self.attachments[attachment_id]
        attachment.ticket_id = ticket_id
        return attachment

    async def bind_to_reply(
        self, *, attachment_id: uuid.UUID, ticket_reply_id: uuid.UUID
    ) -> Attachment | None:
        # US-4.2-implementation-plan.md Architectural Change #11: a distinct
        # method from `bind_to_ticket`, checking `ticket_reply_id IS NULL`
        # against the independent nullable binding column (Resolution OD-1).
        self.bind_reply_calls.append((attachment_id, ticket_reply_id))
        if self.bind_returns_none:
            return None
        attachment = self.attachments[attachment_id]
        attachment.ticket_reply_id = ticket_reply_id
        return attachment

    async def commit(self) -> None:
        self.commit_count += 1


class FakeIdempotencyCache:
    """FR-4 / `US-4.1-db-design.md`'s atomic `SET NX EX` claim/replay gate.

    Gateway-compliant (`AGENTS.md` §3): raises nothing. When `existing_envelope`
    is `None`, `claim` succeeds (this call is the sole claimant). When set,
    `claim` returns `False` and `get_envelope` returns `existing_envelope` on
    every call — `TicketService`, not this cache, does the hash-mismatch /
    poll-exhaustion branching (matches the shipped `app/modules/support/
    cache.py`, not `test-strategy`'s original single raising `claim_or_get`).
    """

    def __init__(self, *, existing_envelope: IdempotencyEnvelope | None = None) -> None:
        self.existing_envelope = existing_envelope
        self.claim_calls: list[dict[str, Any]] = []
        self.get_envelope_calls = 0
        self.resolve_calls: list[dict[str, Any]] = []
        self.release_calls: list[dict[str, Any]] = []

    async def claim(
        self, *, user_id: uuid.UUID, key: str, request_hash: str, ttl_seconds: int
    ) -> bool:
        self.claim_calls.append(
            {
                "user_id": user_id,
                "key": key,
                "request_hash": request_hash,
                "ttl_seconds": ttl_seconds,
            }
        )
        return self.existing_envelope is None

    async def get_envelope(self, *, user_id: uuid.UUID, key: str) -> IdempotencyEnvelope | None:
        self.get_envelope_calls += 1
        return self.existing_envelope

    async def resolve(
        self,
        *,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
        ticket_id: uuid.UUID,
        ttl_seconds: int,
    ) -> None:
        self.resolve_calls.append(
            {
                "user_id": user_id,
                "key": key,
                "request_hash": request_hash,
                "ticket_id": ticket_id,
                "ttl_seconds": ttl_seconds,
            }
        )

    async def release(self, *, user_id: uuid.UUID, key: str) -> None:
        self.release_calls.append({"user_id": user_id, "key": key})


class FakeRateLimitCache:
    def __init__(self, *, count: int = 1) -> None:
        self.count = count
        self.record_calls: list[dict[str, Any]] = []

    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        self.record_calls.append({"user_id": user_id, "window_seconds": window_seconds})
        return self.count

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        return 1800


class FakeAuditService:
    def __init__(self) -> None:
        self.record_event_calls: list[dict[str, Any]] = []

    async def record_event(
        self,
        *,
        category: str,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        outcome: str | None,
        payload: dict[str, object] | None,
    ) -> None:
        self.record_event_calls.append(
            {
                "category": category,
                "event": event,
                "actor_id": actor_id,
                "target_id": target_id,
                "outcome": outcome,
                "payload": payload,
            }
        )


class FakeUserService:
    """Cross-module collaborator resolving FR-1's confirmation-email
    recipient (`app.modules.users.service.UserService.get_email_for_user`,
    added as a plan gap — see `docs/catalog/US-4.1-pipeline-status.md`) and
    FR-5's account-status gate (`get_account_status_for_user`, added when
    IMPLEMENTATION's T5-T7 rework added the deactivated-account 403 check).
    """

    def __init__(
        self,
        *,
        email: str | None = "requester@example.com",
        account_status: str | None = "active",
    ) -> None:
        self.email = email
        self.account_status = account_status
        self.calls: list[uuid.UUID] = []

    async def get_email_for_user(self, user_id: uuid.UUID) -> str | None:
        self.calls.append(user_id)
        return self.email

    async def get_account_status_for_user(self, user_id: uuid.UUID) -> str | None:
        return self.account_status


class FakeEmailSender:
    """Only `send_ticket_created_email` is exercised by `TicketService` — the
    other `EmailSender` Protocol members are never called by this module.
    """

    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.sent: list[dict[str, str]] = []
        self.reply_notifications_sent: list[dict[str, str]] = []
        self.queue_notifications_sent: list[dict[str, str]] = []
        self.resolved_emails_sent: list[dict[str, str]] = []

    async def send_ticket_created_email(self, *, to: str, ticket_number: str) -> None:
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.sent.append({"to": to, "ticket_number": ticket_number})

    async def send_ticket_resolved_email(
        self, *, to: str, ticket_number: str, resolution_note: str
    ) -> None:
        # US-4.3 FR-1: "the requester is emailed the resolution note plus a
        # link to the ticket detail page" (OD-8). Not part of the shipped
        # `EmailSender` Protocol as of this test-writing pass - a new method
        # `implementation_plan.md` does not list under Files To Modify
        # (`app/core/email.py` is absent from that table). Flagged as a plan
        # gap in `US-4.3-test-generation-report.md`, matching US-4.1's own
        # `get_email_for_user` precedent (`workflow-state.yaml` UserServiceProtocol
        # note). `service-and-router-builder` must add this method to
        # `EmailSender`/`LoggingEmailSender` for `TicketService.resolve_ticket`
        # to call it.
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.resolved_emails_sent.append(
            {"to": to, "ticket_number": ticket_number, "resolution_note": resolution_note}
        )

    async def send_ticket_reply_notification(self, *, to: str, ticket_number: str) -> None:
        # FR-1: best-effort notification to the requester on an agent reply.
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.reply_notifications_sent.append({"to": to, "ticket_number": ticket_number})

    async def send_ticket_reply_queue_notification(self, *, ticket_number: str) -> None:
        # FR-2: best-effort notification to the fixed support-queue address
        # (Resolution OD-2) — no `to` parameter; the recipient is read from
        # settings inside the real implementation, not passed by the caller.
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.queue_notifications_sent.append({"ticket_number": ticket_number})

    async def send_verification_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_email_change_confirmation(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_email_change_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_refresh_reuse_alert(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_password_reset_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError

    async def send_password_reset_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_mfa_recovery_used_notice(self, *, to: str) -> None:
        raise NotImplementedError

    async def send_invitation_email(self, *, to: str, raw_token: str) -> None:
        raise NotImplementedError


def _make_service(
    *,
    ticket_repository: FakeTicketRepository | None = None,
    attachment_repository: FakeAttachmentRepository | None = None,
    idempotency_cache: FakeIdempotencyCache | None = None,
    rate_limit_cache: FakeRateLimitCache | None = None,
    audit_service: FakeAuditService | None = None,
    user_service: FakeUserService | None = None,
    email_sender: FakeEmailSender | None = None,
) -> tuple[
    TicketService,
    FakeTicketRepository,
    FakeAttachmentRepository,
    FakeIdempotencyCache,
    FakeRateLimitCache,
    FakeAuditService,
    FakeUserService,
    FakeEmailSender,
]:
    ticket_repository = ticket_repository or FakeTicketRepository()
    attachment_repository = attachment_repository or FakeAttachmentRepository()
    idempotency_cache = idempotency_cache or FakeIdempotencyCache()
    rate_limit_cache = rate_limit_cache or FakeRateLimitCache(count=1)
    audit_service = audit_service or FakeAuditService()
    user_service = user_service or FakeUserService()
    email_sender = email_sender or FakeEmailSender()
    service = TicketService(
        ticket_repository,
        attachment_repository,
        idempotency_cache,
        rate_limit_cache,
        audit_service,
        user_service,
        email_sender,
    )
    return (
        service,
        ticket_repository,
        attachment_repository,
        idempotency_cache,
        rate_limit_cache,
        audit_service,
        user_service,
        email_sender,
    )


class FakeTicketReplyRepository:
    """`TicketReplyRepositoryProtocol` fake — mirrors `FakeTicketRepository`'s
    real-ORM-instance convention (`mypy --strict` Protocol return-type
    covariance).
    """

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.commit_count = 0
        self.list_calls: list[dict[str, Any]] = []
        self.list_page: ReplyListPage | None = ReplyListPage(items=[], next_cursor=None)

    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        author_id: uuid.UUID,
        author_kind: str,
        body: str,
        visibility: str,
    ) -> TicketReply:
        self.created.append(
            {
                "ticket_id": ticket_id,
                "author_id": author_id,
                "author_kind": author_kind,
                "body": body,
                "visibility": visibility,
            }
        )
        return _make_reply(
            ticket_id=ticket_id,
            author_id=author_id,
            author_kind=author_kind,
            visibility=visibility,
            body=body,
        )

    async def list_for_ticket(
        self, *, ticket_id: uuid.UUID, cursor: str | None, limit: int
    ) -> ReplyListPage | None:
        self.list_calls.append({"ticket_id": ticket_id, "cursor": cursor, "limit": limit})
        return self.list_page

    async def commit(self) -> None:
        self.commit_count += 1


class FakeTicketReplyRateLimitCache:
    """Distinct Valkey-counter fake from `FakeRateLimitCache` (ticket
    creation's) — Risk 6's two-independent-counters requirement.
    """

    def __init__(self, *, count: int = 1) -> None:
        self.count = count
        self.record_calls: list[dict[str, Any]] = []

    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int:
        self.record_calls.append({"user_id": user_id, "window_seconds": window_seconds})
        return self.count

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int:
        return 1800


def _make_reply_service(
    *,
    ticket_repository: FakeTicketRepository | None = None,
    reply_repository: FakeTicketReplyRepository | None = None,
    attachment_repository: FakeAttachmentRepository | None = None,
    rate_limit_cache: FakeTicketReplyRateLimitCache | None = None,
    audit_service: FakeAuditService | None = None,
    email_sender: FakeEmailSender | None = None,
) -> tuple[
    TicketReplyService,
    FakeTicketRepository,
    FakeTicketReplyRepository,
    FakeAttachmentRepository,
    FakeTicketReplyRateLimitCache,
    FakeAuditService,
    FakeEmailSender,
]:
    # US-4.3 implementation-plan.md Decision 3: `TicketReplyService` gains a
    # new *required* `audit_service` constructor parameter (DR-4's FR-4 audit
    # fix) - positioned right after `rate_limit_cache`, mirroring
    # `TicketService.__init__`'s own repos/caches-then-audit_service-then-
    # optional-collaborators ordering. This is test-writer's own
    # collaborator-shape assumption (no design doc fixes the literal
    # parameter order) - `audit_service` is kept out of the returned tuple's
    # final position so every existing `*_, email_sender = _make_reply_service(...)`
    # unpack below keeps binding `email_sender` correctly.
    ticket_repository = ticket_repository or FakeTicketRepository()
    reply_repository = reply_repository or FakeTicketReplyRepository()
    attachment_repository = attachment_repository or FakeAttachmentRepository()
    rate_limit_cache = rate_limit_cache or FakeTicketReplyRateLimitCache(count=1)
    audit_service = audit_service or FakeAuditService()
    email_sender = email_sender or FakeEmailSender()
    service = TicketReplyService(
        ticket_repository,
        reply_repository,
        attachment_repository,
        rate_limit_cache,
        audit_service,
        email_sender,
    )
    return (
        service,
        ticket_repository,
        reply_repository,
        attachment_repository,
        rate_limit_cache,
        audit_service,
        email_sender,
    )


# --- ST-AC1/FR-1: successful creation ---------------------------------------


async def test_create_ticket_happy_path_writes_audit_event_and_queues_email() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    service, ticket_repo, _, idempotency_cache, _, audit_service, user_service, email_sender = (
        _make_service()
    )

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-1",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert
    assert result.status == "open"
    assert result.requester_id == requester_id
    created_ticket_id = next(iter(ticket_repo.existing.values())).id
    assert len(audit_service.record_event_calls) == 1
    call = audit_service.record_event_calls[0]
    assert call["category"] == "tickets"
    assert call["event"] == "ticket_created"
    assert call["actor_id"] == requester_id
    assert call["target_id"] == created_ticket_id
    assert call["outcome"] == "success"
    assert ticket_repo.commit_count == 1
    assert idempotency_cache.resolve_calls[0]["user_id"] == requester_id
    assert idempotency_cache.resolve_calls[0]["key"] == "key-1"
    assert idempotency_cache.resolve_calls[0]["ticket_id"] == created_ticket_id
    assert idempotency_cache.release_calls == []
    # ST-AC1: "a confirmation email containing the ticket number is queued".
    assert user_service.calls == [requester_id]
    assert email_sender.sent == [
        {"to": "requester@example.com", "ticket_number": "CP-2026-0000001"}
    ]


# --- ST-AC5/FR-5: deactivated-account gate -----------------------------------


async def test_create_ticket_deactivated_account_raises_before_any_write() -> None:
    # Arrange: FR-5's account-deactivated check runs first, before the
    # idempotency claim or any repository/audit write (US-4.1-db-design.md's
    # stated ordering).
    requester_id = uuid.uuid4()
    user_service = FakeUserService(account_status="deactivated")
    service, ticket_repo, _, idempotency_cache, _, audit_service, user_service, _ = _make_service(
        user_service=user_service
    )

    # Act / Assert
    with pytest.raises(AccountDeactivatedError):
        await service.create_ticket(
            requester_id=requester_id,
            idempotency_key="key-1",
            subject=_SUBJECT,
            body=_BODY,
            category=_CATEGORY,
            attachment_ids=[],
        )
    assert idempotency_cache.claim_calls == []
    assert audit_service.record_event_calls == []
    assert ticket_repo.created == []


async def test_create_ticket_active_account_proceeds() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    user_service = FakeUserService(account_status="active")
    service, *_ = _make_service(user_service=user_service)

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-1",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert
    assert result.status == "open"


async def test_create_ticket_no_email_on_file_skips_dispatch_without_failing() -> None:
    # Arrange: FR-1's confirmation email is best-effort — a requester with no
    # resolvable email must not block ticket creation.
    requester_id = uuid.uuid4()
    service, *_, email_sender = _make_service(user_service=FakeUserService(email=None))

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-1b",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert
    assert result.status == "open"
    assert email_sender.sent == []


async def test_create_ticket_email_dispatch_failure_does_not_fail_the_request() -> None:
    # Arrange: the ticket is already committed by the time email dispatch
    # runs — a dispatch failure must not undo it or propagate.
    requester_id = uuid.uuid4()
    service, ticket_repo, *_ = _make_service(email_sender=FakeEmailSender(raises=True))

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-1c",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert
    assert result.status == "open"
    assert ticket_repo.commit_count == 1


async def test_create_ticket_commits_exactly_once_with_attachment_bound() -> None:
    # Arrange: transaction-boundary contract (implementation-plan §2) — the
    # ticket insert, the attachment bind, and the audit write are one
    # transaction with a single commit issued by support.service, not
    # audit.service.
    requester_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    attachment_repo = FakeAttachmentRepository(
        attachments={
            attachment_id: _make_attachment(
                attachment_id=attachment_id, uploaded_by=requester_id, ticket_id=None
            )
        }
    )
    service, ticket_repo, attachment_repo, *_ = _make_service(attachment_repository=attachment_repo)

    # Act
    await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-2",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[attachment_id],
    )

    # Assert
    assert ticket_repo.commit_count == 1
    assert len(attachment_repo.bind_calls) == 1


# --- ST-AC4/FR-4: idempotency replay, reuse, and the poll-exhaustion race ---


async def test_create_ticket_replay_returns_original_ticket_without_second_write() -> None:
    # Arrange: a stored envelope whose `request_hash` matches this call's
    # (same subject/body/category/attachments) and already carries the
    # resolved `ticket_id` — a genuine replay, no poll needed.
    requester_id = uuid.uuid4()
    original = _make_ticket(requester_id=requester_id)
    ticket_repo = FakeTicketRepository(existing={original.id: original})
    matching_hash = _hash_request(
        subject=_SUBJECT, body=_BODY, category=_CATEGORY, attachment_ids=[]
    )
    idempotency_cache = FakeIdempotencyCache(
        existing_envelope=IdempotencyEnvelope(request_hash=matching_hash, ticket_id=original.id)
    )
    rate_limit_cache = FakeRateLimitCache(count=1)
    service, ticket_repo, _, idempotency_cache, rate_limit_cache, audit_service, *_ = _make_service(
        ticket_repository=ticket_repo,
        idempotency_cache=idempotency_cache,
        rate_limit_cache=rate_limit_cache,
    )

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-3",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert: same ticket, no second insert, no second audit write, and —
    # DB design's explicit ordering requirement — the rate limit is never
    # consulted on a genuine replay.
    assert result.id == original.id
    assert ticket_repo.created == []
    assert audit_service.record_event_calls == []
    assert rate_limit_cache.record_calls == []
    assert ticket_repo.commit_count == 0
    assert idempotency_cache.resolve_calls == []
    assert idempotency_cache.release_calls == []


async def test_create_ticket_idempotency_key_reused_with_different_body_raises() -> None:
    # Arrange: the stored envelope's `request_hash` does not match this
    # call's — the service, not the cache, detects the mismatch.
    requester_id = uuid.uuid4()
    idempotency_cache = FakeIdempotencyCache(
        existing_envelope=IdempotencyEnvelope(
            request_hash="stored-hash-of-a-different-body", ticket_id=None
        )
    )
    service, ticket_repo, _, idempotency_cache, _, audit_service, *_ = _make_service(
        idempotency_cache=idempotency_cache
    )

    # Act & Assert
    with pytest.raises(IdempotencyKeyReuseError):
        await service.create_ticket(
            requester_id=requester_id,
            idempotency_key="key-4",
            subject="Different subject",
            body="Different body.",
            category=_CATEGORY,
            attachment_ids=[],
        )
    assert ticket_repo.created == []
    assert audit_service.record_event_calls == []
    assert idempotency_cache.release_calls == []


async def test_create_ticket_idempotency_poll_exhausted_propagates_unhandled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: DB design's stated behavior for the mid-flight-race,
    # poll-budget-exhausted path — an unhandled server error, deliberately
    # not a new contract slug, so the service must let it propagate rather
    # than translate it into one of its own ProblemError subclasses. The
    # stored envelope's hash matches but its `ticket_id` never resolves
    # within the bounded poll (`_POLL_MAX_ATTEMPTS`). `_POLL_INTERVAL_SECONDS`
    # is patched to 0 so this test does not sleep for real.
    monkeypatch.setattr("app.modules.support.service._POLL_INTERVAL_SECONDS", 0)
    requester_id = uuid.uuid4()
    matching_hash = _hash_request(
        subject=_SUBJECT, body=_BODY, category=_CATEGORY, attachment_ids=[]
    )
    idempotency_cache = FakeIdempotencyCache(
        existing_envelope=IdempotencyEnvelope(request_hash=matching_hash, ticket_id=None)
    )
    service, ticket_repo, _, idempotency_cache, rate_limit_cache, audit_service, *_ = _make_service(
        idempotency_cache=idempotency_cache
    )

    # Act & Assert
    with pytest.raises(RuntimeError):
        await service.create_ticket(
            requester_id=requester_id,
            idempotency_key="key-5",
            subject=_SUBJECT,
            body=_BODY,
            category=_CATEGORY,
            attachment_ids=[],
        )
    assert ticket_repo.created == []
    assert rate_limit_cache.record_calls == []
    assert audit_service.record_event_calls == []
    assert idempotency_cache.release_calls == []


# --- ST-AC6/FR-6: creation rate limit, and its ordering vs. idempotency -----


async def test_create_ticket_rate_limit_exceeded_raises_429_and_releases_the_claimed_key() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    rate_limit_cache = FakeRateLimitCache(count=_RATE_LIMIT + 1)
    service, ticket_repo, _, idempotency_cache, rate_limit_cache, audit_service, *_ = _make_service(
        rate_limit_cache=rate_limit_cache
    )

    # Act & Assert
    with pytest.raises(TicketCreationRateLimitError) as exc_info:
        await service.create_ticket(
            requester_id=requester_id,
            idempotency_key="key-6",
            subject=_SUBJECT,
            body=_BODY,
            category=_CATEGORY,
            attachment_ids=[],
        )
    assert exc_info.value.headers is not None
    assert "Retry-After" in exc_info.value.headers
    assert ticket_repo.created == []
    assert audit_service.record_event_calls == []
    # This request won the claim, then failed before `resolve` — the key
    # must be released so a retry does not poll a permanently-stuck envelope
    # (cache.py's `release`, added mid-build; see pipeline-status.md).
    assert idempotency_cache.release_calls == [{"user_id": requester_id, "key": "key-6"}]


async def test_create_ticket_within_rate_limit_succeeds() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    rate_limit_cache = FakeRateLimitCache(count=_RATE_LIMIT)
    service, ticket_repo, *_ = _make_service(rate_limit_cache=rate_limit_cache)

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-7",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[],
    )

    # Assert
    assert result.status == "open"
    assert len(ticket_repo.created) == 1


# --- ST-AC7/FR-7: attachment ownership (IDOR) -------------------------------


async def test_create_ticket_attachment_owned_and_unbound_is_bound() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    attachment_repo = FakeAttachmentRepository(
        attachments={
            attachment_id: _make_attachment(
                attachment_id=attachment_id, uploaded_by=requester_id, ticket_id=None
            )
        }
    )
    service, _, attachment_repo, *_ = _make_service(attachment_repository=attachment_repo)

    # Act
    result = await service.create_ticket(
        requester_id=requester_id,
        idempotency_key="key-8",
        subject=_SUBJECT,
        body=_BODY,
        category=_CATEGORY,
        attachment_ids=[attachment_id],
    )

    # Assert
    assert attachment_repo.bind_calls == [(attachment_id, result.id)]
    assert attachment_repo.attachments[attachment_id].ticket_id == result.id


@pytest.mark.parametrize(
    "attachment_factory",
    [
        pytest.param(
            lambda requester_id, other_id: {
                other_id: _make_attachment(
                    attachment_id=other_id, uploaded_by=uuid.uuid4(), ticket_id=None
                )
            },
            id="owned_by_another_user",
        ),
        pytest.param(
            lambda requester_id, other_id: {
                other_id: _make_attachment(
                    attachment_id=other_id, uploaded_by=requester_id, ticket_id=uuid.uuid4()
                )
            },
            id="already_bound_to_another_ticket",
        ),
        pytest.param(lambda requester_id, other_id: {}, id="unknown_attachment_id"),
    ],
)
async def test_create_ticket_attachment_not_owned_raises_indistinguishable_error(
    attachment_factory: Callable[[uuid.UUID, uuid.UUID], dict[uuid.UUID, Attachment]],
) -> None:
    # Arrange: FR-7 — all three causes (owned by another user, already
    # bound, unknown) must raise the same error, and no ticket is created.
    requester_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    attachment_repo = FakeAttachmentRepository(
        attachments=attachment_factory(requester_id, attachment_id)
    )
    service, ticket_repo, attachment_repo, idempotency_cache, *_ = _make_service(
        attachment_repository=attachment_repo
    )

    # Act & Assert
    with pytest.raises(AttachmentNotOwnedError):
        await service.create_ticket(
            requester_id=requester_id,
            idempotency_key="key-9",
            subject=_SUBJECT,
            body=_BODY,
            category=_CATEGORY,
            attachment_ids=[attachment_id],
        )
    assert ticket_repo.created == []
    assert attachment_repo.bind_calls == []
    # This request won the claim, then failed before `resolve` — released.
    assert idempotency_cache.release_calls == [{"user_id": requester_id, "key": "key-9"}]


# --- ST-AC2/FR-2: listing own tickets ---------------------------------------


async def test_list_own_tickets_scopes_to_requester_and_passes_through_paging() -> None:
    # Arrange
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket_repo = FakeTicketRepository()
    ticket_repo.list_page = TicketListPage(items=[ticket], next_cursor="next-page")
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.list_own_tickets(
        requester_id=requester_id, status=None, cursor="prev-cursor", limit=25
    )

    # Assert
    assert [item.id for item in result.items] == [ticket.id]
    assert result.next_cursor == "next-page"
    assert ticket_repo.list_calls == [
        {"requester_id": requester_id, "cursor": "prev-cursor", "limit": 25}
    ]


# =============================================================================
# US-4.3 (Ticket Resolution) — TicketService.resolve_ticket / close_ticket /
# reopen_ticket
#
# Test-writer's own collaborator-shape assumption (no design doc fixes these
# literal method signatures): keyword-only `(*, ticket_id, actor_id,
# actor_kind, ...)`, matching `create_reply`'s own established call shape,
# returning a `TicketStateRead`-shaped object (US-4.3-openapi.yaml's
# `id`/`ticket_number`/`status`/`resolved_at`/`closed_at`/`updated_at` field
# list). `FakeTicketRepository.transition_status` implements the real
# status-set check (`implementation_plan.md` Decision 2); it cannot evaluate
# real interval arithmetic, so the 7-day window's own elapsed-boundary case
# is simulated via `transition_returns_none`, standing in for "the DB's own
# WHERE clause matched zero rows" (same fake convention as
# `FakeAttachmentRepository.bind_returns_none`). A window-guard-specific
# proof (exact-7-day boundary, DB-evaluated) is an integration-only concern
# — AGENTS.md §5 — see `US-4.3-test-strategy.md`.
# =============================================================================

_RESOLUTION_NOTE = "Restarted the affected service; confirmed the customer's report is fixed."


def _resolved_ticket(*, requester_id: uuid.UUID, resolved_at: datetime = _FIXED_NOW) -> Ticket:
    ticket = _make_ticket(requester_id=requester_id)
    ticket.status = "resolved"
    ticket.resolved_at = resolved_at
    ticket.resolution_note = "Previously resolved."
    return ticket


# --- FR-6 (via Decision 4): _ALLOWED_EVENTS_BY_STATUS is one explicit table -


def test_allowed_events_by_status_matches_the_plan_s_stated_table() -> None:
    # Arrange / Act / Assert: implementation_plan.md Decision 4's literal
    # table - Risk 2's own "treat this table as something worth an explicit
    # test per status value" instruction.
    assert _ALLOWED_EVENTS_BY_STATUS == {
        "open": ["resolve", "close"],
        "waiting_on_support": ["resolve", "close"],
        "waiting_on_customer": ["resolve", "close"],
        "resolved": ["close", "reopen"],
        "closed": [],
    }


# --- FR-1: agent resolves a ticket ------------------------------------------


@pytest.mark.parametrize("status_before", ["open", "waiting_on_support", "waiting_on_customer"])
async def test_resolve_ticket_agent_from_each_eligible_status_succeeds(status_before: str) -> None:
    # Arrange: OD-5's resolve-eligible source-status set.
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = status_before
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, _, email_sender = _make_service(
        ticket_repository=ticket_repo
    )

    # Act
    result = await service.resolve_ticket(
        ticket_id=ticket_id, actor_id=agent_id, actor_kind="agent", resolution_note=_RESOLUTION_NOTE
    )

    # Assert
    assert result.status == "resolved"
    assert result.resolved_at is not None
    assert ticket_repo.transition_calls[-1]["new_status"] == "resolved"
    assert ticket_repo.transition_calls[-1]["resolution_note"] == _RESOLUTION_NOTE
    assert status_before in ticket_repo.transition_calls[-1]["expected_statuses"]
    call = audit_service.record_event_calls[-1]
    assert call["category"] == "tickets"
    assert call["event"] == "ticket_resolved"
    assert call["actor_id"] == agent_id
    assert call["target_id"] == ticket_id
    assert email_sender.resolved_emails_sent == [
        {
            "to": "requester@example.com",
            "ticket_number": ticket.ticket_number,
            "resolution_note": _RESOLUTION_NOTE,
        }
    ]


async def test_resolve_ticket_email_dispatch_failure_does_not_fail_the_request() -> None:
    # Arrange: best-effort, after commit (create_ticket's own precedent).
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(
        ticket_repository=ticket_repo, email_sender=FakeEmailSender(raises=True)
    )

    # Act
    result = await service.resolve_ticket(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        resolution_note=_RESOLUTION_NOTE,
    )

    # Assert
    assert result.status == "resolved"
    assert ticket_repo.commit_count == 1


async def test_resolve_ticket_commits_exactly_once() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    await service.resolve_ticket(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        resolution_note=_RESOLUTION_NOTE,
    )

    # Assert
    assert ticket_repo.commit_count == 1


# --- FR-7: customer attempts to resolve (403), state checked before actor --


async def test_resolve_ticket_customer_on_open_ticket_raises_insufficient_permission() -> None:
    # Arrange: FR-7 - a customer may close their own ticket but not resolve.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InsufficientPermissionError):
        await service.resolve_ticket(
            ticket_id=ticket_id,
            actor_id=requester_id,
            actor_kind="customer",
            resolution_note=_RESOLUTION_NOTE,
        )
    assert ticket_repo.transition_calls == []


async def test_resolve_ticket_customer_on_closed_ticket_raises_409_not_403() -> None:
    # Arrange: the spec's own NFR - "state is checked before actor": a
    # customer resolving a *closed* ticket must get 409 (FR-6), never 403
    # (FR-7), so the response never leaks the ticket's resolve-ineligible
    # state to a caller who cannot act on it in the first place.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "closed"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.resolve_ticket(
            ticket_id=ticket_id,
            actor_id=requester_id,
            actor_kind="customer",
            resolution_note=_RESOLUTION_NOTE,
        )
    assert exc_info.value.allowed_events == []
    assert ticket_repo.transition_calls == []


# --- FR-6: illegal transition rejected (409, allowed_events per status) ----


@pytest.mark.parametrize(
    "status_before,expected_allowed",
    [
        ("resolved", ["close", "reopen"]),
        ("closed", []),
    ],
)
async def test_resolve_ticket_ineligible_status_raises_409_with_allowed_events(
    status_before: str, expected_allowed: list[str]
) -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = status_before
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.resolve_ticket(
            ticket_id=ticket_id,
            actor_id=agent_id,
            actor_kind="agent",
            resolution_note=_RESOLUTION_NOTE,
        )
    assert exc_info.value.allowed_events == expected_allowed
    assert ticket_repo.transition_calls == []


# --- FR-9: concurrent resolution (conditional UPDATE loses the race) -------


async def test_resolve_ticket_concurrency_loss_raises_409_not_silent_overwrite() -> None:
    # Arrange: the ticket's status-based check passes (still "open" from this
    # request's own `get_by_id` read), but `transition_status`'s conditional
    # UPDATE affects zero rows - another agent's resolve committed first.
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    ticket_repo.transition_returns_none = True
    service, ticket_repo, _, _, _, audit_service, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.resolve_ticket(
            ticket_id=ticket_id,
            actor_id=uuid.uuid4(),
            actor_kind="agent",
            resolution_note=_RESOLUTION_NOTE,
        )
    # Reports the pre-check status's allowed_events, not a re-fetched one -
    # implementation-plan Decision 4's own stated fallthrough.
    assert exc_info.value.allowed_events == ["resolve", "close"]
    assert audit_service.record_event_calls == []


# --- FR-8: acting on someone else's ticket (404) ----------------------------


@pytest.mark.parametrize("method_name", ["resolve_ticket", "close_ticket", "reopen_ticket"])
async def test_transition_endpoints_different_customer_raises_404(method_name: str) -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "resolved" if method_name == "reopen_ticket" else "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)
    method = getattr(service, method_name)
    kwargs: dict[str, object] = {
        "ticket_id": ticket_id,
        "actor_id": uuid.uuid4(),
        "actor_kind": "customer",
    }
    if method_name == "resolve_ticket":
        kwargs["resolution_note"] = _RESOLUTION_NOTE

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await method(**kwargs)
    assert ticket_repo.transition_calls == []


async def test_transition_endpoints_unknown_ticket_raises_404() -> None:
    # Arrange
    service, *_ = _make_service()

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.close_ticket(
            ticket_id=uuid.uuid4(), actor_id=uuid.uuid4(), actor_kind="agent"
        )


# --- FR-2: ticket closed by requester or agent ------------------------------


async def test_close_ticket_requester_sets_closed_and_audits_self() -> None:
    # Arrange: OD-6/OD-7 - `closed_by` is the closing user's id; the actor
    # observed by this narrow `AuditServiceProtocol` is `actor_id` alone
    # (the "actor=self" vs "actor=agent:{id}" display distinction is an
    # `audit.service`-internal `actor_role` resolution this Protocol does not
    # expose - matching `create_ticket`'s own audit assertions, which check
    # only `actor_id`).
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.close_ticket(
        ticket_id=ticket_id, actor_id=requester_id, actor_kind="customer"
    )

    # Assert
    assert result.status == "closed"
    assert result.closed_at is not None
    assert ticket_repo.transition_calls[-1]["closed_by"] == requester_id
    call = audit_service.record_event_calls[-1]
    assert call["event"] == "ticket_closed"
    assert call["actor_id"] == requester_id


async def test_close_ticket_agent_sets_closed_and_audits_agent() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "waiting_on_support"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.close_ticket(ticket_id=ticket_id, actor_id=agent_id, actor_kind="agent")

    # Assert
    assert result.status == "closed"
    assert ticket_repo.transition_calls[-1]["closed_by"] == agent_id
    call = audit_service.record_event_calls[-1]
    assert call["event"] == "ticket_closed"
    assert call["actor_id"] == agent_id


async def test_close_ticket_from_resolved_succeeds() -> None:
    # Arrange: FR-2's "any non-closed status" scope includes "resolved",
    # unlike FR-1's narrower OD-5 set.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.close_ticket(
        ticket_id=ticket_id, actor_id=requester_id, actor_kind="customer"
    )

    # Assert
    assert result.status == "closed"


async def test_close_ticket_already_closed_raises_409() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "closed"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.close_ticket(
            ticket_id=ticket_id, actor_id=requester_id, actor_kind="customer"
        )
    assert exc_info.value.allowed_events == []
    assert ticket_repo.transition_calls == []


async def test_close_ticket_commits_exactly_once() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    await service.close_ticket(ticket_id=ticket_id, actor_id=uuid.uuid4(), actor_kind="agent")

    # Assert
    assert ticket_repo.commit_count == 1


# --- FR-5: direct reopen of a resolved ticket -------------------------------


async def test_reopen_ticket_requester_within_window_succeeds_and_audits_self() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.reopen_ticket(
        ticket_id=ticket_id, actor_id=requester_id, actor_kind="customer"
    )

    # Assert
    assert result.status == "waiting_on_support"
    assert result.resolved_at is None
    last_call = ticket_repo.transition_calls[-1]
    assert last_call["clear_resolved_at"] is True
    assert last_call["require_resolved_within_window"] is True
    assert last_call["expected_statuses"] == ["resolved"]
    call = audit_service.record_event_calls[-1]
    assert call["event"] == "ticket_reopened"
    assert call["actor_id"] == requester_id


async def test_reopen_ticket_agent_succeeds_and_audits_agent() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    result = await service.reopen_ticket(ticket_id=ticket_id, actor_id=agent_id, actor_kind="agent")

    # Assert
    assert result.status == "waiting_on_support"
    call = audit_service.record_event_calls[-1]
    assert call["event"] == "ticket_reopened"
    assert call["actor_id"] == agent_id


@pytest.mark.parametrize(
    "status_before,expected_allowed",
    [
        ("open", ["resolve", "close"]),
        ("waiting_on_support", ["resolve", "close"]),
        ("waiting_on_customer", ["resolve", "close"]),
        ("closed", []),
    ],
)
async def test_reopen_ticket_non_resolved_status_raises_409(
    status_before: str, expected_allowed: list[str]
) -> None:
    # Arrange: FR-6, generalized per US-4.3-api-design.md Open Questions #2 -
    # /reopen is only ever valid from "resolved".
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = status_before
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.reopen_ticket(ticket_id=ticket_id, actor_id=uuid.uuid4(), actor_kind="agent")
    assert exc_info.value.allowed_events == expected_allowed
    assert ticket_repo.transition_calls == []


async def test_reopen_ticket_outside_window_raises_409_same_as_invalid_state() -> None:
    # Arrange: implementation_plan.md Risk 1's own documented, not-otherwise-
    # specified fallthrough - a "resolved" ticket outside the 7-day window
    # but not yet auto-closed gets the *same* 409 a genuine invalid-state
    # caller gets, since the status-only `_ALLOWED_EVENTS_BY_STATUS` table
    # cannot see the window has lapsed; only `transition_status`'s own
    # conditional UPDATE (simulated here via `transition_returns_none`)
    # discovers it, and the service does not re-fetch to report a different
    # `allowed_events` list.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    ticket_repo.transition_returns_none = True
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        await service.reopen_ticket(
            ticket_id=ticket_id, actor_id=requester_id, actor_kind="customer"
        )
    assert exc_info.value.allowed_events == ["close", "reopen"]


async def test_reopen_ticket_commits_exactly_once() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_service(ticket_repository=ticket_repo)

    # Act
    await service.reopen_ticket(ticket_id=ticket_id, actor_id=uuid.uuid4(), actor_kind="agent")

    # Assert
    assert ticket_repo.commit_count == 1


# =============================================================================
# US-4.2 (Ticket Replies) — TicketReplyService.create_reply / get_ticket_detail
#
# Test-writer's own collaborator-shape assumption (docs/tests/US-4.2-test-
# strategy.md "Shipped contract this suite is written against"): a new
# `TicketReplyService` class, not new methods on `TicketService` — the plan
# (docs/plans/US-4.2-implementation-plan.md Architectural Change #4) leaves
# this file-internal split open; if service-and-router-builder ships a
# different shape, a reconciliation TEST_WRITING pass updates this file the
# same way US-4.1's v2 pass reconciled test_support_service.py against its
# own shipped collaborator shapes.
# =============================================================================


# --- TR-AC1/FR-1: agent public reply --------------------------------------


async def test_create_reply_agent_public_on_open_ticket_sets_waiting_on_customer() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "open"
    ticket.first_response_at = None
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=agent_id,
        actor_kind="agent",
        body="We're looking into it.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    assert result.author_kind == "agent"
    assert result.visibility == "public"
    assert ticket_repo.update_calls[-1]["status"] == "waiting_on_customer"
    assert reply_repo.commit_count == 1


async def test_create_reply_agent_public_on_resolved_ticket_status_unchanged() -> None:
    # Arrange: Resolution OD-5 — an agent's public reply on a resolved ticket
    # does not reopen it.
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "resolved"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Still resolved.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert: no status write at all — the "leave unchanged" branch.
    assert all(call["status"] is None for call in ticket_repo.update_calls)


async def test_create_reply_agent_internal_note_status_unchanged() -> None:
    # Arrange: an internal note is not customer-facing communication —
    # no status transition regardless of the ticket's prior status.
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Internal note.",
        visibility="internal",
        attachment_ids=[],
    )

    # Assert
    assert all(call["status"] is None for call in ticket_repo.update_calls)


async def test_create_reply_first_response_at_stamped_once_on_first_public_agent_reply() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket.first_response_at = None
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="First reply.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    stamped_calls = [c for c in ticket_repo.update_calls if c["first_response_at"] is not None]
    assert len(stamped_calls) == 1


async def test_create_reply_first_response_at_not_restamped_on_second_public_agent_reply() -> None:
    # Arrange: `first_response_at` already set — stamped exactly once (FR-1).
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "waiting_on_customer"
    ticket.first_response_at = _FIXED_NOW
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Second reply.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    assert all(c["first_response_at"] is None for c in ticket_repo.update_calls)


async def test_create_reply_agent_notifies_requester() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, *_, email_sender = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Reply body.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert: FR-1's requester notification, best-effort after commit.
    assert len(email_sender.reply_notifications_sent) == 1
    assert email_sender.queue_notifications_sent == []


# --- TR-AC2/FR-2: customer reply --------------------------------------------


async def test_create_reply_customer_on_waiting_on_customer_sets_waiting_on_support() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "waiting_on_customer"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="Any update?",
        visibility=None,
        attachment_ids=[],
    )

    # Assert
    assert result.author_kind == "customer"
    assert ticket_repo.update_calls[-1]["status"] == "waiting_on_support"


async def test_create_reply_customer_on_resolved_reopens_to_waiting_on_support() -> None:
    # Arrange: Resolution OD-8 — a customer reply on a resolved ticket
    # reopens it to the same target status FR-2's ordinary case produces.
    #
    # US-4.3 DESIGN_REVIEW v2 DR-4 / implementation-plan.md Decision 2:
    # test-writer's own reconciliation of this pre-existing US-4.2 test —
    # this specific sub-case (source status "resolved") now goes through
    # `transition_status(..., require_resolved_within_window=True)`, not
    # `update()`, and writes an audit_log entry (`ticket_reopened`). The
    # *ordinary* FR-2 case (source status "waiting_on_customer", the test
    # above) is deliberately left on plain `update()` — applying the window
    # guard there too would attach `AND resolved_at >= now() - interval
    # '7 days'` to a row whose `resolved_at` is NULL, which never matches in
    # SQL, silently breaking FR-2. This split is test-writer's own
    # collaborator-shape assumption, not literally spelled out by the plan's
    # single-branch description — flagged in `US-4.3-test-generation-report.md`
    # for reconciliation-reviewer.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _, _, _, audit_service, _ = _make_reply_service(
        ticket_repository=ticket_repo
    )

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="Actually it's still broken.",
        visibility=None,
        attachment_ids=[],
    )

    # Assert
    last_transition = ticket_repo.transition_calls[-1]
    assert last_transition["new_status"] == "waiting_on_support"
    assert last_transition["clear_resolved_at"] is True
    assert last_transition["require_resolved_within_window"] is True
    assert ticket.status == "waiting_on_support"
    assert ticket.resolved_at is None
    call = audit_service.record_event_calls[-1]
    assert call["event"] == "ticket_reopened"
    assert call["actor_id"] == requester_id


async def test_create_reply_customer_on_resolved_outside_window_makes_no_status_write() -> None:
    # Arrange: the reply-driven reopen shares `transition_status`'s window
    # guard with `/reopen` (implementation-plan.md Decision 2's "not a
    # second copy") — a reply outside the 7-day window is still accepted
    # (FR-6 does not gate replies), but produces no status change and no
    # `ticket_reopened` audit write. Simulated via `transition_returns_none`
    # (the fake cannot itself evaluate real interval arithmetic — an
    # integration-level concern, `US-4.3-test-strategy.md`).
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _resolved_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    ticket_repo.transition_returns_none = True
    service, ticket_repo, reply_repo, _, _, audit_service, _ = _make_reply_service(
        ticket_repository=ticket_repo
    )

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="Still there?",
        visibility=None,
        attachment_ids=[],
    )

    # Assert: the reply itself is still accepted...
    assert result.body == "Still there?"
    assert len(reply_repo.created) == 1
    # ...but the ticket never transitions and nothing is audited.
    assert ticket.status == "resolved"
    assert audit_service.record_event_calls == []


@pytest.mark.parametrize("status_before", ["open", "waiting_on_support"])
async def test_create_reply_customer_on_other_status_makes_no_status_write(
    status_before: str,
) -> None:
    # Arrange: API_DESIGN v3 Open Question #1 (carried non-blocking through
    # DESIGN_REVIEW/IMPACT_ANALYSIS) — not stated by any FR/AC. The
    # implementation plan's own conservative default (Architectural Change
    # #4): reply still accepted, no status write.
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = status_before
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, _reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="Just checking in.",
        visibility=None,
        attachment_ids=[],
    )

    # Assert: still accepted (a created reply is returned)...
    assert result.body == "Just checking in."
    # ...but no status write at all.
    assert all(c["status"] is None for c in ticket_repo.update_calls)


async def test_create_reply_customer_notifies_queue_not_requester() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "waiting_on_customer"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, *_, email_sender = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="Any update?",
        visibility=None,
        attachment_ids=[],
    )

    # Assert: FR-2 — no assignment concept (OD-2), always the fixed queue.
    assert len(email_sender.queue_notifications_sent) == 1
    assert email_sender.reply_notifications_sent == []


# --- FR-6: closed and resolved tickets --------------------------------------


@pytest.mark.parametrize("actor_kind", ["agent", "customer"])
async def test_create_reply_any_actor_on_closed_ticket_raises_ticket_closed(
    actor_kind: str,
) -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "closed"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)
    actor_id = requester_id if actor_kind == "customer" else uuid.uuid4()

    # Act & Assert
    with pytest.raises(TicketClosedError):
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=actor_id,
            actor_kind=actor_kind,
            body="Reopening attempt.",
            visibility="public",
            attachment_ids=[],
        )
    assert reply_repo.created == []
    assert ticket_repo.update_calls == []


# --- TR-AC5/FR-5: internal notes restricted to agents -----------------------


async def test_create_reply_customer_internal_raises_from_service_not_integrity() -> None:
    # Arrange: the service's own explicit check must raise before any insert
    # is attempted — never a caught `IntegrityError` translated after the
    # fact (implementation-plan Architectural Change #5 / db-design v3's
    # explicit layering note).
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(InsufficientPermissionError):
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=requester_id,
            actor_kind="customer",
            body="Let me sneak an internal note.",
            visibility="internal",
            attachment_ids=[],
        )
    # No insert was ever attempted — the fake never even had the chance to
    # raise an IntegrityError, proving the rejection happens before any
    # repository call, not by catching a constraint violation.
    assert reply_repo.created == []


async def test_create_reply_customer_omitted_visibility_defaults_to_public() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket.status = "waiting_on_customer"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        body="No visibility given.",
        visibility=None,
        attachment_ids=[],
    )

    # Assert
    assert result.visibility == "public"


async def test_create_reply_agent_omitted_visibility_defaults_to_public() -> None:
    # Arrange: Resolution OD-6 — same default for both actor kinds.
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="No visibility given.",
        visibility=None,
        attachment_ids=[],
    )

    # Assert
    assert result.visibility == "public"


# --- TR-AC4/FR-4: ownership/scope authorization -----------------------------


async def test_create_reply_different_customer_raises_ticket_not_found() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=uuid.uuid4(),
            actor_kind="customer",
            body="Not my ticket.",
            visibility=None,
            attachment_ids=[],
        )
    assert reply_repo.created == []


async def test_create_reply_caller_neither_owner_nor_agent_raises_ticket_not_found() -> None:
    # Arrange: API_DESIGN v3 Open Question #2 — generalizes FR-4's GET-
    # specific rule to POST. Not reachable under the shipped role seed
    # (tickets:read/tickets:write always travel together), asserted here at
    # the unit level where `actor_kind` is injected directly rather than
    # derived from a real JWT scope list.
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=uuid.uuid4(),
            actor_kind="customer",
            body="Neither owner nor agent.",
            visibility=None,
            attachment_ids=[],
        )
    assert reply_repo.created == []


async def test_create_reply_unknown_ticket_raises_ticket_not_found() -> None:
    # Arrange
    service, _ticket_repo, reply_repo, *_ = _make_reply_service()

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.create_reply(
            ticket_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            actor_kind="agent",
            body="No such ticket.",
            visibility="public",
            attachment_ids=[],
        )
    assert reply_repo.created == []


# --- OD-1/FR-1/FR-2: attachment reply-binding (IDOR) ------------------------


async def test_create_reply_attachment_owned_and_unbound_is_bound_to_the_reply() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    attachment_repo = FakeAttachmentRepository(
        attachments={
            attachment_id: _make_attachment(
                attachment_id=attachment_id, uploaded_by=agent_id, ticket_reply_id=None
            )
        }
    )
    service, _, _reply_repo, attachment_repo, *_ = _make_reply_service(
        ticket_repository=ticket_repo, attachment_repository=attachment_repo
    )

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=agent_id,
        actor_kind="agent",
        body="See attached.",
        visibility="public",
        attachment_ids=[attachment_id],
    )

    # Assert
    assert attachment_repo.bind_reply_calls == [(attachment_id, result.id)]
    assert attachment_repo.attachments[attachment_id].ticket_reply_id == result.id


@pytest.mark.parametrize(
    "attachment_factory",
    [
        pytest.param(
            lambda actor_id, other_id: {
                other_id: _make_attachment(attachment_id=other_id, uploaded_by=uuid.uuid4())
            },
            id="owned_by_another_user",
        ),
        pytest.param(
            lambda actor_id, other_id: {
                other_id: _make_attachment(
                    attachment_id=other_id, uploaded_by=actor_id, ticket_reply_id=uuid.uuid4()
                )
            },
            id="already_bound_to_another_reply",
        ),
        pytest.param(lambda actor_id, other_id: {}, id="unknown_attachment_id"),
    ],
)
async def test_create_reply_attachment_not_owned_raises_indistinguishable_error(
    attachment_factory: Callable[[uuid.UUID, uuid.UUID], dict[uuid.UUID, Attachment]],
) -> None:
    # Arrange: FR-1/BR-016 — same non-disclosure rule as US-4.1's own
    # attachment-ownership check (US-4.1 FR-7).
    ticket_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    attachment_repo = FakeAttachmentRepository(
        attachments=attachment_factory(agent_id, attachment_id)
    )
    service, _, reply_repo, attachment_repo, *_ = _make_reply_service(
        ticket_repository=ticket_repo, attachment_repository=attachment_repo
    )

    # Act & Assert
    with pytest.raises(AttachmentNotOwnedError):
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=agent_id,
            actor_kind="agent",
            body="See attached.",
            visibility="public",
            attachment_ids=[attachment_id],
        )
    assert reply_repo.created == []
    assert attachment_repo.bind_reply_calls == []


# --- NFR: reply rate limit (30/hour), independent of ticket-creation's -----


async def test_create_reply_rate_limit_exceeded_raises_429_with_retry_after() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    rate_limit_cache = FakeTicketReplyRateLimitCache(count=31)
    service, ticket_repo, reply_repo, *_ = _make_reply_service(
        ticket_repository=ticket_repo, rate_limit_cache=rate_limit_cache
    )

    # Act & Assert
    with pytest.raises(TicketReplyRateLimitError) as exc_info:
        await service.create_reply(
            ticket_id=ticket_id,
            actor_id=uuid.uuid4(),
            actor_kind="agent",
            body="Reply 31.",
            visibility="public",
            attachment_ids=[],
        )
    assert exc_info.value.headers is not None
    assert "Retry-After" in exc_info.value.headers
    assert reply_repo.created == []


async def test_create_reply_at_rate_limit_boundary_succeeds() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    rate_limit_cache = FakeTicketReplyRateLimitCache(count=30)
    service, *_ = _make_reply_service(
        ticket_repository=ticket_repo, rate_limit_cache=rate_limit_cache
    )

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Reply 30.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    assert result.body == "Reply 30."


def test_ticket_reply_rate_key_never_collides_with_ticket_create_rate_key() -> None:
    # Arrange: Risk 6 — an implementation accidentally sharing one Valkey
    # counter between ticket creation and replies would silently exhaust one
    # user-facing limit against the other's traffic.
    from app.core.cache_keys import ticket_create_rate_key, ticket_reply_rate_key

    user_id = uuid.uuid4()

    # Act
    create_key = ticket_create_rate_key(user_id)
    reply_key = ticket_reply_rate_key(user_id)

    # Assert
    assert create_key != reply_key


# --- Transaction boundary ----------------------------------------------------


async def test_create_reply_commits_exactly_once() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act
    await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Reply body.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    assert reply_repo.commit_count == 1


async def test_create_reply_email_dispatch_failure_does_not_fail_the_request() -> None:
    # Arrange: the reply is already committed by the time email dispatch
    # runs — a dispatch failure must not undo it or propagate (matches
    # `create_ticket`'s own best-effort-after-commit precedent).
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket.status = "open"
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, ticket_repo, reply_repo, *_ = _make_reply_service(
        ticket_repository=ticket_repo, email_sender=FakeEmailSender(raises=True)
    )

    # Act
    result = await service.create_reply(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        body="Reply body.",
        visibility="public",
        attachment_ids=[],
    )

    # Assert
    assert result.body == "Reply body."
    assert reply_repo.commit_count == 1


# --- FR-3/FR-4/GET Thread Pagination: get_ticket_detail ---------------------


async def test_get_ticket_detail_owner_customer_returns_ticket_and_thread() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=requester_id)
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    reply = _make_reply(ticket_id=ticket_id, author_id=requester_id, author_kind="customer")
    reply_repo = FakeTicketReplyRepository()
    reply_repo.list_page = ReplyListPage(items=[reply], next_cursor="next-page")
    service, *_ = _make_reply_service(ticket_repository=ticket_repo, reply_repository=reply_repo)

    # Act
    result = await service.get_ticket_detail(
        ticket_id=ticket_id,
        actor_id=requester_id,
        actor_kind="customer",
        cursor=None,
        limit=50,
    )

    # Assert
    assert result.id == ticket_id
    assert [item.id for item in result.replies.items] == [reply.id]
    assert result.replies.next_cursor == "next-page"


async def test_get_ticket_detail_agent_scopes_thread_query_by_ticket_id() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    reply_repo = FakeTicketReplyRepository()
    service, *_ = _make_reply_service(ticket_repository=ticket_repo, reply_repository=reply_repo)

    # Act
    await service.get_ticket_detail(
        ticket_id=ticket_id,
        actor_id=uuid.uuid4(),
        actor_kind="agent",
        cursor="prev-cursor",
        limit=25,
    )

    # Assert
    assert reply_repo.list_calls == [{"ticket_id": ticket_id, "cursor": "prev-cursor", "limit": 25}]


async def test_get_ticket_detail_different_customer_raises_ticket_not_found() -> None:
    # Arrange
    ticket_id = uuid.uuid4()
    ticket = _make_ticket(requester_id=uuid.uuid4())
    ticket.id = ticket_id
    ticket_repo = FakeTicketRepository(existing={ticket_id: ticket})
    service, *_ = _make_reply_service(ticket_repository=ticket_repo)

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.get_ticket_detail(
            ticket_id=ticket_id,
            actor_id=uuid.uuid4(),
            actor_kind="customer",
            cursor=None,
            limit=50,
        )


async def test_get_ticket_detail_unknown_ticket_raises_ticket_not_found() -> None:
    # Arrange
    service, *_ = _make_reply_service()

    # Act & Assert
    with pytest.raises(TicketNotFoundError):
        await service.get_ticket_detail(
            ticket_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            actor_kind="agent",
            cursor=None,
            limit=50,
        )
