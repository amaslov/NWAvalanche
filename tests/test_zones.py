"""Tests for AvalancheZone enum lookup and metadata."""

from __future__ import annotations

import pytest

from src.zones import AvalancheZone, MountainWeatherZone, avalanche_to_mountain_weather


def test_from_cli_returns_zone() -> None:
    assert AvalancheZone.from_cli("STEVENS") is AvalancheZone.STEVENS
    assert AvalancheZone.from_cli("stevens") is AvalancheZone.STEVENS
    assert AvalancheZone.from_cli("MT_HOOD") is AvalancheZone.MT_HOOD


def test_from_cli_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown zone"):
        AvalancheZone.from_cli("Crystal")


def test_zone_metadata_matches_api() -> None:
    assert AvalancheZone.STEVENS.api_id == 1649
    assert AvalancheZone.STEVENS.display_name == "Stevens Pass"
    assert AvalancheZone.STEVENS.slug == "stevens-pass"
    assert AvalancheZone.SNOQUALMIE.api_id == 1653


def test_all_ten_zones_present() -> None:
    expected_ids = {1645, 1646, 1647, 1648, 1649, 1653, 1654, 1655, 1656, 1657}
    assert {z.api_id for z in AvalancheZone} == expected_ids


def test_zone_url_format() -> None:
    assert AvalancheZone.STEVENS.url.endswith("/stevens-pass")
    assert AvalancheZone.STEVENS.url.startswith("https://www.nwac.us/")


def test_mountain_weather_mapping_stub_returns_none() -> None:
    assert avalanche_to_mountain_weather(AvalancheZone.STEVENS) is None


def test_mountain_weather_zone_is_empty() -> None:
    assert list(MountainWeatherZone) == []
