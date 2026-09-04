import asyncio
import hashlib
import json
import logging
import uuid
from typing import Protocol

from app.core.email import EmailSender
from app.core.exceptions import FieldError
from app.modules.support.cache import IdempotencyEnvelope
from app.modules.support.exceptions import (
    AccountDeactivatedError,
    AttachmentNotOwnedError,
    IdempotencyKeyReuseError,
    TicketCreationRateLimitError,
    ValidationFailedError,
)
from app.modules.support.models import Attachment, Ticket
from app.modules.support.repository import TicketListPage
from app.modules.support.schemas import TicketListResponse, TicketRead

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

    async def commit(self) -> None: ...


class AttachmentRepositoryProtocol(Protocol):
    async def get_by_id(self, attachment_id: uuid.UUID) -> Attachment | None: ...

    async def bind_to_ticket(
        self, *, attachment_id: uuid.UUID, ticket_id: uuid.UUID
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
