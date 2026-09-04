import uuid


def revoke_before_key(user_id: uuid.UUID) -> str:
    return f"revoke_before:{user_id}"


def perm_epoch_key(user_id: uuid.UUID) -> str:
    return f"perm_epoch:{user_id}"


def login_fail_account_key(user_id: uuid.UUID) -> str:
    return f"login_fail:account:{user_id}"


def login_fail_ip_key(ip: str) -> str:
    return f"login_fail:ip:{ip}"


def refresh_rate_limit_key(family_id: uuid.UUID) -> str:
    return f"refresh_rate_limit:{family_id}"


def password_reset_cooldown_key(email_hash: str) -> str:
    return f"password_reset_cooldown:{email_hash}"


def password_reset_account_hourly_key(email_hash: str) -> str:
    return f"password_reset_account_hourly:{email_hash}"


def password_reset_ip_hourly_key(ip: str) -> str:
    return f"password_reset_ip_hourly:{ip}"


def mfa_token_key(token_hash: str) -> str:
    return f"mfa_token:{token_hash}"


def mfa_verify_attempts_key(token_hash: str) -> str:
    return f"mfa_verify_attempts:{token_hash}"


def mfa_used_step_key(user_id: uuid.UUID, step: int) -> str:
    return f"mfa_used_step:{user_id}:{step}"


def idempotency_key(user_id: uuid.UUID, key: str) -> str:
    return f"idempotency:{user_id}:{key}"


def ticket_create_rate_key(user_id: uuid.UUID) -> str:
    return f"ticket_create_rate:{user_id}"
