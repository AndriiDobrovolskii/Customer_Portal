import uuid


def revoke_before_key(user_id: uuid.UUID) -> str:
    return f"revoke_before:{user_id}"


def login_fail_account_key(user_id: uuid.UUID) -> str:
    return f"login_fail:account:{user_id}"


def login_fail_ip_key(ip: str) -> str:
    return f"login_fail:ip:{ip}"
