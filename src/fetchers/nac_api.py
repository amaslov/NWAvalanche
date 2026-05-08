"""HTTP client for the National Avalanche Center public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from src.zones import AvalancheZone

BASE_URL = "https://api.avalanche.org/v2/public"
USER_AGENT = "NWAC-Daily-Summary/0.1 (amaslov85@gmail.com)"
DEFAULT_TIMEOUT = 60.0


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


class NACClient:
    """Minimal client. Caller owns retries above this layer."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        if client is None:
            client = httpx.Client(
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=DEFAULT_TIMEOUT,
            )
        self._client = client

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NACClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def list_products(self, center_id: str = "NWAC") -> list[dict[str, Any]]:
        r = self._client.get(f"{BASE_URL}/products", params={"avalanche_center_id": center_id})
        r.raise_for_status()
        return r.json()

    def get_product(self, product_id: int) -> dict[str, Any]:
        r = self._client.get(f"{BASE_URL}/product/{product_id}")
        r.raise_for_status()
        return r.json()

    def latest_forecast_id(
        self, zone: AvalancheZone, as_of: datetime, *, listing: list[dict] | None = None
    ) -> int | None:
        """Return the id of the most recent `forecast` for this zone published at or before as_of.

        `listing` lets callers reuse a single list_products() call across zones in the same run.
        """
        records = listing if listing is not None else self.list_products()
        candidates: list[tuple[datetime, int]] = []
        for r in records:
            if r.get("product_type") != "forecast":
                continue
            zones = r.get("forecast_zone") or []
            if not any(z.get("id") == zone.api_id for z in zones):
                continue
            published = r.get("published_time")
            if not published:
                continue
            pub_dt = parse_iso(published)
            if pub_dt <= as_of:
                candidates.append((pub_dt, r["id"]))
        if not candidates:
            return None
        return max(candidates)[1]
