import logging
from functools import lru_cache
from typing import NamedTuple

import geoip2.database
import geoip2.errors
import maxminddb

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GeoLocation(NamedTuple):
    city: str | None
    country: str | None


@lru_cache
def _get_reader() -> geoip2.database.Reader | None:
    """US-2.6/OD-4: the .mmdb file is fetched at build/deploy time, not
    committed to this repo (see docs/plans/US-010-implementation-plan.md
    Risks) - its absence in local dev/CI is expected, not an error.
    """
    settings = get_settings()
    try:
        return geoip2.database.Reader(settings.geoip_database_path)
    except (OSError, maxminddb.InvalidDatabaseError):
        logger.info(
            "GeoLite2 database not available at %s; session locations will be omitted",
            settings.geoip_database_path,
        )
        return None


def resolve_location(ip: str) -> GeoLocation | None:
    """FR-1/OD-4: never raises - a private/loopback IP, an IP with no
    database entry, a malformed IP string, or a missing database file all
    resolve to `None` rather than failing the request.
    """
    reader = _get_reader()
    if reader is None:
        return None
    try:
        response = reader.city(ip)
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None
    return GeoLocation(city=response.city.name, country=response.country.name)
