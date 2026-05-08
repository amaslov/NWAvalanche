"""Tests for NWSWeatherProduct.validate() and render() against saved fixtures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.fetchers.nws_api import NWSClient
from src.products.nws_weather import (
    NAMED_LOCATIONS,
    ZONE_COORDINATES,
    ZONE_LOCATIONS,
    NWSPeriod,
    NWSWeather,
    NWSWeatherProduct,
    location_for_zone,
)
from src.zones import AvalancheZone

FIXTURES = Path(__file__).parent / "fixtures" / "nws"


@pytest.fixture
def raw_nws() -> dict:
    return {
        "points": json.loads((FIXTURES / "points_stevens.json").read_text()),
        "forecast": json.loads((FIXTURES / "forecast_stevens.json").read_text()),
        "hourly": json.loads((FIXTURES / "hourly_stevens.json").read_text()),
    }


@pytest.fixture
def product() -> NWSWeatherProduct:
    return NWSWeatherProduct(client=NWSClient.__new__(NWSClient))


def _fresh_as_of() -> datetime:
    return datetime(2026, 5, 8, 21, tzinfo=UTC)


def test_validate_returns_nws_weather(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    assert isinstance(result, NWSWeather)
    assert result.kind == "nws_weather"
    assert result.zone_name == "Stevens Pass"
    assert result.forecast_office == "OTX"


def test_attribution_is_nws_not_nwac(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    assert "National Weather Service" in result.source.attribution
    assert "NWAC" not in result.source.attribution
    assert "Northwest Avalanche Center" not in result.source.attribution


def test_periods_parsed(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    assert len(result.daily_periods) >= 1
    assert len(result.hourly_periods) >= 24
    p = result.daily_periods[0]
    assert isinstance(p, NWSPeriod)
    assert p.temperature_unit == "F"
    assert p.short_forecast


def test_precip_probability_unpacked(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    first_with_precip = next(
        (h for h in result.hourly_periods if h.precip_probability is not None), None
    )
    assert first_with_precip is not None
    assert isinstance(first_with_precip.precip_probability, int)


def test_freshness_marker_set_correctly(product: NWSWeatherProduct, raw_nws: dict) -> None:
    fresh = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    assert fresh.is_stale is False
    very_late = datetime(2026, 6, 1, tzinfo=UTC)
    stale = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=very_late)
    assert stale.is_stale is True


def test_render_contains_required_sections(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    md = product.render(result)
    assert "## NWS Hourly Weather: Stevens Pass" in md
    assert "National Weather Service" in md
    assert "### Period forecast" in md
    assert "### Next 48 hours" in md
    assert "| Time | Temp | Wind | Precip | Conditions |" in md


def test_render_table_has_at_least_24_rows(product: NWSWeatherProduct, raw_nws: dict) -> None:
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    md = product.render(result)
    table_rows = [line for line in md.splitlines() if line.startswith("| ") and " mph" in line]
    assert len(table_rows) >= 24


def test_all_zones_have_coordinates() -> None:
    missing = [z for z in AvalancheZone if z not in ZONE_COORDINATES]
    assert missing == []


def test_all_zones_map_to_a_named_location() -> None:
    missing = [z for z in AvalancheZone if z not in ZONE_LOCATIONS]
    assert missing == []


def test_zone_location_keys_resolve_to_named_locations() -> None:
    unresolved = [(z, key) for z, key in ZONE_LOCATIONS.items() if key not in NAMED_LOCATIONS]
    assert unresolved == []


def test_named_locations_include_user_specified_points() -> None:
    required = {
        "STEVENS_PASS",
        "SNOQUALMIE_PASS",
        "MT_BAKER_SKI",
        "MT_HOOD_TIMBERLINE",
        "MT_ST_HELENS",
    }
    assert required.issubset(NAMED_LOCATIONS.keys())


def test_west_south_uses_mt_st_helens() -> None:
    assert location_for_zone(AvalancheZone.WEST_SOUTH).display_name == "Mt St Helens"


def test_render_does_not_mix_nwac_attribution(product: NWSWeatherProduct, raw_nws: dict) -> None:
    """The NWS section must not be labeled with NWAC; CLAUDE.md attribution rule."""
    result = product.validate(raw_nws, zone=AvalancheZone.STEVENS, as_of=_fresh_as_of())
    md = product.render(result)
    assert "NWAC" not in md
    assert "Northwest Avalanche Center" not in md
