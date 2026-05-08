"""NWAC zone definitions and cross-product mappings."""

from __future__ import annotations

from enum import Enum


class AvalancheZone(Enum):
    """NWAC avalanche forecast zones, keyed by API zone id."""

    OLYMPICS = (1645, "Olympics", "olympics")
    WEST_NORTH = (1646, "West Slopes North", "west-slopes-north")
    WEST_CENTRAL = (1647, "West Slopes Central", "west-slopes-central")
    WEST_SOUTH = (1648, "West Slopes South", "west-slopes-south")
    STEVENS = (1649, "Stevens Pass", "stevens-pass")
    SNOQUALMIE = (1653, "Snoqualmie Pass", "snoqualmie-pass")
    EAST_NORTH = (1654, "East Slopes North", "east-slopes-north")
    EAST_CENTRAL = (1655, "East Slopes Central", "east-slopes-central")
    EAST_SOUTH = (1656, "East Slopes South", "east-slopes-south")
    MT_HOOD = (1657, "Mt Hood", "mt-hood")

    def __init__(self, api_id: int, display_name: str, slug: str) -> None:
        self.api_id = api_id
        self.display_name = display_name
        self.slug = slug

    @property
    def url(self) -> str:
        return f"https://www.nwac.us/avalanche-forecast/#/{self.slug}"

    @property
    def filename_slug(self) -> str:
        return self.slug

    @classmethod
    def from_cli(cls, name: str) -> AvalancheZone:
        try:
            return cls[name.upper()]
        except KeyError as exc:
            valid = ", ".join(z.name for z in cls)
            raise ValueError(f"Unknown zone {name!r}. Valid: {valid}") from exc


class MountainWeatherZone(Enum):
    """NWAC mountain weather forecast zones. Phase 2 will populate this."""


def avalanche_to_mountain_weather(zone: AvalancheZone) -> MountainWeatherZone | None:
    """Stub mapping for Phase 2. Phase 1 always returns None."""
    return None
