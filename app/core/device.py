from user_agents import parse

_UNKNOWN = "Unknown device"


def resolve_device_label(user_agent: str | None) -> str:
    """OD-3: "{browser family} on {OS family}"; falls back to "Unknown
    device" when the header is missing or `user_agents` can't recognize a
    browser/OS in it (surfaced as the library's own "Other" placeholder) -
    never raises.
    """
    if not user_agent:
        return _UNKNOWN
    parsed = parse(user_agent)
    browser = parsed.browser.family
    os_family = parsed.os.family
    if browser in ("Other", "") or os_family in ("Other", ""):
        return _UNKNOWN
    return f"{browser} on {os_family}"
