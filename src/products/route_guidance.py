"""Route guidance product. Stub that proves the plug-in pattern. No Phase yet."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.products.base import ProductUnavailable
from src.schema import ValidatedProduct


class RouteGuidanceProduct:
    """Phase 1 stub. Architectural forward-compatibility, not a development target."""

    name = "route_guidance"

    def fetch(self, zone, *, as_of: datetime, **kwargs: Any) -> dict[str, Any]:
        raise ProductUnavailable("Route guidance product is not in any phase yet")

    def validate(self, raw: dict[str, Any], **kwargs: Any) -> ValidatedProduct:
        raise NotImplementedError

    def render(self, validated: ValidatedProduct) -> str:
        raise NotImplementedError
