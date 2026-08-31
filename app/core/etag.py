import hashlib
import json


def compute_profile_etag(fields: dict[str, str | None]) -> str:
    """A strong ETag over the given field name/value pairs.

    Deliberately generic (no ORM import — app.core must stay domain-free):
    the caller builds `fields` from whatever model it holds. Reusable by a
    future GET /v1/profile. Recomputed after every write so the response
    header reflects post-update state, compared against the pre-update value
    on the way in.
    """
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return f'"{digest}"'
