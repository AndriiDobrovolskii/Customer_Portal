from pathlib import Path

from app.core.config import get_settings

_breached_passwords_cache: frozenset[str] | None = None


def _load_breached_passwords() -> frozenset[str]:
    settings = get_settings()
    path = Path(settings.breached_password_list_path)
    with path.open(encoding="utf-8") as f:
        return frozenset(line.strip() for line in f if line.strip())


def is_breached_password(password: str) -> bool:
    """OD-1: a local static list, never a live network call. Loaded once
    into a module-level `frozenset[str]` on first use — O(1) membership
    check, no bloom filter needed at this list's scale (a few hundred
    entries). The password itself is never transmitted anywhere; this is a
    pure in-process lookup.
    """
    global _breached_passwords_cache
    if _breached_passwords_cache is None:
        _breached_passwords_cache = _load_breached_passwords()
    return password in _breached_passwords_cache
