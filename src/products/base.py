"""Product protocol and shared product-layer exceptions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from src.schema import ValidatedProduct


class ProductUnavailable(Exception):
    """Raised when a product has no record for the requested zone and date.

    Distinct from a fetch or schema failure: not an error, just absence.
    """


STALE_THRESHOLD = timedelta(hours=24)


def is_stale(issued_at: datetime, as_of: datetime) -> bool:
    return (as_of - issued_at) > STALE_THRESHOLD


@runtime_checkable
class Product(Protocol):
    """Every data source implements this. The pipeline only sees this protocol."""

    name: str

    def fetch(self, zone, *, as_of: datetime) -> dict: ...
    def validate(self, raw: dict, *, as_of: datetime) -> ValidatedProduct: ...
    def render(self, validated: ValidatedProduct) -> str: ...
