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
    TicketCreationRateLimitError,
)
from app.modules.support.models import Attachment, Ticket
from app.modules.support.repository import TicketListPage
from app.modules.support.service import TicketService, _hash_request

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
    return ticket


def _make_attachment(
    *,
    attachment_id: uuid.UUID | None = None,
    uploaded_by: uuid.UUID,
    ticket_id: uuid.UUID | None = None,
) -> Attachment:
    attachment = Attachment(uploaded_by=uploaded_by, ticket_id=ticket_id)
    attachment.id = attachment_id or uuid.uuid4()
    attachment.created_at = _FIXED_NOW
    return attachment


class FakeTicketRepository:
    def __init__(self, *, existing: dict[uuid.UUID, Ticket] | None = None) -> None:
        self.existing = existing or {}
        self.created: list[dict[str, Any]] = []
        self.commit_count = 0
        self.list_calls: list[dict[str, Any]] = []
        self.list_page: TicketListPage | None = TicketListPage(items=[], next_cursor=None)

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

    async def commit(self) -> None:
        self.commit_count += 1


class FakeAttachmentRepository:
    def __init__(self, *, attachments: dict[uuid.UUID, Attachment] | None = None) -> None:
        self.attachments = attachments or {}
        self.bind_calls: list[tuple[uuid.UUID, uuid.UUID]] = []
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

    async def send_ticket_created_email(self, *, to: str, ticket_number: str) -> None:
        if self.raises:
            raise RuntimeError("email dispatch failed")
        self.sent.append({"to": to, "ticket_number": ticket_number})

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
