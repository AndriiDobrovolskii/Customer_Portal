from collections.abc import Iterator

import geoip2.errors
import pytest

from app.core import geoip as geoip_module
from app.core.geoip import GeoLocation, resolve_location

pytestmark = pytest.mark.unit


class _FakeCityField:
    def __init__(self, name: str | None) -> None:
        self.name = name


class _FakeCityResponse:
    def __init__(self, *, city: str | None, country: str | None) -> None:
        self.city = _FakeCityField(city)
        self.country = _FakeCityField(country)


class _FakeReader:
    """Stands in for `geoip2.database.Reader` - no real GeoLite2 database
    is bundled in this repo (OD-4: fetched at build/deploy time), so the
    "resolvable IP"/"private IP"/"no entry" branches of `resolve_location`
    can only be exercised against a substitute reader, not a real file.
    """

    def __init__(
        self,
        *,
        responses: dict[str, _FakeCityResponse] | None = None,
    ) -> None:
        self._responses = responses or {}

    def city(self, ip: str) -> _FakeCityResponse:
        if ip not in self._responses:
            raise geoip2.errors.AddressNotFoundError("not found")
        return self._responses[ip]


@pytest.fixture(autouse=True)
def _clear_reader_cache() -> Iterator[None]:
    geoip_module._get_reader.cache_clear()
    yield
    geoip_module._get_reader.cache_clear()


def test_geoip_lookup_resolvable_ip_returns_city_country(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    fake_reader = _FakeReader(
        responses={"8.8.8.8": _FakeCityResponse(city="Mountain View", country="United States")}
    )
    monkeypatch.setattr(geoip_module, "_get_reader", lambda: fake_reader)

    # Act
    result = resolve_location("8.8.8.8")

    # Assert
    assert result == GeoLocation(city="Mountain View", country="United States")


def test_geoip_lookup_private_ip_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: MaxMind databases have no entry for private/reserved ranges,
    # surfaced as AddressNotFoundError - same as any other unresolvable IP.
    fake_reader = _FakeReader()
    monkeypatch.setattr(geoip_module, "_get_reader", lambda: fake_reader)

    # Act
    result = resolve_location("192.168.1.1")

    # Assert
    assert result is None


def test_geoip_lookup_unresolvable_ip_returns_none_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_reader = _FakeReader()
    monkeypatch.setattr(geoip_module, "_get_reader", lambda: fake_reader)

    # Act
    result = resolve_location("203.0.113.99")

    # Assert
    assert result is None


def test_geoip_lookup_missing_database_file_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange: the real (un-substituted) `_get_reader` - no .mmdb file is
    # bundled in this repo, so this exercises the actual absent-file path.
    from app.core.config import get_settings

    monkeypatch.setenv("GEOIP_DATABASE_PATH", "app/core/data/does-not-exist.mmdb")
    get_settings.cache_clear()

    # Act
    result = resolve_location("8.8.8.8")

    # Assert
    assert result is None

    get_settings.cache_clear()
