"""NWAC mountain weather product. Stub for Phase 1, implemented in Phase 2."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.products.base import ProductUnavailable
from src.schema import ValidatedProduct


class MountainWeatherProduct:
    """Phase 1 stub. Present so the pipeline can register it without conditionals."""

    name = "mountain_weather"

    def fetch(self, zone, *, as_of: datetime, **kwargs: Any) -> dict[str, Any]:
        raise ProductUnavailable("Mountain weather product not implemented until Phase 2")

    def validate(self, raw: dict[str, Any], **kwargs: Any) -> ValidatedProduct:
        raise NotImplementedError

    def render(self, validated: ValidatedProduct) -> str:
        raise NotImplementedError
