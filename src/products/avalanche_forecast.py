"""NWAC avalanche forecast product (Phase 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.fetchers.nac_api import NACClient, parse_iso
from src.products.base import ProductUnavailable, is_stale
from src.schema import ProductSource, ValidatedProduct
from src.zones import AvalancheZone

DANGER_LABELS = {
    -1: "No Rating",
    0: "No Rating",
    1: "Low",
    2: "Moderate",
    3: "Considerable",
    4: "High",
    5: "Extreme",
}

ELEVATION_BAND_DISPLAY = {
    "upper": "Above Treeline",
    "middle": "Near Treeline",
    "lower": "Below Treeline",
}


class DangerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_day: Literal["current", "tomorrow"]
    lower: int | None
    middle: int | None
    upper: int | None


class AvalancheProblem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    avalanche_problem_id: int
    rank: int
    name: str
    likelihood: str
    discussion_html: str = Field(alias="discussion")
    location: list[str]
    size: list[str]
    icon: str
    problem_description: str


class AvalancheForecast(ValidatedProduct):
    """Validated NWAC avalanche forecast for one zone."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["avalanche_forecast"] = "avalanche_forecast"
    zone_name: str
    author: str
    danger_today: DangerEntry
    danger_tomorrow: DangerEntry | None
    danger_rating_today: int
    danger_label_today: str
    bottom_line_html: str
    hazard_discussion_html: str
    weather_discussion_html: str | None
    announcement_html: str | None
    problems: list[AvalancheProblem]
    raw_id: int


class AvalancheForecastProduct:
    """Product protocol implementation for NWAC avalanche forecasts."""

    name = "avalanche_forecast"

    def __init__(self, client: NACClient) -> None:
        self.client = client

    def fetch(
        self,
        zone: AvalancheZone,
        *,
        as_of: datetime,
        listing: list[dict] | None = None,
    ) -> dict[str, Any]:
        product_id = self.client.latest_forecast_id(zone, as_of, listing=listing)
        if product_id is None:
            raise ProductUnavailable(
                f"No NWAC avalanche forecast found for {zone.display_name} "
                f"on or before {as_of.isoformat()}"
            )
        return self.client.get_product(product_id)

    def validate(
        self, raw: dict[str, Any], *, zone: AvalancheZone, as_of: datetime
    ) -> AvalancheForecast:
        if raw.get("product_type") != "forecast":
            raise ValueError(f"Expected product_type 'forecast', got {raw.get('product_type')!r}")

        zones = raw.get("forecast_zone") or []
        if not any(z.get("id") == zone.api_id for z in zones):
            raise ValueError(
                f"Detail record does not include zone {zone.display_name} (id {zone.api_id})"
            )

        danger_entries = [DangerEntry(**d) for d in raw.get("danger") or []]
        current = next((d for d in danger_entries if d.valid_day == "current"), None)
        if current is None:
            raise ValueError("Forecast missing a 'current' danger entry")
        tomorrow = next((d for d in danger_entries if d.valid_day == "tomorrow"), None)

        rating = max(
            (v for v in (current.lower, current.middle, current.upper) if v is not None),
            default=-1,
        )
        if rating not in DANGER_LABELS:
            raise ValueError(f"Unknown danger rating value {rating!r}")

        problems = [AvalancheProblem(**p) for p in raw.get("forecast_avalanche_problems") or []]
        problems.sort(key=lambda p: p.rank)

        published = parse_iso(raw["published_time"])

        source = ProductSource(
            name="NWAC Avalanche Forecast",
            url=zone.url,
            issued_at=published,
            attribution="Northwest Avalanche Center",
        )

        return AvalancheForecast(
            source=source,
            is_stale=is_stale(published, as_of),
            zone_name=zone.display_name,
            author=raw.get("author") or "NWAC",
            danger_today=current,
            danger_tomorrow=tomorrow,
            danger_rating_today=rating,
            danger_label_today=DANGER_LABELS[rating],
            bottom_line_html=raw.get("bottom_line") or "",
            hazard_discussion_html=raw.get("hazard_discussion") or "",
            weather_discussion_html=raw.get("weather_discussion"),
            announcement_html=raw.get("announcement"),
            problems=problems,
            raw_id=int(raw["id"]),
        )

    def render(self, validated: ValidatedProduct) -> str:
        if not isinstance(validated, AvalancheForecast):
            raise TypeError(f"render expected AvalancheForecast, got {type(validated).__name__}")
        return _render_avalanche_forecast(validated)


def _render_avalanche_forecast(f: AvalancheForecast) -> str:
    parts: list[str] = []
    parts.append(f"## NWAC Avalanche Forecast: {f.zone_name}")
    parts.append("")
    parts.append(f"**Source**: [{f.source.attribution}]({f.source.url})  ")
    parts.append(f"**Issued**: {f.source.issued_at.isoformat()} by {f.author}  ")
    parts.append(f"**Forecast id**: {f.raw_id}")
    parts.append("")

    parts.append("### Danger rating (today)")
    parts.append("")
    parts.append(f"**{f.danger_label_today}** (level {f.danger_rating_today})")
    parts.append("")
    parts.append("| Elevation band | Rating |")
    parts.append("|---|---:|")
    for attr, band in (
        ("upper", "Above Treeline"),
        ("middle", "Near Treeline"),
        ("lower", "Below Treeline"),
    ):
        value = getattr(f.danger_today, attr)
        label = DANGER_LABELS.get(value, "No Rating") if value is not None else "No Rating"
        parts.append(f"| {band} | {label} ({value if value is not None else '-'}) |")
    parts.append("")

    if f.problems:
        parts.append("### Avalanche problems")
        parts.append("")
        for prob in f.problems:
            parts.append(f"#### {prob.rank}. {prob.name}")
            parts.append("")
            parts.append(f"- **Likelihood**: {prob.likelihood}")
            parts.append(f"- **Size**: {' to '.join(prob.size) if prob.size else 'n/a'}")
            parts.append("- **Aspect / elevation**:")
            for band_key, band_label in ELEVATION_BAND_DISPLAY.items():
                aspects = [
                    loc.split(" ", 1)[0] for loc in prob.location if loc.endswith(" " + band_key)
                ]
                if aspects:
                    parts.append(f"  - {band_label}: {', '.join(aspects)}")
            parts.append("")
            parts.append(prob.discussion_html)
            parts.append("")

    if f.bottom_line_html:
        parts.append("### Bottom line")
        parts.append("")
        parts.append(f.bottom_line_html)
        parts.append("")

    if f.hazard_discussion_html:
        parts.append("### Hazard discussion")
        parts.append("")
        parts.append(f.hazard_discussion_html)
        parts.append("")

    if f.weather_discussion_html:
        parts.append("### Weather discussion")
        parts.append("")
        parts.append(f.weather_discussion_html)
        parts.append("")

    if f.announcement_html:
        parts.append("### Announcement")
        parts.append("")
        parts.append(f.announcement_html)
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
