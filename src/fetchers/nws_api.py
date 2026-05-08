"""HTTP client for the National Weather Service public API (weather.gov)."""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://api.weather.gov"
USER_AGENT = "NWAC-Daily-Summary/0.1 (amaslov85@gmail.com)"
DEFAULT_TIMEOUT = 60.0


class NWSClient:
    """Minimal client. weather.gov requires a contact User-Agent."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        if client is None:
            client = httpx.Client(
                headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
                timeout=DEFAULT_TIMEOUT,
            )
        self._client = client

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NWSClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def get_points(self, lat: float, lon: float) -> dict[str, Any]:
        r = self._client.get(f"{BASE_URL}/points/{lat},{lon}")
        r.raise_for_status()
        return r.json()

    def get(self, url: str) -> dict[str, Any]:
        r = self._client.get(url)
        r.raise_for_status()
        return r.json()
