"""NWS hourly weather product (Phase 2.5).

Pulls weather.gov gridpoint daily forecast and hourly forecast for one
representative coordinate per NWAC zone. Renders verbatim NWS prose and a
multi-day hourly table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.fetchers.nac_api import parse_iso
from src.fetchers.nws_api import NWSClient
from src.products.base import ProductUnavailable, is_stale
from src.schema import ProductSource, ValidatedProduct
from src.zones import AvalancheZone

# Representative coordinate per NWAC zone for NWS gridpoint lookup.
# These are subjective picks: pass summits or popular trailheads. Adjust freely.
ZONE_COORDINATES: dict[AvalancheZone, tuple[float, float]] = {
    AvalancheZone.OLYMPICS: (47.967, -123.498),  # Hurricane Ridge
    AvalancheZone.WEST_NORTH: (48.857, -121.679),  # Mt Baker Ski Area
    AvalancheZone.WEST_CENTRAL: (46.870, -121.760),  # West side, Mt Rainier
    AvalancheZone.WEST_SOUTH: (46.787, -121.735),  # Paradise (Mt Rainier)
    AvalancheZone.STEVENS: (47.7462, -121.0866),  # Stevens Pass summit
    AvalancheZone.SNOQUALMIE: (47.4244, -121.4136),  # Snoqualmie Pass summit
    AvalancheZone.EAST_NORTH: (48.5917, -120.4006),  # Mazama
    AvalancheZone.EAST_CENTRAL: (47.286, -120.399),  # Mission Ridge
    AvalancheZone.EAST_SOUTH: (46.6357, -121.3941),  # White Pass
    AvalancheZone.MT_HOOD: (45.3308, -121.7110),  # Timberline Lodge
}


class NWSPeriod(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    number: int
    name: str
    is_daytime: bool = Field(alias="isDaytime")
    start_time: datetime = Field(alias="startTime")
    end_time: datetime = Field(alias="endTime")
    temperature: int
    temperature_unit: str = Field(alias="temperatureUnit")
    wind_speed: str = Field(alias="windSpeed")
    wind_direction: str | None = Field(default=None, alias="windDirection")
    short_forecast: str = Field(alias="shortForecast")
    detailed_forecast: str = Field(default="", alias="detailedForecast")
    precip_probability: int | None = Field(default=None, alias="probabilityOfPrecipitation")

    @field_validator("precip_probability", mode="before")
    @classmethod
    def _unpack_precip(cls, v: object) -> int | None:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, dict):
            val = v.get("value")
            return int(val) if val is not None else None
        return None


class NWSWeather(ValidatedProduct):
    """Validated NWS gridpoint weather forecast for one zone."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["nws_weather"] = "nws_weather"
    zone_name: str
    elevation_meters: float | None
    forecast_office: str
    daily_periods: list[NWSPeriod]
    hourly_periods: list[NWSPeriod]


class NWSWeatherProduct:
    """Product protocol implementation for NWS hourly weather."""

    name = "nws_weather"
    HOURLY_RENDER_HOURS = 48
    DAILY_PERIODS_RENDERED = 6

    def __init__(self, client: NWSClient) -> None:
        self.client = client

    def fetch(self, zone: AvalancheZone, *, as_of: datetime) -> dict[str, Any]:
        if zone not in ZONE_COORDINATES:
            raise ProductUnavailable(f"No NWS coordinates configured for {zone.display_name}")
        lat, lon = ZONE_COORDINATES[zone]
        points = self.client.get_points(lat, lon)
        f_url = points["properties"]["forecast"]
        h_url = points["properties"]["forecastHourly"]
        forecast = self.client.get(f_url)
        hourly = self.client.get(h_url)
        return {"points": points, "forecast": forecast, "hourly": hourly}

    def validate(self, raw: dict[str, Any], *, zone: AvalancheZone, as_of: datetime) -> NWSWeather:
        f_props = raw["forecast"]["properties"]
        h_props = raw["hourly"]["properties"]
        p_props = raw["points"]["properties"]

        update_time = f_props.get("updateTime") or f_props.get("generatedAt")
        if update_time is None:
            raise ValueError("NWS forecast missing both updateTime and generatedAt")
        updated = parse_iso(update_time)

        elevation = f_props.get("elevation") or {}
        elevation_m = elevation.get("value") if isinstance(elevation, dict) else None

        office = p_props.get("cwa", "UNKNOWN")
        lat, lon = ZONE_COORDINATES[zone]
        public_url = f"https://forecast.weather.gov/MapClick.php?lat={lat}&lon={lon}"

        source = ProductSource(
            name="NWS Hourly Weather",
            url=public_url,
            issued_at=updated,
            attribution=f"National Weather Service ({office})",
        )

        daily_periods = [NWSPeriod(**p) for p in f_props.get("periods") or []]
        hourly_periods = [NWSPeriod(**p) for p in h_props.get("periods") or []]

        return NWSWeather(
            source=source,
            is_stale=is_stale(updated, as_of),
            zone_name=zone.display_name,
            elevation_meters=elevation_m,
            forecast_office=office,
            daily_periods=daily_periods,
            hourly_periods=hourly_periods,
        )

    def render(self, validated: ValidatedProduct) -> str:
        if not isinstance(validated, NWSWeather):
            raise TypeError(f"render expected NWSWeather, got {type(validated).__name__}")
        return _render_nws(
            validated,
            hourly_hours=self.HOURLY_RENDER_HOURS,
            daily_count=self.DAILY_PERIODS_RENDERED,
        )


def _render_nws(w: NWSWeather, *, hourly_hours: int, daily_count: int) -> str:
    parts: list[str] = []
    parts.append(f"## NWS Hourly Weather: {w.zone_name}")
    parts.append("")
    parts.append(f"**Source**: [{w.source.attribution}]({w.source.url})  ")
    parts.append(f"**Gridpoint update time**: {w.source.issued_at.isoformat()}  ")
    if w.elevation_meters is not None:
        elev_ft = round(w.elevation_meters * 3.28084)
        parts.append(f"**Gridpoint elevation**: {round(w.elevation_meters)} m ({elev_ft} ft)")
    parts.append("")

    if w.daily_periods:
        parts.append("### Period forecast (NWS prose, verbatim)")
        parts.append("")
        for period in w.daily_periods[:daily_count]:
            wind = f"{period.wind_speed} {period.wind_direction or ''}".strip()
            parts.append(
                f"**{period.name}** ({period.temperature} {period.temperature_unit}, "
                f"wind {wind}): {period.detailed_forecast}"
            )
            parts.append("")

    if w.hourly_periods:
        parts.append(f"### Next {hourly_hours} hours")
        parts.append("")
        parts.append("| Time | Temp | Wind | Precip | Conditions |")
        parts.append("|---|---:|---|---:|---|")
        for hp in w.hourly_periods[:hourly_hours]:
            time_str = hp.start_time.strftime("%a %H:%M")
            wind = f"{hp.wind_speed} {hp.wind_direction or ''}".strip()
            precip = f"{hp.precip_probability}%" if hp.precip_probability is not None else "-"
            parts.append(
                f"| {time_str} | {hp.temperature} {hp.temperature_unit} | "
                f"{wind} | {precip} | {hp.short_forecast} |"
            )
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
