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
