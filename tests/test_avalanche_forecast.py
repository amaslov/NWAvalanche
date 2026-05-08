"""Tests for AvalancheForecastProduct.validate() against a saved fixture."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.fetchers.nac_api import NACClient
from src.products.avalanche_forecast import (
    DANGER_LABELS,
    AvalancheForecast,
    AvalancheForecastProduct,
)
from src.zones import AvalancheZone

FIXTURE = Path(__file__).parent / "fixtures" / "forecast_snoqualmie_185078.json"


@pytest.fixture
def raw_forecast() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def product() -> AvalancheForecastProduct:
    return AvalancheForecastProduct(client=NACClient.__new__(NACClient))


def test_validate_returns_avalanche_forecast(
    product: AvalancheForecastProduct, raw_forecast: dict
) -> None:
    as_of = datetime(2026, 4, 19, 12, tzinfo=UTC)
    result = product.validate(raw_forecast, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    assert isinstance(result, AvalancheForecast)
    assert result.kind == "avalanche_forecast"
    assert result.zone_name == "Snoqualmie Pass"
    assert result.author == "Dallas Glass"
    assert result.raw_id == 185078


def test_danger_rating_today_is_max_of_bands(
    product: AvalancheForecastProduct, raw_forecast: dict
) -> None:
    as_of = datetime(2026, 4, 19, 12, tzinfo=UTC)
    result = product.validate(raw_forecast, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    assert result.danger_rating_today == 2
    assert result.danger_label_today == "Moderate"
    assert result.danger_label_today == DANGER_LABELS[2]


def test_problems_sorted_by_rank(product: AvalancheForecastProduct, raw_forecast: dict) -> None:
    as_of = datetime(2026, 4, 19, 12, tzinfo=UTC)
    result = product.validate(raw_forecast, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    ranks = [p.rank for p in result.problems]
    assert ranks == sorted(ranks)


def test_narrative_passes_through_html(
    product: AvalancheForecastProduct, raw_forecast: dict
) -> None:
    as_of = datetime(2026, 4, 19, 12, tzinfo=UTC)
    result = product.validate(raw_forecast, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    assert result.bottom_line_html.startswith("<p>")
    assert result.hazard_discussion_html.startswith("<p>")


def test_freshness_marker_set_correctly(
    product: AvalancheForecastProduct, raw_forecast: dict
) -> None:
    fresh = product.validate(
        raw_forecast,
        zone=AvalancheZone.SNOQUALMIE,
        as_of=datetime(2026, 4, 19, 12, tzinfo=UTC),
    )
    assert fresh.is_stale is False

    stale = product.validate(
        raw_forecast,
        zone=AvalancheZone.SNOQUALMIE,
        as_of=datetime(2026, 5, 8, 12, tzinfo=UTC),
    )
    assert stale.is_stale is True


def test_wrong_zone_rejected(product: AvalancheForecastProduct, raw_forecast: dict) -> None:
    with pytest.raises(ValueError, match="does not include zone"):
        product.validate(
            raw_forecast,
            zone=AvalancheZone.STEVENS,
            as_of=datetime(2026, 4, 19, 12, tzinfo=UTC),
        )


def test_source_metadata_complete(product: AvalancheForecastProduct, raw_forecast: dict) -> None:
    result = product.validate(
        raw_forecast,
        zone=AvalancheZone.SNOQUALMIE,
        as_of=datetime(2026, 4, 19, 12, tzinfo=UTC),
    )
    assert result.source.attribution == "Northwest Avalanche Center"
    assert "snoqualmie" in result.source.url
    assert result.source.issued_at.isoformat() == "2026-04-19T01:30:00+00:00"
