import asyncio
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol

from app.core.email import EmailSender
from app.core.exceptions import FieldError
from app.modules.support.cache import IdempotencyEnvelope
from app.modules.support.exceptions import (
    AccountDeactivatedError,
    AttachmentNotOwnedError,
    IdempotencyKeyReuseError,
    InsufficientPermissionError,
    TicketClosedError,
    TicketCreationRateLimitError,
    TicketNotFoundError,
    TicketReplyRateLimitError,
    ValidationFailedError,
)
from app.modules.support.models import Attachment, Ticket, TicketReply
from app.modules.support.repository import ReplyListPage, TicketListPage
from app.modules.support.schemas import (
    ReplyRead,
    ReplyThreadPage,
    TicketDetailRead,
    TicketListResponse,
    TicketRead,
)

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL_SECONDS = 86400  # FR-4: 24 hours
_RATE_LIMIT_WINDOW_SECONDS = 3600  # FR-6: 1 hour
_RATE_LIMIT_MAX_CREATES = 5  # FR-6
_POLL_INTERVAL_SECONDS = 0.1  # US-4.1-db-design.md's bounded poll: 100ms
_POLL_MAX_ATTEMPTS = 5  # ...up to 5 times, 500ms total
_MAX_LIST_LIMIT = 100  # US-4.1-openapi.yaml, reusing US-3.1's own unstated choice


class TicketRepositoryProtocol(Protocol):
    async def create(
        self, *, requester_id: uuid.UUID, subject: str, body: str, category: str
    ) -> Ticket: ...

    async def get_by_id(self, ticket_id: uuid.UUID) -> Ticket | None: ...

    async def list_for_requester(
        self, *, requester_id: uuid.UUID, cursor: str | None, limit: int
    ) -> TicketListPage | None: ...

    async def update(
        self,
        ticket_id: uuid.UUID,
        *,
        status: str | None = None,
        first_response_at: datetime | None = None,
    ) -> Ticket | None: ...

    async def commit(self) -> None: ...


class AttachmentRepositoryProtocol(Protocol):
    async def get_by_id(self, attachment_id: uuid.UUID) -> Attachment | None: ...

    async def bind_to_ticket(
        self, *, attachment_id: uuid.UUID, ticket_id: uuid.UUID
    ) -> Attachment | None: ...

    async def bind_to_reply(
        self, *, attachment_id: uuid.UUID, ticket_reply_id: uuid.UUID
    ) -> Attachment | None: ...

    async def commit(self) -> None: ...


class TicketIdempotencyCacheProtocol(Protocol):
    async def claim(
        self, *, user_id: uuid.UUID, key: str, request_hash: str, ttl_seconds: int
    ) -> bool: ...

    async def get_envelope(self, *, user_id: uuid.UUID, key: str) -> IdempotencyEnvelope | None: ...

    async def resolve(
        self,
        *,
        user_id: uuid.UUID,
        key: str,
        request_hash: str,
        ticket_id: uuid.UUID,
        ttl_seconds: int,
    ) -> None: ...

    async def release(self, *, user_id: uuid.UUID, key: str) -> None: ...


class TicketCreationRateLimitCacheProtocol(Protocol):
    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int: ...

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int: ...


class AuditServiceProtocol(Protocol):
    """Cross-module collaborator (`app.modules.audit.service`), service ->
    service per `AGENTS.md` §3 — never `audit.repository`/`AuditLog`
    directly.
    """

    async def record_event(
        self,
        *,
        category: str,
        event: str,
        actor_id: uuid.UUID,
        target_id: uuid.UUID | None,
        outcome: str | None,
        payload: dict[str, object] | None,
    ) -> None: ...


class UserServiceProtocol(Protocol):
    """Cross-module collaborator (`app.modules.users.service`) resolving the
    requester's email for FR-1's confirmation email — not part of
    `US-4.1-implementation-plan.md`'s stated collaborator list, flagged as a
    plan gap in `docs/catalog/US-4.1-pipeline-status.md` — and the
    requester's current account status for FR-5's deactivated-account gate.
    """

    async def get_email_for_user(self, user_id: uuid.UUID) -> str | None: ...

    async def get_account_status_for_user(self, user_id: uuid.UUID) -> str | None: ...


def _hash_request(
    *, subject: str, body: str, category: str, attachment_ids: list[uuid.UUID]
) -> str:
    """FR-4's "different body" comparison covers the full request payload
    (OD-2's adopted recommendation), not just `body` — a deterministic
    JSON serialization, sorted, so field order never affects the hash.
    """
    canonical = json.dumps(
        {
            "subject": subject,
            "body": body,
            "category": category,
            "attachment_ids": sorted(str(a) for a in attachment_ids),
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class TicketService:
    def __init__(
        self,
        repository: TicketRepositoryProtocol,
        attachment_repository: AttachmentRepositoryProtocol,
        idempotency_cache: TicketIdempotencyCacheProtocol,
        rate_limit_cache: TicketCreationRateLimitCacheProtocol,
        audit_service: AuditServiceProtocol,
        user_service: UserServiceProtocol,
        email_sender: EmailSender,
    ) -> None:
        self._repository = repository
        self._attachment_repository = attachment_repository
        self._idempotency_cache = idempotency_cache
        self._rate_limit_cache = rate_limit_cache
        self._audit_service = audit_service
        self._user_service = user_service
        self._email_sender = email_sender

    async def create_ticket(
        self,
        *,
        requester_id: uuid.UUID,
        idempotency_key: str,
        subject: str,
        body: str,
        category: str,
        attachment_ids: list[uuid.UUID],
    ) -> TicketRead:
        """FR-1/FR-4/FR-5/FR-6/FR-7. Order per `US-4.1-db-design.md`:
        idempotency gate -> rate limit (skipped on replay) -> attachment
        ownership -> ticket insert -> attachment bind -> audit write, all in
        one transaction, one commit (`US-4.1-implementation-plan.md`
        Architectural Change #2). FR-5's account-deactivated check runs
        first, before any cache/DB write: `CurrentUserDep` never checks
        account status itself (a session survives its own account's
        deactivation unless separately revoked — `users/dependencies.py`),
        so a still-valid session for an already-deactivated account must be
        rejected here instead.
        """
        status = await self._user_service.get_account_status_for_user(requester_id)
        if status == "deactivated":
            raise AccountDeactivatedError

        request_hash = _hash_request(
            subject=subject, body=body, category=category, attachment_ids=attachment_ids
        )

        claimed = await self._idempotency_cache.claim(
            user_id=requester_id,
            key=idempotency_key,
            request_hash=request_hash,
            ttl_seconds=_IDEMPOTENCY_TTL_SECONDS,
        )
        if not claimed:
            ticket_id = await self._resolve_idempotency_replay(
                requester_id=requester_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
            ticket = await self._repository.get_by_id(ticket_id)
            if ticket is None:
                # The envelope named a ticket id that no longer exists -
                # not a case any design artifact anticipates (tickets are
                # never deleted by this story). Propagates as an unhandled
                # server error, same as the poll-exhaustion path.
                raise RuntimeError("idempotency envelope referenced a missing ticket")
            return TicketRead.model_validate(ticket)

        try:
            # Only a genuinely new claim reaches the rate limit - a replay
            # branch above already returned before this point (FR-4/FR-6
            # ordering, US-4.1-db-design.md).
            count = await self._rate_limit_cache.record_and_check(
                requester_id, window_seconds=_RATE_LIMIT_WINDOW_SECONDS
            )
            if count > _RATE_LIMIT_MAX_CREATES:
                retry_after = await self._rate_limit_cache.get_retry_after_seconds(requester_id)
                raise TicketCreationRateLimitError(retry_after_seconds=retry_after)

            validated_attachments: list[Attachment] = []
            for attachment_id in attachment_ids:
                attachment = await self._attachment_repository.get_by_id(attachment_id)
                if (
                    attachment is None
                    or attachment.uploaded_by != requester_id
                    or attachment.ticket_id is not None
                ):
                    raise AttachmentNotOwnedError
                validated_attachments.append(attachment)

            ticket = await self._repository.create(
                requester_id=requester_id, subject=subject, body=body, category=category
            )

            for attachment in validated_attachments:
                bound = await self._attachment_repository.bind_to_ticket(
                    attachment_id=attachment.id, ticket_id=ticket.id
                )
                if bound is None:
                    # Lost a concurrent race for this attachment between the
                    # ownership check above and this bind - indistinguishable
                    # from any other attachment-not-owned cause (FR-7).
                    raise AttachmentNotOwnedError

            await self._audit_service.record_event(
                category="tickets",
                event="ticket_created",
                actor_id=requester_id,
                target_id=ticket.id,
                outcome="success",
                payload={"ticket_number": ticket.ticket_number, "category": category},
            )

            await self._repository.commit()
        except Exception:
            # This request is the sole claimant of `idempotency_key` - a
            # failure here must release it, or every retry with the same
            # key would poll against a stuck `ticket_id: null` envelope
            # until its 24h TTL expires (found while building this method;
            # see cache.py's `release` docstring).
            await self._idempotency_cache.release(user_id=requester_id, key=idempotency_key)
            raise

        # Cache writes strictly after commit (AGENTS.md §3).
        await self._idempotency_cache.resolve(
            user_id=requester_id,
            key=idempotency_key,
            request_hash=request_hash,
            ticket_id=ticket.id,
            ttl_seconds=_IDEMPOTENCY_TTL_SECONDS,
        )

        # Best-effort, after commit (register_user's precedent,
        # app/modules/users/service.py): a failed dispatch must not undo
        # the already-committed ticket.
        email = await self._user_service.get_email_for_user(requester_id)
        if email is not None:
            try:
                await self._email_sender.send_ticket_created_email(
                    to=email, ticket_number=ticket.ticket_number
                )
            except Exception:
                logger.exception("failed to send ticket created email")

        return TicketRead.model_validate(ticket)

    async def _resolve_idempotency_replay(
        self, *, requester_id: uuid.UUID, idempotency_key: str, request_hash: str
    ) -> uuid.UUID:
        """US-4.1-db-design.md's bounded-poll gate: called only when `claim`
        returned False (the key already exists). Raises `IdempotencyKeyReuseError`
        on a stored-hash mismatch; raises a bare `RuntimeError` when the poll
        budget is exhausted, matching the DB design's explicit "unhandled
        server error, no new contract slug" statement for that case - this
        method deliberately lets it propagate rather than catching and
        re-wrapping it.
        """
        envelope = await self._idempotency_cache.get_envelope(
            user_id=requester_id, key=idempotency_key
        )
        for _ in range(_POLL_MAX_ATTEMPTS):
            if envelope is None:
                break
            if envelope.request_hash != request_hash:
                raise IdempotencyKeyReuseError
            if envelope.ticket_id is not None:
                return envelope.ticket_id
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            envelope = await self._idempotency_cache.get_envelope(
                user_id=requester_id, key=idempotency_key
            )
        raise RuntimeError("idempotency poll exhausted: in-flight request did not resolve")

    async def list_own_tickets(
        self, *, requester_id: uuid.UUID, status: str | None, cursor: str | None, limit: int
    ) -> TicketListResponse:
        """FR-2. `status` filtering by anything other than "open" yields an
        empty page, not an error (US-4.1-openapi.yaml's own stated
        behavior) - this story never produces a ticket in any other state.
        """
        if not 1 <= limit <= _MAX_LIST_LIMIT:
            raise ValidationFailedError(
                errors=[
                    FieldError(
                        field="limit", message="limit must be between 1 and 100.", code="max"
                    )
                ]
            )

        if status is not None and status != "open":
            return TicketListResponse(items=[], next_cursor=None)

        page = await self._repository.list_for_requester(
            requester_id=requester_id, cursor=cursor, limit=limit
        )
        if page is None:
            raise ValidationFailedError(
                errors=[FieldError(field="cursor", message="Invalid cursor.", code="invalid")]
            )

        return TicketListResponse(
            items=[TicketRead.model_validate(ticket) for ticket in page.items],
            next_cursor=page.next_cursor,
        )


# =============================================================================
# US-4.2 (Ticket Replies) — TicketReplyService
# =============================================================================

_REPLY_RATE_LIMIT_WINDOW_SECONDS = 3600  # NFR: 1 hour
_REPLY_RATE_LIMIT_MAX_REPLIES = 30  # NFR


class TicketReplyRepositoryProtocol(Protocol):
    async def create(
        self,
        *,
        ticket_id: uuid.UUID,
        author_id: uuid.UUID,
        author_kind: str,
        body: str,
        visibility: str,
    ) -> TicketReply: ...

    async def list_for_ticket(
        self, *, ticket_id: uuid.UUID, cursor: str | None, limit: int
    ) -> ReplyListPage | None: ...

    async def commit(self) -> None: ...


class TicketReplyRateLimitCacheProtocol(Protocol):
    async def record_and_check(self, user_id: uuid.UUID, *, window_seconds: int) -> int: ...

    async def get_retry_after_seconds(self, user_id: uuid.UUID) -> int: ...


class TicketReplyService:
    def __init__(
        self,
        ticket_repository: TicketRepositoryProtocol,
        reply_repository: TicketReplyRepositoryProtocol,
        attachment_repository: AttachmentRepositoryProtocol,
        rate_limit_cache: TicketReplyRateLimitCacheProtocol,
        email_sender: EmailSender,
        user_service: UserServiceProtocol | None = None,
    ) -> None:
        """`user_service` is optional (unlike `TicketService`'s required
        collaborator of the same shape): FR-1's requester notification is
        best-effort regardless of whether a real email address can be
        resolved (test-writer's own collaborator-shape assumption fixes this
        class's five other constructor args; see
        `docs/tests/US-4.2-test-strategy.md`). When wired (`dependencies.py`,
        real deployment), it resolves the requester's actual email; when
        absent, `_resolve_requester_email` falls back to a non-email
        placeholder rather than skipping the dispatch — the notification
        methods themselves are still Protocol-shaped exactly as this
        module's tests require.
        """
        self._ticket_repository = ticket_repository
        self._reply_repository = reply_repository
        self._attachment_repository = attachment_repository
        self._rate_limit_cache = rate_limit_cache
        self._email_sender = email_sender
        self._user_service = user_service

    async def _resolve_requester_email(self, requester_id: uuid.UUID) -> str:
        if self._user_service is not None:
            email = await self._user_service.get_email_for_user(requester_id)
            if email is not None:
                return email
        return str(requester_id)

    async def create_reply(
        self,
        *,
        ticket_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_kind: str,
        body: str,
        visibility: str | None,
        attachment_ids: list[uuid.UUID],
    ) -> ReplyRead:
        """FR-1/FR-2/FR-4/FR-5/FR-6. Authorization, status-gating, and
        `first_response_at` stamping follow `US-4.2-implementation-plan.md`
        Architectural Change #4's table exactly - the "customer reply on
        `\"open\"`/`\"waiting_on_support\"`" case (API_DESIGN Open Question #1)
        makes no status write, by design, not by omission.
        """
        ticket = await self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError

        if actor_kind == "customer" and ticket.requester_id != actor_id:
            # Also covers API_DESIGN Open Question #2 (a caller neither the
            # requester nor an agent): the router only ever passes
            # actor_kind="agent" for a tickets:write holder, so any other
            # caller reaches this branch and fails the ownership check.
            raise TicketNotFoundError

        if ticket.status == "closed":
            raise TicketClosedError

        if visibility is None:
            visibility = "public"
        if visibility == "internal" and actor_kind != "agent":
            # FR-5's own service-layer check, raised before any repository
            # call - never a caught IntegrityError from the CHECK backstop
            # (db-design v3's explicit layering note).
            raise InsufficientPermissionError

        count = await self._rate_limit_cache.record_and_check(
            actor_id, window_seconds=_REPLY_RATE_LIMIT_WINDOW_SECONDS
        )
        if count > _REPLY_RATE_LIMIT_MAX_REPLIES:
            retry_after = await self._rate_limit_cache.get_retry_after_seconds(actor_id)
            raise TicketReplyRateLimitError(retry_after_seconds=retry_after)

        validated_attachments: list[Attachment] = []
        for attachment_id in attachment_ids:
            attachment = await self._attachment_repository.get_by_id(attachment_id)
            if (
                attachment is None
                or attachment.uploaded_by != actor_id
                or attachment.ticket_reply_id is not None
            ):
                raise AttachmentNotOwnedError
            validated_attachments.append(attachment)

        reply = await self._reply_repository.create(
            ticket_id=ticket_id,
            author_id=actor_id,
            author_kind=actor_kind,
            body=body,
            visibility=visibility,
        )

        for attachment in validated_attachments:
            bound = await self._attachment_repository.bind_to_reply(
                attachment_id=attachment.id, ticket_reply_id=reply.id
            )
            if bound is None:
                # Lost a concurrent race for this attachment between the
                # ownership check above and this bind (FR-1/FR-2/BR-016) -
                # indistinguishable from any other attachment-not-owned cause.
                raise AttachmentNotOwnedError

        status_update: str | None = None
        first_response_at_update: datetime | None = None
        if actor_kind == "agent":
            if visibility == "public":
                if ticket.first_response_at is None:
                    first_response_at_update = datetime.now(UTC)
                if ticket.status != "resolved":
                    status_update = "waiting_on_customer"
            # Internal notes are not customer-facing communication (FR-3) -
            # no status transition, no first_response_at stamp, regardless
            # of the ticket's prior status.
        elif ticket.status in ("waiting_on_customer", "resolved"):
            # Resolution OD-8: the resolved-ticket case reopens the ticket
            # to the same target status the ordinary case already produces.
            status_update = "waiting_on_support"

        if status_update is not None or first_response_at_update is not None:
            await self._ticket_repository.update(
                ticket_id, status=status_update, first_response_at=first_response_at_update
            )

        await self._reply_repository.commit()

        # Best-effort, after commit (TicketService.create_ticket's
        # precedent): a failed dispatch must not undo the already-committed
        # reply.
        try:
            if actor_kind == "agent":
                to = await self._resolve_requester_email(ticket.requester_id)
                await self._email_sender.send_ticket_reply_notification(
                    to=to, ticket_number=ticket.ticket_number
                )
            else:
                await self._email_sender.send_ticket_reply_queue_notification(
                    ticket_number=ticket.ticket_number
                )
        except Exception:
            logger.exception("failed to send ticket reply notification")

        return ReplyRead.model_validate(reply)

    async def get_ticket_detail(
        self,
        *,
        ticket_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_kind: str,
        cursor: str | None,
        limit: int,
    ) -> TicketDetailRead:
        """FR-3/FR-4/GET Thread Pagination. Composed from two direct
        repository calls, not `model_validate()`d off a single ORM object -
        no `relationship()` exists between `Ticket` and `TicketReply`
        (US-4.2-entity-model.md "Relationships").
        """
        ticket = await self._ticket_repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError

        if actor_kind == "customer" and ticket.requester_id != actor_id:
            raise TicketNotFoundError

        page = await self._reply_repository.list_for_ticket(
            ticket_id=ticket_id, cursor=cursor, limit=limit
        )
        if page is None:
            raise ValidationFailedError(
                errors=[FieldError(field="cursor", message="Invalid cursor.", code="invalid")]
            )

        return TicketDetailRead(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            status=ticket.status,
            requester_id=ticket.requester_id,
            subject=ticket.subject,
            body=ticket.body,
            category=ticket.category,
            first_response_at=ticket.first_response_at,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            replies=ReplyThreadPage(
                items=[ReplyRead.model_validate(item) for item in page.items],
                next_cursor=page.next_cursor,
            ),
        )
