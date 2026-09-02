from dataclasses import dataclass

from app.core.exceptions import DomainError, FieldError
from app.core.problem_details import ProblemError

_PASSWORD_POLICY_MESSAGES = {
    "min_length": "Password must be at least 12 characters.",
    "breached": "This password has appeared in a known data breach. Choose a different one.",
    "reused": "New password must be different from your current password.",
}


@dataclass(slots=True)
class RegistrationValidationError(DomainError):
    errors: list[FieldError]


class DuplicateEmailError(DomainError):
    """Raised when a registration email is already in use (case-insensitive)."""


class InvalidCredentialsError(ProblemError):
    """Raised for a wrong password or an unknown email — same response either way."""

    type_slug = "invalid-credentials"
    title = "Invalid Credentials"
    status = 401
    detail = "The email or password is incorrect."


class EmailNotVerifiedError(ProblemError):
    type_slug = "email-not-verified"
    title = "Email Not Verified"
    status = 403
    detail = "This account's email address has not been verified yet."


class AccountDeactivatedError(ProblemError):
    type_slug = "account-deactivated"
    title = "Account Deactivated"
    status = 403
    detail = (
        "This account has been deactivated. Log in again to reactivate it within the grace period."
    )


class TooManyAttemptsError(ProblemError):
    type_slug = "too-many-attempts"
    title = "Too Many Attempts"
    status = 429
    detail = "Too many failed login attempts. Try again later."

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after_seconds)}


class TokenInvalidError(ProblemError):
    """Raised for RT-AC2/RT-AC3/RT-AC5/RT-AC6 — reused uniformly so an
    unknown, expired, revoked-by-logout, reused, or raced-out refresh token
    all produce an identical response (FR-3's indistinguishability
    requirement, resolved OD-3 scoped to status/body only).
    """

    type_slug = "token-invalid"
    title = "Refresh Token Invalid"
    status = 401
    detail = "This session can no longer be refreshed. Sign in again."


class PasswordResetTokenInvalidError(ProblemError):
    """FR-4: unknown token hash or already-consumed token (including the
    losing side of the atomic consume race). Deliberately a separate class
    from refresh's `TokenInvalidError` (401) — this story's FR-4 requires
    `400`, and this codebase already has per-module duplication of the same
    `token-invalid` slug under different classes (`email_verification`,
    `profile`), so this follows that established convention rather than
    reusing a class with the wrong status.
    """

    type_slug = "token-invalid"
    title = "Password Reset Token Invalid"
    status = 400
    detail = "This password reset link is no longer valid. Request a new one."


class PasswordResetTokenExpiredError(ProblemError):
    """FR-4: the token's `expires_at` has passed."""

    type_slug = "token-expired"
    title = "Password Reset Token Expired"
    status = 400
    detail = "This password reset link has expired. Request a new one."


class PasswordPolicyError(ProblemError):
    """FR-5: new password too short, breached, or equal to the current
    password. Uses `ProblemError`'s existing `errors` field — one
    `FieldError` per failed rule, per PR-AC5's "errors array states which
    rule failed."
    """

    type_slug = "password-policy"
    title = "Password Does Not Meet Policy"
    status = 422
    detail = "Choose a password of at least 12 characters that you have not used before."

    def __init__(self, *, rules: list[str]) -> None:
        super().__init__()
        self.errors = [
            FieldError(field="new_password", message=_PASSWORD_POLICY_MESSAGES[rule], code=rule)
            for rule in rules
        ]


class TokenStaleError(ProblemError):
    """MR-AC2 (US-3.2/spec US-012): the session's access token was issued
    before the target's last role change (`perm_epoch`). Deliberately a
    distinct type slug from `UnauthenticatedError` — the client is meant
    to react by calling `/auth/refresh`, not by re-authenticating from
    scratch, since `perm_epoch` invalidates access tokens only.
    """

    type_slug = "token-stale"
    title = "Token Predates a Permission Change"
    status = 401
    detail = "Your permissions changed. Refresh the session to continue."


class MfaInvalidCodeError(ProblemError):
    """FR-4: incorrect code, replayed code, or an invalid/expired/already-
    consumed mfa_token — all indistinguishable (US-009 MF-AC4). Also
    reused by FR-2's activate (wrong code, or no PENDING enrolment at
    all — an Open Question the API design left as one generic shape,
    see docs/designs/api/US-009-api-design.md) and by FR-8's disable
    (wrong TOTP code).
    """

    type_slug = "mfa-invalid-code"
    title = "Invalid MFA Code"
    status = 401
    detail = "The code you entered is incorrect or has expired."


class MfaRequiredForRoleError(ProblemError):
    """FR-6: caller holds admin/auditor/support_agent — MFA cannot be
    disabled on a privileged account. Matches the source story's Error
    Envelope example verbatim.
    """

    type_slug = "mfa-required-for-role"
    title = "MFA Required For This Role"
    status = 409
    detail = "Accounts with administrative access must keep multi-factor authentication enabled."


class MfaEnrollmentRequiredError(ProblemError):
    """FR-6/FR-7: the caller's access token is enrolment-scoped (a
    privileged-role grant without MFA past its grace period, or a prior
    recovery-code use) and the endpoint being called is not one of the
    two enrolment endpoints that accept such a token. This is the
    default-deny check at the shared authenticated-request choke point
    (get_authenticated_user) — see docs/plans/US-009-implementation-plan.md
    Architectural Change #2.
    """

    type_slug = "mfa-enrollment-required"
    title = "MFA Enrolment Required"
    status = 403
    detail = "Complete multi-factor authentication enrolment to continue."


class UnauthenticatedError(ProblemError):
    type_slug = "unauthenticated"
    title = "Unauthenticated"
    status = 401
    detail = "A valid access token is required."

    def __init__(self) -> None:
        super().__init__()
        self.headers = {"WWW-Authenticate": "Bearer"}
