"""Tests for the Phase 1 markdown render."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.fetchers.nac_api import NACClient
from src.products.avalanche_forecast import AvalancheForecastProduct
from src.render import render_daily_post
from src.schema import DailyContext
from src.zones import AvalancheZone

FIXTURE = Path(__file__).parent / "fixtures" / "forecast_snoqualmie_185078.json"


@pytest.fixture
def rendered_post_fresh() -> str:
    raw = json.loads(FIXTURE.read_text())
    product = AvalancheForecastProduct(client=NACClient.__new__(NACClient))
    as_of = datetime(2026, 4, 19, 12, tzinfo=UTC)
    validated = product.validate(raw, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    context = DailyContext(zone=AvalancheZone.SNOQUALMIE, as_of=as_of, products=[validated])
    return render_daily_post(context, {"avalanche_forecast": product.render})


@pytest.fixture
def rendered_post_stale() -> str:
    raw = json.loads(FIXTURE.read_text())
    product = AvalancheForecastProduct(client=NACClient.__new__(NACClient))
    as_of = datetime(2026, 5, 8, 12, tzinfo=UTC)
    validated = product.validate(raw, zone=AvalancheZone.SNOQUALMIE, as_of=as_of)
    context = DailyContext(zone=AvalancheZone.SNOQUALMIE, as_of=as_of, products=[validated])
    return render_daily_post(context, {"avalanche_forecast": product.render})


def test_title_contains_zone_and_date(rendered_post_fresh: str) -> None:
    assert rendered_post_fresh.startswith("# Snoqualmie Pass - 2026-04-19")


def test_sources_section_above_ai_summary(rendered_post_fresh: str) -> None:
    src_idx = rendered_post_fresh.index("## Sources")
    ai_idx = rendered_post_fresh.index("## AI summary")
    assert src_idx < ai_idx


def test_attribution_present(rendered_post_fresh: str) -> None:
    assert "Northwest Avalanche Center" in rendered_post_fresh


def test_danger_label_rendered_verbatim(rendered_post_fresh: str) -> None:
    assert "Moderate" in rendered_post_fresh
    assert "level 2" in rendered_post_fresh


def test_problems_section_present(rendered_post_fresh: str) -> None:
    assert "### Avalanche problems" in rendered_post_fresh
    assert "Wet Loose" in rendered_post_fresh


def test_narrative_html_passed_through(rendered_post_fresh: str) -> None:
    assert "<p>Warm and mostly sunny" in rendered_post_fresh
    assert "### Bottom line" in rendered_post_fresh
    assert "### Hazard discussion" in rendered_post_fresh


def test_ai_summary_placeholder_present(rendered_post_fresh: str) -> None:
    assert "_LLM summary will appear here in Phase 3._" in rendered_post_fresh


def test_no_stale_banner_when_fresh(rendered_post_fresh: str) -> None:
    assert "STALE" not in rendered_post_fresh


def test_stale_banner_appears_when_stale(rendered_post_stale: str) -> None:
    assert "**STALE**" in rendered_post_stale
    assert "avalanche_forecast" in rendered_post_stale
