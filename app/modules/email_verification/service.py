import hashlib
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.core.config import get_settings
from app.core.email import EmailSender, LoggingEmailSender
from app.modules.email_verification.exceptions import (
    InvalidRequestError,
    TokenExpiredError,
    TokenInvalidError,
    TooManyAttemptsError,
)
from app.modules.email_verification.models import EmailVerificationToken
from app.modules.email_verification.schemas import ResendResponse, VerifyEmailResponse
from app.modules.users.models import User

_GENERIC_RESEND_MESSAGE = (
    "If this email is registered and unverified, a verification email has been sent."
)
_TOKEN_BYTES = 32


class EmailVerificationRepositoryProtocol(Protocol):
    async def get_user_by_email(self, email: str) -> User | None: ...

    async def get_latest_token_for_user(
        self, user_id: uuid.UUID
    ) -> EmailVerificationToken | None: ...

    async def get_token_by_hash(self, token_hash: str) -> EmailVerificationToken | None: ...

    async def create_token(
        self, *, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> EmailVerificationToken: ...

    async def consume_token(self, token_id: uuid.UUID) -> bool: ...

    async def mark_user_verified(self, user_id: uuid.UUID) -> None: ...

    async def find_purge_candidates(self, cutoff: datetime) -> list[User]: ...

    async def delete_user(self, user_id: uuid.UUID) -> None: ...

    async def create_audit_log(
        self, *, event: str, subject_user_id: uuid.UUID, detail: str
    ) -> None: ...

    async def commit(self) -> None: ...


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class EmailVerificationService:
    def __init__(
        self,
        repository: EmailVerificationRepositoryProtocol,
        email_sender: EmailSender | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._email_sender = email_sender or LoggingEmailSender()
        self._clock = clock

    async def verify_email(self, raw_token: str | None) -> VerifyEmailResponse:
        if not raw_token:
            raise TokenInvalidError

        token_hash = _hash_token(raw_token)
        token = await self._repository.get_token_by_hash(token_hash)
        if token is None:
            raise TokenInvalidError
        if token.consumed_at is not None:
            raise TokenInvalidError
        if token.expires_at <= self._clock():
            raise TokenExpiredError

        won_race = await self._repository.consume_token(token.id)
        if not won_race:
            raise TokenInvalidError

        await self._repository.mark_user_verified(token.user_id)
        await self._repository.commit()
        return VerifyEmailResponse(email_verified=True)

    async def resend_verification(self, email: str | None) -> ResendResponse:
        normalized = (email or "").strip()
        if not normalized or "@" not in normalized:
            raise InvalidRequestError

        user = await self._repository.get_user_by_email(normalized)
        if user is None or user.email_verified:
            return ResendResponse(message=_GENERIC_RESEND_MESSAGE)

        settings = get_settings()
        latest = await self._repository.get_latest_token_for_user(user.id)
        if latest is not None:
            elapsed = (self._clock() - latest.issued_at).total_seconds()
            if elapsed < settings.resend_cooldown_seconds:
                retry_after = int(settings.resend_cooldown_seconds - elapsed)
                raise TooManyAttemptsError(retry_after_seconds=retry_after)

        raw_token = await self._issue_token(user.id)
        await self._repository.commit()
        await self._email_sender.send_verification_email(to=user.email, raw_token=raw_token)
        return ResendResponse(message=_GENERIC_RESEND_MESSAGE)

    async def issue_pending_token(self, user_id: uuid.UUID) -> str:
        raw_token = await self._issue_token(user_id)
        await self._repository.commit()
        return raw_token

    async def _issue_token(self, user_id: uuid.UUID) -> str:
        settings = get_settings()
        raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
        expires_at = self._clock() + timedelta(hours=settings.verification_token_ttl_hours)
        await self._repository.create_token(
            user_id=user_id, token_hash=_hash_token(raw_token), expires_at=expires_at
        )
        return raw_token

    async def purge_unverified_accounts(self) -> int:
        settings = get_settings()
        cutoff = self._clock() - timedelta(days=settings.unverified_account_purge_after_days)
        candidates = await self._repository.find_purge_candidates(cutoff)
        for user in candidates:
            await self._repository.create_audit_log(
                event="unverified_account_purged",
                subject_user_id=user.id,
                detail=(
                    f"Automatic purge: account created {user.created_at.isoformat()} "
                    f"exceeded the {settings.unverified_account_purge_after_days}-day "
                    "unverified window."
                ),
            )
            await self._repository.delete_user(user.id)
        await self._repository.commit()
        return len(candidates)
