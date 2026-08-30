import uuid


def revoke_before_key(user_id: uuid.UUID) -> str:
    return f"revoke_before:{user_id}"
